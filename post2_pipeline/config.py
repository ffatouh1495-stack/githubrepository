"""
Phase 0 configuration (spec v2): grid definition, physical constants, and
paths. Single place to edit before a run.

Values here are sourced per the Phase 0 build spec ("phase0_spec_for_claude_code.md").
Where the spec marks something "DECIDED BY THE AUTHOR" or gives an exact
figure, it's used verbatim. Anything still needing POST2-manual
verification or a not-yet-supplied data file is marked PENDING below and
in mars_environment.py.
"""

import os

# ---------------------------------------------------------------------------
# POST2 executable (LOCAL WINDOWS MACHINE ONLY)
# ---------------------------------------------------------------------------
POST2_EXE = os.environ.get(
    "POST2_EXE",
    r"C:\Users\Faris Fatouh\Downloads\ALLPOST2FILES\POST2v500\post2_windows_commercial.exe",
)

OUTPUT_ROOT = os.environ.get("POST2_PIPELINE_OUTPUT", "results")

# Reference files that should exist alongside POST2 on the Windows machine,
# per the spec -- used to validate the pipeline before the 32-run grid.
# "Use these as references for input-file format, and confirm your
# pipeline can reproduce the problem1a result before building the grid
# runs" -- that reproduction step still needs to happen on the Windows
# machine; this pipeline doesn't do it automatically.
REFERENCE_PROBLEM1A_INP = r"..\problem1a.inp"  # relative to POST2 folder
REFERENCE_PROBLEM1A_OUT = r"..\problem1a.out"

# ---------------------------------------------------------------------------
# Data files (PENDING -- "the author will supply it"; not yet in this repo)
# ---------------------------------------------------------------------------
DATA_DIR = os.environ.get("POST2_PIPELINE_DATA", "data")
MARS_ATMOSPHERE_CSV = os.path.join(DATA_DIR, "mars_atmosphere_gale.csv")
MSL_CD_DIGITIZED_CSV = os.path.join(DATA_DIR, "msl_CD_vs_Mach_digitized.csv")

# ---------------------------------------------------------------------------
# Mars physical constants
# Source: Phase 0 spec "Mars planet constants" table. Radii/MU/J2 come from
# Mars-GRAM documentation (same radii used in the Mars-GRAM run); OMEGA
# from the standard Mars sidereal day (~88,642.66 s). Converted from the
# spec's ft/ft^3 figures to SI (verified by hand, see commit notes) since
# IOFLAG=3 (metric in/out) is used throughout, matching Examples 1A/1B.
# The spec also notes the Brandenburg et al. paper's own MU (4.289e13
# m^3/s^2) differs slightly from this table's value -- rounding in the
# paper's figure, per the spec; this table's value is the one to use.
# ---------------------------------------------------------------------------
MU_MARS = 4.282837e13          # m^3/s^2 (42,828.37 km^3/s^2)
RE_MARS = 3_396_190.0          # m (3,396.19 km)
RP_MARS = 3_376_200.0          # m (3,376.20 km)
OMEGA_MARS = 7.088218e-5       # rad/s
J2_MARS = 1.96045e-3
J3_MARS = J4_MARS = J5_MARS = J6_MARS = J7_MARS = J8_MARS = 0.0
RE_GRAV_MARS = RE_MARS         # PENDING verification -- spec says "likely equal to RE"

# NPC(16) gravity-model option. Reusing npc(16)=2 ("oblate planet model"),
# the same flag validated against Earth in Examples 1A/1B -- it printed
# back RE/RE_GRAV/RP/OMEGA/MU/J2..J8 exactly as given, which is the
# mechanism the spec asks for ("choose the option that actually uses
# these constants"). Not re-verified against the manual for Mars
# specifically, but the mechanism is planet-constant-agnostic.
NPC16_GRAVITY_MODEL_OPTION = 2

G0_STD = 9.80665  # standard g, for the POST2 "weight" input convention only

