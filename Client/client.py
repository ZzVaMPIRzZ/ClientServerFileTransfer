import socket
import tqdm
import os
import argparse


def start_client(file_path, server_address, BUFFER_SIZE=1024):
    """
    A function that starts a client to send a file to a server.

    Parameters:
    - file_path: str, the path to the file to be sent.
    - server_address: tuple, the address of the server to connect to.
    - BUFFER_SIZE: int, the buffer size for reading and sending file data (default is 1024).

    No return value.
    """

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Start the client
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(server_address)

    print(f"Connected to {server_address[0]}:{server_address[1]}")

    # Send the file name and size
    print(f"Sending {file_name} ({file_size} bytes)")
    client_socket.sendall((file_name.encode() + '\t'.encode() + str(file_size).encode()))

    # Create the progress bar
    progress_bar = tqdm.tqdm(range(file_size), f"Sending {file_name}", unit="B", unit_scale=True, unit_divisor=1024,
                             colour="green")

    # Send the file
    with open(file_path, "rb") as file:
        while True:
            data = file.read(BUFFER_SIZE)
            if not data:
                break
            client_socket.sendall(data)
            progress_bar.update(len(data))

    # Close the progress bar
    progress_bar.close()
    # Close the connection
    print(f"File {file_name} sent successfully")
    client_socket.close()


if __name__ == "__main__":
    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-file_name", required=True)
    parser.add_argument("-server_address", required=True)
    parser.add_argument("--buffer_size", type=int, default=1024)
    args = parser.parse_args()

    # Start the client
    IP, str_PORT = args.server_address.split(':')
    server_address = (IP, int(str_PORT))
    start_client(args.file_name, server_address, args.buffer_size)
