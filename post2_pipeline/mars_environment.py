"""
Mars atmosphere + wind block for the POST2 input deck.

STATUS: syntax CONFIRMED against the POST2 v5.0.0 manual (see citations
below). The only remaining blocker is DATA: config.MARS_ATMOSPHERE_CSV
(mars_atmosphere_gale.csv, 146-row Mars-GRAM table) must actually exist
on disk. config.MARS_ATMOSPHERE_READY auto-detects this file's presence.

Confirmed syntax (manual section 6.a.4 unless noted):
  - NPC(5) = 1: general/tabular atmosphere, fill PREST (pressure),
    ATEMT (temperature), CST (speed of sound), DENST (density), each
    indexed by GDALT (geodetic altitude, ft -- IOFLAG=0/English, per the
    manual's section 4.a unit rules: input units cannot be mixed within a
    problem). NPC(5)=7 is deprecated (needs natural-log tables) -- not used.
  - Table syntax (section 6.d): `NAME = "label" monovar GDALT 0 <interp>
    xtrap alt1 val1 alt2 val2 ...` -- log_inp for density/pressure (strictly
    positive, true here), lin_inp for temperature/speed of sound. Table
    size "limited only by swap space" -- 146 points is fine, not thinned.
    This punctuation (double-quoted label, space-separated, no commas) is
    the manual's own example; kept as-is here rather than mixed with the
    comma/single-quote style already validated for cdt/clt in Examples
    1A/1B, since that style hasn't been confirmed for these tables.
  - ATMOSK(1)/(2): used to compute CS = SQRT(ATMOSK(1) x ATEM) and
    DENS = ATMOSK(2) x PRES / ATEM when using a table atmosphere. Both
    default to 1.0; the manual doesn't say what happens when CST/DENST are
    ALSO supplied directly. Per spec: supply CST and DENST explicitly,
    leave ATMOSK at 1.0, and verify in the test run that printed DENS/CS
    at 10/40/80 km match the table (vacuum-check #1) -- do not tune
    ATMOSK to force a match if they don't.
  - NPC(6) = 1: winds from VWT (speed, ft/s), AZW_T (azimuth, deg),
    VWWT (vertical component, positive downward), each vs. GDALT, same
    table syntax as atmosphere. NPC(6)=3 differs only in vector
    interpolation, irrelevant for a constant wind -- NPC(6)=1 used.
    AZWB (azimuth bias) defaults to 180.0, under which AZW_T is
    METEOROLOGICAL: "an azimuth value of zero in the wind table represents
    a wind blowing from the north." AZWB is left at its default; a 0 deg
    AZW_T therefore means the 10 m/s wind blows FROM the north (toward the
    south). If the author meant a different direction, only
    config.WIND_DIRECTION_DEG needs to change.
  - Mars-GRAM's own mean winds are NOT used (per spec) -- VWT/AZW_T come
    only from config.WIND_SPEED_MPS/WIND_DIRECTION_DEG, never the CSV.

Unit conversions for the CSV use the spec's own stated factors exactly
(not independently-derived precise SI conversions), per spec instruction
to "do the conversion in code from the CSV": altitude x3.28084 = ft,
pressure x0.0208854 = lb/ft^2, temperature x1.8 = deg R, speed of sound
x3.28084 = ft/s, density x0.00194032 = slug/ft^3.
"""

import csv
import os
from typing import Dict, List

import config


class MarsEnvironmentNotReady(RuntimeError):
    """Raised when the atmosphere CSV isn't present yet."""


