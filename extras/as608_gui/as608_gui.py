from enum import Enum
from typing import Optional
from pathlib import Path

import cv2
import serial

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QStatusBar,
    QProgressBar,
    QLabel,
    QPushButton,
    QLineEdit,
)

from fingerprint_matcher import Fingerprint, match_minutiae
from utils import decode_image, to_pixmap, find_arduino_port

script_dir = Path(__file__).parent.resolve()
db_dir = script_dir / "db"
db_dir.mkdir(exist_ok=True)


class DeviceState(Enum):
    Initialization = 0x00
    InitializationComplete = 0x01
    InitializationFailed = 0x02
    CommandSuccess = 0x03
    CommandFailed = 0x04
    CommandTimeout = 0x05
    NoFingerDetected = 0x06
    DataStart = 0x07
    DataEnd = 0x08
    Idle = 0x69

    def __str__(self):
        return self.name


class Command(Enum):
    GetImage = b"\x01"
    UpImage = b"\x0A"
    WriteReg = b"\x0E"

    Acknowledgement = b"\x30"
    PrintDeviceParameters = b"\x32"

    def __str__(self):
        return self.name


class AS608Thread(QThread):
    image_dimension = (256, 288)
    n_image_bytes = image_dimension[0] * image_dimension[1] // 2

    update_status = pyqtSignal(str)
    update_message = pyqtSignal(str)
    update_fp_grid = pyqtSignal(Fingerprint, int)
    update_pbar_value = pyqtSignal(int)
    update_pbar_range = pyqtSignal(int, int)
    update_pbar_format = pyqtSignal(str)

    toggle_name_input = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.ser = serial.Serial(find_arduino_port().device, 57600, timeout=1)
        self.current_fp: Optional[Fingerprint] = None
        self.initialized = False

    def init_as608(self):
        while True:
            state_byte = self.ser.read(1)
            if not state_byte:
                continue

            state = DeviceState(state_byte[0])
            if state == DeviceState.Initialization:
                self.update_status.emit("Initializing")
            elif state == DeviceState.InitializationComplete:
                self.update_status.emit("Initialization complete.")
                break
            elif state == DeviceState.InitializationFailed:
                raise Exception("Initialization failed.")

        self.initialized = True

    def run(self):
        if not self.initialized:
            self.init_as608()

        self.update_pbar_range.emit(0, 0)
        self.update_pbar_format.emit("")
        self.get_fingerprint_image()

        self.update_pbar_range.emit(0, self.n_image_bytes)
        self.update_pbar_format.emit("%v/%m")
        self.update_pbar_value.emit(0)

        self.upload_fingerprint_image()

        self.update_pbar_range.emit(0, 0)
        self.update_pbar_format.emit("")

        self.match_fingerprint()

        self.update_pbar_range.emit(0, 1)
        self.update_pbar_value.emit(1)

    def get_fingerprint_image(self):
        self.ser.write(Command.GetImage.value)
        self.update_message.emit("Place your finger on the sensor")
        self.update_status.emit("Capturing finger image")

        try:
            while True:
                response = self.ser.read(1)
                if not response:
                    continue

                response_state = DeviceState(response[0])
                if response_state == DeviceState.NoFingerDetected:
                    continue

                if response_state != DeviceState.CommandSuccess:
                    raise ValueError("Command failed")

                self.update_message.emit("Finger image successfully captured")
                self.update_status.emit("Finger image captured")
                break
        except ValueError as e:
            self.update_message.emit(
                f"Failed to capture finger image. Please try again. ({e})"
            )
            self.update_status.emit("Failed to capture finger image")

    def upload_fingerprint_image(self):
        self.ser.write(Command.UpImage.value)
        self.update_message.emit(
            "Downloading image from sensor. Please wait..."
        )
        self.update_status.emit("Downloading image")
        self.update_pbar_value.emit(0)
        image_bytes = bytearray()

        try:
            while True:
                state_bytes = self.ser.read(1)
                if not state_bytes:
                    continue

                state = DeviceState(state_bytes[0])
                if state != DeviceState.DataStart:
                    if state != DeviceState.CommandSuccess:
                        raise ValueError("Data transfer error")

                    self.update_message.emit("Image downloaded successfully.")
                    self.update_status.emit("Download complete.")
                    break

                length_bytes = self.ser.read(1)
                length = int.from_bytes(length_bytes, byteorder="big")
                while length > self.ser.in_waiting:
                    pass

                data_bytes = self.ser.read(length)
                image_bytes.extend(data_bytes)
                self.update_pbar_value.emit(len(image_bytes))

                state_bytes = self.ser.read(1)
                state = DeviceState(state_bytes[0])
                if state != DeviceState.DataEnd:
                    raise ValueError("Data transfer error")

            if len(image_bytes) != self.n_image_bytes:
                raise ValueError("Image size mismatch")

            image = decode_image(image_bytes, self.image_dimension)
            self.current_fp = Fingerprint(image)
            self.update_fp_grid.emit(self.current_fp, 0)
            self.update_status.emit("Image downloaded")

        except ValueError as e:
            self.update_message.emit(
                f"Failed to download image. Please try again. ({e})"
            )
            self.update_status.emit("Failed to download image")

    def match_fingerprint(self):
        best_n_matches = 12
        best_match_fp = None

        for fp_path in db_dir.glob("*/original.bmp"):
            fp = Fingerprint(cv2.imread(str(fp_path), cv2.IMREAD_GRAYSCALE))
            self.update_fp_grid.emit(fp, 1)
            n_matches = match_minutiae(fp.minutiae, self.current_fp.minutiae)
            print(f"{fp_path.parent.name}: {n_matches} matches")

            if n_matches >= best_n_matches:
                best_match_fp = fp
                best_n_matches = n_matches

        if best_match_fp is not None:
            self.update_status.emit("Fingerprint matched")
            self.update_message.emit(f"Hello, {fp_path.parent.name}!")
        else:
            self.update_status.emit("Fingerprint not matched")
            self.update_message.emit(
                "Hello, stranger! Do you want to register your fingerprint?"
            )
            self.toggle_name_input.emit(True)


