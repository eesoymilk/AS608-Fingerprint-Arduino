#include "AS608Fingerprint.h"

#include "HardwareSerial.h"

namespace AS608 {

uint8_t read_byte(SoftwareSerial &serial)
{
    while (!serial.available()) {
        delay(1);
    }
    return serial.read();
}

Packet::Packet(
    uint8_t type, uint16_t data_length, uint8_t *data, uint32_t address
)
    : address(address), type(type), length(data_length + 2)
{
    memcpy(this->data, data, data_length);
}

Packet::Packet(SoftwareSerial &serial)
{
    uint32_t timeout;

    while (true) {
        timeout = millis() + 2000;
        while (serial.available() < 2) {
            if (millis() > timeout) {
                type = PacketType::PacketTimeout;
                return;
            }
            delay(1);
        }

        uint8_t high = serial.read();
        uint8_t low = serial.peek();

        if (high == highByte(StartCode) && low == lowByte(StartCode)) {
            serial.read();
            break;
        }
    }

    timeout = millis() + 7000;
    while (serial.available() < 7) {
        if (millis() > timeout) {
            type = PacketType::PacketTimeout;
            return;
        }
        delay(1);
    }

    address = serial.read() << 24;
    address |= serial.read() << 16;
    address |= serial.read() << 8;
    address |= serial.read();

    type = serial.read();

    length = serial.read() << 8;
    length |= serial.read();

    for (size_t i = 0; i < length - 2; i++) {
        timeout = millis() + 1000;
        while (serial.available() < 1) {
            if (millis() > timeout) {
                type = PacketType::PacketTimeout;
                return;
            }
            delay(1);
        }
        data[i] = serial.read();
    }

    timeout = millis() + 2000;
    while (serial.available() < 2) {
        if (millis() > timeout) {
            type = PacketType::PacketTimeout;
            return;
        }
        delay(1);
    }

    checksum = serial.read() << 8;
    checksum |= serial.read();
}

void Packet::read_start_code(SoftwareSerial &serial)
{
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

    // this->print();
}

void Packet::print() const
{
    Serial.println(F("----------------------"));
    Serial.print(F("| Start Code: 0x"));
    Serial.println(StartCode, HEX);
    Serial.print(F("| Address: 0x"));
    Serial.println(address, HEX);
    Serial.print(F("| Type: 0x"));
    Serial.println(type, HEX);
    Serial.print(F("| Length: "));
    Serial.println(length);

    Serial.print(F("| Data: "));
    for (int i = 0; i < length - 2; ++i) {
        if (data[i] < 0x10)
            Serial.print(F("0"));  // Leading zero for single digit hex
        Serial.print(data[i], HEX);
        Serial.print(F(" "));
    }
    Serial.println();

    Serial.print(F("| Checksum: 0x"));
    Serial.println(checksum, HEX);
    Serial.println(F("----------------------"));
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

    packet = Packet(*serial);

    // packet.print();

    return packet;
}

Packet FingerprintModule::read_packet()
{
    return Packet(*serial);
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

    Serial.write(response.type);

    return response.type == PacketType::AcknowledgePacket &&
           response.data[0] == ConfirmationCode::OK;
}

ConfirmationCode FingerprintModule::read_parameters()
{
    uint8_t data[1] = {CommandCode::ReadSysPara};

    Packet response = send_command(data, sizeof(data));

    if (response.type != PacketType::AcknowledgePacket ||
        response.length != 19) {
        return ConfirmationCode::PacketReceiveError;
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
        return ConfirmationCode::PacketReceiveError;
    }

    return static_cast<ConfirmationCode>(response.data[0]);
}

ConfirmationCode FingerprintModule::write_reg(
    uint8_t reg_address, uint8_t reg_value
)
{
    uint8_t data[] = {CommandCode::WriteReg, reg_address, reg_value};

    Packet response = send_command(data, sizeof(data));

    if (response.type != PacketType::AcknowledgePacket) {
        return ConfirmationCode::PacketReceiveError;
    }

    return static_cast<ConfirmationCode>(response.data[0]);
}

void FingerprintModule::print() const
{
    Serial.print(F("Status Register: 0x"));
    Serial.println(status_register, HEX);
    Serial.print(F("Sensor Type: 0x"));
    Serial.println(sensor_type, HEX);
    Serial.print(F("Capacity: 0x"));
    Serial.println(capacity, HEX);
    Serial.print(F("Security Level: "));
    Serial.println(security_level);
    Serial.print(F("Device Address: 0x"));
    Serial.println(device_address, HEX);
    Serial.print(F("Data Packet Length: "));
    Serial.println(data_packet_length);
    Serial.print(F("Baudrate: "));
    Serial.println(baudrate);
}

}  // namespace AS608
