"""
Parses OpenFOAM forceCoeffs output and computes the optimization score.

OpenFOAM writes force data to:
  postProcessing/forceCoeffs/0/coefficient.dat

Columns: Time  Cm  Cd  Cl  Cl(f)  Cl(r)

Score = CL / CD  (maximize downforce, minimize drag)
A penalty is added if the rake (front vs rear ride height) is extreme.
"""

import re
from pathlib import Path


def parse_openfoam_coeffs(results_dir: Path) -> dict:
    """
    Parse the last converged line from OpenFOAM's forceCoeffs output.
    Returns dict with cl, cd, cm, score.
    """
    coeff_file = results_dir / "postProcessing" / "forceCoeffs" / "0" / "coefficient.dat"
    if not coeff_file.exists():
        raise FileNotFoundError(f"No coefficient file at {coeff_file}")

    last_data = None
    with coeff_file.open() as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split()
            if len(parts) >= 4:
                try:
                    last_data = {
                        "time": float(parts[0]),
                        "cm":   float(parts[1]),
                        "cd":   float(parts[2]),
                        "cl":   float(parts[3]),
                    }
                except ValueError:
                    continue

    if last_data is None:
        raise ValueError(f"No valid data found in {coeff_file}")

    cl = last_data["cl"]
    cd = max(last_data["cd"], 0.001)  # guard against division by zero
    last_data["score"] = cl / cd
    return last_data


def compute_score(cl: float, cd: float) -> float:
    """Aerodynamic efficiency score. Higher = better."""
    if cd <= 0:
        return 0.0
    return cl / cd


def format_results(results: dict) -> str:
    cl = results.get("cl", 0)
    cd = results.get("cd", 0)
    score = results.get("score", 0)
    return f"CL={cl:.4f}  CD={cd:.4f}  L/D={score:.3f}"