class AS608Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_fp: Optional[Fingerprint] = None

        self.setWindowTitle("AS608 Fingerprint Sensor GUI")

        self.as608_thread = AS608Thread()

        self.init_ui()
        self.init_fingerprint_thread()
        self.show()

        self.as608_thread.start()

    def init_ui(self):
        self.central_widget = QWidget(self)
        self.central_layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.setup_fp_grid()

        self.pbar = QProgressBar(self.central_widget)

        self.message_label = QLabel(self.central_widget)
        self.message_label.setFont(QFont("Syetem", 14))
        self.message_label.setText(
            "Hello, welcome to the AS608 Fingerprint Sensor GUI!"
        )

        self.init_inputs()

        # Status bar
        self.status_bar = QStatusBar(self)
        self.status_bar.setFont(QFont("System", 10))
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Status: Not connected")

        # Add widgets to the central layout
        self.central_layout.addLayout(self.fp_grid)
        self.central_layout.addWidget(self.pbar)
        self.central_layout.addWidget(self.message_label)
        self.central_layout.addLayout(self.input_layout)

    def setup_fp_grid(self) -> None:
        self.fp_grid = QGridLayout()
        self.fp_labels: list[list[QLabel], list[QLabel]] = [[], []]
        for i in range(2):
            for j in range(4):
                label = QLabel(self.central_widget)
                label.setMinimumSize(256, 288)
                self.fp_labels[i].append(label)
                self.fp_grid.addWidget(label, i, j)

    def init_inputs(self):
        self.input_layout = QHBoxLayout()

        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(30)
        self.name_input.setFont(QFont("System", 14))
        self.name_input.setPlaceholderText("Enter your name here")
        self.name_input.returnPressed.connect(self.register_fingerprint)
        self.name_input.hide()
        self.input_layout.addWidget(self.name_input, stretch=1)

        self.btn = QPushButton("Restart")
        self.btn.setFixedSize(100, 30)
        self.btn.setFont(QFont("System", 14))
        self.btn.clicked.connect(self.restart)
        self.input_layout.addWidget(self.btn)

    def init_fingerprint_thread(self):
        self.as608_thread.update_status.connect(self.update_status)
        self.as608_thread.update_fp_grid.connect(self.update_fp_grid)
        self.as608_thread.toggle_name_input.connect(self.toggle_name_input)

        self.as608_thread.update_message.connect(self.message_label.setText)
        self.as608_thread.update_pbar_value.connect(self.pbar.setValue)
        self.as608_thread.update_pbar_range.connect(self.pbar.setRange)
        self.as608_thread.update_pbar_format.connect(self.pbar.setFormat)

    def update_status(self, status):
        self.status_bar.showMessage(f"Status: {status}")

    def update_fp_grid(self, fp: Fingerprint, row: int):
        if row not in (0, 1):
            raise ValueError("row exceeds grid size")
        if row == 0:
            self.current_fp = fp
        for i, img in enumerate(
            [
                fp.img,
                fp.enhanced_img,
                fp.skeleton_img,
                fp.result_img,
            ]
        ):
            self.fp_labels[row][i].setPixmap(to_pixmap(img))

    def toggle_name_input(self, show: bool):
        self.name_input.setVisible(show)

    def register_fingerprint(self):
        if self.current_fp is None:
            return

        name = self.name_input.text()
        if not name:
            return

        self.current_fp.save(db_dir, name)
        self.message_label.setText(
            f"Fingerprint successfully registered as \"{name}\"!"
        )
        self.name_input.clear()

    def restart(self):
        if self.as608_thread.isRunning():
            self.as608_thread.terminate()
            self.as608_thread.ser.close()
            self.as608_thread = AS608Thread()
            self.init_fingerprint_thread()
        self.name_input.hide()
        self.as608_thread.start()

    def closeEvent(self, a0):
        self.as608_thread.terminate()
        self.as608_thread.ser.close()
        print("serial port closed")
        super().closeEvent(a0)


def main():
    app = QApplication([])
    window = AS608Window()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
