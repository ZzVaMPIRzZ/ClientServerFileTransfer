from enum import Enum


class Response(Enum):
    """
    Ответы сервера
    """
    SUCCESS = b'\x00'
    FILE_IS_BEING_ALREADY_TRANSFERRED = b'\x11'
    ERROR = b'\xff'
