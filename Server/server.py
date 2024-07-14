import socket
import os
import argparse
import csv
import time
from datetime import datetime, timezone

from ConnectionFailedError import ConnectionFailedError
from MessageTypeError import MessageTypeError
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
    try:
        server_socket.bind((server_IP, server_PORT))
        server_socket.listen(1)
    except OSError as e:
        print(f"Error binding socket: {e}")
        exit(1)

    server_socket.listen(1)

    return server_socket


def receive_message(client_socket):
    """
    A function that receives a message from a client.

    Parameters:
    - client_socket: socket, the socket connection to the client

    Returns:
    - str, the message
    """
    try:
        len_of_message = int.from_bytes(client_socket.recv(8))
        message_type = client_socket.recv(6)
        message = client_socket.recv(len_of_message)
    except ConnectionError:
        return None
    except ValueError as e:
        print(f"Error receiving message: {e}")
        exit(1)

    return message_type, message


# def receive_file_name(client_socket):
#     """
#     A function that receives the file name from a client.
#
#     Parameters:
#     - client_socket: socket, the socket connection to the client
#
#     Returns:
#     - str, the name of the file
#     - int, the total size of the file
#     - datetime, the time of the last change of the file
#     """
#     message_type, data = receive_message(client_socket)
#     if message_type != MessageType.START.value:
#         raise MessageTypeError(f"Invalid message type: {message_type}")
#
#     data = data.decode()
#     str_file_name, str_file_size = data.split("\t")
#     file_name = os.path.basename(str_file_name)
#     file_size = int(str_file_size)
#
#     return file_name, file_size


# def receive_file(file_name, server_socket, client_socket):
#     """
#     A function that receives a file from a client.
#
#     Parameters:
#     - file_name: str, the name of the file to be received
#     - file_size: int, the total size of the file to be received
#     - client_socket: socket, the socket connection to the client
#     - offset: int, the offset to start receiving data from (default is 0)
#     - BUFFER_SIZE: int, the buffer size for receiving data (default is 1024)
#
#     Returns:
#     - int, the number of bytes left to receive
#     """
#     result = Result.ERROR
#     try:
#         with open(file_name, "wb") as file:
#             while True:
#                 try:
#                     message_type, data = receive_message(client_socket)
#                     if message_type == MessageType.END.value:
#                         result = Result.SUCCESS
#                         break
#                     if message_type == MessageType.CANCEL.value:
#                         result = Result.CANCEL
#                         break
#                     if not message_type:
#                         raise ConnectionError
#                     if message_type != MessageType.DATA.value:
#                         raise MessageTypeError(f"Invalid message type: {message_type}")
#                     file.write(data)
#                 except MessageTypeError as e:
#                     raise e
#                 except (socket.timeout, ConnectionError):
#                     client_socket.close()
#                     # time.sleep(1)
#                     client_socket, _ = connect_client(server_socket, 3)
#                     if client_socket is None:
#                         raise ConnectionFailedError
#
#                 # client_socket.shutdown(socket.SHUT_RDWR)
#                 # client_socket.close()
#                 # time.sleep(1)
#                 # client_socket, _ = connect_client(server_socket, 3)
#     except (MessageTypeError, ConnectionFailedError) as e:
#         raise e
#     finally:
#         if result != Result.SUCCESS:
#             os.remove(file_name)
#
#     return result


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

    # Start receiving files
    try:
        while True:
            # Accept a connection
            client_socket, client_address = connect_client(server_socket)
            print(f"Connection from {client_address[0]}:{client_address[1]}")

            message_type = None
            file = None
            file_name = None
            result = Result.SUCCESS
            while message_type != MessageType.END.value:
                message_type, data = receive_message(client_socket)
                if message_type == MessageType.START.value:
                    client_socket.send(Response.SUCCESS.value)
                    if file:
                        file.close()
                        os.remove(file_name)
                        print(f"Error receiving file {file_name}")
                    file_name = data.decode().split('\t')[0]
                    file_size = int(data.decode().split('\t')[1])
                    file = open(file_name, "wb")
                    print(f"Receiving file {file_name} ({file_size} bytes) ...")
                elif message_type == MessageType.DATA.value:
                    if not file:
                        client_socket.send(Response.ERROR.value)
                        result = Result.ERROR
                        break
                    client_socket.send(Response.SUCCESS.value)
                    file.write(data)
                elif message_type == MessageType.CANCEL.value:
                    client_socket.send(Response.SUCCESS.value)
                    result = Result.CANCEL
                    break
                elif not message_type:
                    client_socket.close()
                    # time.sleep(1)
                    client_socket, _ = connect_client(server_socket, 3)
                    if client_socket is None:
                        result = Result.ERROR
                        break

            if file:
                file.close()

            if result == Result.SUCCESS:
                client_socket.send(Response.SUCCESS.value)
                print(f"File {file_name} received successfully")
            elif result == Result.CANCEL:
                print(f"File {file_name} canceled")
            else:
                print(f"Error receiving file {file_name}")

            update_log_file(file_name, result)

            # Close the connection
            if client_socket:
                client_socket.close()
    except KeyboardInterrupt:
        print("Server stopped")
    # except Exception as e:
    #     print(f"Error: {e}")
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
