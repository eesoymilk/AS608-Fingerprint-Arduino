from serial.tools.list_ports import comports

from as608_controller import AS608Controller


def find_arduino_port():
    com_ports = sorted(comports())
    arduino_port = next(
        filter(lambda port: "Arduino" in port.description, com_ports), None
    )

    if arduino_port is None:
        raise ValueError("Arduino not found")

    return arduino_port


def main():
    try:
        arduino_port = find_arduino_port()
        with AS608Controller(port_name=arduino_port.device) as controller:
            controller.run()
    except ValueError as e:
        print(e)


if __name__ == "__main__":
    main()
