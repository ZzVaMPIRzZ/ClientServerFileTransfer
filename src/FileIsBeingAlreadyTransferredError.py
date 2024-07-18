class FileIsBeingAlreadyTransferredError(Exception):
    def __init__(self):
        super().__init__("File is being already transferred")