# ---------------------------------------------------------------------------
# Fixed entry state (IDENTICAL for all 32 runs -- do not vary per scenario)
# Source: Brandenburg, Williams, Woffinden, Putnam, "Demonstration of
# Linear Covariance Analysis Techniques..." (NASA JSC/UIUC), Table 1
# ("MSL Entry Interface State"). See spec for full discussion, including
# the longitude sign resolution and the 125 km vs 133 km note.
# ---------------------------------------------------------------------------
EI_ALTITUDE_M = 133_000.0          # 436,352 ft; NOT 125 km -- see spec note
EI_GDLAT_DEG = -3.9186             # geodetic latitude (paper Table 1)
EI_GCLAT_DEG = -3.872746729711164  # PENDING verification: geocentric-latitude
                                    # equivalent of GDLAT above, via
                                    # tan(gclat) = (1-f)^2 tan(gdlat) with
                                    # Mars flattening f = (RE-RP)/RE =
                                    # 0.0058860. Computed because the
                                    # validated npc(4)=2 input keyword from
                                    # Examples 1A/1B is GCLAT (geocentric),
                                    # but the spec's sourced value is
                                    # GDLAT (geodetic). Verify against the
                                    # manual whether npc(4)=2 actually wants
                                    # geocentric latitude, or whether there's
                                    # a geodetic-latitude input option --
                                    # if the latter exists, use EI_GDLAT_DEG
                                    # directly instead of this conversion.
EI_LONG_DEG = 126.72               # +126.72 E (spec resolves the paper's
                                    # apparent sign error -- see spec note)
EI_VELI_MPS = 6080.1504            # 19,948 ft/s, INERTIAL velocity
EI_GAMMAI_DEG = -15.489            # INERTIAL flight path angle
EI_AZVELI_DEG = 93.2065            # INERTIAL heading

# Expected Gale Crater touchdown, for the post-run sanity check the spec
# asks for ("confirm the trajectory ends near Gale to within a reasonable
# distance"). Source: spec's Table 3 reference.
GALE_TOUCHDOWN_LAT_DEG = -4.59
GALE_TOUCHDOWN_LON_DEG = 137.44

# Local terrain height at Gale Crater relative to the MOLA areoid --
# Mars-GRAM output, per spec. The atmosphere table and all POST2 GDALT
# values are referenced to the areoid (not corrected for the ~0.43 km
# areoid-to-ellipsoid offset -- accepted simplification, do not "fix").
GALE_SURFACE_GDALT_M = -3755.0

# Atmosphere table coverage (Mars-GRAM, see MARS_ATMOSPHERE_CSV above).
ATMOSPHERE_TABLE_MIN_GDALT_M = -5000.0
ATMOSPHERE_TABLE_MAX_GDALT_M = 140_000.0
ATMOSPHERE_TABLE_GAMMA = 1.30  # assumed, used to compute speed of sound column

# ---------------------------------------------------------------------------
# Event sequence (Mach-triggered; see spec "Event Sequence and End Condition")
# ---------------------------------------------------------------------------
CHUTE_DEPLOY_MACH = 1.7   # Karlgaard et al., AAS 13-307, p. 3
HEATSHIELD_SEP_MACH = 0.7  # Karlgaard et al., p. 3; Way et al. Section 2.5

# Handoff: altitude ABOVE LOCAL SURFACE, not above the areoid. Converted to
# an areoid-referenced GDALT trigger value below.
HANDOFF_ALTITUDE_ABOVE_SURFACE_M = 1700.0  # Fig. 2 labeled value (not the
                                            # text's 1.6 km -- see spec note)
HANDOFF_GDALT_M = GALE_SURFACE_GDALT_M + HANDOFF_ALTITUDE_ABOVE_SURFACE_M  # -2055.0
HANDOFF_REFERENCE_VELOCITY_MPS = 78.9  # Fig. 2 labeled value, surface-relative

# Bank angle: ONE fixed value for the whole entry, all 32 runs.
# Sign/convention PENDING verification against the POST2 manual (spec:
# "confirm the sign convention in the POST2 manual"). Magnitude from
# Brandenburg et al. Table 1 (-15 deg alongside -10 deg angle of attack;
# angle of attack itself is NOT used here since lift is set directly from
# the L/D table instead -- see spec).
BANK_ANGLE_DEG = 15.0

