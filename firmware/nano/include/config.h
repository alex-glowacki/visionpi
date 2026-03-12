#pragma once
#include <cstdint>

// USB serial (Pi <=> Nano)
static constexpr uint32_t PC_BAUD = 115200;

// Sabertooth Simplified Serial
static constexpr uint32_t SABERTOOTH_BAUD = 9600;

// Safety: stop motors if no valid command received within this time
static constexpr uint32_t COMMAND_TIMEOUT_MS = 500;

// Ramping limits (command units per second in normalised [-1..+1] space)
static constexpr float RAMP_RATE_PER_SEC = 3.0f;  // 0 → 1 in ~0.33 s
static constexpr bool ENABLE_RAMPING = true;

// Deadband: treat tiny values as 0
static constexpr float INPUT_DEADBAND = 0.02f;

// Print debug output to USB serial
static constexpr bool ENABLE_DEBUG = true;