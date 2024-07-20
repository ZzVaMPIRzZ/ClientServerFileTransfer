class ConnectionFailedError(ConnectionError):
    """
    Исключение, возникающее при неудачной попытке подключения к серверу.
    """
    def __init__(self):
        super().__init__("Connection failed")
