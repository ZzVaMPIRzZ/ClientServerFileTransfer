import signal
import time
import socket
import tqdm
import os
import argparse
from sys import exit
from ipaddress import ip_address

from Enums import MessageType, Response

CLIENT_CLOSE = False


def validate_ip_port(IP, PORT):
    """
    Проверяет IP-адрес на валидность.
    Args:
        IP: str, IP-адрес
        PORT: int, порт

    raise:
        ValueError
    """
    ip_address(IP)
    if int(PORT) > 65535 or int(PORT) < 1:
        raise ValueError("Invalid PORT")


def connect_to_server(server_IP, server_PORT):
    """
    Подключается к серверу.
    Args:
        server_IP: str, IP-адрес сервера
        server_PORT: int, порт сервера

    raise:
        ConnectionError
    """
    try:
        validate_ip_port(server_IP, server_PORT)
    except ValueError:
        raise ConnectionError("Invalid IP or PORT")
    client_socket = None
    for i in range(3):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client_socket.settimeout(3)
        try:
            time.sleep(0.1)
            client_socket.connect((server_IP, server_PORT))
            break
        except (ConnectionError, socket.timeout):
            if i == 2:
                raise ConnectionError("Connection failed")

    # print(f"Client socket created: {client_socket}")
    return client_socket


def send_message(client_socket, message_type, data):
    """
    Отправляет сообщение на сервер.
    Args:
        client_socket: socket, сокет клиента
        message_type: MessageType, тип сообщения
        data: bytes, данные

    raise:
        ConnectionError
    """
    try:
        client_socket.send(message_type.value)
        client_socket.send(len(data).to_bytes(8))
        client_socket.send(data)
        response = client_socket.recv(1)
        if response == Response.FILE_IS_BEING_ALREADY_TRANSFERRED.value:
            raise ConnectionError("File is being already transferred")
        if response != Response.SUCCESS.value:
            if response == Response.ERROR.value:
                raise ConnectionError("Transfer failed")
            raise ConnectionError("Connection failed")
    except ConnectionError as e:
        raise e


def send_file_params(client_socket, file_path):
    """
    Отправляет параметры файла на сервер.
    Args:
        client_socket: socket, сокет клиента
        file_path: str, путь к файлу
    """
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    title = (file_name.encode() + '\t'.encode() +
             str(file_size).encode())

    send_message(client_socket, MessageType.START, title)


def send_file(file_path, client_socket, BUFFER_SIZE=1024):
    """
    Генератор, отправляющий файл на сервер.
    Args:
        file_path: str, путь к файлу
        client_socket: socket, сокет клиента
        BUFFER_SIZE: int, размер буфера

    Returns:

    Yield:
        client_socket: socket, сокет клиента (возможно, что в процессе он может измениться из-за переподключения),
        len(data): int, количество отправленных байт

    """

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
                except ConnectionError as e:
                    raise e
            file_size -= len(data)
            yield len(data)
            if file_size == 0:
                send_message(client_socket, MessageType.END, b'\x00')
                break


def main(file_path, server_IP, server_PORT, BUFFER_SIZE=1024):
    """
    Основная функция
    Args:
        file_path: str, путь к файлу
        server_IP: str, IP-адрес сервера
        server_PORT: int, порт сервера
        BUFFER_SIZE: int, размер буфера
    """
    if os.path.exists(file_path) is False:
        print(f"File {file_path} not found. Exiting...")
        exit(1)
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    try:
        client_socket = connect_to_server(server_IP, server_PORT)
    except ConnectionError as e:
        print(e)
        exit(1)
    print(f"Connected to {server_IP}:{server_PORT}")

    print(f"Sending {file_name} ({file_size} bytes)")
    progress_bar = tqdm.tqdm(range(file_size),
                             f"Sending {file_name}",
                             unit="B",
                             unit_scale=True,
                             unit_divisor=1024,
                             colour="green"
                             )

    def exit_gracefully(signum, frame):
        global CLIENT_CLOSE
        if not CLIENT_CLOSE:
            CLIENT_CLOSE = True
            send_message(client_socket, MessageType.CANCEL, b'\x00')
            client_socket.close()
            progress_bar.close()
            print("Exiting...")
            exit(0)

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    # Отправка файла
    try:
        for data_len in send_file(file_path, client_socket, BUFFER_SIZE):
            progress_bar.update(data_len)
        progress_bar.close()
    except ConnectionError as e:
        progress_bar.close()
        print(e)
        exit(1)
    finally:
        client_socket.close()

    print(f"File {os.path.basename(file_path)} sent successfully")


if __name__ == "__main__":
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser()
    parser.add_argument("-file_name", required=True)
    parser.add_argument("-server_IP", required=True)
    parser.add_argument("-server_PORT", type=int, required=True)
    parser.add_argument("--buffer_size", type=int, default=1024)
    args = parser.parse_args()

    # Запуск основной функции
    try:
        validate_ip_port(args.server_IP, args.server_PORT)
        if args.buffer_size <= 0 or args.buffer_size > 32768:
            raise ValueError("Buffer size must be between 1 and 32768")
    except ValueError as e:
        print(e)
        exit(1)
    main(args.file_name, args.server_IP, args.server_PORT, args.buffer_size)
