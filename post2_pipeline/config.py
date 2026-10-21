"""
Phase 0 configuration (spec v3): grid definition, physical constants, and
paths. Single place to edit before a run.

UNIT SYSTEM: per the spec's manual-confirmed IOFLAG section, this deck
uses IOFLAG = 0 (English units) throughout -- input units cannot be mixed
within a problem. All POST2-input-facing constants below are in English
units (ft, ft/s, ft^3/s^2, lbf, degrees R, lb/ft^2, slug/ft^3). Grid
parameters the rest of the pipeline reasons about (diameter, mass,
ballistic coefficient) stay in metric/SI, matching the rest of the
project's reporting (e.g. MSL's published beta ~145 kg/m^2) -- conversion
to English units happens only where a value is actually written into the
.inp deck (see generate_input.py) or where POST2's English-unit output is
read back (see parse_output.py).
"""

import os

# ---------------------------------------------------------------------------
# Unit conversion factors
# ---------------------------------------------------------------------------
# Spec-specified factors (used for the atmosphere CSV conversion, per spec's
# own stated conversion instructions -- used exactly as given):
SPEC_M_TO_FT = 3.28084
SPEC_PA_TO_LBFT2 = 0.0208854
SPEC_K_TO_RANKINE = 1.8
SPEC_KGM3_TO_SLUGFT3 = 0.00194032

# Precise standard conversions (used elsewhere -- entry state, gravity
# constants, vehicle sref/lref/weight -- where the spec didn't give its
# own explicit factor):
M_PER_FT = 0.3048               # exact, SI-defined
FT_PER_M = 1.0 / M_PER_FT
FT2_PER_M2 = 1.0 / (M_PER_FT ** 2)
KG_TO_LBF = 2.2046226218487757  # weight of 1 kg at standard gravity, in lbf
N_PER_LBF = 4.4482216152605

G0_SI = 9.80665                 # standard g, m/s^2
G0_ENGLISH = G0_SI / M_PER_FT   # standard g, ft/s^2 (~32.174049)

# ---------------------------------------------------------------------------
# POST2 executable (LOCAL WINDOWS MACHINE ONLY)
# ---------------------------------------------------------------------------
POST2_EXE = os.environ.get(
    "POST2_EXE",
    r"C:\Users\Faris Fatouh\Downloads\ALLPOST2FILES\POST2v500\post2_windows_commercial.exe",
)

OUTPUT_ROOT = os.environ.get("POST2_PIPELINE_OUTPUT", "results")
REFERENCE_PROBLEM1A_INP = r"..\problem1a.inp"
REFERENCE_PROBLEM1A_OUT = r"..\problem1a.out"

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
DATA_DIR = os.environ.get("POST2_PIPELINE_DATA", "data")
MARS_ATMOSPHERE_CSV = os.path.join(DATA_DIR, "mars_atmosphere_gale.csv")
MSL_CD_DIGITIZED_CSV = os.path.join(DATA_DIR, "msl_CD_vs_Mach_digitized.csv")

# ---------------------------------------------------------------------------
# IOFLAG -- CONFIRMED from the POST2 v5.0.0 manual (sections 4.a, 6.a.4):
# IOFLAG must not change within a problem. The entry state and planet
# constants here are sourced in English units, so English (IOFLAG=0) is
# used throughout, not metric (IOFLAG=3, used in Examples 1A/1B).
# ---------------------------------------------------------------------------
IOFLAG = 0

# ---------------------------------------------------------------------------
# Mars physical constants -- English units, per spec table (sourced from
# Mars-GRAM documentation for MU/radii/J2; standard Mars sidereal day for
# OMEGA). RE_GRAV PENDING verification (spec: "likely equal to RE").
# ---------------------------------------------------------------------------
MU_MARS_FT3_S2 = 1.5125e15        # ft^3/s^2 (42,828.37 km^3/s^2)
RE_MARS_FT = 1.1142356e7          # ft (3,396.19 km)
RP_MARS_FT = 1.1076772e7          # ft (3,376.20 km)
OMEGA_MARS = 7.088218e-5          # rad/s (time-based, unit-system-independent)
J2_MARS = 1.96045e-3
J3_MARS = J4_MARS = J5_MARS = J6_MARS = J7_MARS = J8_MARS = 0.0
RE_GRAV_MARS_FT = RE_MARS_FT      # PENDING verify -- spec says "likely equal to RE"

