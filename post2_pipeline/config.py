"""
Phase 0 configuration: grid definition, physical constants, and paths.

This is the single place to edit before a run. Nothing here executes
anything by itself.
"""

import os

# ---------------------------------------------------------------------------
# POST2 executable / working directory (LOCAL WINDOWS MACHINE ONLY)
# ---------------------------------------------------------------------------
# POST2 only runs on your Windows machine (post2_windows_commercial.exe).
# This pipeline is meant to be copied to / run from that machine. Point
# these at your actual install; the values below match the folder we found
# during the Example 1B walkthrough (ALLPOST2FILES\POST2v500).
POST2_EXE = os.environ.get(
    "POST2_EXE",
    r"C:\Users\faris\Downloads\ALLPOST2FILES\POST2v500\post2_windows_commercial.exe",
)

# Where generated .inp files, raw .out files, and the summary CSV go.
OUTPUT_ROOT = os.environ.get("POST2_PIPELINE_OUTPUT", "results")

# ---------------------------------------------------------------------------
# Mars physical constants (NASA Mars Fact Sheet values)
# ---------------------------------------------------------------------------
MU_MARS = 4.282837e13          # m^3/s^2, gravitational parameter
RE_MARS = 3_396_200.0          # m, equatorial radius
RP_MARS = 3_376_200.0          # m, polar radius
OMEGA_MARS = 7.088218e-5       # rad/s, rotation rate
J2_MARS = 1.960454e-3          # unnormalized J2 zonal harmonic

# Standard Earth g. Used ONLY for the POST2 "weight" input convention
# (wgtsg = mass_kg * G0_STD) and for reporting deceleration in "g's" the
# way Mars EDL literature conventionally does (e.g. "MSL saw ~10 g") --
# NOT Mars surface gravity. Confirmed against the Example 1B output, where
# POST2 printed GO = 9.80665 regardless of which planet's gravity model
# (npc(16)) was driving the actual equations of motion.
G0_STD = 9.80665

# ---------------------------------------------------------------------------
# Entry interface
# ---------------------------------------------------------------------------
EI_ALTITUDE_M = 125_000.0      # m, matches the Earth EI altitude used in
                                # Examples 1A/1B and standard Mars EDL practice

# TODO (per-scenario, Phase 0 simplification): entry flight path angle should
# be re-checked for dynamic feasibility at each grid point rather than fixed
# at -15.49 deg (MSL's actual value) everywhere. Phase 0 uses MSL's value as
# a starting point for all 32 scenarios; flag any scenario whose output looks
# non-physical (skip-out, doesn't reach the surface, absurd g-loads) for a
# feasibility re-check before trusting its numbers.
GAMMA_I_DEG = -15.49
VELI_MPS = 5900.0

# ---------------------------------------------------------------------------
# Mass model
# ---------------------------------------------------------------------------
# The spec's grid gives *payload* mass (900-3600 kg), not total entry mass.
# MSL's real payload/entry-mass ratio (899 kg payload / 3257 kg entry mass)
# is used here as a stand-in mass fraction to back out a total entry mass
# for each grid cell. This is a documented Phase 0 placeholder -- it applies
# the same ratio to both the rigid and inflatable designs, even though their
# real aeroshell mass fractions differ. Revisit before any science-grade run.
PAYLOAD_MASS_FRACTION = 899.0 / 3257.0  # ~0.2760

# ---------------------------------------------------------------------------
# Parameter grid (Phase 0: exactly one run per cell)
# ---------------------------------------------------------------------------
RIGID_DIAMETERS_M = [3.0, 3.5, 4.0, 4.5]
INFLATABLE_DIAMETERS_M = [6.0, 9.0, 12.0, 15.0]
PAYLOAD_MASSES_KG = [900.0, 1800.0, 2700.0, 3600.0]

DESIGNS = {
    "rigid": {
        "diameters_m": RIGID_DIAMETERS_M,
    },
    "inflatable": {
        "diameters_m": INFLATABLE_DIAMETERS_M,
    },
}

# ---------------------------------------------------------------------------
# Fixed-wind test conditions (Phase 0: same for all 32 runs)
# ---------------------------------------------------------------------------
WIND_SPEED_MPS = 10.0
WIND_DIRECTION_DEG = 0.0

# ---------------------------------------------------------------------------
# Jettison / decelerator-deploy trigger (dynamic-pressure based, per spec --
# NOT altitude or time)
# ---------------------------------------------------------------------------
# Representative values from published Mars EDL literature, not derived
# from a real trajectory for these specific grid cells. Rigid uses MSL's
# approximate real supersonic-parachute-deploy dynamic pressure; inflatable
# uses a lower value representative of the Mach ~0.9-2 release window
# described in the spec. Verify against each run's actual Mach at trigger.
JETTISON_DYNP_PA = {
    "rigid": 750.0,
    "inflatable": 500.0,
}

# Post-jettison "decelerator" drag stand-in. Phase 0 does NOT model real
# parachute geometry/inflation -- this is only enough drag increase to
# validate that the trigger + phase-swap + output-parsing mechanics work.
POST_JETTISON_CD = 2.0
POST_JETTISON_CL = 0.0

# ---------------------------------------------------------------------------
# Sutton-Graves convective heating coefficient
# ---------------------------------------------------------------------------
# q = K * sqrt(rho / Rn) * V^3  (W/m^2, rho in kg/m^3, V in m/s, Rn in m)
# Sutton-Graves is derived for air but is commonly applied as an
# approximation for CO2-dominated Mars entry heating in the literature.
SUTTON_GRAVES_K = 1.7415e-4

# Effective nose radius as a fraction of base (aeroshell) radius.
# Rigid: matches MSL's actual geometry (nose radius 1.125 m / base radius
# 2.25 m = 0.5).
# Inflatable: HIADs are much blunter than a rigid capsule relative to their
# diameter -- approximated here as a larger fraction of the base radius.
# Both are documented Phase 0 approximations.
NOSE_RADIUS_FRACTION = {
    "rigid": 0.5,
    "inflatable": 0.7,
}

# ---------------------------------------------------------------------------
# Mars atmosphere / wind (PENDING -- do not run until this is filled in)
# ---------------------------------------------------------------------------
# Left as None on purpose. generate_input.py raises if this is missing, so
# the pipeline cannot silently run with no atmosphere or the wrong one --
# the same failure mode Example 1A hit before npc(5) was set.
#
# Fill in via mars_environment.py once Mars-GRAM data / the POST2 manual's
# Mars (or generic tabular) atmosphere section is available.
MARS_ATMOSPHERE_READY = False
