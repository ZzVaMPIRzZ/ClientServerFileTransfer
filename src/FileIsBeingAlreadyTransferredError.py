class FileIsBeingAlreadyTransferredError(Exception):
    """
    Исключение, возникающее при поптыке передать файл, когда файл с таким же названием уже передаётся от другого клиента
    """
    def __init__(self):
        super().__init__("File is being already transferred")
