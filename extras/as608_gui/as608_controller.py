import time
from enum import Enum

import serial
from PIL import Image
from tqdm import tqdm


def decode_image(image_bytes: bytearray | bytes, dimension: tuple[int, int]):
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
    image = Image.frombytes("L", dimension, bytes(pixels))
    return image


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
    GetImage = 0x01
    UpImage = 0x0A
    WriteReg = 0x0E

    Acknowledgement = 0x30
    PrintDeviceParameters = 0x31

    def __str__(self):
        return self.name


class AS608Controller:
    def __init__(
        self,
        port_name: str = "/dev/ttyACM0",
        image_dimension: tuple[int, int] = (256, 288),
    ):
        print(f"Connecting to {port_name}...")
        self.ser = serial.Serial(port_name, 57600, timeout=1)
        self.image_dimension = image_dimension
        self.n_image_bytes = int(image_dimension[0] * image_dimension[1] / 2)

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

    def print_device_info(self):
        print("--- Device info ---")
        while self.ser.in_waiting < 7:
            time.sleep(0.1)
        for _ in range(7):
            line = self.ser.readline()
            print(line.decode("utf-8"), end="")
        print("-------------------")

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
        elif command == Command.PrintDeviceParameters:
            self.print_device_info()
        elif command == Command.WriteReg:
            reg_addr = int(input("Enter register address: "), 16).to_bytes(
                1, byteorder="big"
            )
            reg_value = int(input("Enter register value: "), 16).to_bytes(
                1, byteorder="big"
            )
            print(f"Register address: {reg_addr.hex()}")
            print(f"Register value: {reg_value.hex()}")
            self.ser.write(reg_addr)
            self.ser.write(reg_value)

            while self.ser.in_waiting < 1:
                time.sleep(0.1)

            state_byte = self.ser.read(1)
            state = DeviceState(state_byte[0])
            if state == DeviceState.CommandSuccess:
                print("Command success.")
            else:
                print(f"Command failed. State: {state}")

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
        pbar = tqdm(desc="Downloading fingerprint image", total=self.n_image_bytes)
        image_bytes = bytearray()
        while True:
            state_bytes = self.ser.read(1)
            if not state_bytes:
                continue

            state = DeviceState(state_bytes[0])
            if state != DeviceState.DataStart:
                if state == DeviceState.CommandSuccess:
                    print("Command success.")
                    break

                print(f"State is not DataStart. State: {state}")
                return

            length_bytes = self.ser.read(1)
            length = int.from_bytes(length_bytes, byteorder="big")
            while length > self.ser.in_waiting:
                ...

            data_bytes = self.ser.read(length)
            image_bytes.extend(data_bytes)
            pbar.update(length)

            state_bytes = self.ser.read(1)
            state = DeviceState(state_bytes[0])
            if state != DeviceState.DataEnd:
                print(f"State is not DataEnd. State: {state}")
                return

        if len(image_bytes) != self.n_image_bytes:
            print(f"Image is not 256 by 288. Length: {len(image_bytes)}")
            return

        image = decode_image(image_bytes, self.image_dimension)
        image.show()
