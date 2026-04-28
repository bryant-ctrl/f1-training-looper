"""
Validates design parameters against F1 2026 Technical Regulations.
Catches illegal designs before wasting CFD compute on them.

Key articles referenced:
  Art. 3.3  — Front wing dimensions
  Art. 3.6  — Rear wing dimensions
  Art. 3.12 — Diffuser
  Art. 3.13 — Floor and plank
  Art. 10.4 — Ride height / car reference plane
"""

from dataclasses import dataclass


@dataclass
class Violation:
    article: str
    param: str
    value: float
    limit: float
    message: str


# All linear dimensions in mm, angles in degrees.
LIMITS = {
    # Front wing
    "front_wing_main_angle":  {"min": 0.0,  "max": 35.0,  "article": "3.3.1"},
    "front_wing_flap_angle":  {"min": 0.0,  "max": 45.0,  "article": "3.3.2"},
    # Rear wing
    "rear_wing_main_angle":   {"min": 0.0,  "max": 25.0,  "article": "3.6.1"},
    "rear_wing_beam_angle":   {"min": 0.0,  "max": 20.0,  "article": "3.6.3"},
    # Ride heights (mm above reference plane)
    "front_ride_height":      {"min": 25.0, "max": 120.0, "article": "10.4.1"},
    "rear_ride_height":       {"min": 50.0, "max": 150.0, "article": "10.4.2"},
    # Diffuser
    "diffuser_angle":         {"min": 0.0,  "max": 15.0,  "article": "3.12.1"},
    "diffuser_exit_height":   {"min": 0.0,  "max": 175.0, "article": "3.12.3"},
    # Floor edge
    "floor_edge_height":      {"min": 0.0,  "max": 50.0,  "article": "3.13.2"},
}


def check(params: dict) -> list[Violation]:
    violations = []
    for param, value in params.items():
        if param not in LIMITS:
            continue
        bounds = LIMITS[param]
        if value < bounds["min"]:
            violations.append(
                Violation(
                    article=bounds["article"],
                    param=param,
                    value=value,
                    limit=bounds["min"],
                    message=f"{param}={value} is below minimum {bounds['min']} (Art. {bounds['article']})",
                )
            )
        if value > bounds["max"]:
            violations.append(
                Violation(
                    article=bounds["article"],
                    param=param,
                    value=value,
                    limit=bounds["max"],
                    message=f"{param}={value} exceeds maximum {bounds['max']} (Art. {bounds['article']})",
                )
            )
    return violations


def clamp_to_legal(params: dict) -> dict:
    """Return a copy of params with all values clamped within legal limits."""
    out = dict(params)
    for param, value in out.items():
        if param in LIMITS:
            bounds = LIMITS[param]
            out[param] = max(bounds["min"], min(bounds["max"], value))
    return out


DEFAULT_PARAMS = {
    "front_wing_main_angle": 12.0,
    "front_wing_flap_angle": 20.0,
    "rear_wing_main_angle":  12.0,
    "rear_wing_beam_angle":  8.0,
    "front_ride_height":     40.0,
    "rear_ride_height":      80.0,
    "diffuser_angle":        8.0,
    "diffuser_exit_height":  120.0,
    "floor_edge_height":     20.0,
}
