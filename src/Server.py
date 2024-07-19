import signal
import socket
import os
import argparse
import csv
from datetime import datetime, timezone
from sys import exit

import select

from ResponseEnum import Response
from ResultEnum import Result
from TypeEnum import MessageType

CLOSE_SERVER = False


def create_log_file_if_not_exists(recreate=False):
    """
    Создает лог-файл, если он не существует.
    Args:
        recreate: bool, пересоздать лог-файл

    raise:
        OSError
    """
    if recreate or not os.path.exists("../Server/log_file.csv"):
        try:
            with open("../Server/log_file.csv", "w", newline="") as log_file:
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
    with open("../Server/log_file.csv", "a", newline="") as log_file:
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

    fd_to_socket = {server_socket.fileno(): server_socket}  # Словарь файловый дескриптор -> сокет клиента
    lens_of_data = {}  # Словарь сокет клиента -> длина данных
    message_types = {}  # Словарь сокет клиента -> тип сообщения
    files = {}  # Словарь сокет клиента -> файл
    addresses = {}  # Словарь сокет клиента -> IP-адрес и порт
    file_names = []  # Список имен файлов, которые передаются в данный момент

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
            epoll.close()
            for i in files:
                files[i].close()
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
                        client_socket, client_address = connect_client(server_socket)
                        addresses[client_socket] = client_address
                        client_socket.setblocking(False)
                        fd_to_socket[client_socket.fileno()] = client_socket
                        epoll.register(client_socket, select.EPOLLIN)
                        print(f"Connection from {client_address[0]}:{client_address[1]}")
                    else:
                        client_socket = s
                        client_address = addresses[client_socket]
                        try:
                            if client_socket in lens_of_data:
                                # Принимаем данные (3-ий шаг)
                                data = client_socket.recv(lens_of_data[client_socket])

                                if lens_of_data[client_socket] - len(data) != 0:
                                    raise ConnectionError

                                # Обрабатываем данные (в 3-ем шаге)
                                if message_types[client_socket] == MessageType.START.value:
                                    # Если получили имя файла (самый первый отправленный пакет с данными)
                                    file_name = data.decode().split('\t')[0]
                                    file_size = int(data.decode().split('\t')[1])

                                    # Если файл с таким именем в данный момент принимается от другого клиента,
                                    # то отклоняем принятие ещё одного файла с таким названием
                                    if file_name in file_names:
                                        client_socket.send(Response.FILE_IS_BEING_ALREADY_TRANSFERRED.value)
                                        epoll.unregister(client_socket)
                                        if client_socket in fd_to_socket:
                                            del fd_to_socket[client_socket]
                                        del addresses[client_socket]
                                        client_socket.close()
                                        print(f"File {file_name} is being transferred right now. Skipping...")
                                    else:
                                        client_socket.send(Response.SUCCESS.value)
                                        files[client_socket] = open(file_name, "wb")
                                        file_names.append(file_name)
                                        print(f"Receiving file {file_name} ({file_size} bytes) ...")

                                elif message_types[client_socket] == MessageType.DATA.value:
                                    # Если получили данные
                                    if client_socket in files:
                                        client_socket.send(Response.SUCCESS.value)
                                        files[client_socket].write(data)
                                    else:
                                        client_socket.send(Response.ERROR.value)
                                        raise ConnectionError
                                else:
                                    # Во всех остальных случаях
                                    if (message_types[client_socket] == MessageType.END.value or
                                            message_types[client_socket] == MessageType.CANCEL.value):
                                        client_socket.send(Response.SUCCESS.value)

                                    file_name = files[client_socket].name
                                    if message_types[client_socket] == MessageType.END.value:
                                        update_log_file(file_name, Result.SUCCESS.name)
                                        print(
                                            f"Connection from {client_address[0]}:{client_address[1]} closed "
                                            f"successfully")
                                    elif message_types[client_socket] == MessageType.CANCEL.value:
                                        update_log_file(file_name, Result.CANCEL.name)
                                        print(f"Connection from {client_address[0]}:{client_address[1]} canceled")
                                    else:
                                        update_log_file(file_name, Result.ERROR.name)
                                        print(
                                            f"Connection from {client_address[0]}:{client_address[1]} closed with"
                                            f" error")

                                    if client_socket in files:
                                        files[client_socket].close()
                                        if message_types[client_socket] != MessageType.END.value:
                                            os.remove(files[client_socket].name)
                                    file_names.remove(files[client_socket].name)
                                    del files[client_socket]
                                    epoll.unregister(client_socket)
                                    if client_socket in fd_to_socket:
                                        del fd_to_socket[client_socket]
                                    del addresses[client_socket]
                                    client_socket.close()

                                del lens_of_data[client_socket]
                                del message_types[client_socket]

                            elif client_socket in message_types:
                                # Принимаем длину сообщения (2-ой шаг)
                                message = client_socket.recv(8)
                                if message is None:
                                    raise ConnectionError
                                lens_of_data[client_socket] = int.from_bytes(message)
                                continue
                            else:
                                # Принимаем тип сообщения (1-ый шаг)
                                message = client_socket.recv(6)
                                if message is None:
                                    raise ConnectionError
                                message_types[client_socket] = message
                                continue
                        except ConnectionError:
                            epoll.unregister(client_socket)
                            if client_socket in fd_to_socket:
                                del fd_to_socket[client_socket]
                            if client_socket in addresses:
                                del addresses[client_socket]
                            if client_socket in files:
                                del files[client_socket]
                            if client_socket in lens_of_data:
                                del lens_of_data[client_socket]
                            if client_socket in message_types:
                                del message_types[client_socket]
                            client_socket.close()
                            print(f"Connection from {client_address[0]}:{client_address[1]} closed with error")
    finally:
        server_socket.close()


if __name__ == "__main__":
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser()
    parser.add_argument("-directory", default="data", help="Directory to store received files (default: ./data)")
    parser.add_argument("-server_IP", default="127.0.0.1", help="Server IP")
    parser.add_argument("-server_PORT", default=12345, help="Server port")
    args = parser.parse_args()

    # Запуск сервера
    main(args.directory, args.server_IP, args.server_PORT)
