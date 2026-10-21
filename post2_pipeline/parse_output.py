"""
Parse a POST2 .out trajectory file into the Phase 0 metrics dict, plus the
5 "no silent vacuum run" verification checks the spec requires on every run.

UNITS: with IOFLAG=0 (English), POST2's printed row values (gdalt, velr,
veli, dynp, dens, asxi/asyi/aszi, ...) are in English units (ft, ft/s,
lb/ft^2, slug/ft^3, ft/s^2). All values are converted back to SI here
before being reported, so the final metrics/CSV stay consistent with the
rest of the project's metric reporting (e.g. ballistic coefficient in
kg/m^2, matching MSL's published ~145 kg/m^2). The raw .out file itself
stays in its native English units -- only this module's output is converted.

Row-parsing mechanics (finding/splitting profile rows, skipping the
"Elliptic Orbit" sub-blocks, tracking phases) are unit-independent and
unchanged from earlier builds, hand-verified against the real Example 1B
output.
"""

import math
import re
from typing import Dict, List, Optional

import config
import generate_input

_TOKEN_RE = re.compile(r"\b([a-z][a-z0-9]*)\s+([+-]?\d+\.\d+[eE][+-]?\d+)")
_PHASE_RE = re.compile(r"Begin Phase\s+([\d.]+)")
# CHKTERM's own "ESN=" (event sequence number) tells us which event the
# integrator was actually in when an ALTMIN/other safety-net termination
# fired -- more reliable than "Begin Phase" markers for telling whether a
# run that hit ALTMIN had already reached event 100 (handoff) or was still
# stuck in an earlier event (e.g. ESN=70, never made it past heat-shield
# separation) when the race between ALTMIN and the event-100 criterion was
# decided. Confirmed against a real run: "...ESN= 70.000; VEH= 1."
_ESN_RE = re.compile(r"ESN=\s*([\d.]+)")
_SUMMARY_RE = re.compile(
    r"POST2 (Completed|Terminated Abnormally) with (\d+) Warnings? and (\d+) Errors?",
    re.IGNORECASE,
)
# See run_post2.py's matching comment: the ALTMIN global-safety-net handoff
# termination prints "Terminated Abnormally" + this CHKTERM message rather
# than "Completed" -- confirmed against a real successful run. It's the
# designed outcome for the handoff event, not a genuine failure.
_ALTMIN_TERMINATION_RE = re.compile(r"Trajectory terminated by ALTMIN=", re.IGNORECASE)

PA_PER_LBFT2 = config.N_PER_LBF * config.FT2_PER_M2  # ~47.8803, precise (not the spec's rounded atm-CSV factor)


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
        return {"warnings": None, "errors": None, "termination_mode": None, "altmin_triggered": False}
    return {
        "warnings": int(match.group(2)),
        "errors": int(match.group(3)),
        "termination_mode": match.group(1).strip().lower().replace(" ", "_"),
        "altmin_triggered": bool(_ALTMIN_TERMINATION_RE.search(text)),
    }


def _sensed_accel_g(r: Dict) -> float:
    """asxi/asyi/aszi are in ft/s^2 under IOFLAG=0; divide by standard g
    in the same units so the ratio (g's) comes out unit-independent."""
    ax, ay, az = r.get("asxi", 0.0), r.get("asyi", 0.0), r.get("aszi", 0.0)
    return math.sqrt(ax * ax + ay * ay + az * az) / config.G0_ENGLISH


def _ft_to_m(x: Optional[float]) -> Optional[float]:
    return None if x is None else x * config.M_PER_FT


def _lbft2_to_pa(x: Optional[float]) -> Optional[float]:
    return None if x is None else x * PA_PER_LBFT2