# NPC(16) gravity-model option. NOT explicitly confirmed in the manual
# quote the spec provided (unlike IOFLAG/atmosphere/wind) -- reusing
# npc(16)=2 ("oblate planet model"), the flag validated against Earth in
# Examples 1A/1B, where it printed back RE/RE_GRAV/RP/OMEGA/MU/J2..J8
# exactly as given, which is the mechanism the spec asks for ("choose the
# option that actually uses these constants").
NPC16_GRAVITY_MODEL_OPTION = 2

# ---------------------------------------------------------------------------
# Fixed entry state (IDENTICAL for all 32 runs -- do not vary per scenario)
# Source: Brandenburg, Williams, Woffinden, Putnam, "Demonstration of
# Linear Covariance Analysis Techniques..." (NASA JSC/UIUC), Table 1
# ("MSL Entry Interface State"). Values given directly in English units by
# the spec are used verbatim (not re-derived from the metric figures).
# ---------------------------------------------------------------------------
EI_ALTITUDE_FT = 436352.0          # 133.0 km; NOT 125 km -- see spec note
EI_GDLAT_DEG = -3.9186             # geodetic latitude (paper Table 1)
EI_GCLAT_DEG = -3.872746729711164  # PENDING verification: geocentric-latitude
                                    # equivalent of GDLAT above, via
                                    # tan(gclat) = (1-f)^2 tan(gdlat) with
                                    # Mars flattening f = (RE-RP)/RE =
                                    # 0.0058860 (unit-independent ratio).
                                    # The validated npc(4)=2 input keyword
                                    # from Examples 1A/1B is GCLAT
                                    # (geocentric); the spec's sourced value
                                    # is GDLAT (geodetic). Verify against the
                                    # manual whether npc(4)=2 wants geocentric
                                    # latitude, or whether a geodetic option
                                    # exists -- if so, use EI_GDLAT_DEG directly.
EI_LONG_DEG = 126.72               # +126.72 E (spec resolves the paper's
                                    # apparent sign error -- see spec note)
EI_VELI_FTS = 19948.0              # INERTIAL velocity (6.08 km/s)
EI_GAMMAI_DEG = -15.489            # INERTIAL flight path angle
EI_AZVELI_DEG = 93.2065            # INERTIAL heading

GALE_TOUCHDOWN_LAT_DEG = -4.59
GALE_TOUCHDOWN_LON_DEG = 137.44

# Local terrain height at Gale Crater relative to the MOLA areoid, in both
# units (metric for the rest of the pipeline's bookkeeping, English for
# anything written into the deck). Not corrected for the ~0.43 km
# areoid-to-ellipsoid offset, per spec -- do not "fix".
GALE_SURFACE_GDALT_M = -3755.0
GALE_SURFACE_GDALT_FT = -12319.5542

ATMOSPHERE_TABLE_MIN_GDALT_M = -5000.0
ATMOSPHERE_TABLE_MAX_GDALT_M = 140_000.0
ATMOSPHERE_TABLE_MIN_GDALT_FT = -16404.2
ATMOSPHERE_TABLE_MAX_GDALT_FT = 459317.6
ATMOSPHERE_TABLE_GAMMA = 1.30  # assumed, used by the author to compute the CSV's speed-of-sound column

# ---------------------------------------------------------------------------
# Event sequence (Mach-triggered; see spec "Event Sequence and End Condition")
# ---------------------------------------------------------------------------
CHUTE_DEPLOY_MACH = 1.7
HEATSHIELD_SEP_MACH = 0.7

HANDOFF_ALTITUDE_ABOVE_SURFACE_M = 1700.0
HANDOFF_ALTITUDE_ABOVE_SURFACE_FT = 5577.428
HANDOFF_GDALT_M = GALE_SURFACE_GDALT_M + HANDOFF_ALTITUDE_ABOVE_SURFACE_M       # -2055.0
HANDOFF_GDALT_FT = GALE_SURFACE_GDALT_FT + HANDOFF_ALTITUDE_ABOVE_SURFACE_FT    # -6742.13
HANDOFF_REFERENCE_VELOCITY_MPS = 78.9  # Fig. 2 labeled value, surface-relative

