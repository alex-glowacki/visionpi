# test/conftest.py
"""Shared pytest fixtures for the visionpi test suite."""

from __future__ import annotations

import time
import pytest

from motors.mock_driver import MockMotorDriver
from robot.params import FollowParams
from vision.detections_reader import Detection, DetectionFrame


@pytest.fixture
def mock_driver() -> MockMotorDriver:
    return MockMotorDriver(print_hz=0.0)    # silence output during tests


@pytest.fixture
def default_params() -> FollowParams:
    return FollowParams()


def make_frame(
    detections: list[Detection],
    frame_id: int = 1,
    width: int = 1280,
    height: int = 720,
) -> DetectionFrame:
    """Helper: build a DetectionFrame from a list of Detection objects."""
    return DetectionFrame(
        ts=time.time(),
        frame_id=frame_id,
        width=width,
        height=height,
        detections=detections,
    )
    

def make_person(
    cx: float = 0.5,
    cy: float = 0.5,
    w: float = 0.2,
    h: float = 0.4,
    confidence: float = 0.9,
    track_id: int = 1,
) -> Detection:
    """Helper: build a person Detection centered at (cx, cy)."""
    return Detection(
        track_id=track_id,
        label="person",
        confidence=confidence,
        x=cx - w / 2,
        y=cy - h / 2,
        w=w,
        h=h,
    )