def _atmosphere_cross_match() -> Dict:
    """Vacuum check #1's table cross-match: interpolate the loaded
    atmosphere table (English units, same as POST2's printed output under
    IOFLAG=0) at 10/40/80 km and return the expected dens (slug/ft^3) and
    speed of sound (ft/s) at each, for comparison against the run's
    printed values. Returns None values if the atmosphere CSV isn't
    available (shouldn't happen for a run that actually executed, but
    defensive)."""
    try:
        import mars_environment
        table = mars_environment._load_atmosphere_table_english()
    except Exception:
        return {"available": False}

    alts_ft = sorted(r["alt_ft"] for r in table)
    dens_by_alt = {r["alt_ft"]: r["dens_slugft3"] for r in table}
    cs_by_alt = {r["alt_ft"]: r["cs_fts"] for r in table}

    def interp(target_ft, values_by_alt):
        if target_ft <= alts_ft[0]:
            return values_by_alt[alts_ft[0]]
        if target_ft >= alts_ft[-1]:
            return values_by_alt[alts_ft[-1]]
        for a0, a1 in zip(alts_ft, alts_ft[1:]):
            if a0 <= target_ft <= a1:
                v0, v1 = values_by_alt[a0], values_by_alt[a1]
                frac = (target_ft - a0) / (a1 - a0)
                return v0 + frac * (v1 - v0)
        return values_by_alt[alts_ft[-1]]

    targets_km = [10, 40, 80]
    expected = {}
    for km in targets_km:
        ft = km * 1000.0 * config.SPEC_M_TO_FT
        expected[km] = {"dens_slugft3": interp(ft, dens_by_alt), "cs_fts": interp(ft, cs_by_alt)}
    return {"available": True, "expected": expected}


