from enum import Enum
import serial
from serial.tools.list_ports import comports

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
)


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


def decode_image(image_bytes: bytearray | bytes, dimension: tuple[int, int]) -> QImage:
    # Initialize an array for the decoded pixel data
    pixels = bytearray()

    for byte in image_bytes:
        # Extract the high and low nibbles and scale them
        high_nibble = (byte >> 4) & 0x0F
        low_nibble = byte & 0x0F

        # Scale the 4-bit values to 8-bit (0-255) values
        pixels.append(high_nibble * 17)  # 17 = 255 / 15
        pixels.append(low_nibble * 17)

    # Create a QImage from the pixel data
    return QImage(pixels, *dimension, QImage.Format.Format_Grayscale8)


def find_arduino_port():
    com_ports = comports()
    arduino_port = next(filter(lambda p: "Arduino" in p.description, com_ports), None)
    if arduino_port is None:
        raise ValueError("Arduino not found")
    return arduino_port


class AS608Thread(QThread):
    image_dimension = (256, 288)
    n_image_bytes = image_dimension[0] * image_dimension[1] // 2

    update_status = pyqtSignal(str)
    update_image = pyqtSignal(QPixmap)
    update_progress = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.ser = serial.Serial(find_arduino_port().device, 57600, timeout=1)

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

    def run(self):
        self.init_as608()

        while True:
            self.get_fingerprint_image()
            self.upload_fingerprint_image()

    def get_fingerprint_image(self):
        self.ser.write(Command.GetImage.value)
        self.update_status.emit("Capturing finger image.")

        while True:
            response = self.ser.read(1)
            if not response:
                continue

            response_state = DeviceState(response[0])
            if response_state == DeviceState.NoFingerDetected:
                continue

            if response_state == DeviceState.CommandSuccess:
                self.update_status.emit("Finger image captured.")
            else:
                self.update_status.emit("Failed to capture finger image.")
            break

    def upload_fingerprint_image(self):
        self.ser.write(Command.UpImage.value)
        self.update_status.emit("Downloading image.")
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
            self.update_progress.emit(int(len(image_bytes) / self.n_image_bytes * 100))

            state_bytes = self.ser.read(1)
            state = DeviceState(state_bytes[0])
            if state != DeviceState.DataEnd:
                self.update_status.emit("Failed to download image.")
                return

        if len(image_bytes) != self.n_image_bytes:
            self.update_status.emit("Failed to download image.")
            return

        image = decode_image(image_bytes, self.image_dimension)
        pixmap = QPixmap.fromImage(image)
        self.update_image.emit(pixmap)
        self.update_status.emit("Image downloaded.")
        image.save("fingerprint.bmp")


class AS608Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.start_fingerprint_thread()

    def initUI(self):
        self.label_status = QLabel("Status: Not connected", self)
        self.label_image = QLabel(self)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)

        layout = QVBoxLayout()
        layout.addWidget(self.label_status)
        layout.addWidget(self.label_image)
        layout.addWidget(self.progress_bar)

        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)

        self.setGeometry(300, 300, 350, 250)
        self.setWindowTitle("AS608 Fingerprint Sensor Controller")
        self.show()

    def start_fingerprint_thread(self):
        self.as608_thread = AS608Thread()
        self.as608_thread.update_status.connect(self.update_status)
        self.as608_thread.update_image.connect(self.update_image)
        self.as608_thread.update_progress.connect(self.update_progress)
        self.as608_thread.start()

    def update_status(self, status):
        self.label_status.setText(f"Status: {status}")

    def update_image(self, image):
        self.label_image.setPixmap(image)

    def update_progress(self, progress: int):
        self.progress_bar.setValue(progress)

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
