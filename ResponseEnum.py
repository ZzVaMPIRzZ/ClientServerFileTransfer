from enum import Enum


class Response(Enum):
    SUCCESS = b'\x00'
    ERROR = b'\xff'
