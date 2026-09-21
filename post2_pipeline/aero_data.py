"""
Representative CD/CL-vs-Mach tables for the two Phase 0 vehicle configs.

THESE ARE PLACEHOLDER, LITERATURE-REPRESENTATIVE VALUES, NOT MISSION DATA.
They exist to (a) exercise the POST2 table-input pipeline end-to-end and
(b) land approximately on MSL's known values at the 900 kg / 4.5 m rigid
grid cell as a sanity check:
    - ballistic coefficient  ~145 kg/m^2
    - L/D                    ~0.24
Replace with mentor/mission-provided tables before treating results as
science-grade.

Rigid (70-deg sphere-cone, MSL/Viking heritage):
  CD is the vehicle's *trimmed axial-force coefficient* (~1.42 hypersonic),
  not the higher (~1.7) zero-angle-of-attack symmetric pressure-drag
  estimate -- MSL flew at a ~16 deg trim angle of attack for lift, and its
  published ballistic coefficient (~145 kg/m^2) is computed from that lower
  trimmed CA. Using 1.42 here is what makes the 900 kg / 4.5 m baseline
  cell reproduce MSL's ~145 kg/m^2 BC (verified: entry_mass=3260.6 kg,
  sref=15.90 m^2, CD=1.42 -> BC=144.4 kg/m^2). CL is derived as a constant
  L/D = 0.24 (MSL's actual trimmed hypersonic L/D, held constant across the
  table for Phase 0 simplicity -- documented, not physical across the
  whole Mach range).

Inflatable (HIAD, blunt-cone):
  A separate, somewhat higher-CD table (HIADs are bluffer than a rigid
  capsule of the same diameter) and CL = 0 throughout -- HIAD concepts in
  the literature are typically flown ballistic (axisymmetric, non-lifting),
  which this pipeline adopts as a Phase 0 simplification.
"""

from typing import List, Tuple

RIGID_L_OVER_D = 0.24

# (Mach, CD) pairs, representative 70-deg sphere-cone TRIMMED axial-force
# drag polar (see module docstring for why hypersonic CD=1.42, not 1.7).
RIGID_CD_TABLE: List[Tuple[float, float]] = [
    (0.0, 0.75),
    (0.2, 0.78),
    (0.4, 0.85),
    (0.6, 1.00),
    (0.8, 1.25),
    (0.9, 1.38),
    (1.0, 1.42),   # transonic drag-rise peak (muted vs. symmetric case)
    (1.2, 1.40),
    (1.5, 1.38),
    (2.0, 1.36),
    (2.5, 1.38),
    (3.0, 1.40),
    (4.0, 1.41),
    (5.0, 1.42),
    (10.0, 1.42),
    (30.0, 1.42),
]

# (Mach, CD) pairs, representative HIAD blunt-cone drag polar.
INFLATABLE_CD_TABLE: List[Tuple[float, float]] = [
    (0.0, 0.92),
    (0.2, 0.95),
    (0.4, 1.05),
    (0.6, 1.25),
    (0.8, 1.50),
    (1.0, 1.70),   # transonic drag-rise peak
    (1.2, 1.65),
    (1.5, 1.55),
    (2.0, 1.50),
    (3.0, 1.58),
    (5.0, 1.63),
    (10.0, 1.65),
    (30.0, 1.65),
]


def _format_monovar_table(name: str, pairs: List[Tuple[float, float]]) -> str:
    """Render a POST2 monovariate (vs. Mach) table in the same
    'name', monovar, mach, 0, lin_inp, xtrap, m1, v1, m2, v2, ... syntax
    validated in Examples 1A/1B."""
    header = f"{name} = '{name}', monovar, mach, 0, lin_inp, xtrap,"
    # Every individual value gets its own trailing comma (matching the
    # validated 1A/1B table style: "0.0, 0.23,  0.3, 0.22,  0.6, 0.21,"),
    # not just the last one on a wrapped line.
    body_values = [f"{mach}, {value:.4f}," for mach, value in pairs]
    # Wrap 4 pairs per line for readability, matching the manual's style.
    lines = [header]
    for i in range(0, len(body_values), 4):
        lines.append("  ".join(body_values[i:i + 4]))
    return "\n".join(lines)


def cd_table_lines(design: str) -> str:
    table = RIGID_CD_TABLE if design == "rigid" else INFLATABLE_CD_TABLE
    return _format_monovar_table("cdt", table)


def cl_table_lines(design: str) -> str:
    if design == "rigid":
        cl_table = [(m, round(cd * RIGID_L_OVER_D, 4)) for m, cd in RIGID_CD_TABLE]
        return _format_monovar_table("clt", cl_table)
    # Inflatable: ballistic, no lift.
    return "clt = 'clt', constant, 0, 0.0,"


def entry_cd_reference(design: str) -> float:
    """Hypersonic (entry) CD value used for the ballistic-coefficient
    calculation reported per scenario -- the conventional choice when
    quoting a single BC number for an entry vehicle."""
    table = RIGID_CD_TABLE if design == "rigid" else INFLATABLE_CD_TABLE
    return table[-1][1]  # highest-Mach (hypersonic) entry
