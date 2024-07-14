import os
import sys

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, \
    QFileDialog, QSpinBox, QProgressDialog, QMessageBox
from PyQt5.QtCore import Qt

from ConnectionFailedError import ConnectionFailedError
from TypeEnum import MessageType
from client import connect_to_server, send_file, send_message


class ClientForm(QWidget):
    def __init__(self):
        super().__init__()

        self.send_button = None
        self.progress_dialog = None
        self.buffer_spinbox = None
        self.buffer_label = None
        self.file_button = None
        self.file_textbox = None
        self.file_label = None
        self.server_port_spinbox = None
        self.server_IP_textbox = None
        self.server_port_label = None
        self.server_IP_label = None
        self.client_IP_label = None
        self.client_port_label = None
        self.error_dialog = None

        self.init_ui()

    def init_ui(self):
        # Создание вертикального макета
        main_layout = QVBoxLayout()

        # IP = '127.0.0.1'
        # port = '12345'
        #
        # client_IP_and_port_layout = QHBoxLayout()
        # self.client_IP_label = QLabel(f'Ваш IP: {IP}')
        # self.client_port_label = QLabel(f'Ваш порт: {port}')
        # client_IP_and_port_layout.addWidget(self.client_IP_label)
        # client_IP_and_port_layout.addWidget(self.client_port_label)
        # main_layout.addLayout(client_IP_and_port_layout)

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
        self.buffer_spinbox.setFixedWidth(60)
        self.buffer_spinbox.setRange(1, 65535)
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

        # Создание кнопки
        self.send_button = QPushButton('Отправить', self)
        self.send_button.clicked.connect(self.__send)
        main_layout.addWidget(self.send_button)

        # Установка макета
        self.setLayout(main_layout)

        # Настройки основного окна
        self.setWindowTitle('ClientServer')
        self.setGeometry(400, 400, 500, 160)
        self.setMaximumSize(500, 160)
        self.setMinimumSize(500, 160)

    def __send(self):
        try:
            client_socket = connect_to_server(self.server_IP_textbox.text(), self.server_port_spinbox.value())
        except ConnectionFailedError as e:
            self.error_dialog = QMessageBox()
            self.error_dialog.setIcon(QMessageBox.Critical)
            self.error_dialog.setWindowTitle("Ошибка")
            self.error_dialog.setText("Сервер недоступен")
            self.error_dialog.setStandardButtons(QMessageBox.Ok)
            self.error_dialog.exec_()
            return
        self.progress_dialog = QProgressDialog(
            f"Отправляем {self.file_textbox.text()}",
            "Отмена", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setWindowTitle('Прогресс')
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

        try:
            sent_data = 0
            for client_socket, data_len in send_file(self.file_textbox.text(),
                                                     client_socket,
                                                     self.server_IP_textbox.text(),
                                                     self.server_port_spinbox.value(),
                                                     self.buffer_spinbox.value()):
                sent_data += data_len
                self.progress_dialog.setValue(int(100 * sent_data / os.path.getsize(self.file_textbox.text())))
                if self.progress_dialog.wasCanceled():
                    send_message(client_socket, MessageType.CANCEL, b'')
                    self.cancel_dialog = QMessageBox()
                    self.cancel_dialog.setIcon(QMessageBox.Warning)
                    self.cancel_dialog.setWindowTitle("Отмена")
                    self.cancel_dialog.setText("Отменено пользователем")
                    self.cancel_dialog.setStandardButtons(QMessageBox.Ok)
                    self.cancel_dialog.exec_()
                    return
            self.progress_dialog.setValue(100)
            self.progress_dialog.close()
            self.message_dialog = QMessageBox()
            self.message_dialog.setIcon(QMessageBox.Information)
            self.message_dialog.setWindowTitle("Успех")
            self.message_dialog.setText("Файл успешно отправлен!")
            self.message_dialog.setStandardButtons(QMessageBox.Ok)
            self.message_dialog.exec_()
        except ConnectionFailedError:
            self.progress_dialog.close()
            self.error_dialog = QMessageBox()
            self.error_dialog.setIcon(QMessageBox.Critical)
            self.error_dialog.setWindowTitle("Ошибка")
            self.error_dialog.setText("Сервер недоступен")
            self.error_dialog.setStandardButtons(QMessageBox.Ok)
            self.error_dialog.exec_()
            return
        finally:
            client_socket.close()

    def __open_file_dialog(self):
        # Открытие диалога выбора файла
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly  # Дополнительные опции, например, только для чтения
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", "Все файлы (*);;Текстовые файлы (*.txt)",
                                                   options=options)
        if file_name:
            # Обновление текстового поля введенным путем
            self.file_textbox.setText(file_name)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    form = ClientForm()
    form.show()
    sys.exit(app.exec_())
