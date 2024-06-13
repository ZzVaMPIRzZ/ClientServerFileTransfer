import socket
import os
import argparse
import csv
from datetime import datetime, timezone


def create_log_file_if_not_exists(recreate=False):
    """
    A function that creates a log file if it doesn't exist.
    """
    if recreate or not os.path.exists("log_file.csv"):
        try:
            with open("log_file.csv", "w", newline="") as log_file:
                writer = csv.writer(log_file, delimiter="\t")
                writer.writerow(["File Name", "Date and Time", "Key"])
        except OSError as e:
            print(f"Error creating log file: {e}")
            exit(1)


def create_keys_file_if_not_exists(recreate=False):
    """
    A function that creates a keys file if it doesn't exist.
    """
    if recreate or not os.path.exists("keys.csv"):
        try:
            with open("keys.csv", "w", newline="") as keys_file:
                writer = csv.writer(keys_file, delimiter="\t")
                writer.writerow(["Key"])
        except OSError as e:
            print(f"Error creating keys file: {e}")
            exit(1)


def go_to_dir(directory):
    """
    A function that changes the working directory.
    """

    # Create the directory if it doesn't exist
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(f"Error creating directory: {e}")
            exit(1)

    # Change the working directory
    os.chdir(directory)


def start_server(server_IP, server_PORT):
    """
    A function that starts a server to listen for incoming files.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((server_IP, server_PORT))
    except OSError as e:
        print(f"Error binding socket: {e}")
        exit(1)

    server_socket.listen(1)

    return server_socket


def receive_file_name(client_socket):
    len_of_title = int.from_bytes(client_socket.recv(8))
    file_name, file_size, time_of_last_change = client_socket.recv(len_of_title).decode().split('\t')
    file_name = os.path.basename(file_name)
    file_size = int(file_size)
    time_of_last_change = datetime.strptime(time_of_last_change, "%Y-%m-%d %H:%M:%S.%f")

    return file_name, file_size, time_of_last_change


def receive_file(file_name, file_size, client_socket, offset=0, BUFFER_SIZE=1024):
    """
    A function that receives a file from a client.

    Parameters:
    - file_name: str, the name of the file to be received
    - client_socket: socket, the socket connection to the client
    - BUFFER_SIZE: int, the buffer size for receiving data (default is 1024)

    No return value.
    """
    client_socket.sendall(offset.to_bytes(8))
    file_mode = "ab" if offset > 0 else "wb"
    with open(file_name, file_mode) as file:
        while True:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                break
            file.write(data)
            file_size -= len(data)
    return file_size - offset


def generate_key(keys):
    """
    A function that generates a new key.
    """
    key = 0
    while key in keys + [0]:
        key = int.from_bytes(os.urandom(8))
    return key


def read_keys_file():
    """
    A function that reads the keys file and returns a list of keys.
    """
    keys = []
    if os.path.exists("keys.csv"):
        with open("keys.csv", "r") as key_file:
            reader = csv.reader(key_file, delimiter="\t")
            next(reader)
            for row in reader:
                keys.append(int(row[0]))
    return keys


def read_log_file():
    """
    A function that reads the log file and returns a dictionary of logs.
    """
    logs = dict()
    if os.path.exists("log_file.csv"):
        with open("log_file.csv", "r") as log_file:
            reader = csv.reader(log_file, delimiter="\t")
            next(reader)
            for row in reader:
                logs[row[0]] = (
                    datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc),
                    int(row[2])
                )
    return logs


def check_key(client_socket, keys):
    """
    A function that checks the key of the client and returns the key.
    """
    key = int.from_bytes(client_socket.recv(8))
    if key not in keys or key == 0:
        key = generate_key(keys)
        keys.append(key)
        with open("keys.csv", "a", newline="") as key_file:
            writer = csv.writer(key_file, delimiter="\t")
            writer.writerow([key])

    client_socket.sendall(key.to_bytes(8))

    return key


def update_log_file(file_name, key):
    """
    A function that updates the log file with the file name and key.
    """
    with open("log_file.csv", "a", newline="") as log_file:
        writer = csv.writer(log_file, delimiter="\t")
        writer.writerow([file_name, str(datetime.now(tz=timezone.utc)).split('+')[0], key])


def main(directory="data", server_IP="127.0.0.1", server_PORT=12345, BUFFER_SIZE=1024):
    """
    A function that starts a server to listen for incoming files, receives files, and logs the file names and
    timestamps.

    Parameters:
    - directory: str, the directory path where files will be stored (default is "data")
    - server_address: tuple, the IP address and port number to bind the server socket (default is ("127.0.0.1", 12345))
    - BUFFER_SIZE: int, the size of the buffer for receiving data (default is 1024)
    """

    go_to_dir(directory)  # Change the working directory

    create_log_file_if_not_exists()  # Create the log file
    create_keys_file_if_not_exists()  # Create the keys file

    keys = read_keys_file()

    logs = read_log_file()

    server_socket = start_server(server_IP, server_PORT)  # Start the server

    print(f"Server listening on {server_IP}:{server_PORT}")
    print(f"Working directory: {os.getcwd()}")

    # Start receiving files
    try:
        while True:
            # Accept a connection
            client_socket, client_address = server_socket.accept()
            print(f"Connection from {client_address[0]}:{client_address[1]}")

            # Check the key
            key = check_key(client_socket, keys)

            # Receive the file name and size
            file_name, file_size, time_of_last_change = receive_file_name(client_socket)
            file_size = int(file_size)
            time_of_last_change = time_of_last_change.replace(tzinfo=timezone.utc)
            print(f"Receiving {file_name} ({file_size} bytes)")

            # Check if the file has already been received
            if file_name in logs and logs[file_name][0] > time_of_last_change and logs[file_name][1] == key:
                offset = os.path.getsize(file_name)
            else:
                offset = 0

            # Receive the file
            unreceived_file_size = receive_file(file_name, file_size, client_socket, offset, BUFFER_SIZE)
            if unreceived_file_size == 0:
                print(f"File {file_name} received successfully")
            else:
                print(f"File {file_name} received with errors (Unreceived file size: {unreceived_file_size} bytes)")

            # Add the file name and date and time to the log file
            logs[file_name] = (datetime.now(tz=timezone.utc), key)

            update_log_file(file_name, key)

            # Close the connection
            client_socket.close()
    except KeyboardInterrupt:
        print("Server stopped")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server_socket.close()


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-directory", default="data", help="Directory to store received files")
    parser.add_argument("-server_IP", default="127.0.0.1", help="Server IP")
    parser.add_argument("-server_PORT", default=12345, help="Server port")
    parser.add_argument("--buffer_size", type=int, default=1024, help="Buffer size")
    args = parser.parse_args()

    # Start the server
    main(args.directory, args.server_IP, args.server_PORT, args.buffer_size)
