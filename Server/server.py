import socket
import os
import argparse
import csv
from datetime import datetime, timezone

import select

from ResponseEnum import Response
from ResultEnum import Result
from TypeEnum import MessageType


def create_log_file_if_not_exists(recreate=False):
    """
    A function that creates a log file if it doesn't exist.

    Parameters:
    - recreate: bool, whether to recreate the file if it already exists (default is False)

    No return value.
    """
    if recreate or not os.path.exists("log_file.csv"):
        try:
            with open("log_file.csv", "w", newline="") as log_file:
                writer = csv.writer(log_file, delimiter="\t")
                writer.writerow(["File Name", "Date and Time", "Result"])
        except OSError as e:
            print(f"Error creating log file: {e}")
            exit(1)


def go_to_dir(directory):
    """
    A function that changes the working directory.

    Parameters:
    - directory: str, the directory path

    No return value.
    """
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(f"Error creating directory: {e}")
            exit(1)

    os.chdir(directory)


def start_server(server_IP, server_PORT):
    """
    A function that starts a server.

    Parameters:
    - server_address: tuple, the IP address and port number to bind the server socket

    Returns:
    - socket, the server socket
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.settimeout(1)
    server_socket.setblocking(False)
    try:
        server_socket.bind((server_IP, server_PORT))
        server_socket.listen(5)
    except OSError as e:
        print(f"Error binding socket: {e}")
        exit(1)

    server_socket.listen(1)

    return server_socket


def update_log_file(file_name, result):
    """
    A function that updates the log file with the name and time of the last change of a file.

    Parameters:
    - file_name: str, the name of the file
    - key: int, the key of the client

    No return value.
    """
    with open("log_file.csv", "a", newline="") as log_file:
        writer = csv.writer(log_file, delimiter="\t")
        writer.writerow([file_name, str(datetime.now(tz=timezone.utc)).split('.')[0], result])


def connect_client(server_socket, times=0):
    if times == 0:
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                # client_socket.settimeout(3)
                break
            except (ConnectionResetError, ConnectionAbortedError, socket.timeout):
                pass
                # time.sleep(1)
    else:
        client_socket, client_address = None, None
        for _ in range(times):
            try:
                client_socket, client_address = server_socket.accept()
                # client_socket.settimeout(3)
                break
            except (ConnectionResetError, ConnectionAbortedError, socket.timeout):
                pass
                # time.sleep(1)
    # print(f"Client connected: {client_address}")
    return client_socket, client_address


def main(directory="data", server_IP="127.0.0.1", server_PORT=12345):
    """
    A function that starts a server to listen for incoming files, receives files, and logs the file names and
    timestamps.

    Parameters:
    - directory: str, the directory path where files will be stored (default is "data")
    - server_address: tuple, the IP address and port number to bind the server socket (default is ("127.0.0.1", 12345))
    - BUFFER_SIZE: int, the size of the buffer for receiving data (default is 1024)

    No return value.
    """
    go_to_dir(directory)

    create_log_file_if_not_exists()

    server_socket = start_server(server_IP, server_PORT)

    print(f"Server listening on {server_IP}:{server_PORT}")
    print(f"Working directory: {os.getcwd()}")

    inputs = [server_socket]
    lens_of_data = {}
    message_types = {}
    files = {}

    # Start receiving files
    try:
        while True:
            # Accept a connection

            readable, _, _ = select.select(inputs, [], [])

            for s in readable:
                if s is server_socket:
                    client_socket, client_address = connect_client(server_socket)
                    client_socket.setblocking(False)
                    inputs.append(client_socket)
                    print(f"Connection from {client_address[0]}:{client_address[1]}")
                else:
                    client_socket = s
                    client_address = client_socket.getpeername()
                    try:
                        if client_socket in lens_of_data:
                            data = client_socket.recv(lens_of_data[client_socket])

                            if lens_of_data[client_socket] - len(data) != 0:
                                raise ConnectionError

                            if message_types[client_socket] == MessageType.START.value:
                                client_socket.send(Response.SUCCESS.value)
                                file_name = data.decode().split('\t')[0]
                                file_size = int(data.decode().split('\t')[1])
                                files[client_socket] = open(file_name, "wb")
                                print(f"Receiving file {file_name} ({file_size} bytes) ...")
                            elif message_types[client_socket] == MessageType.DATA.value:
                                if files[client_socket] is None:
                                    client_socket.send(Response.ERROR.value)
                                    raise ConnectionError
                                else:
                                    client_socket.send(Response.SUCCESS.value)
                                    files[client_socket].write(data)
                            else:
                                if (message_types[client_socket] == MessageType.END.value or
                                        message_types[client_socket] == MessageType.CANCEL.value):
                                    client_socket.send(Response.SUCCESS.value)
                                if files[client_socket] is not None:
                                    update_log_file(files[client_socket].name, Result.ERROR.value)
                                    files[client_socket].close()
                                    if message_types[client_socket] != MessageType.END.value:
                                        os.remove(files[client_socket].name)
                                del files[client_socket]
                                inputs.remove(client_socket)
                                client_socket.close()
                                if message_types[client_socket] == MessageType.END.value:
                                    print(f"Connection from {client_address[0]}:{client_address[1]} closed successfully")
                                elif message_types[client_socket] == MessageType.CANCEL.value:
                                    print(f"Connection from {client_address[0]}:{client_address[1]} canceled")
                                else:
                                    print(f"Connection from {client_address[0]}:{client_address[1]} closed with error")

                            del lens_of_data[client_socket]
                            del message_types[client_socket]

                        elif client_socket in message_types:
                            message = client_socket.recv(8)
                            if message is None:
                                raise ConnectionError
                            lens_of_data[client_socket] = int.from_bytes(message)
                            continue
                        else:
                            message = client_socket.recv(6)
                            if message is None:
                                raise ConnectionError
                            message_types[client_socket] = message
                            continue
                    except ConnectionError:
                        inputs.remove(client_socket)
                        client_socket.close()
                        print(f"Connection from {client_address[0]}:{client_address[1]} closed with error")

    except KeyboardInterrupt:
        print("Server stopped")
    finally:
        server_socket.close()


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-directory", default="data", help="Directory to store received files")
    parser.add_argument("-server_IP", default="127.0.0.1", help="Server IP")
    parser.add_argument("-server_PORT", default=12345, help="Server port")
    args = parser.parse_args()

    # Start the server
    main(args.directory, args.server_IP, args.server_PORT)
