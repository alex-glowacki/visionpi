#!/usr/bin/env python3
# robot/params.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FollowParams:
    """
    Tunables for the person-follow controller.
    
    Bbox coordinates are expected normalized to [0..1].
    Error is defined as:
    
        err = (person_center_x - 0.5)
        
    So:
        err < 0 => person is left of center (turn left)
        err > 0 => person is right of center (turn right) 
    """
    
    # Vision filtering
    min_conf: float = 0.30              # Ignore detections below this confidence
    
    # Steering behavior
    deadband: float = 0.06              # Within abs(err) < deadband, go straight
    steer_gain: float = 1.50            # Multiplies err into a steer value
    
    # Speeds (normalized -1..+1)
    base_speed: float = 0.80            # Forward speed when target is centered
    turn_speed: float = 0.65            # Steering influence on left/right wheels
    
    # If target is far off-center, reduce forward motion to avoid spiralling
    hard_turn_err: float = 0.25         # abs(err) >= this => base speed becomes 0