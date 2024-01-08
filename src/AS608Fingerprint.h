#pragma once

#include <Arduino.h>

#include "SoftwareSerial.h"

namespace AS608 {

constexpr uint16_t StartCode = 0xEF01;

enum PacketType : uint8_t {
    CommandPacket = 0x01,
    DataPacket = 0x02,
    AcknowledgePacket = 0x07,
    EndOfDataPacket = 0x08,

    // self-defined packet types
    PacketTimeout = 0x21,
};

enum CommandCode : uint8_t {
    GetImage = 0x01,
    GenChar = 0x02,
    Match = 0x03,
    Search = 0x04,
    RegModel = 0x05,
    StoreChar = 0x06,
    LoadChar = 0x07,
    UpChar = 0x08,
    DownChar = 0x09,
    UpImage = 0x0A,
    DownImage = 0x0B,
    DeleteChar = 0x0C,
    Empty = 0x0D,
    WriteReg = 0x0E,
    ReadSysPara = 0x0F,
    Enroll = 0x10,
    Identify = 0x11,
    SetPwd = 0x12,
    VfyPwd = 0x13,
    GetRandomCode = 0x14,
    SetChipAddr = 0x15,
    ReadINFpage = 0x16,
    PortControl = 0x17,
    WriteNotepad = 0x18,
    ReadNotepad = 0x19,
    BurnCode = 0x1A,
    HighSpeedSearch = 0x1B,
    GenBinImage = 0x1C,
    ValidTempleteNum = 0x1D,
    UserGPIOCommand = 0x1E,
    ReadIndexTable = 0x1F,

    // self-defined command codes
    Acknowledgement = 0x30,
    PrintDeviceParameters = 0x31,
};

enum ConfirmationCode : uint8_t {
    OK = 0x00,
    PacketReceiveError = 0x01,
    NoFingerDetected = 0x02,

    FingerEnrollFail = 0x03,
    FingerprintImageDisorderly = 0x06,
    FingerprintImagePoorQuality = 0x07,
    FingerMismatch = 0x08,
    FingerNotFound = 0x09,

    CharacterFileCombinationFail = 0x0A,
    PageIDBeyondLimit = 0x0B,
    TemplateReadError = 0x0C,
    TemplateUploadError = 0x0D,
    PacketResponseFail = 0x0E,
    ImageUploadFail = 0x0F,
    TemplateDeleteFail = 0x10,
    FingerLibraryClearFail = 0x11,
    PrimaryImageInvalid = 0x15,

    FlashWriteError = 0x18,
    UndefinedError = 0x19,
    InvalidRegisterNumber = 0x1A,
    RegisterConfigurationError = 0x1B,
    IncorrectNotepadPageNumber = 0x1C,
    CommunicationPortOperationFail = 0x1D,

    // self-defined error codes
    // BadPacket = 0x21,
};

uint8_t read_byte(SoftwareSerial &serial);

struct Packet {
    uint32_t address;
    uint8_t type;
    uint16_t length;
    uint8_t data[128];
    uint16_t checksum;

    Packet(
        uint8_t type,
        uint16_t data_length,
        uint8_t *data,
        uint32_t address = 0xFFFFFFFF
    );

    Packet(SoftwareSerial &serial);

    void send(SoftwareSerial &serial);

    void print() const;

    static void read_start_code(SoftwareSerial &serial);
};

class FingerprintModule {
    uint32_t password;
    SoftwareSerial *serial;

   public:
    uint16_t status_register, sensor_type, capacity, security_level;
    uint32_t device_address;
    uint16_t data_packet_length, baudrate;

    FingerprintModule(SoftwareSerial *serial, uint32_t password = 0);

    void begin(uint32_t baudrate = 57600);

    Packet send_command(uint8_t *data, uint16_t length);

    Packet read_packet();

    bool verify_password();

    ConfirmationCode read_parameters();

    ConfirmationCode get_image();

    ConfirmationCode up_image();

    ConfirmationCode write_reg(uint8_t reg_address, uint8_t reg_value);

    void print() const;
};

}  // namespace AS608
