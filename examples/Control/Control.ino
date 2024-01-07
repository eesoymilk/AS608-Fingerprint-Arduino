#include "AS608Fingerprint.h"
#include "Controller.h"

using namespace AS608;
using namespace Controller;

SoftwareSerial fingerprint_serial = SoftwareSerial(2, 3);
FingerprintModule finger = FingerprintModule(&fingerprint_serial);
ConfirmationCode buffer_code;
uint8_t buffer_byte;

void setup()
{
    Serial.begin(9600);
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

    finger.read_parameters();
    Serial.write(DeviceState::InitializationComplete);
    Serial.write(DeviceState::Idle);
}

void loop()  // run over and over again
{
    // Serial.write(DeviceState::Idle);

    if (!Serial.available()) {
        delay(100);
        return;
    }

    buffer_byte = Serial.read();

    switch (buffer_byte) {
        case CommandCode::GetImage:
            try_to_get_image();
            break;
        case CommandCode::UpImage:
            upload_image();
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

    Serial.write(DeviceState::DataStart);

    while (true) {
        Packet packet = finger.read_packet();

        if (packet.type != PacketType::DataPacket &&
            packet.type != PacketType::EndOfDataPacket) {
            // Serial.println("Invalid packet type");
            Serial.write(DeviceState::DataEnd);
            Serial.write(DeviceState::CommandFailed);
            return;
        }

        // Serial.println("Received packet!!!");

        Serial.write(packet.length - 2);
        for (uint8_t i = 0; i < packet.length - 2; i++) {
            while (!Serial.availableForWrite()) {
                delay(1);
            }
            Serial.write(packet.data[i]);
        }

        while (!Serial.available()) {
            delay(1);
        }
        uint8_t cmd_code = Serial.read();
        if (cmd_code != CommandCode::Acknowledgement) {
            // Serial.println("Invalid command code");
            Serial.write(DeviceState::DataEnd);
            Serial.write(DeviceState::CommandFailed);
            return;
        }

        if (packet.type == PacketType::EndOfDataPacket) {
            // Serial.println("End of data packet");
            Serial.write(DeviceState::DataEnd);
            Serial.write(DeviceState::CommandSuccess);
            return;
        }

        delay(1000);
    }

    while (1) {
        Serial.write(0x69);
        delay(1);
    }
}
