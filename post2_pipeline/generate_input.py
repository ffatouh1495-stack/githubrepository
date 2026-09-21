"""
Build a single POST2 .inp deck for one (design, diameter, payload_mass)
scenario.

This is the "reusable function" layer the spec asks for -- Phase 0 calls
build_input_deck() once per grid cell; a future Monte Carlo phase would
call the same function many times per cell with dispersed inputs instead
of writing a new template each time.
"""

import math
from typing import Dict

import config
import aero_data
import mars_environment


def entry_mass_kg(payload_mass_kg: float) -> float:
    """Total simulated entry mass for a given payload mass, using the
    MSL-heritage payload mass fraction (see config.PAYLOAD_MASS_FRACTION)."""
    return payload_mass_kg / config.PAYLOAD_MASS_FRACTION


def reference_area_m2(diameter_m: float) -> float:
    return math.pi * (diameter_m / 2.0) ** 2


def ballistic_coefficient(design: str, diameter_m: float, payload_mass_kg: float) -> float:
    """beta = m / (CD * SREF), per spec. Uses total entry mass and the
    design's hypersonic (entry) CD, matching the convention behind MSL's
    published ~145 kg/m^2 figure (see aero_data module docstring)."""
    m = entry_mass_kg(payload_mass_kg)
    cd = aero_data.entry_cd_reference(design)
    sref = reference_area_m2(diameter_m)
    return m / (cd * sref)


def scenario_id(design: str, diameter_m: float, payload_mass_kg: float) -> str:
    return f"{design}_d{diameter_m:g}_m{payload_mass_kg:g}"


