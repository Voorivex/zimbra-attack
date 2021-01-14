import socket
from typing import List


class MemcachedClient:

    def __init__(self,
                 host: str,
                 port: int = 11211):
        """
        This class initializes a Memcached client.

        :param host: IP address or hostname of the server.
        :param port: Server port number, default is 11211
        """

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ip = socket.gethostbyname(host)
        self.__socket.connect((ip, port))

    def __read_socket(self) -> bytes:
        """
        This method reads data from the socket.
        :return: data read from the socket.
        """
        data = b""
        while True:
            chunk_data = self.__socket.recv(2048)
            if not chunk_data:
                break
            data += chunk_data
            if b"END" in chunk_data or b"ERROR" in chunk_data:
                break
        return data

    def __send_command(self, cmd: str):
        """
        This method sends Memcached command to the server.
        :param cmd: Single memcached command.
        :return:
        """
        cmd += "\r\n"
        cmd = cmd.encode()
        self.__socket.send(cmd)

    def stats_slabs(self) -> List[int]:
        """
        This method gets slabs statistics.
        :return: List of slabs
        """
        try:
            self.__send_command("stats slabs")
            data = self.__read_socket()
            slabs = []
            lines = data.split(b"\r\n")
            for line in lines:
                if b':chunk_size ' in line:

                    try:
                        slab_id = line.split(b"STAT ")[1].split(b":c")[0]
                        slab_id = int(slab_id)
                        slabs.append(slab_id)
                    except Exception:
                        pass
            return slabs
        except Exception as e:
            raise Exception(f"Failed to extract slabs: {e}")

    def get_key_value(self, key_name: str) -> str:
        """
        This method returns value of the key stored in the cache.
        :param key_name: Key name
        :return: Key value
        """
        self.__send_command(f"get {key_name}")
        data = self.__read_socket()
        key_value = data.split(b"\r\n")[1].strip().decode()
        return key_value

    def set_key_value(self, key_name: str, key_value: str):
        """
        This method sets value of a memcached key.

        :param key_name: Key name
        :param key_value: Value to set
        :return:
        """
        self.__send_command(f"set {key_name} 0 0 {len(key_value)}")
        self.__send_command(key_value)

    def delete_key(self, key_name: str):
        """
        This method deletes a stored key.
        :param key_name: Key name
        :return:
        """
        self.__send_command(f"delete {key_name}")

    def set_items(self, items_dict: dict):
        """
        This method extracts key-value items from the dict and stores them
        in the cache.
        :param items_dict: dict of key-value items.
        :return:
        """
        for key, value in items_dict.items():
            self.set_key_value(key, value)

    def extract_keys(self) -> List[str]:
        """
        This method extracts all key names from the cache.
        :return: List of key names.
        """

        keys = []
        slabs = self.stats_slabs()
        for slab_id in slabs:
            self.__send_command(f"stats cachedump {slab_id} 0")
            data = self.__read_socket()

            lines = data.split(b"\r\n")

            for line in lines:
                if line.startswith(b"ITEM "):

                    try:
                        key_name = line.split(b"ITEM ")[1].split(b" ")[0]

                        key_name = key_name.decode()
                        keys.append(key_name)
                    except Exception:
                        pass
        return keys

    def delete_keys(self, keys: List[str]):
        """
        This method deletes keys in the list from the cache.
        :param keys: List of key names.
        :return:
        """
        for key_name in keys:
            self.delete_key(key_name)

    def extract_items(self) -> dict:
        """
        This method extracts all key-value items stored in the cache.
        :return: Dict of key:value items.
        """
        items_dict = {}
        key_names = self.extract_keys()
        for key_name in key_names:
            items_dict[key_name] = self.get_key_value(key_name)
        return items_dict

    def close(self):
        """
        This method closes the socket connection.
        :return:
        """
        self.__socket.shutdown(socket.SHUT_RDWR)
        self.__socket.close()
