#!/usr/bin/env python3
# robot/follow_controller.py

from __future__ import annotations

from typing import Optional

from motors.driver_base import MotorDriver, clamp
from robot.params import FollowParams
from vision.detections_reader import Detection, DetectionFrame


class FollowController:
    """
    Pure control logic - no file I/O, no sleeps, no loops.
    
    Responsibilities:
    - Choose a target person from a DetectionFrame.
    - Convert the target's position error into differential track speeds.
    - Send the resulting command to the injected MotorDriver.
    
    Easy to unit-test: just pass a MockMotorDriver and synthetic frames.
    """
    
    def __init__(
        self,
        driver: MotorDriver,
        params: Optional[FollowParams] = None,
    ) -> None:
        self.driver = driver
        self.p = params or FollowParams()
        
    def choose_target_person(self, frame: DetectionFrame) -> Optional[Detection]:
        """Return the person with the largest bbox area above min_conf, or None."""
        people = [
            d for d in frame.detections
            if d.label == "person" and d.confidence >= self.p.min_conf
        ]
        if not people:
            return None
        # "Closest" heuristic: biggest bounding-box area
        return max(people, key=lambda d: d.w * d.h)
    
    def update(self, frame: DetectionFrame) -> str:
        """
        Run one control step from the latest detection frame.
        Returns a short status string suitable for logging.
        """
        target = self.choose_target_person(frame)
        if target is None:
            self.driver.stop()
            return "STOP (no person)"
        
        # Normalized bbox center X; err < 0 = left, err > 0 = right
        cx = target.x + target.w / 2.0
        err = cx - 0.5
        
        # Reduce forward speed when far off-center to avoid spiralling
        base = self.p.base_speed
        if abs(err) >= self.p.hard_turn_err:
            base = 0.0
            
        # Dead-band: go straight if nearly centered
        if abs(err) <= self.p.deadband:
            speed = base if base > 0 else self.p.base_speed
            self.driver.set_tracks(speed, speed)
            return (
                f"FORWARD err={err:+.3f} cx={cx:.3f} "
                f"id={target.track_id} conf={target.confidence:.2f}"
            )
            
        # Differential steering
        steer = clamp(err * self.p.steer_gain, -1.0, 1.0)
        left = clamp(base - steer * self.p.turn_speed, -1.0, 1.0)
        right = clamp(base + steer * self.p.turn_speed, -1.0, 1.0)
        
        self.driver.set_tracks(left, right)
        
        action = "TURN_LEFT" if err < 0 else "TURN RIGHT"
        return (
            f"{action} err={err:+.3f} cx={cx:.3f} "
            f"tracks=({left:+.2f},{right:+.2f}) "
            f"id={target.track_id} conf={target.confidence:.2f}"
        )