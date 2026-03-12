# Firmware Archive

Historical firmware snapshots kept for reference.
The active firmware is `../src/main.cpp`.

| File                | Date       | Notes                                                     |
| ------------------- | ---------- | --------------------------------------------------------- |
| 20260301_main.cpp   | 2026-03-01 | Initial RC driver, no LiDAR                               |
| 20260302_main.cpp   | 2026-03-02 | Added LiDAR safety, IMU tilt-stop                         |
| 20260304_main.cpp   | 2026-03-04 | Added yaw damping — **contains buf[9] out-of-bounds bug** |
| main1.cpp           | —          | Modulino Pixels state LEDs + heartbeat                    |
| main_full.cpp       | —          | Full feature set with Modulino library IMU                |
| lidar_test_main.cpp | —          | Standalone TF-Luna frame parser test                      |