def _load_atmosphere_table_english() -> List[Dict[str, float]]:
    """Read config.MARS_ATMOSPHERE_CSV (Altitude_m, Pressure_Pa,
    Temperature_K, SpeedOfSound_mps, Density_kgm3, [MolWeight, GasLawError
    -- ignored]), convert to English units using the spec's own stated
    factors, sorted by altitude."""
    rows = []
    with open(config.MARS_ATMOSPHERE_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            alt_m, pres_pa, temp_k, cs_mps, dens_kgm3 = (float(x) for x in row[:5])
            rows.append({
                "alt_ft": alt_m * config.SPEC_M_TO_FT,
                "pres_lbft2": pres_pa * config.SPEC_PA_TO_LBFT2,
                "temp_r": temp_k * config.SPEC_K_TO_RANKINE,
                "cs_fts": cs_mps * config.SPEC_M_TO_FT,  # same factor, m/s -> ft/s
                "dens_slugft3": dens_kgm3 * config.SPEC_KGM3_TO_SLUGFT3,
            })
    rows.sort(key=lambda r: r["alt_ft"])
    if len(rows) != 146:
        raise MarsEnvironmentNotReady(
            f"Expected 146 rows in {config.MARS_ATMOSPHERE_CSV} per spec, got {len(rows)}. "
            "Stop and report to the author rather than silently proceeding (do not thin the table)."
        )
    return rows


def _format_table(name: str, alt_value_pairs, interp: str) -> str:
    """Manual-confirmed table syntax: NAME = "label" monovar GDALT 0
    <interp> xtrap alt1 val1 alt2 val2 ... (space-separated, no commas,
    double-quoted label). Wrapped across lines for readability only --
    whitespace/newlines are equivalent to POST2's free-form parser."""
    header = f'{name} = "{name}" monovar GDALT 0 {interp} xtrap'
    tokens = [f"{alt:.2f} {val:.6g}" for alt, val in alt_value_pairs]
    lines = [header]
    for i in range(0, len(tokens), 4):
        lines.append(" ".join(tokens[i:i + 4]))
    return "\n".join(lines)


def build_environment_block(wind_speed_mps: float, wind_direction_deg: float) -> List[str]:
    """
    Return the list of POST2 input lines for the Mars atmosphere + wind
    model. Raises MarsEnvironmentNotReady if the atmosphere CSV isn't
    present at config.MARS_ATMOSPHERE_CSV yet.
    """
    if not os.path.exists(config.MARS_ATMOSPHERE_CSV):
        raise MarsEnvironmentNotReady(
            f"{config.MARS_ATMOSPHERE_CSV} not found. The atmosphere/wind "
            "table SYNTAX is confirmed (see this module's docstring) -- the "
            "only thing missing is the data file itself. Place the "
            "146-row Mars-GRAM CSV (Gale Crater) at that path and re-run."
        )

    table = _load_atmosphere_table_english()
    prest_pairs = [(r["alt_ft"], r["pres_lbft2"]) for r in table]
    atemt_pairs = [(r["alt_ft"], r["temp_r"]) for r in table]
    cst_pairs = [(r["alt_ft"], r["cs_fts"]) for r in table]
    denst_pairs = [(r["alt_ft"], r["dens_slugft3"]) for r in table]

    wind_speed_fts = wind_speed_mps * config.SPEC_M_TO_FT
    alt_min_ft = table[0]["alt_ft"]
    alt_max_ft = table[-1]["alt_ft"]

    lines = [
        "npc(5) = 1,           // general/tabular atmosphere (CONFIRMED, manual 6.a.4)",
        "atmosk(1) = 1.0,  atmosk(2) = 1.0,   // CONFIRMED defaults; CST/DENST supplied explicitly",
        _format_table("PREST", prest_pairs, "log_inp"),
        _format_table("ATEMT", atemt_pairs, "lin_inp"),
        _format_table("CST", cst_pairs, "lin_inp"),
        _format_table("DENST", denst_pairs, "log_inp"),
        "npc(6) = 1,           // winds from VWT/AZW_T/VWWT tables (CONFIRMED, manual 6.a.4)",
        f'VWT = "wind speed" monovar GDALT 0 lin_inp xtrap {alt_min_ft:.1f} {wind_speed_fts:.4f} {alt_max_ft:.1f} {wind_speed_fts:.4f}',
        f'AZW_T = "wind azimuth" monovar GDALT 0 lin_inp xtrap {alt_min_ft:.1f} {wind_direction_deg:.4f} {alt_max_ft:.1f} {wind_direction_deg:.4f}',
        f'VWWT = "vertical wind" monovar GDALT 0 lin_inp xtrap {alt_min_ft:.1f} 0.0 {alt_max_ft:.1f} 0.0',
        "// AZWB left at its CONFIRMED default (180.0): AZW_T is meteorological,",
        "// 0 deg = wind blowing FROM the north (see module docstring).",
    ]
    return lines
