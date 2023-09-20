import rp2
import network
import ubinascii
import time
import usocket

import sys

def get_logger():
    try:
        import logging
    except ImportError:
        import mip
        mip.install("logging")
        import logging

    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    global logger
    logger = logging.getLogger(__name__)


class Request:
    @staticmethod
    def parse_header(request):
        http_lines = request.decode().split('\r\n')
        http_request_split = http_lines[0].split(' ')
        http_request_path_split = http_request_split[1].split('?')
        http_request = Request(
            method=http_request_split[0], path=http_request_path_split[0],
            protocol=http_request_split[2]
        )    

        if len(http_request_path_split) > 1:
            print(http_request_path_split[1])
            http_request.parameter = dict(
                param.split('=')
                for param in http_request_path_split[1].split('&')
            )
        if len(http_lines) > 1:
            http_request.header = dict(
                header.split(': ')
                for header in http_lines[1:]
                if header is not None and header != ""
            )
        return http_request

    def __init__(
            self, method, path, protocol,
            host="", header={}, content=None, parameter={}):
        self._method = method
        self._host = host
        self._path = path
        self._parameter = parameter
        self._protocol = protocol
        self._header = header
        self._content = content
    def __repr__(self):
        return repr({
            "method": self._method,
            "host": self._host,
            "path": self._path,
            "parameter": self._parameter,
            "protocol": self._protocol,
            "header": self._header,
            "content": self._content
        })
    def __str__(self):
        return self.request_bytes.decode()

    @property
    def method(self):
        return self._method
    @method.setter
    def method(self, method):
        if self._method is None or len(self._method) == 0:
            self._method = method
    @property
    def host(self):
        return self._host
    @host.setter
    def host(self, host):
        if self._host is None or len(self._host) == 0:
            self._host = host
    @property
    def path(self):
        return self._path
    @path.setter
    def path(self, path):
        if self._path is None or len(self._path) == 0:
            self._path = path
    @property
    def parameter(self):
        return self._parameter
    @parameter.setter
    def parameter(self, parameter):
        if self._parameter is None or len(self._parameter) == 0:
            self.paramter = parameter
    @property
    def protocol(self):
        return self._protocol
    @protocol.setter
    def protocol(self, protocol):
        if self._protocol is None or len(self._protocol) == 0:
            self._protocol = protocol
    @property
    def header(self):
        return self._header
    @header.setter
    def header(self, header):
        if self._header is None or len(self._header) == 0:
            self._header = header
    @property
    def content(self):
        return self._content
    @content.setter
    def content(self, content):
        if self._content is None or len(self._content) == 0:
            self._content = content
    @property
    def request_bytes(self):
        request = bytearray(self._header_request_bytes)
        request.extend(b"" if self._content is None else f"{self._content}".encode())
        return request
    @property
    def _header_request_bytes(self):
        headers = "\r\n".join(': '.join(header) for header in self._header.items())
        strpath = self._path
        if len(self._parameter) > 0:
            strpath += f"?{'&'.join('='.join(item) for item in self._parameter.items())}"
        return f"{self._method} {strpath} {self._protocol}\r\n{headers}\r\n\r\n".encode()

class Response(Request):
    messages = {
        "100": "Continue", "101": "Switching Protocols", "102": "Processing",
        "200": "OK", "201": "Created", "202": "Accepted", "204": "No Content", "206":"Partial Content",
        "300": "Multiple Choice", "301": "Moved Permanently", "302": "Found",
        "400": "Bad Request", "401": "Unauthorized", "403": "Forbidden", "404": "Not Found", "409": "Conflict"
    }
    def __init__(self, method, path, protocol, status,
            host="", header={}, content=None, parameter={}):
        super().__init__(method, path, protocol, host, header, content, parameter)
        self._status = status

    def __repr__(self):
        return repr({
            "method": self._method,
            "host": self._host,
            "path": self._path,
            "parameter": self._parameter,
            "protocol": self._protocol,
            "status": self._status,
            "message": Response.messages[self._status],
            "header": self._header,
            "content": self._content
        })
    def __str__(self):
        return self.response_bytes.decode()
    @property
    def status(self):
        return self._status
    @property
    def response_bytes(self):
        response = bytearray(self._header_response_bytes)
        response.extend(b"" if self._content is None else f"{self._content}".encode())
        return response
    @property
    def _header_response_bytes(self):
        headers = "\r\n".join(': '.join(header) for header in self._header.items())
        strpath = self._path
        if len(self._parameter) > 0:
            strpath += f"?{'&'.join('='.join(item) for item in self._parameter.items())}"
        return f"{self._protocol} {self._status} {Response.messages[self._status]}\r\n{headers}\r\n\r\n".encode()