def build_input_deck(
    design: str,
    diameter_m: float,
    payload_mass_kg: float,
    wind_speed_mps: float = config.WIND_SPEED_MPS,
    wind_direction_deg: float = config.WIND_DIRECTION_DEG,
    _preview: bool = False,
) -> str:
    """
    Return the full text of a POST2 .inp deck for one scenario.

    Raises mars_environment.MarsEnvironmentNotReady until the Mars
    atmosphere/wind block has been filled in and verified -- this
    function is intentionally not safe to call for a real run before then.

    _preview: internal use by make_reference_templates() only, to render a
    human-readable reference .inp with a placeholder comment in place of
    the real atmosphere block. Never set this for an actual run.
    """
    if design not in config.DESIGNS:
        raise ValueError(f"Unknown design {design!r}; expected one of {list(config.DESIGNS)}")

    if _preview:
        env_lines = [
            "// >>> PLACEHOLDER -- Mars atmosphere/wind syntax not yet confirmed.",
            "// >>> This reference file is NOT runnable as-is. See",
            "// >>> mars_environment.py for why, and README.md for status.",
            f"// >>> wind_speed_mps={wind_speed_mps}, wind_direction_deg={wind_direction_deg}",
        ]
    else:
        env_lines = mars_environment.build_environment_block(wind_speed_mps, wind_direction_deg)

    sref = reference_area_m2(diameter_m)
    lref = diameter_m
    m_entry = entry_mass_kg(payload_mass_kg)
    wgtsg_entry = m_entry * config.G0_STD
    wgtsg_post = payload_mass_kg * config.G0_STD
    jettison_dynp = config.JETTISON_DYNP_PA[design]
    sid = scenario_id(design, diameter_m, payload_mass_kg)

    lines = [
        f"srchm = 0,           // no search or optimization",
        f"ioflag = 3,           // metric input / metric output",
        f"ipro = -1,           // print final trajectory only",
        f"opt = 0,             // no optimization",
        f"title = 'Phase0 {sid}',",
        f"event = 1,            // event or phase number",
        f"fesn = 100,           // final event number",
        f"maxtim = 5000.0,      // maximum allowable time",
        f"altmax = 5.0e6,       // maximum allowable altitude",
        f"pinc = 1,             // print interval (fine, for peak-search/heat-load integration)",
        f"prnc = 1,             // plot interval",
        f"dt = 1.0,             // integration time step",
        f"npc(1) = 3,           // calculate conics at end of each integ. step",
        f"npc(2) = 1,           // fourth order runge-kutta",
        f"// Input initial position",
        f"npc(4) = 2,           // position vector initialization flag",
        f"gdalt = {config.EI_ALTITUDE_M},     // initial geodetic altitude (entry interface)",
        f"long = 100.0,         // initial east long. relative to prime meridian (arbitrary, fixed across grid)",
        f"gclat = 40.0,         // initial geocentric latitude (arbitrary, fixed across grid)",
        f"// Input velocity vector",
        f"npc(3) = 2,           // input gammai, veli, azveli",
        f"gammai = {config.GAMMA_I_DEG},       // initial inertial flight path angle (MSL value; re-check feasibility per scenario)",
        f"azveli = 90.0,        // initial azimuth angle of inert. vel. vector",
        f"veli = {config.VELI_MPS},        // initial value of inertial velocity",
        f"// Mars atmosphere + wind",
        *env_lines,
        f"// Model planetary gravity (Mars)",
        f"npc(16) = 2,          // oblate planet model",
        f"omega = {config.OMEGA_MARS},   // rotation rate of attracting planet",
        f"mu = {config.MU_MARS},      // gravitational constant of attracting planet",
        f"re = {config.RE_MARS},     // equatorial radius of planet",
        f"rp = {config.RP_MARS},     // polar radius of planet",
        f"re_grav = {config.RE_MARS}, // reference radius of planet for the gravity model",
        f"j2 = {config.J2_MARS},   // Mars J2 (higher-order terms not modeled -- Phase 0 simplification)",
        f"// Input vehicle characteristics -- Phase 1 (entry, full aeroshell)",
        f"wgtsg = {wgtsg_entry:.6f},   // (N) entry weight = entry_mass * standard g",
        f"sref = {sref:.6f},          // (sq m) reference area = pi*(d/2)^2, d={diameter_m} m",
        f"lref = {lref},              // (m) reference length = diameter",
        f"npc(8) = 2,           // use drag, lift, & side force coefficients",
        aero_data.cd_table_lines(design),
        aero_data.cl_table_lines(design),
        f"event = 50,           // jettison / decelerator-deploy trigger",
        f"critr = 'dynp',       // dynamic-pressure based trigger (NOT altitude or time, per spec)",
        f"value = {jettison_dynp},   // Pa, representative {design} deploy dynamic pressure",
        f"mdl = 1,              // ignore the sign of the deriv. of critr",
        f"wgtsg = {wgtsg_post:.6f},   // (N) post-jettison weight = payload_mass * standard g",
        f"cdt = 'cdt', constant, 0, {config.POST_JETTISON_CD},   // post-jettison drag (Phase 0 stand-in, not real parachute geometry)",
        f"clt = 'clt', constant, 0, {config.POST_JETTISON_CL},   // post-jettison lift (Phase 0: none modeled)",
        f"event = 100,          // touchdown",
        f"critr = 'gdalt',",
        f"value = 0.0,",
        f"mdl = 1,",
        f"endprb = 1,",
        f"endjob = 1,",
    ]
    return "\n".join(lines) + "\n"


def write_input_deck(design: str, diameter_m: float, payload_mass_kg: float, out_path: str,
                      wind_speed_mps: float = config.WIND_SPEED_MPS,
                      wind_direction_deg: float = config.WIND_DIRECTION_DEG) -> None:
    text = build_input_deck(design, diameter_m, payload_mass_kg, wind_speed_mps, wind_direction_deg)
    with open(out_path, "w", newline="\r\n") as f:
        f.write(text)


def make_reference_templates(templates_dir: str = "templates") -> None:
    """Write human-readable, non-runnable reference decks (one per design)
    for eyeballing the structure directly, using the baseline grid cell
    for each design. Regenerate with:
        python -c "import generate_input; generate_input.make_reference_templates()"
    """
    import os

    os.makedirs(templates_dir, exist_ok=True)
    samples = {
        "rigid": (4.5, 900.0),
        "inflatable": (9.0, 1800.0),
    }
    for design, (diameter_m, payload_mass_kg) in samples.items():
        text = build_input_deck(design, diameter_m, payload_mass_kg, _preview=True)
        path = os.path.join(templates_dir, f"{design}_template.inp")
        with open(path, "w", newline="\r\n") as f:
            f.write(text)


if __name__ == "__main__":
    make_reference_templates()
