#include "AS608Fingerprint.h"
#include "Controller.h"

using namespace AS608;
using namespace Controller;

SoftwareSerial fingerprint_serial = SoftwareSerial(2, 3);
FingerprintModule finger = FingerprintModule(&fingerprint_serial);
ConfirmationCode buffer_code;
uint8_t buffer_byte[3];

void setup()
{
    Serial.begin(57600);
    while (!Serial)
        ;
    delay(100);
    Serial.write(DeviceState::Initialization);

    finger.begin(57600);

    if (!finger.verify_password()) {
        while (1) {
            Serial.write(DeviceState::InitializationFailed);
            delay(1);
        }
    }

    Serial.write(DeviceState::InitializationComplete);
}

void loop()  // run over and over again
{
    // Serial.write(DeviceState::Idle);

    if (!Serial.available()) {
        delay(100);
        return;
    }

    buffer_byte[0] = Serial.read();

    switch (buffer_byte[0]) {
        case CommandCode::GetImage:
            try_to_get_image();
            break;
        case CommandCode::UpImage:
            upload_image();
            break;
        case CommandCode::PrintDeviceParameters:
            finger.read_parameters();
            finger.print();
            Serial.write(DeviceState::CommandSuccess);
            break;
        case CommandCode::WriteReg:
            write_reg();
            break;

        default:
            Serial.write(DeviceState::CommandFailed);
            break;
    }
}

void try_to_get_image()
{
    while (true) {
        buffer_code = finger.get_image();

        if (buffer_code == ConfirmationCode::NoFingerDetected) {
            Serial.write(DeviceState::NoFingerDetected);
            continue;
        }

        Serial.write(
            buffer_code == ConfirmationCode::OK ? DeviceState::CommandSuccess
                                                : DeviceState::CommandFailed
        );
        break;
    }
}

void upload_image()
{
    buffer_code = finger.up_image();

    if (buffer_code != ConfirmationCode::OK) {
        Serial.write(DeviceState::CommandFailed);
        return;
    }

    while (true) {
        Packet packet = finger.read_packet();

        if (packet.type == PacketType::PacketTimeout) {
            Serial.write(DeviceState::CommandTimeout);
            return;
        }

        if (packet.type != PacketType::DataPacket &&
            packet.type != PacketType::EndOfDataPacket) {
            Serial.write(DeviceState::CommandFailed);
            return;
        }

        Serial.write(DeviceState::DataStart);
        Serial.write(packet.length - 2);
        Serial.write(packet.data, packet.length - 2);
        Serial.write(DeviceState::DataEnd);

        if (packet.type == PacketType::EndOfDataPacket) {
            Serial.write(DeviceState::CommandSuccess);
            return;
        }
    }
}

void write_reg()
{
    while (Serial.available() < 2) {
        delay(1);
    }
    buffer_byte[1] = Serial.read();
    buffer_byte[2] = Serial.read();
    buffer_code = finger.write_reg(buffer_byte[1], buffer_byte[2]);
    Serial.write(
        buffer_code == ConfirmationCode::OK ? DeviceState::CommandSuccess
                                            : DeviceState::CommandFailed
    );
}
