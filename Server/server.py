import socket
import os
import argparse
import csv
from datetime import datetime


def start_server(directory="data", server_address=("127.0.0.1", 12345), BUFFER_SIZE=1024):
    """
    A function that starts a server to listen for incoming files, receives files, and logs the file names and timestamps.

    Parameters:
    - directory: str, the directory path where files will be stored (default is "data")
    - server_address: tuple, the IP address and port number to bind the server socket (default is ("127.0.0.1", 12345))
    - BUFFER_SIZE: int, the size of the buffer for receiving data (default is 1024)
    """

    # Create the directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Change the working directory
    os.chdir(directory)

    # Create the log file if it doesn't exist
    if not os.path.exists("log_file.csv"):
        with open("log_file.csv", "w", newline="") as log_file:
            writer = csv.writer(log_file, delimiter="\t")
            writer.writerow(["File Name", "Date and Time"])

    # Start the server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(server_address)
    server_socket.listen(1)

    print(f"Server listening on {server_address[0]}:{server_address[1]}")
    print(f"Working directory: {os.getcwd()}")

    # Start receiving files
    while True:
        # Accept a connection
        client_socket, client_address = server_socket.accept()
        print(f"Connection from {client_address[0]}:{client_address[1]}")

        # Receive the file name and size
        file_name, file_size = client_socket.recv(BUFFER_SIZE).decode().split('\t')
        file_name = os.path.basename(file_name)
        file_size = int(file_size)
        print(f"Receiving {file_name} ({file_size} bytes)")

        # Receive the file
        with open(file_name, "wb") as file:
            while True:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                file.write(data)

        print(f"File {file_name} received successfully")

        # Add the file name and date and time to the log file
        with open("log_file.csv", "a", newline="") as log_file:
            writer = csv.writer(log_file, delimiter="\t")
            writer.writerow([file_name, str(datetime.now())])

        # Close the connection
        client_socket.close()


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-directory", default="data", help="Directory to store received files")
    parser.add_argument("-server_address", default="127.0.0.1:12345", help="Server address")
    parser.add_argument("--buffer_size", type=int, default=1024, help="Buffer size")
    args = parser.parse_args()

    # Start the server
    IP, str_PORT = args.server_address.split(':')
    server_address = (IP, int(str_PORT))
    start_server(args.directory, server_address, args.buffer_size)
