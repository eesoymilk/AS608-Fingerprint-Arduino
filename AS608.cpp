#include "AS608.h"

namespace AS608 {

Packet::Packet(
    uint8_t type, uint16_t data_length, uint8_t *data, uint32_t address
)
    : address(address), type(type), length(data_length + 2)
{
    memcpy(this->data, data, data_length);
}

void Packet::read_start_code(SoftwareSerial &serial)
{
    while (true) {
        while (serial.available() < 2) {
            delay(1);
        }

        uint8_t high = serial.read();
        uint8_t low = serial.peek();

        if (high == highByte(StartCode) && low == lowByte(StartCode)) {
            serial.read();
            return;
        }
    }
}

void Packet::send(SoftwareSerial &serial)
{
    serial.write(static_cast<uint8_t>(StartCode >> 8));
    serial.write(static_cast<uint8_t>(StartCode & 0xFF));

    serial.write(static_cast<uint8_t>(address >> 24));
    serial.write(static_cast<uint8_t>(address >> 16));
    serial.write(static_cast<uint8_t>(address >> 8));
    serial.write(static_cast<uint8_t>(address));

    serial.write(type);
    serial.write(static_cast<uint8_t>(length >> 8));
    serial.write(static_cast<uint8_t>(length & 0xFF));

    checksum = (this->length >> 8) + (this->length & 0xFF) + this->type;

    for (size_t i = 0; i < length - 2; i++) {
        checksum += data[i];
        serial.write(data[i]);
    }

    serial.write(static_cast<uint8_t>(checksum >> 8));
    serial.write(static_cast<uint8_t>(checksum & 0xFF));
}

Packet Packet::read_from(SoftwareSerial &serial)
{
    read_start_code(serial);

    while (serial.available() < 7) {
        delay(1);
    }

    uint8_t type, *data;
    uint16_t length;

    uint32_t address = serial.read() << 24;
    address |= serial.read() << 16;
    address |= serial.read() << 8;
    address |= serial.read();

    type = serial.read();

    length = serial.read() << 8;
    length |= serial.read();

    while (serial.available() < length) {
        delay(1);
    }

    data = new uint8_t[length - 2];

    for (size_t i = 0; i < length - 2; i++) {
        data[i] = serial.read();
    }

    uint16_t checksum = serial.read() << 8;
    checksum |= serial.read();

    Packet packet = Packet(type, length - 2, data, address);

    delete[] data;

    return packet;
}

String Packet::to_string() const
{
    String result;

    result += " - Start Code: 0x" + String(StartCode, HEX) + "\n";
    result += " - Address: 0x" + String(address, HEX) + "\n";
    result += " - Type: 0x" + String(type, HEX) + "\n";
    result += " - Length: " + String(length) + "\n";

    result += " - Data: ";
    for (int i = 0; i < length - 2; ++i) {
        if (data[i] < 0x10) result += '0';  // Leading zero for single digit hex
        result += String(data[i], HEX) + " ";
    }
    result += "\n";

    result += " - Checksum: 0x" + String(checksum, HEX) + "\n";

    return result;
}

FingerprintModule::FingerprintModule(SoftwareSerial *serial, uint32_t password)
    : password(password), serial(serial)
{
}

void FingerprintModule::begin(uint32_t baudrate)
{
    delay(1000);
    serial->begin(baudrate);
}

Packet FingerprintModule::send_command(uint8_t *data, uint16_t length)
{
    Packet packet = Packet(PacketType::CommandPacket, length, data);

    packet.send(*serial);

    return Packet::read_from(*serial);
}

Packet FingerprintModule::read_packet()
{
    return Packet::read_from(*serial);
}

bool FingerprintModule::verify_password()
{
    uint8_t data[5] = {
        CommandCode::VfyPwd,
        (uint8_t)((password >> 24) & 0xFF),
        (uint8_t)((password >> 16) & 0xFF),
        (uint8_t)((password >> 8) & 0xFF),
        (uint8_t)(password & 0xFF)
    };

    Packet response = send_command(data, sizeof(data));

    return response.type == PacketType::AcknowledgePacket &&
           response.data[0] == ConfirmationCode::OK;
}

ConfirmationCode FingerprintModule::read_parameters()
{
    uint8_t data[1] = {CommandCode::ReadSysPara};

    Packet response = send_command(data, sizeof(data));

    if (response.type != PacketType::AcknowledgePacket ||
        response.length != 19) {
        return ConfirmationCode::BadPacket;
    }

    if (response.data[0] != ConfirmationCode::OK) {
        return static_cast<ConfirmationCode>(response.data[0]);
    }

    status_register = (response.data[1] << 8) | response.data[2];
    sensor_type = (response.data[3] << 8) | response.data[4];
    capacity = (response.data[5] << 8) | response.data[6];
    security_level = (response.data[7] << 8) | response.data[8];

    device_address = (response.data[9] << 24) | (response.data[10] << 16) |
                     (response.data[11] << 8) | response.data[12];

    data_packet_length = 32 << ((response.data[13] << 8) | response.data[14]);

    baudrate = ((response.data[15] << 8) | response.data[16]) * 9600;

    return static_cast<ConfirmationCode>(response.data[0]);
}

ConfirmationCode FingerprintModule::get_image()
{
    uint8_t data[] = {CommandCode::GetImage};

    Packet response = send_command(data, sizeof(data));

    return static_cast<ConfirmationCode>(response.data[0]);
}

ConfirmationCode FingerprintModule::up_image()
{
    uint8_t data[] = {CommandCode::UpImage};

    Packet response = send_command(data, sizeof(data));

    if (response.type != PacketType::AcknowledgePacket) {
        return ConfirmationCode::BadPacket;
    }

    return static_cast<ConfirmationCode>(response.data[0]);
}

String FingerprintModule::to_string() const
{
    String result;

    result += "Status Register: 0x" + String(status_register, HEX) + "\n";
    result += "Sensor Type: 0x" + String(sensor_type, HEX) + "\n";
    result += "Capacity: 0x" + String(capacity, HEX) + "\n";
    result += "Security Level: 0x" + String(security_level, HEX) + "\n";
    result += "Device Address: 0x" + String(device_address, HEX) + "\n";
    result += "Data Packet Length: " + String(data_packet_length) + "\n";
    result += "Baudrate: " + String(baudrate) + "\n";

    return result;
}

}  // namespace AS608