class MicroWebServer:
    BUFFER_SIZE = 1024

    @staticmethod
    def buffer_receive(connect, size=-1):
        webrequest = bytearray()
        is_end_stream = False
        while not is_end_stream:
            webrequest.extend(connect.recv(MicroWebServer.BUFFER_SIZE))
            is_end_stream = webrequest.endswith(b'\r\n\r\n') or len(webrequest) >= size
        return webrequest
    @staticmethod
    def socket_receive(connect):
        request_header_bytes = MicroWebServer.buffer_receive(connect)
        request = Request.parse_header(request_header_bytes)
        if 'Content-Length' in request.header and request.header["Content-Length"] != '0':
            request_content_bytes = MicroWebServer.buffer_receive(
                connect, size=int(request.header['Content-Length'])
            )
            content = request_content_bytes.decode()
            request.content = content
        return request


    def __init__(self, listen_addr="0.0.0.0", port=80):
        self._listen_addr = listen_addr
        self._port = port

    def _create_socket(self):
        self._socket_addrinfo = usocket.getaddrinfo(self._listen_addr, self._port)
        self._socket = usocket.socket()
        self._socket.bind(self._socket_addrinfo[0][-1])
        self._socket.listen(1)

    def _handle_request(self, request):
        logger.debug(f"Request: \n{request}")
        response = Response(request.method, request.path, request.protocol, "200")
        return response

    def serve(self):
        self._create_socket()
        logger.debug(f"Created socket listening on '{self._listen_addr}:{self._port}'")

        while True:
            try:
                conn, addr = self._socket.accept()
                logger.debug(f"Client connect from '{addr[0]}'")
                request = MicroWebServer.socket_receive(conn)
                response = self._handle_request(request)
                conn.send(response.response_bytes)
                conn.close()
            except OSError as e:
                conn.close()
                logger.debug(f"Client {addr} closed connection.")
            except KeyboardInterrupt:
                machine.reset()





def connect_wlan(ssid, passphrase, hostname="PicoW", country="DE", power_save=False, max_retry=20, wait_time=1):
    rp2.country(country)

    pm_mode = network.WLAN.PM_NONE if power_save is None else (
        network.WLAN.PM_POWERSAVE if power_save else network.WLAN.PM_PERFORMANCE
    )

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=pm_mode)
    wlan.connect(ssid, passphrase)
    wlan_mac_address = ':'.join("{:02x}".format(x) for x in wlan.config("mac"))

    retry = 0
    while retry < max_retry and (wlan.status() > 0 and wlan.status() < 3):
        print(f"\rTrying to connect to '{ssid}' for {retry*wait_time}s.", end="")
        retry += 1
        time.sleep(wait_time)
    if wlan.status() != 3 or not wlan.isconnected():
        raise RuntimeError(f"\nnetwork connection failure: cannot connect to '{ssid}' from '{wlan_mac_address}'.")
    else:
        ip = wlan.ifconfig()[0]
        print(f"\rConnection to '{ssid}' established. Connected via address '{ip}' from '{wlan_mac_address}'.")
    return wlan

def main():
    ssid = "SSID"
    pw = "PASSWORD"
    wlan = connect_wlan(ssid, pw)
    get_logger()

    webserver = MicroWebServer()
    webserver.serve()

if __name__=='__main__':
    main()

