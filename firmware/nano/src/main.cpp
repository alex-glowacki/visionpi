#include <Arduino.h>
#include <Arduino_Modulino.h>
#include <Servo.h>
#include <Wire.h>

// ============================================================
// VisionPi Robot - Nano R4 real-time controller
//
// Features
// - USB-safe startup
// - Pi command input over USB Serial: "left,right\n"
// - Sabertooth 2x12 in R/C mode on D9 / D10
// - TF-Luna on Serial1
// - Modulino Movement over Wire1 (raw I2C, proven working)
// - Modulino Pixels over Wire1 (forced to 0x36)
// - LiDAR obstacle stop / slowdown
// - Tilt-stop protection
// - Gyro yaw damping
// - Host timeout failsafe
// - Output slew limiting
// ============================================================

// -----------------------------
// User settings
// -----------------------------
static constexpr bool DEBUG_USB = true;

// Sabertooth R/C pins
static constexpr int PIN_S1 = 9;
static constexpr int PIN_S2 = 10;

// USB serial
static constexpr uint32_t USB_BAUD = 115200;

// TF-Luna UART
static constexpr uint32_t LIDAR_BAUD = 115200;
static constexpr uint16_t LIDAR_STOP_CM = 40;
static constexpr uint16_t LIDAR_SLOW_CM = 80;
static constexpr uint16_t LIDAR_MIN_VALID_CM = 5;
static constexpr uint16_t LIDAR_MAX_VALID_CM = 800;
static constexpr uint16_t LIDAR_MIN_STRENGTH = 20;
static constexpr uint32_t LIDAR_STALE_MS = 300;

// Host command timeout
static constexpr uint32_t HOST_TIMEOUT_MS = 500;

// Motion shaping
static constexpr float MAX_SLEW_PER_SEC = 1.8f;

// Sabertooth R/C pulse settings
static constexpr int RC_NEUTRAL_US = 1500;
static constexpr int RC_RANGE_US = 400;

// Modulino Movement / LSM6DSOX
static constexpr uint8_t MOVEMENT_ADDR = 0x6A;
static constexpr uint8_t REG_WHO_AM_I = 0x0F;
static constexpr uint8_t WHO_AM_I_EXPECTED = 0x6C;
static constexpr uint8_t REG_CTRL1_XL = 0x10;
static constexpr uint8_t REG_CTRL2_G = 0x11;
static constexpr uint8_t REG_OUTX_L_G = 0x22;
static constexpr uint8_t REG_OUTX_L_A = 0x28;

// Pixels
static constexpr uint8_t PIXELS_ADDR = 0x36;
static constexpr uint8_t PIXEL_BRIGHTNESS = 10;

// Tilt / damping
static constexpr bool USE_TILT_STOP = true;
static constexpr bool USE_YAW_DAMPING = true;
static constexpr float ACCEL_LSB_PER_G = 16384.0f;
static constexpr float GYRO_LSB_PER_DPS = 131.0f;
static constexpr float TILT_STOP_G = 0.80f;
static constexpr float YAW_DAMP_GAIN = 0.012f;

// -----------------------------
// Globals
// -----------------------------
Servo servoS1;
Servo servoS2;

ModulinoPixels pixels(PIXELS_ADDR);

bool pixelsReady = false;

float hostLeft = 0.0f;
float hostRight = 0.0f;
float outLeft = 0.0f;
float outRight = 0.0f;
uint32_t lastHostCmdMs = 0;

uint16_t lidarDistCm = 0;
uint16_t lidarStrength = 0;
bool lidarValid = false;
uint32_t lastGoodLidarMs = 0;

bool movementReady = false;
int16_t rawAx = 0, rawAy = 0, rawAz = 0;
int16_t rawGx = 0, rawGy = 0, rawGz = 0;
uint32_t lastMovementMs = 0;

enum RobotState {
  STATE_BOOT,
  STATE_IDLE,
  STATE_DRIVE,
  STATE_OBSTACLE,
  STATE_TIMEOUT,
  STATE_TILTSTOP
};

RobotState currentState = STATE_BOOT;

// -----------------------------
// Helpers
// -----------------------------
static float clampf(float x, float lo, float hi) {
  if (x < lo) return lo;
  if (x > hi) return hi;
  return x;
}

