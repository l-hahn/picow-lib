import rp2
import network
import ubinascii
import time
import socket

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
    def parse_header(request):
        http_lines = request.decode().split('\r\n')
        http_request_split = http_lines[0].split(' ')
        http_request_path_split = http_request_split[1].split('?')
        http_request = Request(
            method=http_request_split[0], path=http_request_path_split[0],
            protocol=http_request_split[2]
        )    

        if len(http_request_path_split) > 1:
            http_request.set_parameter(dict(
                param.split('=')
                for param in http_request_path_split[1].split('&')
            ))
        if len(http_lines) > 1:
            http_request.set_header(dict(
                header.split(': ')
                for header in http_lines[1:]
                if header is not None and header != ""
            ))
        return http_request

    def __init__(
            self, method, path, protocol,
            host="", header={}, content=None, parameter={}):
        self.method = method
        self.host = host
        self.path = path
        self.parameter = parameter
        self.protocol = protocol
        self.header = header
        self.content = content

    def __repr__(self):
        return repr({
            "method": self.method,
            "host": self.host,
            "path": self.path,
            "parameter": self.parameter,
            "protocol": self.protocol,
            "header": self.header,
            "content": self.content
        })
    def __str__(self):
        return self.get_request().decode()

    def set_header(self, header):
        if self.header is None or len(self.header) == 0:
            self.header = header
    def set_content(self, content):
        if self.content is None or len(self.content) == 0:
            self.content = content
    def set_host(self, host):
        if self.host is None or len(self.host) == 0:
            self.host = host
    def set_parameter(self, parameter):
        if self.parameter is None or len(self.parameter) == 0:
            self.paramter = parameter

    def get_request(self):
        request = bytearray(self.get_header_request())
        request.extend(b"" if self.content is None else f"{self.content}".encode())
        return request
    def get_header_request(self):
        headers = "\r\n".join(': '.join(header) for header in self.header.items())
        strpath = self.path
        if len(self.parameter) > 0:
            strpath += f"?{'&'.join('='.join(item) for item in self.parameter.items())}"
        return f"{self.method} {strpath} {self.protocol}\r\n{headers}\r\n\r\n".encode()

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
        self.status = status

    def __repr__(self):
        return repr({
            "method": self.method,
            "host": self.host,
            "path": self.path,
            "parameter": self.parameter,
            "protocol": self.protocol,
            "status": self.status,
            "message": Response.messages[self.status],
            "header": self.header,
            "content": self.content
        })
    def __str__(self):
        return self.get_response().decode()

    def get_response(self):
        response = bytearray(self.get_header_response())
        response.extend(b"" if self.content is None else f"{self.content}".encode())
        return response
    def get_header_response(self):
        headers = "\r\n".join(': '.join(header) for header in self.header.items())
        strpath = self.path
        if len(self.parameter) > 0:
            strpath += f"?{'&'.join('='.join(item) for item in self.parameter.items())}"
        return f"{self.protocol} {self.status} {Response.messages[self.status]}\r\n{headers}\r\n\r\n".encode()

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
            request.set_content(content)
        return request


    def __init__(self, listen_addr="0.0.0.0", port=80):
        self._listen_addr = listen_addr
        self._port = port

    def _create_socket(self):
        self._socket_addrinfo = socket.getaddrinfo(self._listen_addr, self._port)
        self._socket = socket.socket()
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
                conn.send(response.get_response())
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

