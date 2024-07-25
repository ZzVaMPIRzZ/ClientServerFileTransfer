from enum import Enum


class MessageType(Enum):
    """
    Типы сообщений (все длиной 6 байт)
    """
    START = b'START\x00'
    END = b'END\x00\x00\x00'
    DATA = b'DATA\x00\x00'
    CANCEL = b'CANCEL'


class Result(Enum):
    """
    Результаты обработки файла
    """
    SUCCESS = 0
    ERROR = 1
    CANCEL = 2


class Response(Enum):
    """
    Ответы сервера
    """
    SUCCESS = b'\x00'
    FILE_IS_BEING_ALREADY_TRANSFERRED = b'\x11'
    ERROR = b'\xff'
