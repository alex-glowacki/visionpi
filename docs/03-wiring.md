# VisionPi — Physical Wiring Reference

> This document describes the physical wiring between all hardware components in the VisionPi robot.
> Update this file whenever connections change.
>
> `TBD` = connection exists but pin/location not yet confirmed.

---

## Device Overview

| Device                  | Role                                    | Interface              |
|-------------------------|-----------------------------------------|------------------------|
| Arduino Nano R4         | Motor controller / Modulino host        | USB, GPIO, Qwiic       |
| Sabertooth Motor Driver | Dual-channel PWM motor driver           | PWM (S1/S2), Power     |
| Left Track Motor        | Left drive motor w/ quadrature encoder  | GPIO, Sabertooth       |
| Right Track Motor       | Right drive motor w/ quadrature encoder | GPIO, Sabertooth       |
| Modulino Movement       | IMU (accelerometer/gyroscope)           | Qwiic (I2C)            |
| Modulino Pixels         | LED indicator array                     | Qwiic (I2C)            |

---

## Sabertooth Motor Driver

### Power Terminals

| Terminal | Connection           | Notes                   |
|----------|----------------------|-------------------------|
| B+       | LiFePO4 Battery (+)  | Main drive power input  |
| B−       | LiFePO4 Battery (−)  | Main drive power ground |

### Motor Terminals

| Terminal | Connection              | Notes           |
|----------|-------------------------|-----------------|
| M1A      | Left Motor — Red wire   | Left track (+)  |
| M1B      | Left Motor — Black wire | Left track (−)  |
| M2A      | Right Motor — Red wire  | Right track (+) |
| M2B      | Right Motor — Black wire| Right track (−) |

### Signal Ports (PWM from Arduino Nano R4)

Each signal port (S1, S2) uses a 3-wire connector: Red (5V), Black (GND), White (Signal).

| Sabertooth Port | Wire  | Arduino Nano R4 Pin | Notes              |
|-----------------|-------|---------------------|--------------------|
| S1              | White | D9                  | Left track PWM     |
| S1              | Red   | 5V                  | Signal port power  |
| S1              | Black | GND                 | Signal port ground |
| S2              | White | D10                 | Right track PWM    |
| S2              | Red   | 5V                  | Signal port power  |
| S2              | Black | GND                 | Signal port ground |

---

## DC Motors (CQRobot — Left & Right)

Each motor has a 6-wire connector. Red and Black carry motor power through the Sabertooth.
Yellow, White, Blue, and Gray are encoder wires routed to the Arduino Nano R4.

### Left Track Motor

| Wire   | Function         | Destination              | Notes                    |
|--------|------------------|--------------------------|--------------------------|
| Red    | Motor Power (+)  | Sabertooth M1A           | Via Sabertooth, not Nano |
| Black  | Motor Power (−)  | Sabertooth M1B           | Via Sabertooth, not Nano |
| Yellow | Encoder A Output | Arduino Nano R4 — D2     | Quadrature signal A      |
| White  | Encoder B Output | Arduino Nano R4 — D3     | Quadrature signal B      |
| Blue   | Encoder VCC      | Arduino Nano R4 — 3.3V   | 3.3V–24V range supported |
| Gray   | Encoder GND      | Arduino Nano R4 — GND    | Encoder ground           |

### Right Track Motor

| Wire   | Function         | Destination              | Notes                    |
|--------|------------------|--------------------------|--------------------------|
| Red    | Motor Power (+)  | Sabertooth M2A           | Via Sabertooth, not Nano |
| Black  | Motor Power (−)  | Sabertooth M2B           | Via Sabertooth, not Nano |
| Yellow | Encoder A Output | Arduino Nano R4 — D4     | Quadrature signal A      |
| White  | Encoder B Output | Arduino Nano R4 — D5     | Quadrature signal B      |
| Blue   | Encoder VCC      | Arduino Nano R4 — 3.3V   | 3.3V–24V range supported |
| Gray   | Encoder GND      | Arduino Nano R4 — GND    | Encoder ground           |

> **Note:** Encoder A (Yellow) leads Encoder B (White) when the motor spins forward.
> Swap Yellow/White in firmware if direction reads inverted.

---

## Qwiic / I2C Chain (Arduino Nano R4)

The Modulino devices are daisy-chained via Qwiic connectors starting from the Nano R4's onboard Qwiic port.

```
Arduino Nano R4 (Qwiic)
        │
        ▼
Modulino Movement  ──►  Modulino Pixels
  (IMU / 1st)           (LEDs / 2nd)
```

| Device            | Qwiic Position | I2C Address | Notes                   |
|-------------------|----------------|-------------|-------------------------|
| Modulino Movement | 1st in chain   | Confirmed   | Accelerometer/gyroscope |
| Modulino Pixels   | 2nd in chain   | Confirmed   | LED indicator array     |

> **Note:** Qwiic uses 3.3V logic. Do not connect Qwiic devices to 5V I2C without a level shifter.

---

## Arduino Nano R4 — Pin Summary

| Pin   | Connected To                        | Function               |
|-------|-------------------------------------|------------------------|
| D2    | Left Motor — Encoder A (Yellow)     | Quadrature input       |
| D3    | Left Motor — Encoder B (White)      | Quadrature input       |
| D4    | Right Motor — Encoder A (Yellow)    | Quadrature input       |
| D5    | Right Motor — Encoder B (White)     | Quadrature input       |
| D9    | Sabertooth S1 — White               | Left track PWM output  |
| D10   | Sabertooth S2 — White               | Right track PWM output |
| 3.3V  | Left & Right Motor — Encoder VCC (Blue) | Encoder power      |
| 5V    | Sabertooth S1/S2 — Red              | Signal port power      |
| GND   | Sabertooth S1/S2 — Black            | Signal port ground     |
| GND   | Left & Right Motor — Encoder GND (Gray) | Encoder ground     |
| Qwiic | Modulino Movement (1st in chain)    | I2C chain start        |

---

## Open Items

- [x] Confirm Nano R4 encoder pins for Left Motor (D2, D3)
- [x] Confirm Nano R4 encoder pins for Right Motor (D4, D5)
- [x] Confirm encoder VCC voltage (3.3V)
- [x] Confirm I2C addresses for Modulino Movement and Modulino Pixels
