class MessageTypeError(Exception):
    """
    Исключение, возникающее при некорректном типе сообщения
    """
    def __init__(self, message):
        super().__init__(message)
