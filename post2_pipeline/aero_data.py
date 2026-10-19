"""
Aerodynamic tables for the Phase 0 spec v2: ONE shared CD-vs-Mach table and
ONE shared L/D-vs-Mach table for both the rigid and inflatable designs
(the spec is explicit that this is a deliberate study decision, not an
oversight -- CD depends on shape, not size, so only SREF differs between
scenarios), plus a parachute CD-vs-Mach table used after chute deployment.

STATUS:
  - Body CD-vs-Mach table: SUPPLIED BY THE AUTHOR (spec's own table,
    digitized from Schoenenberger et al., AAS 13-306). Used as given.
  - L/D-vs-Mach table: the spec's markdown only gives two prose endpoints
    (~0.29 near Mach 2, ~0.24 near Mach 25) -- the real per-Mach values
    live in msl_CD_vs_Mach_digitized.csv, which has NOT been supplied yet.
    PLACEHOLDER: linear interpolation between the two cited endpoints.
    Replace once the CSV exists (config.AERO_DATA_FROM_DIGITIZED_FILE).
  - Chute CD-vs-Mach table: the spec describes Fig. 9's "Nominal" curve in
    prose only (4 points) and explicitly asks for it to be digitized from
    the actual figure and shown to the author before the real grid runs.
    PLACEHOLDER: a 4-point table built from that prose description only --
    NOT a true digitization of Fig. 9. Must not be treated as final.
"""

import csv
import math
import os
from typing import List, Tuple

import config

# ---------------------------------------------------------------------------
# Body CD-vs-Mach (SUPPLIED BY THE AUTHOR -- Schoenenberger et al., AAS
# 13-306, digitized; reference area 15.904 m^2 / 4.5 m diameter, i.e.
# diameter-based, matching SREF = pi*(d/2)^2 used here).
#
# Flat-hold regions (Mach < 2.06 held at 1.464; Mach > 25 held at 1.460)
# are implemented as literal repeated-value table points rather than
# relying on POST2's "xtrap" extrapolation behavior, whose exact semantics
# (flat hold vs. slope continuation) haven't been confirmed against the
# manual. Two equal-valued points bracketing the real data force a flat
# segment under linear interpolation regardless of xtrap's behavior
# outside the table.
# ---------------------------------------------------------------------------
_DIGITIZED_CD_TABLE: List[Tuple[float, float]] = [
    (2.06, 1.464), (2.27, 1.418), (2.5, 1.407), (2.8, 1.384),
    (3.0, 1.384), (3.5, 1.385), (4.0, 1.374), (5.0, 1.384),
    (6.0, 1.390), (7.0, 1.390), (8.0, 1.392), (8.9, 1.402),
    (9.9, 1.407), (12.0, 1.418), (14.0, 1.433), (16.0, 1.446),
    (18.1, 1.454), (20.0, 1.459), (22.5, 1.459), (25.0, 1.460),
]
CD_LOW_MACH_HOLD = 1.464   # held constant for all Mach < 2.06
CD_HIGH_MACH_HOLD = 1.460  # held constant for all Mach > 25

BODY_CD_TABLE: List[Tuple[float, float]] = (
    [(0.0, CD_LOW_MACH_HOLD), (config.CHUTE_DEPLOY_MACH, CD_LOW_MACH_HOLD)]
    + _DIGITIZED_CD_TABLE
    + [(30.0, CD_HIGH_MACH_HOLD)]
)

# ---------------------------------------------------------------------------
# L/D-vs-Mach (PLACEHOLDER -- see module docstring)
# ---------------------------------------------------------------------------
LD_AT_MACH_2 = 0.29   # spec prose: "about 0.29 near Mach 2"
LD_AT_MACH_25 = 0.24  # spec prose: "about 0.24 at Mach 25"
LD_ANCHOR_MACH_LOW = 2.06
LD_ANCHOR_MACH_HIGH = 25.0


def _placeholder_ld(mach: float) -> float:
    """Linear interpolation between the two spec-cited endpoints.
    PLACEHOLDER pending msl_CD_vs_Mach_digitized.csv -- see module docstring."""
    if mach <= LD_ANCHOR_MACH_LOW:
        return LD_AT_MACH_2
    if mach >= LD_ANCHOR_MACH_HIGH:
        return LD_AT_MACH_25
    frac = (mach - LD_ANCHOR_MACH_LOW) / (LD_ANCHOR_MACH_HIGH - LD_ANCHOR_MACH_LOW)
    return LD_AT_MACH_2 + frac * (LD_AT_MACH_25 - LD_AT_MACH_2)


# CL table built at the same Mach points as the CD table so CL = CD*(L/D)
# stays internally consistent at every tabulated point. Zero lift below
# Mach 2.06 (spec: balance masses jettisoned near Mach 2.0, "from Mach 2.06
# downward there is NO lift").
BODY_CL_TABLE: List[Tuple[float, float]] = [(0.0, 0.0), (config.CHUTE_DEPLOY_MACH, 0.0)]
for _mach, _cd in _DIGITIZED_CD_TABLE:
    BODY_CL_TABLE.append((_mach, round(_cd * _placeholder_ld(_mach), 4)))
BODY_CL_TABLE.append((30.0, round(CD_HIGH_MACH_HOLD * LD_AT_MACH_25, 4)))

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
    calculation reported per scenario."""
    return CD_HIGH_MACH_HOLD


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
    import config

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


def load_digitized_csv_if_available() -> bool:
    """If msl_CD_vs_Mach_digitized.csv now exists, this is where it would
    be read to replace the placeholder L/D table above. Not implemented
    yet -- returns False (placeholder still in use) until
    config.AERO_DATA_FROM_DIGITIZED_FILE is wired up to this function.
    Deliberately not auto-loading on import: using the real file should be
    an explicit, visible step, not something that silently changes
    behavior between runs depending on whether a file happens to exist."""
    return os.path.exists(config.MSL_CD_DIGITIZED_CSV) and config.AERO_DATA_FROM_DIGITIZED_FILE