# ---------------------------------------------------------------------------
# Mass model
# Source: spec "Total vehicle mass" section. Fixed non-payload vehicle mass
# (2,358 kg = MSL's 3,257 kg entry mass minus 899 kg rover) is the SAME
# for both designs and every diameter -- an accepted simplification, not
# an estimate (replaces the payload-mass-fraction approximation used in
# the Phase 0 v1 build).
# ---------------------------------------------------------------------------
FIXED_VEHICLE_MASS_KG = 2358.0

# Mass dropped at heat-shield/aeroshell separation (Mach 0.7), SAME for
# both designs and every scenario. Explicitly an author assumption, NOT a
# sourced value -- do not describe it as sourced anywhere (code comments,
# README, or the paper). If a published MSL heat-shield-only mass is found
# later, report it with its exact source before swapping this in.
HEATSHIELD_DROP_MASS_KG = 385.0

# Parachute mass (included within FIXED_VEHICLE_MASS_KG already -- do not
# add on top of total mass, and do not scale with chute size).
# Source: Cruz et al., NTRS 20130012762, Table 3.
PARACHUTE_MASS_KG = 46.826

# ---------------------------------------------------------------------------
# Parachute scaling (DECIDED BY THE AUTHOR: MSL disk-gap-band, canopy area
# scaled with total mass, constant chute loading)
# Source: Cruz et al., NTRS 20130012762, Tables 1-3, Fig. 9, Eq. 11-12;
# MSL entry mass 3,257 kg from Way et al., NTRS 20090007730, Table 1.
# ---------------------------------------------------------------------------
MSL_CHUTE_REFERENCE_MASS_KG = 3257.0
MSL_CHUTE_REFERENCE_AREA_M2 = 357.94
CHUTE_OPENING_LOAD_FACTOR = 1.407  # Eq. 11-12, for informational F = q*S0*1.407*CD
CHUTE_INFLATION_TIME_S = 2.0       # ~mortar fire to full inflation, Eq. 11


def chute_area_m2(total_mass_kg: float) -> float:
    """S0 scaled to hold MSL's chute loading (total_mass/S0) constant."""
    return MSL_CHUTE_REFERENCE_AREA_M2 * (total_mass_kg / MSL_CHUTE_REFERENCE_MASS_KG)


def chute_diameter_m(total_mass_kg: float) -> float:
    import math
    return math.sqrt(4.0 * chute_area_m2(total_mass_kg) / math.pi)


# ---------------------------------------------------------------------------
# Parameter grid (Phase 0: exactly one run per cell, 32 total)
# ---------------------------------------------------------------------------
RIGID_DIAMETERS_M = [3.0, 3.5, 4.0, 4.5]
INFLATABLE_DIAMETERS_M = [6.0, 9.0, 12.0, 15.0]
PAYLOAD_MASSES_KG = [900.0, 1800.0, 2700.0, 3600.0]

DESIGNS = {
    "rigid": {"diameters_m": RIGID_DIAMETERS_M},
    "inflatable": {"diameters_m": INFLATABLE_DIAMETERS_M},
}

# ---------------------------------------------------------------------------
# Fixed-wind test conditions (Phase 0: same for all 32 runs)
# ---------------------------------------------------------------------------
WIND_SPEED_MPS = 10.0
WIND_DIRECTION_DEG = 0.0
# PENDING verification: azimuth convention (blows-toward vs. blows-from)
# and what 0 deg references, per the POST2 manual's NPC(6)/AZW_T section.
# Document whatever is found in README.md once confirmed -- see
# mars_environment.py.

# ---------------------------------------------------------------------------
# Mars atmosphere / wind readiness gate (PENDING -- do not run until this
# is True). See mars_environment.py for what's still needed.
# ---------------------------------------------------------------------------
MARS_ATMOSPHERE_READY = False

# Readiness gate for the real digitized CD/L-D and chute-CD tables. False
# until MSL_CD_DIGITIZED_CSV exists and aero_data.py has been updated to
# read it instead of using the inline transcription of the spec's summary
# table (which is NOT the full digitized file the spec asks for).
AERO_DATA_FROM_DIGITIZED_FILE = False