def run_vacuum_checks(rows: List[Dict]) -> Dict:
    """The spec's 5 "no silent vacuum run" checks. Check 4 (wind-variable
    sign/magnitude) is NOT YET IMPLEMENTED -- no confirmed POST2 output
    variable name for wind speed/direction has been observed yet. Reports
    checked=False rather than a fabricated pass."""
    dynp_values = [r.get("dynp", 0.0) for r in rows]
    veli_values = [r.get("veli") for r in rows if "veli" in r]
    gdalt_values = [r["gdalt"] for r in rows]
    decel_g_values = [_sensed_accel_g(r) for r in rows]

    peak_dynp_lbft2 = max(dynp_values) if dynp_values else 0.0
    peak_decel_g = max(decel_g_values) if decel_g_values else 0.0
    veli_initial = veli_values[0] if veli_values else None
    veli_final = veli_values[-1] if veli_values else None
    velocity_drop_frac = (
        (veli_initial - veli_final) / veli_initial
        if veli_initial and veli_final is not None and veli_initial > 0
        else None
    )

    final_row = rows[-1]
    gcrad_ft = final_row.get("gcrad")
    g_computed_mps2 = None
    if gcrad_ft:
        g_computed_ftps2 = config.MU_MARS_FT3_S2 / (gcrad_ft ** 2)
        g_computed_mps2 = g_computed_ftps2 * config.M_PER_FT
    gravity_ok = (g_computed_mps2 is not None) and abs(g_computed_mps2 - 3.71) < 0.5

    min_gdalt_ft, max_gdalt_ft = min(gdalt_values), max(gdalt_values)
    within_table_range = (
        min_gdalt_ft >= config.ATMOSPHERE_TABLE_MIN_GDALT_FT
        and max_gdalt_ft <= config.ATMOSPHERE_TABLE_MAX_GDALT_FT
    )

    cross_match = _atmosphere_cross_match()
    density_match = {"checked": False}
    if cross_match.get("available"):
        # POST2 only prints rows at whatever altitude the trajectory
        # happens to be at each integration step, not at exact round-km
        # altitudes -- the nearest printed row to a target altitude can
        # be several hundred meters off, and since density falls off
        # fast with altitude, that gap alone can look like a multi-percent
        # "mismatch" even when the atmosphere model is working correctly
        # (confirmed against a real run: 486 m gap at the 40 km mark
        # produced a ~5.6% apparent error on its own). So interpolate the
        # PRINTED density between the two rows bracketing the target
        # altitude, to compare like-for-like against the table's value at
        # that exact altitude, rather than comparing to the nearest row's
        # own (different) altitude.
        sorted_by_alt = sorted(
            ((r["gdalt"], r.get("dens")) for r in rows if "dens" in r),
            key=lambda t: t[0],
        )

        def _printed_dens_at(target_ft):
            if not sorted_by_alt:
                return None
            if target_ft <= sorted_by_alt[0][0]:
                return sorted_by_alt[0][1]
            if target_ft >= sorted_by_alt[-1][0]:
                return sorted_by_alt[-1][1]
            for (a0, d0), (a1, d1) in zip(sorted_by_alt, sorted_by_alt[1:]):
                if a0 <= target_ft <= a1:
                    if a1 == a0:
                        return d0
                    frac = (target_ft - a0) / (a1 - a0)
                    return d0 + frac * (d1 - d0)
            return sorted_by_alt[-1][1]

        results = {}
        all_ok = True
        for km, exp in cross_match["expected"].items():
            target_ft = km * 1000.0 * config.SPEC_M_TO_FT
            closest = min(rows, key=lambda r: abs(r["gdalt"] - target_ft))
            printed_dens = _printed_dens_at(target_ft)
            expected_dens = exp["dens_slugft3"]
            rel_err = None
            ok = False
            if printed_dens is not None and expected_dens:
                rel_err = abs(printed_dens - expected_dens) / expected_dens
                ok = rel_err < 0.05  # 5% tolerance (4-sig-fig table, interpolation)
            results[km] = {
                "closest_row_gdalt_ft": closest["gdalt"],
                "printed_dens_slugft3": printed_dens,
                "expected_dens_slugft3": expected_dens,
                "relative_error": rel_err,
                "pass": ok,
            }
            all_ok = all_ok and ok
        density_match = {"checked": True, "pass": all_ok, "by_altitude_km": results}

    return {
        "check1_atmosphere_active": {
            "checked": True,
            "nonzero": peak_dynp_lbft2 > 0.0,
            "peak_dynamic_pressure_pa": _lbft2_to_pa(peak_dynp_lbft2),
            "density_table_match": density_match,
            "pass": (peak_dynp_lbft2 > 0.0) and density_match.get("pass", False),
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
            "g_computed_mps2": g_computed_mps2,
            "expected_mps2": 3.71,
        },
        "check4_wind_active": {
            "checked": False,
            "reason": "no confirmed POST2 output variable name for wind speed/direction observed yet",
        },
        "check5_within_atmosphere_table_range": {
            "checked": True,
            "pass": within_table_range,
            "min_gdalt_m": _ft_to_m(min_gdalt_ft),
            "max_gdalt_m": _ft_to_m(max_gdalt_ft),
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
    handoff_row = max(rows, key=lambda r: r["time"])

    chute_deployed = chute_phase is not None
    heat_shield_never_separated = heatshield_phase is None
    heat_shield_separated = not heat_shield_never_separated

    # "Handoff reached" per the author's own criterion: the vehicle got
    # through the full intended sequence (chute deployed, then heat shield
    # separated) before the run ended -- NOT literally whether POST2's
    # event counter reached exactly 100, since ALTMIN and the event-100
    # criterion can race (same altitude, by design) and ALTMIN sometimes
    # wins by one integration step even on an otherwise-correct run. A run
    # that skipped and never got the heat shield off before terminating is
    # a real failure, not just a missed formality.
    handoff_reached = chute_deployed and heat_shield_separated

    esn_matches = _ESN_RE.findall(text)
    last_event_number_reached = float(esn_matches[-1]) if esn_matches else handoff_row.get("_phase")

    rows_by_time = sorted(rows, key=lambda r: r["time"])
    decel_g_by_row = [(r, _sensed_accel_g(r)) for r in rows_by_time]
    peak_decel_row, peak_decel_g = max(decel_g_by_row, key=lambda t: t[1])
    peak_decel_idx = rows_by_time.index(peak_decel_row)
    rows_after_peak_decel = rows_by_time[peak_decel_idx + 1:]
    # Skip indicator: how high the vehicle climbed back up after peak
    # deceleration -- should stay near zero/flat for a correctly-banked,
    # non-skipping entry. A large positive value here is exactly the
    # "climbs from 20 km back to 33.6 km" symptom from the zero-bank bug.
    max_altitude_after_peak_decel_m = _ft_to_m(
        max((r["gdalt"] for r in rows_after_peak_decel), default=peak_decel_row["gdalt"])
    )

    bnkang_values = [r["bnkang"] for r in rows if "bnkang" in r]
    max_abs_bnkang_deg = max((abs(v) for v in bnkang_values), default=None)

    peak_dynp_pa = _lbft2_to_pa(max(r.get("dynp", 0.0) for r in rows))

    total_mass = generate_input.total_entry_mass_kg(payload_mass_kg)
    bc_kg_m2 = generate_input.ballistic_coefficient(diameter_m, payload_mass_kg)

    opening_force_n = None
    if deploy_row is not None:
        import aero_data
        chute_area_m2 = config.chute_area_m2(total_mass)
        deploy_mach = deploy_row.get("mach", 0.0)
        chute_cd_at_deploy = aero_data.chute_cd_at_mach(deploy_mach)
        deploy_dynp_pa = _lbft2_to_pa(deploy_row.get("dynp", 0.0))
        opening_force_n = (
            deploy_dynp_pa * chute_area_m2
            * config.CHUTE_OPENING_LOAD_FACTOR * chute_cd_at_deploy
        )

    vacuum_checks = run_vacuum_checks(rows)
    summary = parse_summary(text)

    return {
        "post2_termination_mode": summary["termination_mode"],
        "post2_altmin_triggered": summary["altmin_triggered"],
        "payload_mass_kg": payload_mass_kg,
        "vehicle_mass_kg": config.FIXED_VEHICLE_MASS_KG,
        "total_entry_mass_kg": total_mass,
        "ballistic_coefficient_kg_m2": bc_kg_m2,

        "peak_deceleration_g": peak_decel_g,
        "peak_deceleration_time_s": peak_decel_row["time"],
        "peak_dynamic_pressure_pa": peak_dynp_pa,
        "max_altitude_after_peak_decel_m": max_altitude_after_peak_decel_m,
        "max_abs_bnkang_deg": max_abs_bnkang_deg,

        "last_event_number_reached": last_event_number_reached,
        "handoff_reached": handoff_reached,

        "handoff_time_s": handoff_row["time"],
        "handoff_gdalt_m": _ft_to_m(handoff_row.get("gdalt")),
        "handoff_altitude_above_surface_m": _ft_to_m(handoff_row.get("gdalt", 0.0)) - config.GALE_SURFACE_GDALT_M,
        "handoff_velocity_inertial_mps": _ft_to_m(handoff_row.get("veli")),
        "handoff_velocity_relative_mps": _ft_to_m(handoff_row.get("velr")),
        "handoff_mach": handoff_row.get("mach"),
        "handoff_phase": handoff_row.get("_phase"),

        "chute_deploy_time_s": deploy_row.get("time") if deploy_row else None,
        "chute_deploy_altitude_m": _ft_to_m(deploy_row.get("gdalt")) if deploy_row else None,
        "chute_deploy_altitude_above_surface_m": (
            _ft_to_m(deploy_row.get("gdalt", 0.0)) - config.GALE_SURFACE_GDALT_M if deploy_row else None
        ),
        "chute_deploy_mach": deploy_row.get("mach") if deploy_row else None,
        "chute_deploy_dynp_pa": _lbft2_to_pa(deploy_row.get("dynp")) if deploy_row else None,
        "chute_deploy_velocity_relative_mps": _ft_to_m(deploy_row.get("velr")) if deploy_row else None,
        "chute_opening_force_n": opening_force_n,

        "heat_shield_separated": heat_shield_separated,
        "heat_shield_sep_altitude_m": _ft_to_m(heatshield_row.get("gdalt")) if heatshield_row else None,
        "heat_shield_sep_mach": heatshield_row.get("mach") if heatshield_row else None,
        "heat_shield_sep_velocity_relative_mps": _ft_to_m(heatshield_row.get("velr")) if heatshield_row else None,

        "vacuum_check_atmosphere_active": vacuum_checks["check1_atmosphere_active"]["pass"],
        "vacuum_check_decelerates": vacuum_checks["check2_decelerates_from_drag"]["pass"],
        "vacuum_check_mars_gravity": vacuum_checks["check3_mars_gravity"]["pass"],
        "vacuum_check_wind_active_CHECKED": vacuum_checks["check4_wind_active"]["checked"],
        "vacuum_check_within_table_range": vacuum_checks["check5_within_atmosphere_table_range"]["pass"],
        "vacuum_checks_detail": vacuum_checks,
    }
