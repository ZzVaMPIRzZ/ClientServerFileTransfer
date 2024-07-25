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
    if recreate or not os.path.exists("../log_file.csv"):
        try:
            with open("../log_file.csv", "w", newline="") as log_file:
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
    with open("../log_file.csv", "a", newline="") as log_file:
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
    clients_dict = {}
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
            for i in clients_dict:
                os.remove(clients_dict[i]["file"].name)
                clients_dict[i]["file"].close()
                epoll.unregister(i)
                i.close()
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
                        client_socket, client_address = connect_client(server_socket)
                        client_socket.setblocking(False)
                        clients_dict[client_socket] = dict().fromkeys(["address", "data_len", "message_type", "file"])
                        clients_dict[client_socket]["address"] = client_address
                        fd_to_socket[client_socket.fileno()] = client_socket
                        epoll.register(client_socket, select.EPOLLIN)
                        print(f"Connection from {client_address[0]}:{client_address[1]}")
                    else:
                        client_socket = s
                        client_address = clients_dict[client_socket]["address"]
                        try:
                            if clients_dict[client_socket]["data_len"] is not None:
                                # Принимаем данные (3-ий шаг)
                                data = client_socket.recv(clients_dict[client_socket]["data_len"])

                                if clients_dict[client_socket]["data_len"] - len(data) != 0:
                                    raise ConnectionError

                                # Обрабатываем данные (в 3-ем шаге)
                                if clients_dict[client_socket]["message_type"] == MessageType.START.value:
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
                                        del clients_dict[client_socket]
                                        client_socket.close()
                                        print(f"File {file_name} is being transferred right now. Skipping...")
                                    else:
                                        client_socket.send(Response.SUCCESS.value)
                                        clients_dict[client_socket]["file"] = open(file_name, "wb")
                                        file_names.append(file_name)
                                        print(f"Receiving file {file_name} ({file_size} bytes) ...")

                                elif clients_dict[client_socket]["message_type"] == MessageType.DATA.value:
                                    # Если получили данные
                                    if clients_dict[client_socket]["file"] is not None:
                                        client_socket.send(Response.SUCCESS.value)
                                        clients_dict[client_socket]["file"].write(data)
                                    else:
                                        client_socket.send(Response.ERROR.value)
                                        raise ConnectionError
                                else:
                                    # Во всех остальных случаях
                                    file_name = clients_dict[client_socket]["file"].name
                                    if clients_dict[client_socket]["message_type"] == MessageType.END.value:
                                        client_socket.send(Response.SUCCESS.value)
                                        update_log_file(file_name, Result.SUCCESS.name)
                                        print(f"Connection from {client_address[0]}:{client_address[1]} closed "
                                              f"successfully")
                                    elif clients_dict[client_socket]["message_type"] == MessageType.CANCEL.value:
                                        client_socket.send(Response.SUCCESS.value)
                                        update_log_file(file_name, Result.CANCEL.name)
                                        print(f"Connection from {client_address[0]}:{client_address[1]} canceled")
                                    else:
                                        client_socket.send(Response.ERROR.value)
                                        raise ConnectionError

                                    file_names.remove(clients_dict[client_socket]["file"].name)
                                    if clients_dict[client_socket]["message_type"] != MessageType.END.value:
                                        os.remove(clients_dict[client_socket]["file"].name)
                                    clients_dict[client_socket]["file"].close()
                                    epoll.unregister(client_socket)
                                    if client_socket in fd_to_socket:
                                        del fd_to_socket[client_socket]
                                    del clients_dict[client_socket]
                                    client_socket.close()

                                clients_dict[client_socket]["data_len"] = None
                                clients_dict[client_socket]["message_type"] = None

                            elif clients_dict[client_socket]["message_type"] is not None:
                                # Принимаем длину сообщения (2-ой шаг)
                                message = client_socket.recv(8)
                                if message is None:
                                    raise ConnectionError
                                clients_dict[client_socket]["data_len"] = int.from_bytes(message)
                                continue
                            else:
                                # Принимаем тип сообщения (1-ый шаг)
                                message = client_socket.recv(6)
                                if message is None:
                                    raise ConnectionError
                                clients_dict[client_socket]["message_type"] = message
                                continue
                        except ConnectionError:
                            update_log_file(clients_dict[client_socket]["file"].name, Result.ERROR.name)
                            epoll.unregister(client_socket)
                            if client_socket in fd_to_socket:
                                del fd_to_socket[client_socket]
                            del clients_dict[client_socket]
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
