"""
Aerodynamic tables for Phase 0: ONE shared CD-vs-Mach table and ONE shared
L/D-vs-Mach table for both the rigid and inflatable designs (the spec is
explicit that this is a deliberate study decision, not an oversight -- CD
depends on shape, not size, so only SREF differs between scenarios), plus
a parachute CD-vs-Mach table used after chute deployment.

STATUS:
  - Body CD-vs-Mach AND L/D-vs-Mach: loaded directly from the real
    `data/msl_CD_vs_Mach_digitized.csv` (195 rows, Mach 2.0599-25.5634,
    columns Mach_approx/velocity_mps/CA/alpha_deg/L_over_D/CD), digitized
    from Schoenenberger et al., AAS 13-306. Used as given -- per spec,
    "Read the file; do not retype values." The file's own actual first/
    last points (not the spec markdown's rounded 2.06/1.464 and
    25.0/1.460 summary values) are used for the flat-hold boundary
    regions below, since the file supersedes the inline summary table.
    Falls back to a hardcoded transcription of the spec's summary table
    (CD only) + a 2-point L/D interpolation if the CSV isn't present --
    should not be needed now that the file exists, kept for robustness.
  - Chute CD-vs-Mach table: the spec describes Fig. 9's "Nominal" curve in
    prose only (4 points) and explicitly asks for it to be digitized from
    the actual figure and shown to the author before the real grid runs.
    PLACEHOLDER: a 4-point table built from that prose description only --
    NOT a true digitization of Fig. 9, and NOT supplied as a file yet.
    Must not be treated as final.
"""

import csv
import os
from typing import List, Tuple

import config

CHUTE_DEPLOY_MACH = config.CHUTE_DEPLOY_MACH  # 1.7, local alias for readability


def _load_digitized_table() -> List[Tuple[float, float, float]]:
    """Read data/msl_CD_vs_Mach_digitized.csv, skipping '#' comment lines.
    Returns (mach, cd, l_over_d) tuples sorted by Mach."""
    rows = []
    with open(config.MSL_CD_DIGITIZED_CSV, newline="") as f:
        lines = [line for line in f if not line.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    for row in reader:
        rows.append((
            float(row["Mach_approx"]),
            float(row["CD"]),
            float(row["L_over_D"]),
        ))
    rows.sort(key=lambda r: r[0])
    return rows


def _build_body_tables() -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], float]:
    """Returns (cd_table, cl_table, hypersonic_cd_reference)."""
    if config.AERO_DATA_FROM_DIGITIZED_FILE and os.path.exists(config.MSL_CD_DIGITIZED_CSV):
        digitized = _load_digitized_table()
        mach_lo, cd_lo, ld_lo = digitized[0]
        mach_hi, cd_hi, ld_hi = digitized[-1]

        cd_table = (
            [(0.0, cd_lo), (CHUTE_DEPLOY_MACH, cd_lo)]
            + [(m, cd) for m, cd, _ in digitized]
            + [(mach_hi + 5.0, cd_hi)]
        )
        cl_table = (
            [(0.0, 0.0), (CHUTE_DEPLOY_MACH, 0.0)]
            + [(m, round(cd * ld, 4)) for m, cd, ld in digitized]
            + [(mach_hi + 5.0, round(cd_hi * ld_hi, 4))]
        )
        return cd_table, cl_table, cd_hi

    # Fallback: spec markdown's rounded summary table (CD only) + a
    # 2-point L/D interpolation between the prose-cited endpoints. Should
    # not be reached now that msl_CD_vs_Mach_digitized.csv is present.
    fallback_cd = [
        (2.06, 1.464), (2.27, 1.418), (2.5, 1.407), (2.8, 1.384),
        (3.0, 1.384), (3.5, 1.385), (4.0, 1.374), (5.0, 1.384),
        (6.0, 1.390), (7.0, 1.390), (8.0, 1.392), (8.9, 1.402),
        (9.9, 1.407), (12.0, 1.418), (14.0, 1.433), (16.0, 1.446),
        (18.1, 1.454), (20.0, 1.459), (22.5, 1.459), (25.0, 1.460),
    ]
    cd_lo, cd_hi = 1.464, 1.460

    def placeholder_ld(mach):
        if mach <= 2.06:
            return 0.29
        if mach >= 25.0:
            return 0.24
        frac = (mach - 2.06) / (25.0 - 2.06)
        return 0.29 + frac * (0.24 - 0.29)

    cd_table = [(0.0, cd_lo), (CHUTE_DEPLOY_MACH, cd_lo)] + fallback_cd + [(30.0, cd_hi)]
    cl_table = (
        [(0.0, 0.0), (CHUTE_DEPLOY_MACH, 0.0)]
        + [(m, round(cd * placeholder_ld(m), 4)) for m, cd in fallback_cd]
        + [(30.0, round(cd_hi * 0.24, 4))]
    )
    return cd_table, cl_table, cd_hi


