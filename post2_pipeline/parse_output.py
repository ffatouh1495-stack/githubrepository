"""
Parse a POST2 .out trajectory file into the Phase 0 (spec v2) metrics dict,
plus the "no silent vacuum run" verification checks the spec requires on
every run.

Row-parsing mechanics are unchanged from the Phase 0 v1 build (hand-
verified against the real Example 1B output): read the printed profile
rows directly, skip the "Elliptic Orbit" sub-blocks, track which "Begin
Phase" each row belongs to.
"""

import math
import re
from typing import Dict, List, Optional

import config
import generate_input

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
            continue
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

    # Drop "*** Elliptic Orbit ***" ghost rows (same timestamp, TitleCase
    # fields this regex doesn't match) -- real state rows always have gdalt.
    rows = [r for r in rows if "gdalt" in r]
    return rows


def parse_summary(text: str) -> Dict[str, Optional[int]]:
    match = _SUMMARY_RE.search(text)
    if not match:
        return {"warnings": None, "errors": None}
    return {"warnings": int(match.group(1)), "errors": int(match.group(2))}


def _sensed_accel_g(r: Dict) -> float:
    ax, ay, az = r.get("asxi", 0.0), r.get("asyi", 0.0), r.get("aszi", 0.0)
    return math.sqrt(ax * ax + ay * ay + az * az) / config.G0_STD


def run_vacuum_checks(rows: List[Dict]) -> Dict:
    """
    The spec's 5 "no silent vacuum run" checks. Checks 1 and 4 (atmosphere
    table cross-match, wind-variable sign/magnitude) are NOT YET
    IMPLEMENTED -- they depend on the atmosphere CSV being loadable and on
    knowing which variable names POST2 actually prints for wind, neither
    of which is confirmed yet (see mars_environment.py). They report
    checked=False rather than a fabricated pass.
    """
    dynp_values = [r.get("dynp", 0.0) for r in rows]
    veli_values = [r.get("veli") for r in rows if "veli" in r]
    gdalt_values = [r["gdalt"] for r in rows]
    decel_g_values = [_sensed_accel_g(r) for r in rows]

    peak_dynp = max(dynp_values) if dynp_values else 0.0
    peak_decel_g = max(decel_g_values) if decel_g_values else 0.0
    veli_initial = veli_values[0] if veli_values else None
    veli_final = veli_values[-1] if veli_values else None
    velocity_drop_frac = (
        (veli_initial - veli_final) / veli_initial
        if veli_initial and veli_final is not None and veli_initial > 0
        else None
    )

    final_row = rows[-1]
    gcrad_final = final_row.get("gcrad")
    g_computed = config.MU_MARS / (gcrad_final ** 2) if gcrad_final else None
    gravity_ok = (g_computed is not None) and abs(g_computed - 3.71) < 0.5

    min_gdalt, max_gdalt = min(gdalt_values), max(gdalt_values)
    within_table_range = (
        min_gdalt >= config.ATMOSPHERE_TABLE_MIN_GDALT_M
        and max_gdalt <= config.ATMOSPHERE_TABLE_MAX_GDALT_M
    )

    return {
        "check1_atmosphere_active": {
            "checked": False,
            "reason": "needs atmosphere CSV cross-match -- not implemented pending confirmed table syntax",
            "peak_dynamic_pressure_pa": peak_dynp,
            "nonzero": peak_dynp > 0.0,
        },
        "check2_decelerates_from_drag": {
            "checked": True,
            "pass": peak_decel_g > 0.1 and (velocity_drop_frac is not None and velocity_drop_frac > 0.3),
            "peak_deceleration_g": peak_decel_g,
            "velocity_drop_fraction": velocity_drop_frac,
        },
        "check3_mars_gravity": {
            "checked": True,
            "pass": gravity_ok,
            "g_computed_mps2": g_computed,
            "expected_mps2": 3.71,
        },
        "check4_wind_active": {
            "checked": False,
            "reason": "wind output variable name(s) not yet confirmed against the manual",
        },
        "check5_within_atmosphere_table_range": {
            "checked": True,
            "pass": within_table_range,
            "min_gdalt_m": min_gdalt,
            "max_gdalt_m": max_gdalt,
            "table_range_m": [config.ATMOSPHERE_TABLE_MIN_GDALT_M, config.ATMOSPHERE_TABLE_MAX_GDALT_M],
        },
    }


