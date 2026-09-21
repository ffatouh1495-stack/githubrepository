"""
Parse a POST2 .out trajectory file into the Phase 0 metrics dict.

Works directly off the printed profile rows (the repeated
"time ... times ... tdurp ... dens ..." blocks), the same format we
hand-verified against Example 1B's output. Does not rely on any
Mars-specific formatting -- it will work as soon as real Mars runs exist.
"""

import math
import re
from typing import Dict, List, Optional

import config
import generate_input

# Matches "<lowercase_key> <float-in-e-notation>" tokens anywhere in the
# file. Row fields (time, gdalt, dynp, mach, asxi, ...) are all lowercase;
# the "Elliptic Orbit" and header/parameter blocks use TitleCase/UPPERCASE
# keys, so this regex naturally skips them.
_TOKEN_RE = re.compile(r"\b([a-z][a-z0-9]*)\s+([+-]?\d+\.\d+[eE][+-]?\d+)")
_PHASE_RE = re.compile(r"Begin Phase\s+([\d.]+)")
_SUMMARY_RE = re.compile(r"POST2 Completed with (\d+) Warnings? and (\d+) Errors?", re.IGNORECASE)


class Post2ParseError(RuntimeError):
    pass


def _rows_with_phase(text: str) -> List[Dict]:
    phase_starts = [(m.start(), float(m.group(1))) for m in _PHASE_RE.finditer(text)]

    rows: List[Dict] = []
    current: Optional[Dict] = None
    for m in _TOKEN_RE.finditer(text):
        key, val = m.group(1), m.group(2)
        if key == "time":
            if current is not None:
                rows.append(current)
            current = {"_pos": m.start()}
        if current is None:
            continue  # tokens before the first "time" marker -- not a row
        current[key] = float(val)
    if current is not None:
        rows.append(current)

    def phase_for(pos: int) -> Optional[float]:
        phase = None
        for start_pos, phase_num in phase_starts:
            if start_pos <= pos:
                phase = phase_num
            else:
                break
        return phase

    for row in rows:
        row["_phase"] = phase_for(row["_pos"])

    # The "*** Elliptic Orbit ***" sub-block reprints the same timestamp
    # ("time <t>   *** Elliptic Orbit ***") with TitleCase fields (Gdaltp,
    # Eccen, ...) that this regex deliberately doesn't match -- so it comes
    # through as a near-empty row with only "time" and "_pos"/"_phase" set.
    # Real state rows always include gdalt; drop anything that doesn't
    # rather than relying on max()/min() tie-breaking to skip them.
    rows = [r for r in rows if "gdalt" in r]
    return rows


def parse_summary(text: str) -> Dict[str, Optional[int]]:
    match = _SUMMARY_RE.search(text)
    if not match:
        return {"warnings": None, "errors": None}
    return {"warnings": int(match.group(1)), "errors": int(match.group(2))}


def parse_metrics(text: str, design: str, diameter_m: float, payload_mass_kg: float) -> Dict:
    rows = _rows_with_phase(text)
    if not rows:
        raise Post2ParseError("No trajectory rows found in output -- did the run actually execute?")

    phases = sorted({r["_phase"] for r in rows if r["_phase"] is not None})
    if not phases:
        raise Post2ParseError("Could not find any 'Begin Phase' markers in output.")
    post_jettison_phase = phases[1] if len(phases) > 1 else None

    def get(row, key, default=0.0):
        return row.get(key, default)

    peak_dynp_pa = max(get(r, "dynp") for r in rows)

    def sensed_accel_g(r) -> float:
        ax, ay, az = get(r, "asxi"), get(r, "asyi"), get(r, "aszi")
        return math.sqrt(ax * ax + ay * ay + az * az) / config.G0_STD

    peak_decel_g = max(sensed_accel_g(r) for r in rows)

    nose_radius_m = config.NOSE_RADIUS_FRACTION[design] * (diameter_m / 2.0)

    def heat_rate_w_m2(r) -> float:
        dens = get(r, "dens")
        vel = r.get("velr", r.get("vela", 0.0))  # surface-relative velocity for heating
        if dens <= 0 or vel <= 0:
            return 0.0
        return config.SUTTON_GRAVES_K * math.sqrt(dens / nose_radius_m) * vel ** 3

    heat_series = sorted(((r["time"], heat_rate_w_m2(r)) for r in rows), key=lambda t: t[0])
    peak_heat_rate_w_m2 = max(q for _, q in heat_series)

    total_heat_load_j_m2 = 0.0
    for (t0, q0), (t1, q1) in zip(heat_series, heat_series[1:]):
        dt = t1 - t0
        if dt > 0:
            total_heat_load_j_m2 += 0.5 * (q0 + q1) * dt

    touchdown_row = max(rows, key=lambda r: r["time"])
    touchdown_velocity_mps = touchdown_row.get("velr", touchdown_row.get("vela"))
    total_descent_time_s = touchdown_row["time"]

    deploy_row = None
    if post_jettison_phase is not None:
        candidates = [r for r in rows if r["_phase"] == post_jettison_phase]
        if candidates:
            deploy_row = min(candidates, key=lambda r: r["time"])

    bc_kg_m2 = generate_input.ballistic_coefficient(design, diameter_m, payload_mass_kg)

    return {
        "peak_deceleration_g": peak_decel_g,
        "peak_dynamic_pressure_pa": peak_dynp_pa,
        "peak_heat_rate_w_cm2": peak_heat_rate_w_m2 / 1e4,
        "total_heat_load_j_cm2": total_heat_load_j_m2 / 1e4,
        "touchdown_velocity_mps": touchdown_velocity_mps,
        "total_descent_time_s": total_descent_time_s,
        "deploy_altitude_m": deploy_row["gdalt"] if deploy_row else None,
        "deploy_mach": deploy_row["mach"] if deploy_row else None,
        "ballistic_coefficient_kg_m2": bc_kg_m2,
    }
