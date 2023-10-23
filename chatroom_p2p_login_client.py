import json
import logging
import socket
import select
import sys
import hashlib


logging.basicConfig(
    format="\r[%(levelname)s: line %(lineno)d] %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ChatRoomP2PClient:
    def __init__(
        self,
        server_ip: str,
        server_port: int,
        client_ip: str,
        p2p_port: int,
        receive_buffer_size: int = 2048,
    ) -> None:
        self.server_ip = server_ip
        self.server_port = server_port
        self.client_ip = client_ip
        self.p2p_port = p2p_port
        self.receive_buffer_size = receive_buffer_size
        # Create TCP and UDP sockets
        self.client_socket_tcp = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )
        self.client_socket_tcp.settimeout(2)
        self.client_socket_udp = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM
        )
        self.client_socket_udp.settimeout(2)
        self.client_socket_udp.bind(("", self.p2p_port))
        # set the UDP socket to reuse the address
        self.client_socket_udp.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )
        self.list_of_sockets = [
            sys.stdin,
            self.client_socket_tcp,
            self.client_socket_udp,
        ]
        self.p2p_peers: dict[str, str] = {}  # {name: ip}

        # Connect to the chat server using the TCP socket
        try:
            self.client_socket_tcp.connect((self.server_ip, self.server_port))
        except Exception as err:
            logger.error(
                "Unable to connect to the server. Error message : %s", err
            )
            sys.exit()

    # function to change the list of peers received from the server to the
    # dictionary
    def update_peers(self, peers: list[tuple[str, str]]) -> None:
        self.p2p_peers = {peer[0]: peer[1] for peer in peers}

    def run(self) -> None:
        while True:
            read_sockets, _, _ = select.select(self.list_of_sockets, (), ())
            for sock in read_sockets:
                # Incoming zmessage from remote server
                if sock == self.client_socket_tcp:
                    # Receive data from the server
                    # empty string means the server has closed the connection
                    if not (
                        data := bytes(sock.recv(self.receive_buffer_size))
                    ):
                        logger.info("Disconnected from chat server")
                        sys.exit()

                    # check if the data is json
                    data = data.decode().strip()
                    if data.startswith("["):
                        data = json.loads(data)
                        # update the list of peers using the update_peers()
                        # function
                        self.update_peers(data)
                        peers = list(self.p2p_peers.keys())
                        print(f"\rOnline peers: {peers}")
                        print("\r[Me]", end=" ", flush=True)
                        continue

                    print("\r[Server] " + data)
                    print("\r[Me]", end=" ", flush=True)

                    if data == (
                        "Your username is valid. Please enter password."
                    ):
                        msg = sys.stdin.readline().strip()
                        hashed_msg = (
                            hashlib.sha256(msg.encode()).hexdigest().encode()
                        )
                        try:
                            self.client_socket_tcp.send(hashed_msg)
                        except Exception as err:
                            logger.error(
                                "Unable to send message to the server. Error "
                                "message : %s",
                                err,
                            )
                            sys.exit()

                # Incoming message from UDP socket
                elif sock == self.client_socket_udp:
                    # Receive data from a peer
                    data, addr = self.client_socket_udp.recvfrom(
                        self.receive_buffer_size
                    )
                    data = data.decode()
                    peer_ip_address = addr[0]
                    peer_username = [
                        username
                        for username, ip in self.p2p_peers.items()
                        if ip == peer_ip_address
                    ][0]
                    print(
                        f"\r[P2P] {peer_username} (IP: {peer_ip_address}) "
                        f"says: {data}"
                    )
                    print("\r[Me]", end=" ", flush=True)

                # User entered a message
                else:
                    # check if empty message
                    if not (msg := sys.stdin.readline().strip()):
                        print("\r[Me]", end=" ", flush=True)
                        continue
                    # check if the user wants to exit
                    if msg == ":q":
                        self.client_socket_tcp.close()
                        sys.exit()
                    elif msg == ":l":
                        peers = list(self.p2p_peers.keys())
                        print(f"\rOnline peers: {peers}")
                    # check if the user wants to send a p2p message
                    elif msg[0] == "@":
                        idx = msg.find(":")
                        username = msg[1:idx]
                        msg = msg[idx + 1 :]

                        if username in self.p2p_peers:
                            peer_ip_address = self.p2p_peers[username]
                            try:
                                self.client_socket_udp.sendto(
                                    msg.encode(),
                                    (peer_ip_address, self.p2p_port),
                                )
                            except Exception as err:
                                logger.error(
                                    "Unable to send p2p message to %s. Error "
                                    "message : %s",
                                    username,
                                    err,
                                )
                        else:
                            print(f"\rUser ({username}) not found")

                    # broadcast message to all connected clients (through the server)
                    else:
                        msg = msg.encode()
                        try:
                            # send the message to the server
                            self.client_socket_tcp.send(msg)
                        except Exception as err:
                            logger.error(
                                "Unable to send message to the server. Error "
                                "message : %s",
                                err,
                            )
                            sys.exit()

                    print("\r[Me]", end=" ", flush=True)


def main() -> None:
    server_ip = socket.gethostbyname("team11.com")
    server_port = 12000
    max_receive_buffer_size = 2048
    client_ip = socket.gethostbyname(socket.gethostname())
    p2p_port = 13000

    client = ChatRoomP2PClient(
        server_ip, server_port, client_ip, p2p_port, max_receive_buffer_size
    )
    client.run()


if __name__ == "__main__":
    main()
