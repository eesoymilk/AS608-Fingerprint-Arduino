#include "AS608Fingerprint.h"

SoftwareSerial fingerprint_serial = SoftwareSerial(2, 3);
AS608::FingerprintModule finger = AS608::FingerprintModule(&fingerprint_serial);

void setup()
{
    Serial.begin(9600);
    while (!Serial)
        ;
    delay(100);
    Serial.println("\n\nFingerprint reader test");

    finger.begin(57600);

    if (finger.verify_password()) {
        Serial.println("Module connected!");
    } else {
        Serial.println("Failed to connect to the module! Please try again.");
        while (1) {
            delay(1);
        }
    }

    Serial.println(F("Reading sensor parameters"));
    finger.read_parameters();
    finger.print();
}

void loop()  // run over and over again
{
    Serial.println("Ready to scan a fingerprint!");

    while (true) {
        AS608::ConfirmationCode code = finger.get_image();

        if (code == AS608::ConfirmationCode::OK) {
            Serial.println(F("Image taken"));
            break;
        } else if (code == AS608::ConfirmationCode::PacketReceiveError) {
            Serial.println(F("Failed to take image"));
        } else if (code == AS608::ConfirmationCode::NoFingerDetected) {
            Serial.println(F("No finger detected"));
        } else if (code == AS608::ConfirmationCode::FingerprintImageDisorderly) {
            Serial.println(F("Image too distorted"));
        } else {
            Serial.println(F("Unknown error"));
        }
    }

    while (true) {
        AS608::ConfirmationCode code = finger.up_image();

        if (code == AS608::ConfirmationCode::OK) {
            Serial.println(F("Image uploaded"));
            break;
        } else if (code == AS608::ConfirmationCode::PacketReceiveError) {
            Serial.println(F("Failed to upload image"));
        } else if (code == AS608::ConfirmationCode::ImageUploadFail) {
            Serial.println(F("Failed to upload image"));
        } else {
            Serial.println(F("Unknown error"));
        }
    }

    size_t i = 1;
    while (true) {
        AS608::Packet packet = finger.read_packet();

        if (packet.type != AS608::PacketType::DataPacket ||
            packet.type != AS608::PacketType::EndOfDataPacket) {
            Serial.println(F("Failed to read packet"));
            continue;
        }

        for (size_t i = 0; i < packet.length - 2; i++) {
            Serial.write(packet.data[i]);
        }

        if (packet.type == AS608::PacketType::EndOfDataPacket) {
            Serial.println("End of transmission");
            break;
        }
    }

    while (true) {
        delay(1);
    }
}
