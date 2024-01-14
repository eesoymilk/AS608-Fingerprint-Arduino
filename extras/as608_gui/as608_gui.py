import copy
from enum import Enum
from typing import Optional, Literal
from pathlib import Path

import serial
from serial.tools.list_ports import comports

import cv2
import numpy as np
from cv2.typing import MatLike
from numpy.typing import NDArray

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
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


def decode_image(
    image_bytes: bytearray | bytes, dimension: tuple[int, int]
) -> NDArray[np.uint8]:
    # Initialize an array for the decoded pixel data
    pixels = bytearray()

    for byte in image_bytes:
        # Extract the high and low nibbles and scale them
        high_nibble = (byte >> 4) & 0x0F
        low_nibble = byte & 0x0F

        # Scale the 4-bit values to 8-bit (0-255) values
        pixels.append(high_nibble * 17)  # 17 = 255 / 15
        pixels.append(low_nibble * 17)

    pixels_array = np.array(pixels, dtype=np.uint8)
    return np.reshape(pixels_array, (dimension[1], dimension[0]))

    # # Create a QImage from the pixel data
    # return QImage(pixels, *dimension, QImage.Format.Format_Grayscale8)


def to_pixmap(image: NDArray[np.uint8]) -> QPixmap:
    qimage = QImage(
        image,
        image.shape[1],
        image.shape[0],
        image.strides[0],
        QImage.Format.Format_BGR888
        if image.ndim == 3
        else QImage.Format.Format_Grayscale8,
    )
    return QPixmap.fromImage(qimage)


def find_arduino_port():
    com_ports = comports()
    arduino_port = next(
        filter(lambda p: "Arduino" in p.description, com_ports), None
    )
    if arduino_port is None:
        raise ValueError("Arduino not found")
    return arduino_port


