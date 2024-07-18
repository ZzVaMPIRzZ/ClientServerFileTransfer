import time
import socket
import tqdm
import os
import argparse
from sys import exit

from ConnectionFailedError import ConnectionFailedError
from FileIsBeingAlreadyTransferredError import FileIsBeingAlreadyTransferredError
from TypeEnum import MessageType
from ResponseEnum import Response


def connect_to_server(server_IP, server_PORT):
    client_socket = None
    for i in range(3):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client_socket.settimeout(3)
        try:
            time.sleep(0.1)
            client_socket.connect((server_IP, server_PORT))
            break
        except ConnectionRefusedError:
            if i == 2:
                raise ConnectionFailedError

    # print(f"Client socket created: {client_socket}")
    return client_socket


def send_message(client_socket, message_type, data):
    try:
        client_socket.send(message_type.value)
        client_socket.send(len(data).to_bytes(8))
        client_socket.send(data)
        response = client_socket.recv(1)
        if response == Response.FILE_IS_BEING_ALREADY_TRANSFERRED.value:
            raise FileIsBeingAlreadyTransferredError
        if response != b'\x00':
            raise ConnectionFailedError
        # print(sent1, sent2)
    except (ConnectionResetError, ConnectionAbortedError, ConnectionFailedError, FileIsBeingAlreadyTransferredError) as e:
        raise e


def send_file_params(client_socket, file_path):
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    title = (file_name.encode() + '\t'.encode() +
             str(file_size).encode())

    send_message(client_socket, MessageType.START, title)


def send_file(file_path, client_socket, server_IP, server_PORT, BUFFER_SIZE=1024):

    file_size = os.path.getsize(file_path)

    send_file_params(client_socket, file_path)

    with open(file_path, "rb") as file:
        while True:
            data = file.read(BUFFER_SIZE)
            while True:
                # time.sleep(0.005)
                try:
                    send_message(client_socket, MessageType.DATA, data)
                    break
                except (ConnectionResetError, ConnectionAbortedError):
                    client_socket.close()
                    time.sleep(0.1)
                    client_socket = connect_to_server(server_IP, server_PORT)
                except ConnectionFailedError as e:
                    raise e
            file_size -= len(data)
            yield client_socket, len(data)
            if file_size == 0:
                send_message(client_socket, MessageType.END, b'\x00')
                break


def main(file_path, server_IP, server_PORT, BUFFER_SIZE=1024):
    """
    A function that starts a client to send a file to a server.

    Parameters:
    - file_path: str, the path to the file to be sent.
    - server_address: tuple, the address of the server to connect to.
    - BUFFER_SIZE: int, the buffer size for reading and sending file data (default is 1024).

    No return value.
    """

    # Start the client
    if os.path.exists(file_path) is False:
        print(f"File {file_path} not found. Exiting...")
        exit(1)
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    client_socket = connect_to_server(server_IP, server_PORT)
    print(f"Connected to {server_IP}:{server_PORT}")

    print(f"Sending {file_name} ({file_size} bytes)")
    progress_bar = tqdm.tqdm(range(file_size),
                             f"Sending {file_name}",
                             unit="B",
                             unit_scale=True,
                             unit_divisor=1024,
                             colour="green"
                             )

    # Send the file
    try:
        for client_socket, data_len in send_file(file_path, client_socket, server_IP, server_PORT, BUFFER_SIZE):
            progress_bar.update(data_len)
        progress_bar.close()
    except FileIsBeingAlreadyTransferredError:
        progress_bar.close()
        print("File is already transferring. Exiting...")
        exit(1)
    except ConnectionFailedError:
        progress_bar.close()
        print("Failed to reconnect. Exiting...")
        exit(1)
    except KeyboardInterrupt:
        progress_bar.close()
        print("Process interrupted. Exiting...")
        exit(1)
    finally:
        client_socket.close()

    # Close the connection
    print(f"File {os.path.basename(file_path)} sent successfully")

    # except Exception as e:
    #     print(f"Error: {e}")
    # finally:
    #     client_socket.close()


if __name__ == "__main__":
    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-file_name", required=True)
    parser.add_argument("-server_IP", required=True)
    parser.add_argument("-server_PORT", required=True)
    parser.add_argument("--buffer_size", type=int, default=1024)
    args = parser.parse_args()

    # Start the client
    try:
        main(args.file_name, args.server_IP, int(args.server_PORT), args.buffer_size)
    except KeyboardInterrupt:
        print("Process interrupted. Exiting...")
