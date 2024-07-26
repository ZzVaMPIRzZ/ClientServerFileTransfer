import signal
import socket
import os
import argparse
import csv
from datetime import datetime, timezone
from sys import exit

import select

from Enums import Response, Result, MessageType

CLOSE_SERVER = False


def create_log_file_if_not_exists(recreate=False):
    """
    Создает лог-файл, если он не существует.
    Args:
        recreate: bool, пересоздать лог-файл

    raise:
        OSError
    """
    if recreate or not os.path.exists("log_file.csv"):
        try:
            with open("log_file.csv", "w", newline="") as log_file:
                writer = csv.writer(log_file, delimiter="\t")
                writer.writerow(["File Name", "Date and Time", "Result"])
        except OSError as e:
            raise e


def go_to_dir(directory):
    """
    Переход в заданный каталог.
    Args:
        directory: str, каталог

    raise:
        OSError
    """
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            raise e

    os.chdir(directory)


def start_server(server_IP, server_PORT):
    """
    Запуск сервера.
    Args:
        server_IP: str, IP-адрес сервера
        server_PORT: int, порт сервера

    Returns:
        server_socket: socket, сокет сервера
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Установка опции, позволяющей быстро перезапускать сокет после его закрытия
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.settimeout(1)
    server_socket.setblocking(False)
    try:
        server_socket.bind((server_IP, server_PORT))
        server_socket.listen(5)
    except OSError as e:
        raise e

    return server_socket


def update_log_file(file_name, result):
    """
    Обновляет лог-файл.
    Args:
        file_name: str, имя файла
        result: str, результат
    """
    with open("log_file.csv", "a", newline="") as log_file:
        writer = csv.writer(log_file, delimiter="\t")
        writer.writerow([file_name, str(datetime.now(tz=timezone.utc)).split('.')[0], result])


def connect_client(server_socket):
    """
    Подключение клиента.
    Args:
        server_socket: socket, сокет сервера

    Returns:
        client_socket: socket, сокет клиента
        client_address: tuple, IP-адрес и порт клиента
    """
    while True:
        try:
            client_socket, client_address = server_socket.accept()
            break
        except (ConnectionResetError, ConnectionAbortedError, socket.timeout):
            pass
    return client_socket, client_address


def main(directory="data", server_IP="127.0.0.1", server_PORT=12345):
    """
    Основная функция
    Args:
        directory: str, каталог
        server_IP: str, IP-адрес сервера
        server_PORT: int, порт сервера
    """
    try:
        go_to_dir(directory)
        create_log_file_if_not_exists()
        server_socket = start_server(server_IP, server_PORT)
    except OSError as e:
        print(f"Error: {e}")
        exit(1)

    print(f"Server listening on {server_IP}:{server_PORT}")
    print(f"Working directory: {os.getcwd()}")

    epoll = select.epoll()
    epoll.register(server_socket, select.EPOLLIN)

    fd_to_socket = {server_socket.fileno(): server_socket}  # Словарь: файловый дескриптор -> сокет клиента
    clients_dict = {}  # Словарь: сокет клиента -> информация о клиенте и ожидаемом от него сообщении
    file_names = []  # Список имен файлов, которые передаются в данный момент

    def create_client_socket():
        sock, address = connect_client(server_socket)
        sock.setblocking(False)
        clients_dict[sock] = dict().fromkeys(["data_len", "message_type", "file"])
        fd_to_socket[sock.fileno()] = sock
        epoll.register(sock, select.EPOLLIN)
        print(f"Connection from {address[0]}:{address[1]}")

    def close_client_socket(sock, delete_file=False):
        """
        Закрывает сокет клиента.
        Args:
            delete_file: bool, удалить файл после закрытия сокета
            sock: socket, сокет клиента
        """
        epoll.unregister(sock)
        if sock.fileno() in fd_to_socket:
            del fd_to_socket[sock.fileno()]
        if clients_dict[sock]["file"] is not None:
            file_names.remove(clients_dict[sock]["file"].name)
            clients_dict[sock]["file"].close()
            if delete_file:
                os.remove(clients_dict[sock]["file"].name)
        del clients_dict[sock]
        sock.close()

    def handle_start_message(sock, data):
        IP, PORT = sock.getpeername()

        file_name = data.decode().split('\t')[0]
        file_size = int(data.decode().split('\t')[1])

        # Если файл с таким именем в данный момент принимается от другого клиента,
        # то отклоняем принятие ещё одного файла с таким названием
        if file_name in file_names:
            sock.send(Response.FILE_IS_BEING_ALREADY_TRANSFERRED.value)
            raise ConnectionError(f"Client {IP}:{PORT} disconnected because file {file_name} "
                                  f"transfer is already in progress")
        else:
            sock.send(Response.SUCCESS.value)
            clients_dict[sock]["file"] = open(file_name, "wb")
            file_names.append(file_name)
            print(f"Receiving file {file_name} ({file_size} bytes) ...")

    def handle_data_message(sock, data):
        IP, PORT = sock.getpeername()
        if clients_dict[sock]["file"] is not None:
            sock.send(Response.SUCCESS.value)
            clients_dict[sock]["file"].write(data)
        else:
            sock.send(Response.ERROR.value)
            raise ConnectionError(f"Client {IP}:{PORT} disconnected with invalid message type: DATA")

    def handle_end_message(sock):
        IP, PORT = sock.getpeername()
        sock.send(Response.SUCCESS.value)
        update_log_file(clients_dict[sock]["file"].name, Result.SUCCESS.name)
        print(f"Connection from {IP}:{PORT} closed successfully")

    def handle_cancel_message(sock):
        IP, PORT = sock.getpeername()
        sock.send(Response.SUCCESS.value)
        update_log_file(clients_dict[sock]["file"].name, Result.CANCEL.name)
        print(f"Connection from {IP}:{PORT} canceled")

    def handle_message(client_socket, message_type, data):
        client_IP, client_PORT = client_socket.getpeername()
        if message_type == MessageType.START.value:
            handle_start_message(client_socket, data)
        elif message_type == MessageType.DATA.value:
            handle_data_message(client_socket, data)
        elif message_type == MessageType.END.value:
            handle_end_message(client_socket)
            close_client_socket(client_socket)
            return
        elif message_type == MessageType.CANCEL.value:
            handle_cancel_message(client_socket)
            close_client_socket(client_socket, delete_file=True)
            return
        else:
            client_socket.send(Response.ERROR.value)
            raise ConnectionError(f"Client {client_IP}:{client_PORT} disconnected with invalid message type: "
                                  f"{message_type}")

        clients_dict[client_socket]["data_len"] = None
        clients_dict[client_socket]["message_type"] = None

    def hear_client_socket(sock):
        client_socket = sock
        client_IP, client_PORT = client_socket.getpeername()
        try:
            if clients_dict[client_socket]["data_len"] is not None:
                # Принимаем данные (3-ий шаг)
                message = client_socket.recv(clients_dict[client_socket]["data_len"])

                if clients_dict[client_socket]["data_len"] != len(message):
                    raise ConnectionError(f"Client {client_IP}:{client_PORT} disconnected while "
                                          f"receiving data")

                # Обрабатываем данные
                handle_message(client_socket, clients_dict[client_socket]["message_type"], message)

            elif clients_dict[client_socket]["message_type"] is not None:
                # Принимаем длину сообщения (2-ой шаг)
                message = client_socket.recv(8)
                if message is None:
                    raise ConnectionError(f"Client {client_IP}:{client_PORT}"
                                          f" disconnected while receiving message length")
                clients_dict[client_socket]["data_len"] = int.from_bytes(message)
            else:
                # Принимаем тип сообщения (1-ый шаг)
                message = client_socket.recv(6)
                if message is None:
                    raise ConnectionError(f"Client {client_IP}:{client_PORT}"
                                          f" disconnected while receiving message type")
                clients_dict[client_socket]["message_type"] = message
        except ConnectionError as e:
            if clients_dict[client_socket]["file"] is not None:
                update_log_file(clients_dict[client_socket]["file"].name, Result.ERROR.name)
            close_client_socket(client_socket)
            print(e)

    def exit_gracefully(signal_number, frame):
        """
        Завершает программу.
        Args:
            signal_number: int, номер сигнала
            frame: frame, фрейм
        """
        global CLOSE_SERVER
        if not CLOSE_SERVER:
            CLOSE_SERVER = True
            print("\nClosing server socket...")
            epoll.unregister(server_socket)
            clients = list(clients_dict.keys())
            for i in clients:
                close_client_socket(i, delete_file=True)
            epoll.close()
            server_socket.close()
            exit(0)

    # Регистрируем обработчик сигналов для принудительного завершения
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    try:
        while True:
            events = epoll.poll()

            for fd, event in events:
                if event & select.EPOLLIN:
                    s = fd_to_socket[fd]
                    if s is server_socket:
                        create_client_socket()
                    else:
                        hear_client_socket(s)

    finally:
        exit_gracefully(None, None)


if __name__ == "__main__":
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser()
    parser.add_argument("-directory", default="data", help="Directory to store received files (default: ./data)")
    parser.add_argument("-server_IP", default="127.0.0.1", help="Server IP")
    parser.add_argument("-server_PORT", default=12345, help="Server port")
    args = parser.parse_args()

    # Запуск сервера
    main(args.directory, args.server_IP, int(args.server_PORT))
