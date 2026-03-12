# motors/__init__.py
# Keep lightweight: do NOT import hardware/optional deps at import time.

from .driver_base import(
    clamp,
    TrackCommand,
    MotorDriver,
)
from .mock_driver import MockMotorDriver


def get_real_driver():
    """Lazy import so pyserial is only required when actually using real hardware."""
    from .real_driver import RealMotorDriver
    return RealMotorDriver