def parse_metrics(text: str, diameter_m: float, payload_mass_kg: float) -> Dict:
    rows = _rows_with_phase(text)
    if not rows:
        raise Post2ParseError("No trajectory rows found in output -- did the run actually execute?")

    phases = sorted({r["_phase"] for r in rows if r["_phase"] is not None})
    if not phases:
        raise Post2ParseError("Could not find any 'Begin Phase' markers in output.")

    chute_phase = 50.0 if 50.0 in phases else None
    heatshield_phase = 70.0 if 70.0 in phases else None

    def first_row_of_phase(phase_num):
        candidates = [r for r in rows if r["_phase"] == phase_num]
        return min(candidates, key=lambda r: r["time"]) if candidates else None

    deploy_row = first_row_of_phase(chute_phase)
    heatshield_row = first_row_of_phase(heatshield_phase)
    handoff_row = max(rows, key=lambda r: r["time"])  # last row = run termination

    heat_shield_never_separated = heatshield_phase is None

    peak_dynp_pa = max(r.get("dynp", 0.0) for r in rows)
    peak_decel_g = max(_sensed_accel_g(r) for r in rows)

    total_mass = generate_input.total_entry_mass_kg(payload_mass_kg)
    bc_kg_m2 = generate_input.ballistic_coefficient(diameter_m, payload_mass_kg)

    opening_force_n = None
    if deploy_row is not None:
        import aero_data
        chute_area = config.chute_area_m2(total_mass)
        deploy_mach = deploy_row.get("mach", 0.0)
        chute_cd_at_deploy = aero_data.chute_cd_at_mach(deploy_mach)
        opening_force_n = (
            deploy_row.get("dynp", 0.0) * chute_area
            * config.CHUTE_OPENING_LOAD_FACTOR * chute_cd_at_deploy
        )

    vacuum_checks = run_vacuum_checks(rows)

    return {
        "payload_mass_kg": payload_mass_kg,
        "vehicle_mass_kg": config.FIXED_VEHICLE_MASS_KG,
        "total_entry_mass_kg": total_mass,
        "ballistic_coefficient_kg_m2": bc_kg_m2,

        "peak_deceleration_g": peak_decel_g,
        "peak_dynamic_pressure_pa": peak_dynp_pa,

        "handoff_time_s": handoff_row["time"],
        "handoff_gdalt_m": handoff_row.get("gdalt"),
        "handoff_altitude_above_surface_m": handoff_row.get("gdalt", 0.0) - config.GALE_SURFACE_GDALT_M,
        "handoff_velocity_inertial_mps": handoff_row.get("veli"),
        "handoff_velocity_relative_mps": handoff_row.get("velr"),
        "handoff_mach": handoff_row.get("mach"),
        "handoff_phase": handoff_row.get("_phase"),

        "chute_deploy_altitude_m": deploy_row.get("gdalt") if deploy_row else None,
        "chute_deploy_mach": deploy_row.get("mach") if deploy_row else None,
        "chute_deploy_dynp_pa": deploy_row.get("dynp") if deploy_row else None,
        "chute_deploy_velocity_relative_mps": deploy_row.get("velr") if deploy_row else None,
        "chute_opening_force_n": opening_force_n,

        "heat_shield_separated": not heat_shield_never_separated,
        "heat_shield_sep_altitude_m": heatshield_row.get("gdalt") if heatshield_row else None,
        "heat_shield_sep_mach": heatshield_row.get("mach") if heatshield_row else None,
        "heat_shield_sep_velocity_relative_mps": heatshield_row.get("velr") if heatshield_row else None,

        "vacuum_check_atmosphere_active": vacuum_checks["check1_atmosphere_active"]["nonzero"],
        "vacuum_check_decelerates": vacuum_checks["check2_decelerates_from_drag"]["pass"],
        "vacuum_check_mars_gravity": vacuum_checks["check3_mars_gravity"]["pass"],
        "vacuum_check_wind_active_CHECKED": vacuum_checks["check4_wind_active"]["checked"],
        "vacuum_check_within_table_range": vacuum_checks["check5_within_atmosphere_table_range"]["pass"],
        "vacuum_checks_detail": vacuum_checks,
    }