static float moveToward(float current, float target, float maxDelta) {
  if (target > current + maxDelta) return current + maxDelta;
  if (target < current - maxDelta) return current - maxDelta;
  return target;
}

static int trackToMicros(float x) {
  x = clampf(x, -1.0f, 1.0f);
  return RC_NEUTRAL_US + (int)(x * RC_RANGE_US);
}

static void writeTracks(float left, float right) {
  servoS1.writeMicroseconds(trackToMicros(clampf(left, -1.0f, 1.0f)));
  servoS2.writeMicroseconds(trackToMicros(clampf(right, -1.0f, 1.0f)));
}

static void stopTracks() {
  outLeft = outRight = 0.0f;
  writeTracks(0.0f, 0.0f);
}

// -----------------------------
// Raw Wire1 helpers for Movement
// -----------------------------
static uint8_t readReg8(uint8_t addr, uint8_t reg) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  if (Wire1.endTransmission(false) != 0) return 0xFF;
  if (Wire1.requestFrom((int)addr, 1) != 1) return 0xFF;
  return Wire1.read();
}

static int16_t readReg16LE(uint8_t addr, uint8_t regLow) {
  Wire1.beginTransmission(addr);
  Wire1.write(regLow);
  if (Wire1.endTransmission(false) != 0) return 0;
  if (Wire1.requestFrom((int)addr, 2) != 2) return 0;
  uint8_t lo = Wire1.read();
  uint8_t hi = Wire1.read();
  return (int16_t)((hi << 8) | lo);
}

static void writeReg8(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire1.beginTransmission(addr);
  Wire1.write(reg);
  Wire1.write(value);
  Wire1.endTransmission();
}

// -----------------------------
// USB-safe startup
// -----------------------------
static void startUsbSerialSafely() {
  Serial.begin(USB_BAUD);
  uint32_t t0 = millis();
  while (!Serial && (millis() - t0 < 1500)) delay(10);

  if (DEBUG_USB) {
    Serial.println();
    Serial.println(F("[BOOT] Nano R4 robot controller starting"));
    Serial.println(F("[BOOT] USB serial alive"));
  }
}

// -----------------------------
// Host command parser: "left,right\n"
// -----------------------------
static bool parseHostLine(const char *line, float &left, float &right) {
  char *endPtr = nullptr;
  left = strtof(line, &endPtr);
  if (endPtr == line || *endPtr != ',') return false;
  right = strtof(endPtr + 1, &endPtr);
  if (endPtr == nullptr) return false;
  while (*endPtr == ' ' || *endPtr == '\t') endPtr++;
  if (*endPtr != '\0') return false;
  left  = clampf(left,  -1.0f, 1.0f);
  right = clampf(right, -1.0f, 1.0f);
  return true;
}

static void serviceHostCommands() {
  static char lineBuf[48];
  static size_t idx = 0;

  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[idx] = '\0';
      float l = 0.0f, r = 0.0f;
      if (parseHostLine(lineBuf, l, r)) {
        hostLeft = l;
        hostRight = r;
        lastHostCmdMs = millis();
      }
      idx = 0;
      continue;
    }
    if (idx < sizeof(lineBuf) - 1) lineBuf[idx++] = c;
    else idx = 0;
  }
}

// -----------------------------
// TF-Luna reader
// -----------------------------
static void serviceLidar() {
  static uint8_t frame[9];
  static uint8_t idx = 0;

  while (Serial1.available() > 0) {
    uint8_t b = (uint8_t)Serial1.read();

    if (idx == 0) { if (b == 0x59) frame[idx++] = b; continue; }
    if (idx == 1) { if (b == 0x59) frame[idx++] = b; else idx = 0; continue; }

    frame[idx++] = b;

    if (idx >= 9) {
      uint16_t sum = 0;
      for (int i = 0; i < 8; i++) sum += frame[i];
      if ((uint8_t)(sum & 0xFF) == frame[8]) {
        uint16_t dist     = (uint16_t)frame[2] | ((uint16_t)frame[3] << 8);
        uint16_t strength = (uint16_t)frame[4] | ((uint16_t)frame[5] << 8);
        if (dist >= LIDAR_MIN_VALID_CM && dist <= LIDAR_MAX_VALID_CM
            && strength >= LIDAR_MIN_STRENGTH) {
          lidarDistCm   = dist;
          lidarStrength = strength;
          lidarValid    = true;
          lastGoodLidarMs = millis();
        }
      }
      idx = 0;
    }
  }

  if ((millis() - lastGoodLidarMs) > LIDAR_STALE_MS) lidarValid = false;
}

