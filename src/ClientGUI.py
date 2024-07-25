import os
import sys

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, \
    QFileDialog, QSpinBox, QProgressDialog, QMessageBox
from PyQt5.QtCore import Qt

from Errors import ConnectionFailedError, FileIsBeingAlreadyTransferredError
from Enums import MessageType
from Client import connect_to_server, send_file, send_message


class ClientForm(QWidget):
    def __init__(self):
        super().__init__()

        self.send_button = None             # кнопка "Отправить"
        self.progress_dialog = None         # диалоговое окно прогресса
        self.buffer_spinbox = None          # поле для ввода размера буфера
        self.buffer_label = None            # метка "Размер буфера"
        self.file_button = None             # кнопка выбора файла
        self.file_textbox = None            # поле для ввода пути к файлу
        self.file_label = None              # метка "Путь к файлу"
        self.server_port_spinbox = None     # поле для ввода порта сервера
        self.server_IP_textbox = None       # поле для ввода IP-адреса сервера
        self.server_port_label = None       # метка "Порт сервера"
        self.server_IP_label = None         # метка "IP сервера"
        self.client_IP_label = None         # метка "IP клиента"
        self.client_port_label = None       # метка "Порт клиента"
        self.message_dialog = None          # диалоговое окно сообщения

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        server_IP_and_port_layout = QHBoxLayout()
        self.server_IP_label = QLabel('IP сервера:')
        self.server_IP_textbox = QLineEdit(self)
        self.server_port_label = QLabel('Порт сервера:')
        self.server_IP_textbox.setText('127.0.0.1')
        self.server_port_spinbox = QSpinBox(self)
        self.server_port_spinbox.setRange(1, 65535)
        self.server_port_spinbox.setValue(12345)
        self.server_port_spinbox.setFixedWidth(70)
        self.buffer_label = QLabel('Буфер:')
        self.buffer_spinbox = QSpinBox(self)
        self.buffer_spinbox.setFixedWidth(70)
        self.buffer_spinbox.setRange(1, 32768)
        self.buffer_spinbox.setValue(1024)
        server_IP_and_port_layout.addWidget(self.server_IP_label)
        server_IP_and_port_layout.addWidget(self.server_IP_textbox)
        server_IP_and_port_layout.addWidget(self.server_port_label)
        server_IP_and_port_layout.addWidget(self.server_port_spinbox)
        server_IP_and_port_layout.addWidget(self.buffer_label)
        server_IP_and_port_layout.addWidget(self.buffer_spinbox)
        main_layout.addLayout(server_IP_and_port_layout)

        dialog_layout = QHBoxLayout()
        self.file_label = QLabel('Файл:')
        self.file_textbox = QLineEdit(self)
        self.file_button = QPushButton('Выбрать', self)
        self.file_button.clicked.connect(self.__open_file_dialog)
        dialog_layout.addWidget(self.file_label)
        dialog_layout.addWidget(self.file_textbox)
        dialog_layout.addWidget(self.file_button)
        main_layout.addLayout(dialog_layout)

        self.send_button = QPushButton('Отправить', self)
        self.send_button.clicked.connect(self.__send)
        main_layout.addWidget(self.send_button)

        self.setLayout(main_layout)

        self.setWindowTitle('ClientServer')
        self.setGeometry(400, 400, 600, 160)
        self.setMaximumSize(600, 160)
        self.setMinimumSize(600, 160)

    def __show_message(self, icon, title, message):
        """
        Показывает диалоговое окно с сообщением
        Args:
            icon: QMessageBox.Icon, тип иконки
            title: str, заголовок
            message: str, сообщение
        """
        self.message_dialog = QMessageBox(self)
        self.message_dialog.setIcon(icon)
        self.message_dialog.setWindowTitle(title)
        self.message_dialog.setText(message)
        self.message_dialog.setStandardButtons(QMessageBox.Ok)
        self.message_dialog.exec_()

    def __show_progress(self, file_path):
        """
        Показывает диалоговое окно с прогрессом
        Args:
            file_path: str, путь к файлу
        """
        self.progress_dialog = QProgressDialog(
            f"Отправляем {os.path.basename(file_path)}",
            "Отмена", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setWindowTitle('Прогресс')
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

    def __update_progress(self, file_path, sent_data_len):
        """
        Обновляет прогресс
        Args:
            file_path: str, путь к файлу
            sent_data_len: int, количество отправленных байт
        """
        self.progress_dialog.setValue(int(100 * sent_data_len / os.path.getsize(file_path)))

    def __send(self):
        """
        Отправляет файл на сервер
        """
        file_path = self.file_textbox.text()
        server_IP = self.server_IP_textbox.text()
        server_port = self.server_port_spinbox.value()
        buffer_size = self.buffer_spinbox.value()
        if os.path.exists(file_path) is False:
            self.__show_message(QMessageBox.Critical, "Ошибка", f"Файл {file_path} не найден")
            return
        try:
            client_socket = connect_to_server(server_IP, server_port)
        except ConnectionFailedError:
            self.__show_message(QMessageBox.Critical, "Ошибка", "Сервер недоступен")
            return

        sent_data_len = 0
        try:
            self.__show_progress(file_path)
            for data_len in send_file(file_path, client_socket, buffer_size):
                sent_data_len += data_len
                self.__update_progress(file_path, sent_data_len)
                if self.progress_dialog.wasCanceled():
                    send_message(client_socket, MessageType.CANCEL, b'\x00')
                    self.__show_message(QMessageBox.Critical, "Отмена", "Отменено пользователем")
                    return
            self.progress_dialog.setValue(100)
            self.progress_dialog.close()
            self.__show_message(QMessageBox.Information, "Успех", "Файл успешно отправлен")
        except FileIsBeingAlreadyTransferredError:
            self.progress_dialog.close()
            self.__show_message(QMessageBox.Critical, "Ошибка", "Файл уже отправляется от другого клиента")
            return
        except ConnectionError:
            self.progress_dialog.close()
            self.__show_message(QMessageBox.Critical, "Ошибка", "Сервер недоступен")
            return
        finally:
            client_socket.close()

    def __open_file_dialog(self):
        """
        Открывает окно для выбора файла
        """
        # options = QFileDialog.Options()
        # options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", "Все файлы (*)")
        if file_name:
            # Обновление текстового поля введенным путем
            self.file_textbox.setText(file_name)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    form = ClientForm()
    form.show()
    sys.exit(app.exec_())