BODY_CD_TABLE, BODY_CL_TABLE, _ENTRY_CD_REFERENCE = _build_body_tables()

# ---------------------------------------------------------------------------
# Parachute CD-vs-Mach (PLACEHOLDER -- see module docstring. NOT a true
# digitization of Cruz et al. Fig. 9; built only from the 4 points
# described in the spec's prose. Must be replaced with a real digitization
# and shown to the author before the real (non-Phase-0-validation) grid
# runs, per the spec.)
# ---------------------------------------------------------------------------
CHUTE_CD_TABLE: List[Tuple[float, float]] = [
    (0.0, 0.62),
    (0.8, 0.62),
    (0.95, 0.49),
    (1.5, 0.75),
    (2.6, 0.47),
    (5.0, 0.47),  # held flat beyond the described range; chute never
                  # operates above Mach 1.7 (deploy trigger) in practice
]


def _format_monovar_table(name: str, pairs: List[Tuple[float, float]]) -> str:
    """Render a POST2 monovariate (vs. Mach) table, matching the comma-
    per-value style validated in Examples 1A/1B."""
    header = f"{name} = '{name}', monovar, mach, 0, lin_inp, xtrap,"
    body_values = [f"{mach}, {value:.4f}," for mach, value in pairs]
    lines = [header]
    for i in range(0, len(body_values), 4):
        lines.append("  ".join(body_values[i:i + 4]))
    return "\n".join(lines)


def cd_table_lines() -> str:
    return _format_monovar_table("cdt", BODY_CD_TABLE)


def cl_table_lines() -> str:
    return _format_monovar_table("clt", BODY_CL_TABLE)


def chute_cd_table_lines() -> str:
    return _format_monovar_table("cdt", CHUTE_CD_TABLE)


def entry_cd_reference() -> float:
    """Hypersonic (high-Mach) CD, used for the ballistic-coefficient
    calculation reported per scenario -- the real digitized file's own
    highest-Mach value (Mach 25.5634 -> CD 1.4544) when available."""
    return _ENTRY_CD_REFERENCE


def _table_lookup(table: List[Tuple[float, float]], mach: float) -> float:
    """Linear interp, flat-held at the ends -- mirrors POST2's own
    monovar/lin_inp/xtrap table lookup for a (mach, value) table."""
    if mach <= table[0][0]:
        return table[0][1]
    if mach >= table[-1][0]:
        return table[-1][1]
    for (m0, c0), (m1, c1) in zip(table, table[1:]):
        if m0 <= mach <= m1:
            if m1 == m0:
                return c0
            frac = (mach - m0) / (m1 - m0)
            return c0 + frac * (c1 - c0)
    return table[-1][1]


def chute_cd_at_mach(mach: float) -> float:
    return _table_lookup(CHUTE_CD_TABLE, mach)


def body_cd_at_mach(mach: float) -> float:
    return _table_lookup(BODY_CD_TABLE, mach)


def combined_post_chute_cd_table(
    chute_area_m2: float, body_sref_m2: float
) -> List[Tuple[float, float]]:
    """
    Post-chute-deployment drag = chute drag (referenced to S0) + body drag
    (referenced to the body's own SREF), per spec ("Drag after chute
    deployment: chute drag PLUS body drag"). POST2's cdt/clt mechanism
    takes one CD value applied to one declared SREF per phase, so this
    folds both contributions into a single effective CD table referenced
    to body_sref_m2:

        CD_effective(mach) * body_sref = chute_CD(mach) * S0
                                        + body_CD(mach) * body_sref
        CD_effective(mach) = body_CD(mach) + chute_CD(mach) * (S0 / body_sref)

    Built over the union of both source tables' Mach breakpoints (clipped
    to the relevant <= chute-deploy-Mach range), each evaluated via linear
    interpolation. S0 and body_sref are both fixed per scenario, so this
    table only needs to be built once per scenario, not per Mach sample.
    """
    ratio = chute_area_m2 / body_sref_m2
    breakpoints = sorted(
        {m for m, _ in CHUTE_CD_TABLE if m <= config.CHUTE_DEPLOY_MACH}
        | {m for m, _ in BODY_CD_TABLE if m <= config.CHUTE_DEPLOY_MACH}
    )
    table = [
        (m, round(body_cd_at_mach(m) + chute_cd_at_mach(m) * ratio, 4))
        for m in breakpoints
    ]
    return table


def combined_post_chute_cd_table_lines(chute_area_m2: float, body_sref_m2: float) -> str:
    table = combined_post_chute_cd_table(chute_area_m2, body_sref_m2)
    return _format_monovar_table("cdt", table)
