import socket
import select
import json
import time

# Basic logging configuration
import logging

logging.basicConfig(
    format="\r[%(levelname)s: line %(lineno)d] %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ChatRoomP2PServer:
    def __init__(
        self,
        server_ip: str,
        server_port: int,
        receive_buffer_size: int = 2048,
        max_clients: int = 10,
    ) -> None:
        self.server_ip = server_ip
        self.server_port = server_port
        self.receive_buffer_size = receive_buffer_size
        # create a TCP socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", self.server_port))
        # set the maximum number of clients that can be connected to the server
        self.server_socket.listen(max_clients)
        # list of socket descriptors, used as a read list for select()
        self.list_of_sockets = [self.server_socket]
        self.clients: dict[socket.socket, tuple] = {}  # {socket: (name, ip)}

    def broadcast(self, message: bytes, source_socket: socket.socket) -> None:
        for sock in self.clients:
            if sock != source_socket:
                try:
                    # send the message to the client
                    sock.send(message)
                except Exception as err:
                    logger.error(
                        "Unable to send message to client. Error message : %s",
                        err,
                    )
                    sock.close()
                    self.remove(sock)

    def remove(self, sock: socket.socket) -> None:
        if sock in self.list_of_sockets:
            self.list_of_sockets.remove(sock)
            self.clients.pop(sock)

    # function to broadcast list of clients to all connected clients
    def broadcast_list_of_clients(self) -> None:
        # create a list of clients
        # convert the list of clients to json string
        list_of_clients = json.dumps(self.clients.values())
        # sleep for 0.5 seconds to make sure the client has received the
        # welcome message. This is to avoid concatenating the welcome message
        # with the list of clients
        time.sleep(0.5)
        # broadcast the list of clients to all connected clients
        # the source_socket is the server_socket: the server is sending the list
        self.broadcast(list_of_clients.encode(), self.server_socket)

    def run(self) -> None:
        logger.info(
            "Server started on IP: %s, Port: %s",
            self.server_ip,
            self.server_port,
        )
        while True:
            read_sockets, _, _ = select.select(self.list_of_sockets, (), ())
            for sock in read_sockets:
                if sock == self.server_socket:
                    sockfd, addr = self.server_socket.accept()
                    request_choice = (
                        "Welcome to this chatroom! Do you want to login or "
                        "register: "
                    ).encode()

                    # Get the username
                    try:
                        # send the welcome message to the client
                        sockfd.send(request_choice)
                        # receive the username from the client
                        if (
                            choice := sockfd.recv(self.receive_buffer_size)
                            .decode()
                            .strip()
                            .lower()
                        ) not in {
                            "register",
                            "login",
                        }:
                            sockfd.send(
                                (
                                    "You need to either login or register. "
                                    "Please try again."
                                ).encode()
                            )
                            sockfd.close()
                            continue

                        sockfd.send("Please write your username: ".encode())
                        username = (
                            sockfd.recv(self.receive_buffer_size)
                            .decode()
                            .strip()
                            .lower()
                        )

                        if choice == "register":
                            if (
                                not username
                                or len(username) > 20
                                or " " in username
                            ):
                                # send the invalid username message to the client
                                sockfd.send(
                                    "Invalid username. Please try again.".encode()
                                )
                                sockfd.close()
                                continue

                            with open(
                                "users.json", "r", encoding="utf-8"
                            ) as file:
                                dict_users: dict[str, str] = json.load(file)
                                if username in dict_users:
                                    username_already_taken_message = (
                                        "Username already taken. Please try "
                                        "again."
                                    ).encode()
                                    # send the username already taken message to the client
                                    sockfd.send(username_already_taken_message)
                                    sockfd.close()
                                    continue

                            # Username is valid, send a confirmation message
                            # send the confirmation message to the client
                            sockfd.send(
                                "Your username is valid. Please enter password.".encode()
                            )

                            password = sockfd.recv(self.receive_buffer_size)
                            password = password.decode().strip()

                            with open(
                                "users.json", "w", encoding="utf-8"
                            ) as file:
                                dict_users.update({username: password})
                                json.dump(dict_users, file)

                            sockfd.send("You are now registered.".encode())

                        elif choice == "login":  # Could have been an else
                            with open(
                                "users.json", "r", encoding="utf-8"
                            ) as file:
                                dict_users = json.load(file)
                                if username not in dict_users:
                                    sockfd.send(
                                        "Username not registered. Please try "
                                        "again.".encode()
                                    )
                                    sockfd.close()
                                    continue

                            sockfd.send(
                                "Your username is valid. Please enter password.".encode()
                            )

                            if (
                                password := sockfd.recv(
                                    self.receive_buffer_size
                                )
                                .decode()
                                .strip()
                            ) != dict_users[username]:
                                sockfd.send(
                                    "Password did not match username. Please "
                                    "try again.".encode()
                                )
                                sockfd.close()
                                continue

                            sockfd.send("You are now logged in.".encode())

                        sockfd.send(
                            "\n Connected to the chat server.\n To exit the "
                            "chatroom type ':q'\n To list all online users "
                            "type ':l'\n To send a p2p message type "
                            "'@username: message'".encode()
                        )

                    except Exception as err:
                        logger.error(
                            "Unable to get username from client. Error "
                            "message : %s",
                            err,
                        )
                        sockfd.close()
                        continue

                    # Add new socket descriptor to the list of readable connections
                    self.list_of_sockets.append(sockfd)
                    # Add new client to the list of clients
                    client_details = (username, addr[0])
                    self.clients[sockfd] = client_details
                    # Broadcast new client's details to all other clients
                    broadcast_message = (
                        f"{client_details[0]} (IP: "
                        f"{client_details[1]}) connected"
                    )
                    print(f"New client connected: {broadcast_message}")
                    broadcast_message = broadcast_message.encode()
                    # broadcast the message to all clients except the new client
                    self.broadcast(broadcast_message, sockfd)
                    # Broadcast updated list of clients to all clients
                    self.broadcast_list_of_clients()

                # Some incoming message from a client
                else:
                    # get the client details using the socket object that sent the message
                    client_details = self.clients[sock]
                    # receive data from the socket
                    # if data is not empty, broadcast it to all other clients
                    if data := sock.recv(self.receive_buffer_size):
                        broadcast_message = (
                            f"{client_details[0]} (IP: {client_details[1]}) "
                            f"said: {data.decode}"
                        )
                        print(
                            f"Broadcasting message from client: {broadcast_message}"
                        )
                        broadcast_message = broadcast_message.encode()
                        # broadcast the message to all clients except the
                        # client that sent the message
                        self.broadcast(broadcast_message, sock)

                    # if data is empty, the client closed the connection
                    else:
                        broadcast_message = (
                            f"{client_details[0]} (IP: {client_details[1]}) "
                            "is offline"
                        )
                        print(f"Client disconnected: {broadcast_message}")
                        broadcast_message = broadcast_message.encode()
                        # broadcast the message to all clients
                        self.broadcast(broadcast_message, self.server_socket)
                        sock.close()
                        self.remove(sock)
                        # update the list of clients for all clients
                        self.broadcast_list_of_clients()

        # self.server_socket.close()


def main() -> None:
    server_ip = socket.gethostbyname(socket.gethostname())
    server_port = 12000
    receive_buffer_size = 2048
    max_clients = 10

    server = ChatRoomP2PServer(
        server_ip, server_port, receive_buffer_size, max_clients
    )
    server.run()


if __name__ == "__main__":
    main()
