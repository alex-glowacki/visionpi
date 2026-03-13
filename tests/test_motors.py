#!/usr/bin/env python3
# tests/test_motors.py
"""
Unit tests for the motors layer.

Covers:
- clamp() helper
- TrackCommand dataclass
- MockMotorDriver state tracking, clamping, and stop behaivor

No hardware required.
Run with:
    pytest tests/test_motors.py -v
"""

from __future__ import annotations

import pytest

from motors.driver_base import clamp, TrackCommand
from motors.mock_driver import MockMotorDriver


class TestClamp:
    def test_value_within_range_unchanged(self):
        assert clamp(0.5, -1.0, 1.0) == 0.5
        
    def test_value_below_lo_returns_lo(self):
        assert clamp(-2.0, -1.0, 1.0) == -1.0

    def test_value_above_hi_returns_hi(self):
        assert clamp(2.0, -1.0, 1.0) == 1.0

    def test_value_exactly_at_lo(self):
        assert clamp(-1.0, -1.0, 1.0) == -1.0

    def test_value_exactly_at_hi(self):
        assert clamp(1.0, -1.0, 1.0) == 1.0

    def test_zero_is_unchanged(self):
        assert clamp(0.0, -1.0, 1.0) == 0.0

    def test_works_with_asymmetric_range(self):
        assert clamp(5.0, 0.0, 3.0) == 3.0
        assert clamp(-1.0, 0.0, 3.0) == 0.0
        
        
class TestTrackCommand:
    def test_fields_are_stored(self):
        cmd = TrackCommand(left=0.3, right=-0.3)
        assert cmd.left == 0.3
        assert cmd.right == -0.3
        
    def test_is_frozen(self):
        cmd = TrackCommand(left=0.3, right=0.3)
        with pytest.raises(Exception):
            cmd.left = 0.5  # type: ignore[misc]
            
    def test_equality(self):
        assert TrackCommand(0.1, 0.2) == TrackCommand(0.1, 0.2)
        assert TrackCommand(0.1, 0.2) != TrackCommand(0.2, 0.1)
        

class TestMockMotorDriver:
    def test_initial_state_is_none(self):
        driver = MockMotorDriver(print_hz=0.0)
        assert driver._last_left is None
        assert driver._last_right is None
        
    def test_set_tracks_updates_state(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(0.5, -0.5)
        assert driver._last_left == 0.5
        assert driver._last_right == -0.5
        
    def test_set_tracks_clamps_above_one(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(2.0, 3.0)
        assert driver._last_left == 1.0
        assert driver._last_right == 1.0
        
    def test_set_tracks_clamps_below_minus_one(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(-2.0, -5.0)
        assert driver._last_left == -1.0
        assert driver._last_right == -1.0
        
    def test_stop_sets_both_tracks_to_zero(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(0.8, 0.8)
        driver.stop()
        assert driver._last_left == 0.0
        assert driver._last_right == 0.0
        
    def test_state_updates_even_without_printing(self):
        # print_hz=0.0 means nothing ever prints, but state must still update
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(0.3, 0.7)
        assert driver._last_left == 0.3
        assert driver._last_right == 0.7
        
    def test_set_tracks_zero_is_valid(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(0.0, 0.0)
        assert driver._last_left == 0.0
        assert driver._last_right == 0.0
        
    def test_set_tracks_full_reverse(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(-1.0, -1.0)
        assert driver._last_left == -1.0
        assert driver._last_right == -1.0
        
    def test_successive_calls_update_state(self):
        driver = MockMotorDriver(print_hz=0.0)
        driver.set_tracks(0.3, 0.3)
        driver.set_tracks(0.7, -0.2)
        assert driver._last_left == 0.7
        assert driver._last_right == -0.2