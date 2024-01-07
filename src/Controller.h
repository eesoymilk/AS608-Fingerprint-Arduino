#include <Arduino.h>

namespace Controller {

enum DeviceState : uint8_t {
    Initialization = 0x00,
    InitializationComplete = 0x01,
    InitializationFailed = 0x02,

    CommandSuccess = 0x03,
    CommandFailed = 0x04,

    NoFingerDetected = 0x05,

    DataStart = 0x07,
    DataEnd = 0x08,

    Idle = 0x69,
};

}  // namespace Controller
