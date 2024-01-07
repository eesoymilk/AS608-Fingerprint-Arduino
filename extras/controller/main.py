import serial
import time
from enum import Enum
from PIL import Image


class DeviceState(Enum):
    Initialization = 0x00
    InitializationComplete = 0x01
    InitializationFailed = 0x02
    CommandSuccess = 0x03
    CommandFailed = 0x04
    NoFingerDetected = 0x05
    DataStart = 0x07
    DataEnd = 0x08
    Idle = 0x69

    def __str__(self):
        return self.name


class Command(Enum):
    GetImage = 0x01
    UpImage = 0x0A

    Acknowledgement = 0x30

    def __str__(self):
        return self.name


def decode_image(image_bytes: bytearray | bytes, width: int, height: int):
    # Initialize an array for the decoded pixel data
    pixels = bytearray()

    for byte in image_bytes:
        # Extract the high and low nibbles and scale them
        high_nibble = (byte >> 4) & 0x0F
        low_nibble = byte & 0x0F

        # Scale the 4-bit values to 8-bit (0-255) values
        pixels.append(high_nibble * 17)  # 17 = 255 / 15
        pixels.append(low_nibble * 17)

    # Create an image from the pixel data
    image = Image.frombytes("L", (width, height), bytes(pixels))
    return image


class AS608Controller:
    def __init__(self, port_name: str = "/dev/ttyACM1"):
        self.ser = serial.Serial(port_name, 57600, timeout=1)

        while True:
            state_byte = self.ser.read(1)
            if not state_byte:
                continue  # No data received, keep waiting

            state = DeviceState(state_byte[0])
            if state == DeviceState.Initialization:
                print("Initializing...")
            elif state == DeviceState.InitializationComplete:
                print("Initialization complete.")
                break
            elif state == DeviceState.InitializationFailed:
                raise Exception("Initialization failed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.ser.close()

    def run(self):
        while True:
            command_str = input("Enter command: ")
            if command_str == "q":
                break
            self.process_command(command_str)

    def process_command(self, command_str: str):
        command_bytes = int(command_str, 16).to_bytes(1, byteorder="big")
        print(f"Sending command: {command_bytes.hex()}")

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(command_bytes)

        command = Command(command_bytes[0])
        if command == Command.GetImage:
            self.get_fingerprint_image()
        elif command == Command.UpImage:
            self.upload_fingerprint_image()
        else:
            raise Exception(f"Unknown command: {command}")

    def get_fingerprint_image(self):
        while True:
            response = self.ser.read(1)

            if not response:
                continue

            response_state = DeviceState(response[0])

            if response_state == DeviceState.NoFingerDetected:
                print("Please place your finger on the sensor.")
                continue

            if response_state == DeviceState.CommandSuccess:
                print("Finger image captured.")
            else:
                print("Failed to capture finger image.")

            break

    def upload_fingerprint_image(self):
        response = self.ser.read(1)

        if not response:
            raise Exception("No response received.")

        response_state = DeviceState(response[0])

        if response_state != DeviceState.DataStart:
            raise Exception(f"Unexpected response: {response_state}")

        # while True:
        #     response = self.ser.readline()
        #     print(f"Response: {response.decode('utf-8')}")

        image_bytes = bytearray()
        while True:
            while self.ser.in_waiting == 0:
                print("Waiting for data...")
                time.sleep(0.5)

            bytes_read = self.ser.read(1)
            print(f"First read: {bytes_read.hex()}")

            try:
                current_state = DeviceState(bytes_read[0])
                print(f"Current state: {current_state}")
                if current_state == DeviceState.DataEnd:
                    break
            except ValueError:
                pass

            length = int.from_bytes(bytes_read, byteorder="big")
            while length > self.ser.in_waiting:
                time.sleep(0.2)

            bytes_read = self.ser.read(length)
            print(f"Read: {bytes_read.hex()}")
            image_bytes.extend(bytes_read)

            ack_bytes = 0x30.to_bytes(1, byteorder="big")
            self.ser.write(ack_bytes)
            self.ser.reset_input_buffer()

        print(f"Image size: {len(image_bytes)} bytes")
        image = decode_image(image_bytes, 256, 256)
        image.show()


def main():
    with AS608Controller() as controller:
        controller.run()


if __name__ == "__main__":
    main()
