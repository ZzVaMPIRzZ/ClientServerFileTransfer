from datetime import datetime, timezone
import socket
import tqdm
import os
import argparse


def check_key(client_socket):
    key = 0
    if os.path.exists("key.txt"):
        with open("key.txt", "r") as key_file:
            key = int(key_file.read())

    client_socket.sendall(key.to_bytes(8))
    key = int.from_bytes(client_socket.recv(8))
    with open("key.txt", "w") as key_file:
        key_file.write(str(key))


def send_file_params(client_socket, file_name, file_size, file_path):
    title = (file_name.encode() + '\t'.encode() +
             str(file_size).encode() + '\t'.encode() +
             str(datetime.fromtimestamp(os.path.getmtime(file_path), timezone.utc)).split('+')[0].encode())
    client_socket.send(len(title).to_bytes(8))
    client_socket.sendall(title)


def send_file(file_name, file_size, file_path, client_socket, offset, BUFFER_SIZE=1024):
    progress_bar = tqdm.tqdm(range(file_size),
                             f"Sending {file_name}",
                             unit="B",
                             unit_scale=True,
                             unit_divisor=1024,
                             colour="green"
                             )
    progress_bar.update(offset)

    with open(file_path, "rb") as file:
        file.seek(offset)
        while True:
            data = file.read(BUFFER_SIZE)
            if not data:
                break
            client_socket.sendall(data)
            progress_bar.update(len(data))

    progress_bar.close()


def main(file_path, server_IP, server_PORT, BUFFER_SIZE=1024):
    """
    A function that starts a client to send a file to a server.

    Parameters:
    - file_path: str, the path to the file to be sent.
    - server_address: tuple, the address of the server to connect to.
    - BUFFER_SIZE: int, the buffer size for reading and sending file data (default is 1024).

    No return value.
    """

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Get the file name and size
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Start the client
        client_socket.connect((server_IP, server_PORT))
        print(f"Connected to {server_IP}:{server_PORT}")

        # Check the key
        check_key(client_socket)

        # Send the file name and size
        print(f"Sending {file_name} ({file_size} bytes)")
        send_file_params(client_socket, file_name, file_size, file_path)

        # Receive the offset
        offset = int.from_bytes(client_socket.recv(8))

        # Send the file
        send_file(file_name, file_size, file_path, client_socket, offset, BUFFER_SIZE)

        # Close the connection
        print(f"File {file_name} sent successfully")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()


if __name__ == "__main__":
    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-file_name", required=True)
    parser.add_argument("-server_IP", required=True)
    parser.add_argument("-server_PORT", required=True)
    parser.add_argument("--buffer_size", type=int, default=1024)
    args = parser.parse_args()

    # Start the client
    main(args.file_name, args.server_IP, int(args.server_PORT), args.buffer_size)