// -----------------------------
// Movement
// -----------------------------
static bool initMovementRaw() {
  if (readReg8(MOVEMENT_ADDR, REG_WHO_AM_I) != WHO_AM_I_EXPECTED) return false;
  writeReg8(MOVEMENT_ADDR, REG_CTRL1_XL, 0x40); // accel 104 Hz, ±2g
  writeReg8(MOVEMENT_ADDR, REG_CTRL2_G,  0x40); // gyro  104 Hz, 250 dps
  delay(50);
  return true;
}

static void serviceMovement() {
  if (!movementReady) return;
  rawGx = readReg16LE(MOVEMENT_ADDR, REG_OUTX_L_G + 0);
  rawGy = readReg16LE(MOVEMENT_ADDR, REG_OUTX_L_G + 2);
  rawGz = readReg16LE(MOVEMENT_ADDR, REG_OUTX_L_G + 4);
  rawAx = readReg16LE(MOVEMENT_ADDR, REG_OUTX_L_A + 0);
  rawAy = readReg16LE(MOVEMENT_ADDR, REG_OUTX_L_A + 2);
  rawAz = readReg16LE(MOVEMENT_ADDR, REG_OUTX_L_A + 4);
  lastMovementMs = millis();
}

static bool movementIsFresh() {
  return movementReady && ((millis() - lastMovementMs) < 250);
}

// -----------------------------
// Pixels
// -----------------------------
static void setAllPixels(ModulinoColor color, uint8_t brightness = PIXEL_BRIGHTNESS) {
  if (!pixelsReady) return;
  pixels.clear();
  for (int i = 0; i < 8; i++) pixels.set(i, color, brightness);
  pixels.show();
}

static void updatePixels(RobotState state) {
  switch (state) {
    case STATE_BOOT:      setAllPixels(BLUE);   break;
    case STATE_IDLE:      setAllPixels(CYAN);   break;
    case STATE_DRIVE:     setAllPixels(GREEN);  break;
    case STATE_OBSTACLE:  setAllPixels(YELLOW); break;
    case STATE_TIMEOUT:   setAllPixels(VIOLET); break;
    case STATE_TILTSTOP:  setAllPixels(RED);    break;
    default:              setAllPixels(WHITE);  break;
  }
}

// -----------------------------
// Safety
// -----------------------------
static bool hostTimedOut() {
  return (millis() - lastHostCmdMs) > HOST_TIMEOUT_MS;
}

static bool tiltDanger() {
  if (!USE_TILT_STOP || !movementIsFresh()) return false;
  float ax_g = rawAx / ACCEL_LSB_PER_G;
  float ay_g = rawAy / ACCEL_LSB_PER_G;
  return (fabs(ax_g) > TILT_STOP_G || fabs(ay_g) > TILT_STOP_G);
}

