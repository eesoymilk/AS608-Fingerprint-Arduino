import numpy as np
from numpy.typing import NDArray
from serial.tools.list_ports import comports

from PyQt6.QtGui import QImage, QPixmap


def decode_image(
    image_bytes: bytearray | bytes, dimension: tuple[int, int]
) -> NDArray[np.uint8]:
    pixels = bytearray()
    for byte in image_bytes:
        # Extract the high and low nibbles and scale them
        high_nibble = (byte >> 4) & 0x0F
        low_nibble = byte & 0x0F

        # Scale the 4-bit (0-16) values to 8-bit (0-255) values
        pixels.append(high_nibble * 17)  # 17 = 255 / 15
        pixels.append(low_nibble * 17)

    pixels_array = np.array(pixels, dtype=np.uint8)
    return np.reshape(pixels_array, (dimension[1], dimension[0]))


def to_pixmap(image: NDArray[np.uint8]) -> QPixmap:
    return QPixmap.fromImage(
        QImage(
            image,
            image.shape[1],
            image.shape[0],
            image.strides[0],
            QImage.Format.Format_BGR888
            if image.ndim == 3
            else QImage.Format.Format_Grayscale8,
        )
    )


def find_arduino_port():
    com_ports = comports()
    arduino_port = next(
        filter(lambda p: "Arduino" in p.description, com_ports), None
    )
    if arduino_port is None:
        raise ValueError("Arduino not found")
    return arduino_port
