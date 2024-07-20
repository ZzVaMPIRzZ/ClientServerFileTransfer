from enum import Enum


class Result(Enum):
    """
    Результаты обработки файла
    """
    SUCCESS = 0
    ERROR = 1
    CANCEL = 2
