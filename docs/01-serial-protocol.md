# Nano Serial Protocol

This document defines the Pi ↔ Nano USB serial protocol as implemented in
`firmware/nano/visionpi_motor_controller/src/main.cpp`.

---

## Pi → Nano (commands)

Send a comma-separated pair of normalised floats followed by a newline:

```
<left>,<right>\n
```

Values are in the range `[-1.0, +1.0]`:

- `-1.0` = full reverse
- `0.0` = stop / neutral
- `+1.0` = full forward

**Examples:**

```
0.300,0.300\n     # forward at 30%
-0.250,-0.250\n   # reverse at 25%
-0.250,0.250\n    # spin left (tank turn)
0.000,0.000\n     # stop
```

The Nano applies:

- Input clamping to `[-1.0, +1.0]`
- Output slew-rate limiting (`MAX_SLEW_PER_SEC`)
- Yaw damping from the IMU gyro
- LiDAR obstacle slow-down / stop
- Tilt-stop if IMU detects excessive lean

### Host timeout failsafe

If no valid command is received within `HOST_TIMEOUT_MS` (500 ms), the Nano
automatically commands neutral (motors stop). Send commands continuously at
your loop rate to keep the robot moving.

---

## Nano → Pi (telemetry)

The Nano emits debug telemetry every 500 ms when `DEBUG_USB = true`:

```
cmd=(<left>,<right>) out=(<left>,<right>) lidar=<cm|none> movement=<yes|no> [ax=<n> ay=<n> gz=<n>] pixels=<yes|no>
```

`RealMotorDriver` parses these lines to expose `latest_lidar_cm` /
`lidar_age_s` for optional Pi-side LiDAR logic.

---

## Notes

- All messages are newline (`\n`) terminated.
- The Nano is the **final authority** for all low-level safety decisions.
- There is no ACK handshake; the protocol is fire-and-forget.