// -----------------------------
// Motion compute
// -----------------------------
static void computeAndApplyOutputs(float dtSec) {
  float targetLeft  = hostLeft;
  float targetRight = hostRight;

  bool timeout     = hostTimedOut();
  bool obstacle    = false;
  bool tiltStopNow = tiltDanger();

  if (timeout) { targetLeft = targetRight = 0.0f; }

  if (lidarValid) {
    if (lidarDistCm <= LIDAR_STOP_CM) {
      targetLeft = targetRight = 0.0f;
      obstacle = true;
    } else if (lidarDistCm < LIDAR_SLOW_CM) {
      float scale = clampf(
        (float)(lidarDistCm - LIDAR_STOP_CM) / (float)(LIDAR_SLOW_CM - LIDAR_STOP_CM),
        0.0f, 1.0f);
      float forward = 0.5f * (targetLeft + targetRight);
      float turn    = 0.5f * (targetRight - targetLeft);
      if (forward > 0.0f) forward *= scale;
      targetLeft  = clampf(forward - turn, -1.0f, 1.0f);
      targetRight = clampf(forward + turn, -1.0f, 1.0f);
      obstacle = true;
    }
  }

  if (tiltStopNow) { targetLeft = targetRight = 0.0f; }

  if (USE_YAW_DAMPING && movementIsFresh() && !tiltStopNow) {
    float damp = (rawGz / GYRO_LSB_PER_DPS) * YAW_DAMP_GAIN;
    targetLeft  = clampf(targetLeft  + damp, -1.0f, 1.0f);
    targetRight = clampf(targetRight - damp, -1.0f, 1.0f);
  }

  float maxStep = MAX_SLEW_PER_SEC * dtSec;
  outLeft  = moveToward(outLeft,  targetLeft,  maxStep);
  outRight = moveToward(outRight, targetRight, maxStep);
  writeTracks(outLeft, outRight);

  if      (tiltStopNow)                                      currentState = STATE_TILTSTOP;
  else if (timeout)                                          currentState = STATE_TIMEOUT;
  else if (obstacle)                                         currentState = STATE_OBSTACLE;
  else if (fabs(outLeft) > 0.05f || fabs(outRight) > 0.05f) currentState = STATE_DRIVE;
  else                                                       currentState = STATE_IDLE;
}

// -----------------------------
// Setup / loop
// -----------------------------
void setup() {
  startUsbSerialSafely();

  servoS1.attach(PIN_S1);
  servoS2.attach(PIN_S2);
  stopTracks();
  delay(200);

  Serial1.begin(LIDAR_BAUD);
  delay(50);
  while (Serial1.available()) Serial1.read();

  Wire1.begin();
  delay(100);
  Modulino.begin(Wire1);

  pixelsReady   = pixels.begin();
  movementReady = initMovementRaw();

  lastHostCmdMs   = millis();
  lastGoodLidarMs = 0;
  lastMovementMs  = 0;

  currentState = STATE_BOOT;
  updatePixels(currentState);

  if (DEBUG_USB) {
    Serial.print(F("[BOOT] pixelsReady="));
    Serial.println(pixelsReady ? F("yes") : F("no"));
    Serial.print(F("[BOOT] movementReady="));
    Serial.println(movementReady ? F("yes") : F("no"));
    Serial.println(F("[BOOT] ready"));
  }
}

void loop() {
  static uint32_t lastLoopUs    = micros();
  static uint32_t lastDbgMs     = 0;
  static RobotState lastShownState = STATE_BOOT;

  uint32_t nowUs = micros();
  float dtSec = (nowUs - lastLoopUs) * 1.0e-6f;
  lastLoopUs = nowUs;
  if (dtSec <= 0.0f || dtSec > 0.25f) dtSec = 0.01f;

  serviceHostCommands();
  serviceLidar();
  serviceMovement();
  computeAndApplyOutputs(dtSec);

  if (pixelsReady && currentState != lastShownState) {
    updatePixels(currentState);
    lastShownState = currentState;
  }

  if (DEBUG_USB && (millis() - lastDbgMs >= 500)) {
    lastDbgMs = millis();
    Serial.print(F("cmd=("));  Serial.print(hostLeft, 3);
    Serial.print(F(","));      Serial.print(hostRight, 3);
    Serial.print(F(") out=(")); Serial.print(outLeft, 3);
    Serial.print(F(","));      Serial.print(outRight, 3);
    Serial.print(F(") lidar="));
    if (lidarValid) { Serial.print(lidarDistCm); Serial.print(F("cm")); }
    else              Serial.print(F("none"));
    Serial.print(F(" movement=")); Serial.print(movementReady ? F("yes") : F("no"));
    if (movementIsFresh()) {
      Serial.print(F(" ax=")); Serial.print(rawAx);
      Serial.print(F(" ay=")); Serial.print(rawAy);
      Serial.print(F(" gz=")); Serial.print(rawGz);
    }
    Serial.print(F(" pixels=")); Serial.println(pixelsReady ? F("yes") : F("no"));
  }

  delay(5);
}