from enum import Enum


class MessageType(Enum):
    START = b'START\x00'
    END = b'END\x00\x00\x00'
    DATA = b'DATA\x00\x00'
    CANCEL = b'CANCEL'