# Bank angle -- AUTHOR DECISION (not sourced from MSL literature), fixed
# for the whole entry phase, chosen 2025-10 after bank_sweep.py's 0/15/30/
# 45/60/70 deg comparison against the MSL reference (Karlgaard et al.:
# Mach 1.7 at ~12.1 km above ground / ~E+259 s, no skip, handoff at
# 78.9 m/s). No fixed angle in the sweep fully matched the reference
# (MSL flew a time-varying, closed-loop bank profile, not a fixed angle),
# so this is an explicit simplification, not a sourced value. 60 deg was
# the best available compromise: closest Mach-1.7 timing to MSL's ~E+259s
# (240.3 s) among angles that also meaningfully reduced the skip (max
# altitude after peak deceleration: 33.6 km at 0 deg -> 20.7 km at 60 deg,
# vs. 20.0 km at 70 deg for comparison). Sign convention (manual: positive
# BNKANG banks right) still PENDING -- doesn't affect vertical-plane
# results (peak g, skip, Mach-1.7/handoff state), only lateral drift.
# See README "Bank angle (BNKPC/BNKANG)" for the full sweep table.
BANK_ANGLE_DEG = 60.0

# ---------------------------------------------------------------------------
# Mass model (metric -- mass itself is never a direct POST2 input; only
# the derived WEIGHT, converted to lbf at deck-generation time, is).
# ---------------------------------------------------------------------------
FIXED_VEHICLE_MASS_KG = 2358.0
HEATSHIELD_DROP_MASS_KG = 385.0   # author assumption, NOT sourced -- see README
PARACHUTE_MASS_KG = 46.826        # included within FIXED_VEHICLE_MASS_KG already

# ---------------------------------------------------------------------------
# Parachute scaling (metric -- see aero_data.py; the scaling RATIO is
# unit-independent, so this stays in SI for simplicity. Only the final
# SREF used in the deck needs an English-unit conversion, done in
# generate_input.py.)
# ---------------------------------------------------------------------------
MSL_CHUTE_REFERENCE_MASS_KG = 3257.0
MSL_CHUTE_REFERENCE_AREA_M2 = 357.94
CHUTE_OPENING_LOAD_FACTOR = 1.407
CHUTE_INFLATION_TIME_S = 2.0


def chute_area_m2(total_mass_kg: float) -> float:
    return MSL_CHUTE_REFERENCE_AREA_M2 * (total_mass_kg / MSL_CHUTE_REFERENCE_MASS_KG)


def chute_diameter_m(total_mass_kg: float) -> float:
    import math
    return math.sqrt(4.0 * chute_area_m2(total_mass_kg) / math.pi)


# ---------------------------------------------------------------------------
# Parameter grid (Phase 0: exactly one run per cell, 32 total) -- metric,
# matching the rest of the project's reporting.
# ---------------------------------------------------------------------------
RIGID_DIAMETERS_M = [3.0, 3.5, 4.0, 4.5]
INFLATABLE_DIAMETERS_M = [6.0, 9.0, 12.0, 15.0]
PAYLOAD_MASSES_KG = [900.0, 1800.0, 2700.0, 3600.0]

DESIGNS = {
    "rigid": {"diameters_m": RIGID_DIAMETERS_M},
    "inflatable": {"diameters_m": INFLATABLE_DIAMETERS_M},
}

# ---------------------------------------------------------------------------
# Fixed-wind test conditions (Phase 0: same for all 32 runs) -- CONFIRMED
# from the manual: NPC(6)=1, azimuth bias AZWB defaults to 180.0, meaning
# AZW_T is meteorological (0 deg = wind blowing FROM the north). Author
# said "0 degrees"; under this convention that means a wind from the
# north. If a different direction was meant, change WIND_DIRECTION_DEG only.
# ---------------------------------------------------------------------------
WIND_SPEED_MPS = 10.0
WIND_DIRECTION_DEG = 0.0  # meteorological convention (FROM the north) -- see above

# ---------------------------------------------------------------------------
# Readiness gates
# ---------------------------------------------------------------------------
# Atmosphere/wind table SYNTAX is now confirmed (see mars_environment.py);
# this flag now gates only on the DATA FILE actually being present.
MARS_ATMOSPHERE_READY = os.path.exists(MARS_ATMOSPHERE_CSV)

# Readiness gate for the real digitized CD/L-D table. False until
# MSL_CD_DIGITIZED_CSV exists and aero_data.py has been updated to read it
# instead of using the placeholder L/D interpolation.
AERO_DATA_FROM_DIGITIZED_FILE = os.path.exists(MSL_CD_DIGITIZED_CSV)
