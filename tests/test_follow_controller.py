#!/usr/bin/env python3
# test/test_follow_controller.py
"""
Unit tests for FollowController.

No hardware required — uses MockMotorDriver and synthetic DetectionFrames.
Run with:
    pytest tests/test_follow_controller.py -v
"""

from __future__ import annotations

import pytest

from motors.mock_driver import MockMotorDriver
from robot.follow_controller import FollowController
from robot.params import FollowParams
from vision.detections_reader import Detection, DetectionFrame

from tests.conftest import make_frame, make_person


class TestChooseTargetPerson:
    def test_no_detections_returns_none(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        assert ctrl.choose_target_person(make_frame([])) is None

    def test_ignores_non_person_labels(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        car = Detection(1, "car", 0.95, 0.1, 0.1, 0.5, 0.5)
        assert ctrl.choose_target_person(make_frame([car])) is None

    def test_ignores_low_confidence(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        assert ctrl.choose_target_person(make_frame([make_person(confidence=0.10)])) is None

    def test_returns_person_above_min_conf(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        person = make_person(confidence=0.9)
        assert ctrl.choose_target_person(make_frame([person])) is person

    def test_chooses_largest_bbox_when_multiple_people(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        small = make_person(w=0.1, h=0.1, track_id=1)
        large = make_person(w=0.4, h=0.6, track_id=2)
        assert ctrl.choose_target_person(make_frame([small, large])).track_id == 2


class TestUpdate:
    def test_stop_when_no_person(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        ctrl.update(make_frame([]))
        assert mock_driver._last_left == 0.0
        assert mock_driver._last_right == 0.0

    def test_forward_when_centred(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        status = ctrl.update(make_frame([make_person(cx=0.5)]))
        assert "FORWARD" in status
        assert mock_driver._last_left > 0.0
        assert mock_driver._last_left == mock_driver._last_right

    def test_turn_right_when_person_right_of_centre(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        # cx=0.25 in raw frame → mirrored to 0.75 → right of centre
        status = ctrl.update(make_frame([make_person(cx=0.25)]))
        assert "TURN_RIGHT" in status
        assert mock_driver._last_right >= mock_driver._last_left

    def test_turn_left_when_person_left_of_centre(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        # cx=0.75 in raw frame → mirrored to 0.25 → left of centre
        status = ctrl.update(make_frame([make_person(cx=0.75)]))
        assert "TURN_LEFT" in status
        assert mock_driver._last_left >= mock_driver._last_right

    def test_hard_turn_reduces_base_speed_to_zero(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        # cx=0.9 => err=0.4 which exceeds hard_turn_err=0.25
        ctrl.update(make_frame([make_person(cx=0.9)]))
        assert min(mock_driver._last_left, mock_driver._last_right) <= 0.0

    def test_outputs_clamped_to_unit_range(self, mock_driver, default_params):
        ctrl = FollowController(mock_driver, default_params)
        ctrl.update(make_frame([make_person(cx=0.99)]))
        assert -1.0 <= mock_driver._last_left <= 1.0
        assert -1.0 <= mock_driver._last_right <= 1.0


class TestDetectionsReader:
    def test_returns_none_when_file_missing(self, tmp_path):
        from vision.detections_reader import DetectionsReader
        reader = DetectionsReader(path=str(tmp_path / "no_such_file.json"))
        assert reader.read_latest() is None

    def test_parses_valid_payload(self, tmp_path):
        import json
        from vision.detections_reader import DetectionsReader

        payload = {
            "ts": 1234567890.0,
            "frame_id": 42,
            "image": {"width": 1280, "height": 720, "format": "RGB"},
            "detections": [{
                "track_id": 7,
                "label": "person",
                "confidence": 0.88,
                "bbox": {"x": 0.3, "y": 0.2, "w": 0.2, "h": 0.4},
            }],
        }
        f = tmp_path / "detections.json"
        f.write_text(json.dumps(payload))

        reader = DetectionsReader(path=str(f))
        frame = reader.read_latest()

        assert frame is not None
        assert frame.frame_id == 42
        assert len(frame.detections) == 1
        d = frame.detections[0]
        assert d.label == "person"
        assert d.track_id == 7
        assert abs(d.confidence - 0.88) < 1e-6

    def test_deduplicates_same_frame_id(self, tmp_path):
        import json
        from vision.detections_reader import DetectionsReader

        payload = {
            "ts": 1234567890.0,
            "frame_id": 1,
            "image": {"width": 640, "height": 480, "format": "RGB"},
            "detections": [],
        }
        f = tmp_path / "detections.json"
        f.write_text(json.dumps(payload))

        reader = DetectionsReader(path=str(f))
        assert reader.read_latest() is not None  # first read: new frame
        assert reader.read_latest() is None      # second read: same frame_id