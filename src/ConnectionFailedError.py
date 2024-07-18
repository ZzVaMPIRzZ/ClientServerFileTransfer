class ConnectionFailedError(ConnectionError):
    def __init__(self):
        super().__init__("Connection failed")