class AS608Thread(QThread):
    image_dimension = (256, 288)
    n_image_bytes = image_dimension[0] * image_dimension[1] // 2

    update_status = pyqtSignal(str)
    update_message = pyqtSignal(str)
    update_fingerprint = pyqtSignal(Fingerprint, str)
    update_progress = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.ser = serial.Serial(find_arduino_port().device, 57600, timeout=1)
        self.current_fp: Optional[Fingerprint] = None
        self.initialized = False

    def init_as608(self):
        while True:
            state_byte = self.ser.read(1)
            if not state_byte:
                continue  # No data received, keep waiting

            state = DeviceState(state_byte[0])
            if state == DeviceState.Initialization:
                self.update_status.emit("Initializing...")
            elif state == DeviceState.InitializationComplete:
                self.update_status.emit("Initialization complete.")
                break
            elif state == DeviceState.InitializationFailed:
                raise Exception("Initialization failed.")

        self.initialized = True

    def run(self):
        if not self.initialized:
            self.init_as608()
        self.get_fingerprint_image()
        self.upload_fingerprint_image()
        self.match_fingerprint()

    def get_fingerprint_image(self):
        self.ser.write(Command.GetImage.value)
        self.update_status.emit("Capturing finger image")

        while True:
            response = self.ser.read(1)
            if not response:
                continue

            response_state = DeviceState(response[0])
            if response_state == DeviceState.NoFingerDetected:
                continue

            if response_state == DeviceState.CommandSuccess:
                self.update_status.emit("Finger image captured")
            else:
                self.update_status.emit("Failed to capture finger image")
            break

    def upload_fingerprint_image(self):
        self.ser.write(Command.UpImage.value)
        self.update_status.emit("Downloading image")
        self.update_progress.emit(0)
        image_bytes = bytearray()

        while True:
            state_bytes = self.ser.read(1)
            if not state_bytes:
                continue

            state = DeviceState(state_bytes[0])
            if state != DeviceState.DataStart:
                if state == DeviceState.CommandSuccess:
                    self.update_status.emit("Download complete.")
                    break

                self.update_status.emit("Failed to download image.")
                return

            length_bytes = self.ser.read(1)
            length = int.from_bytes(length_bytes, byteorder="big")
            while length > self.ser.in_waiting:
                pass

            data_bytes = self.ser.read(length)
            image_bytes.extend(data_bytes)
            self.update_progress.emit(
                int(len(image_bytes) / self.n_image_bytes * 100)
            )

            state_bytes = self.ser.read(1)
            state = DeviceState(state_bytes[0])
            if state != DeviceState.DataEnd:
                self.update_status.emit("Failed to download image.")
                return

        if len(image_bytes) != self.n_image_bytes:
            self.update_status.emit("Failed to download image")
            return

        image = decode_image(image_bytes, self.image_dimension)
        self.current_fp = Fingerprint(image)
        self.update_fingerprint.emit(self.current_fp, "top")
        self.update_status.emit("Image downloaded")

    def match_fingerprint(self):
        for fp_path in db_dir.glob("*.bmp"):
            fp = Fingerprint(cv2.imread(str(fp_path), cv2.IMREAD_GRAYSCALE))
            self.update_fingerprint.emit(fp, "bottom")
            n_matches = match_minutiae(self.current_fp.minutiae, fp.minutiae)
            print(f"{fp_path.name}: {n_matches} matches")
            if n_matches > 12:
                self.update_status.emit("Fingerprint matched")
                self.update_message.emit(f"Hello, {fp_path.stem}!")
                return

        self.update_status.emit("Fingerprint not matched")
        self.update_message.emit(
            "Hello, stranger! Do you want to register your fingerprint?"
        )


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

        self.fp_grid = QGridLayout()
        self.top_fp_raw_label = QLabel(self.central_widget)
        self.top_fp_raw_label.setMinimumSize(256, 288)
        self.top_fp_enhanced_label = QLabel(self.central_widget)
        self.top_fp_enhanced_label.setMinimumSize(256, 288)
        self.top_fp_skeleton_label = QLabel(self.central_widget)
        self.top_fp_skeleton_label.setMinimumSize(256, 288)
        self.top_fp_result_label = QLabel(self.central_widget)
        self.top_fp_result_label.setMinimumSize(256, 288)

        self.bottom_fp_raw_label = QLabel(self.central_widget)
        self.bottom_fp_raw_label.setMinimumSize(256, 288)
        self.bottom_fp_enhanced_label = QLabel(self.central_widget)
        self.bottom_fp_enhanced_label.setMinimumSize(256, 288)
        self.bottom_fp_skeleton_label = QLabel(self.central_widget)
        self.bottom_fp_skeleton_label.setMinimumSize(256, 288)
        self.bottom_fp_result_label = QLabel(self.central_widget)
        self.bottom_fp_result_label.setMinimumSize(256, 288)

        self.fp_grid.addWidget(self.top_fp_raw_label, 0, 0)
        self.fp_grid.addWidget(self.top_fp_enhanced_label, 0, 1)
        self.fp_grid.addWidget(self.top_fp_skeleton_label, 0, 2)
        self.fp_grid.addWidget(self.top_fp_result_label, 0, 3)
        self.fp_grid.addWidget(self.bottom_fp_raw_label, 1, 0)
        self.fp_grid.addWidget(self.bottom_fp_enhanced_label, 1, 1)
        self.fp_grid.addWidget(self.bottom_fp_skeleton_label, 1, 2)
        self.fp_grid.addWidget(self.bottom_fp_result_label, 1, 3)

        self.progress_bar = QProgressBar(self.central_widget)

        self.message_label = QLabel(self.central_widget)
        self.message_label.setText(
            "Hello, welcome to the AS608 Fingerprint Sensor GUI!"
        )

        self.name_input = QLineEdit(self.central_widget)
        self.name_input.setPlaceholderText("Enter your name here")
        self.name_input.returnPressed.connect(self.register_fingerprint)

        buttons_layout = QHBoxLayout()
        self.btn1 = QPushButton("Yes", self.central_widget)
        self.btn2 = QPushButton("No", self.central_widget)
        self.btn2.clicked.connect(self.restart)
        buttons_layout.addWidget(self.btn1)
        buttons_layout.addWidget(self.btn2)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Status: Not connected")

        # Add widgets to the central layout
        self.central_layout.addLayout(self.fp_grid)
        self.central_layout.addWidget(self.progress_bar)
        self.central_layout.addWidget(self.message_label)
        self.central_layout.addWidget(self.name_input)
        self.central_layout.addLayout(buttons_layout)

    def init_fingerprint_thread(self):
        self.as608_thread.update_status.connect(self.update_status)
        self.as608_thread.update_message.connect(self.message_label.setText)
        self.as608_thread.update_fingerprint.connect(self.update_fingerprint)
        self.as608_thread.update_progress.connect(self.update_progress)

    def update_status(self, status):
        self.status_bar.showMessage(f"Status: {status}")

    def update_fingerprint(self, fp: Fingerprint, side: str):
        if side == "top":
            self.current_fp = fp
            self.top_fp_raw_label.setPixmap(to_pixmap(fp.img))
            self.top_fp_enhanced_label.setPixmap(to_pixmap(fp.enhanced_img))
            self.top_fp_skeleton_label.setPixmap(to_pixmap(fp.skeleton_img))
            self.top_fp_result_label.setPixmap(to_pixmap(fp.result_img))
        elif side == "bottom":
            self.bottom_fp_raw_label.setPixmap(to_pixmap(fp.img))
            self.bottom_fp_enhanced_label.setPixmap(to_pixmap(fp.enhanced_img))
            self.bottom_fp_skeleton_label.setPixmap(to_pixmap(fp.skeleton_img))
            self.bottom_fp_result_label.setPixmap(to_pixmap(fp.result_img))
        else:
            raise ValueError("side must be either 'top' or 'bottom'")

    def update_progress(self, progress: int):
        self.progress_bar.setValue(progress)

    def register_fingerprint(self):
        if self.current_fp is None:
            return

        name = self.name_input.text()
        if not name:
            return

        cv2.imwrite(str(db_dir / f"{name}.bmp"), self.current_fp.img)
        self.message_label.setText(f"Hello, {name}!")
        self.name_input.clear()

    def restart(self):
        if self.as608_thread.isRunning():
            self.as608_thread.terminate()
            self.as608_thread.ser.close()
            self.as608_thread = AS608Thread()
            self.init_fingerprint_thread()
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
