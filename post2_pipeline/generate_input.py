"""
Build a single POST2 .inp deck for one (design, diameter, payload_mass)
scenario, per the Phase 0 spec v2 event chain:

  event 1   entry (fixed state, full vehicle mass, body lift+drag table,
            fixed bank angle)        -- trigger: mach = CHUTE_DEPLOY_MACH
  event 50  chute deployed (mass unchanged; drag becomes chute+body
            combined, lift zeroed)   -- trigger: mach = HEATSHIELD_SEP_MACH
  event 70  heat shield separated (mass -= HEATSHIELD_DROP_MASS_KG; same
            combined drag table continues)
  event 100 handoff (altitude above local surface = 1.7 km) -- termination

`altmin` is also set to the handoff GDALT as a global safety net, so a
scenario that never reaches Mach 0.7 (heat shield never separates, which
the spec says is a valid, expected outcome for some scenarios) still
terminates at the handoff altitude instead of falling through toward the
true surface undetected. See README for why this is needed and that it's
an inferred (not manual-confirmed) behavior of ALTMIN.
"""

import math
from typing import Dict

import config
import aero_data
import mars_environment


def total_entry_mass_kg(payload_mass_kg: float) -> float:
    return config.FIXED_VEHICLE_MASS_KG + payload_mass_kg


def post_heatshield_mass_kg(payload_mass_kg: float) -> float:
    return total_entry_mass_kg(payload_mass_kg) - config.HEATSHIELD_DROP_MASS_KG


def reference_area_m2(diameter_m: float) -> float:
    return math.pi * (diameter_m / 2.0) ** 2


def ballistic_coefficient(diameter_m: float, payload_mass_kg: float) -> float:
    """beta = total_mass / (CD_hypersonic * SREF), per spec."""
    m = total_entry_mass_kg(payload_mass_kg)
    cd = aero_data.entry_cd_reference()
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
    atmosphere/wind table syntax and the mars_atmosphere_gale.csv data
    have both been confirmed/supplied -- this function is intentionally
    not safe to call for a real run before then.
    """
    if design not in config.DESIGNS:
        raise ValueError(f"Unknown design {design!r}; expected one of {list(config.DESIGNS)}")

    if _preview:
        env_lines = [
            "// >>> PLACEHOLDER -- Mars atmosphere table (NPC(5)=1 / PREST /",
            "// >>> ATEMT / CST / DENST) and wind table (NPC(6) / VWT / AZW_T)",
            "// >>> syntax not yet confirmed, and mars_atmosphere_gale.csv not",
            "// >>> yet supplied. This reference file is NOT runnable as-is.",
            "// >>> See mars_environment.py and README.md for status.",
            f"// >>> wind_speed_mps={wind_speed_mps}, wind_direction_deg={wind_direction_deg}",
        ]
    else:
        env_lines = mars_environment.build_environment_block(wind_speed_mps, wind_direction_deg)

    sref = reference_area_m2(diameter_m)
    lref = diameter_m
    m_total = total_entry_mass_kg(payload_mass_kg)
    m_post_heatshield = post_heatshield_mass_kg(payload_mass_kg)
    wgtsg_entry = m_total * config.G0_STD
    wgtsg_post_heatshield = m_post_heatshield * config.G0_STD
    chute_area = config.chute_area_m2(m_total)
    chute_diameter = config.chute_diameter_m(m_total)
    sid = scenario_id(design, diameter_m, payload_mass_kg)

    combined_cd_lines = aero_data.combined_post_chute_cd_table_lines(chute_area, sref)

    lines = [
        "srchm = 0,           // no search or optimization",
        "ioflag = 3,           // metric input / metric output",
        "ipro = -1,           // print final trajectory only",
        "opt = 0,             // no optimization",
        f"title = 'Phase0 {sid}',",
        "event = 1,            // event or phase number",
        "fesn = 100,           // final event number",
        "maxtim = 5000.0,      // maximum allowable time",
        f"altmax = 5.0e6,       // maximum allowable altitude (skip-out catch)",
        f"altmin = {config.HANDOFF_GDALT_M},    // PENDING verify: global safety-net so a run",
        "                      // that never separates the heat shield still stops at",
        "                      // the handoff altitude instead of falling through --",
        "                      // see generate_input.py module docstring",
        "pinc = 1,             // print interval (fine, for later analysis)",
        "prnc = 1,             // plot interval",
        "dt = 1.0,             // integration time step",
        "npc(1) = 3,           // calculate conics at end of each integ. step",
        "npc(2) = 1,           // fourth order runge-kutta",
        "// Fixed entry state -- SAME for all 32 scenarios, per spec",
        "// (Brandenburg et al., Table 1 'MSL Entry Interface State')",
        "npc(4) = 2,           // position vector initialization flag",
        f"gdalt = {config.EI_ALTITUDE_M},     // initial geodetic altitude (133.0 km, NOT 125 km -- see README)",
        f"long = {config.EI_LONG_DEG},        // initial east longitude",
        f"gclat = {config.EI_GCLAT_DEG},  // PENDING verify: geocentric-latitude equivalent of",
        f"                      // the sourced GDLAT={config.EI_GDLAT_DEG} -- see config.py",
        "npc(3) = 2,           // input gammai, veli, azveli (inertial)",
        f"gammai = {config.EI_GAMMAI_DEG},     // initial inertial flight path angle",
        f"azveli = {config.EI_AZVELI_DEG},     // initial inertial heading",
        f"veli = {config.EI_VELI_MPS},    // initial inertial velocity",
        "// Mars atmosphere + wind",
        *env_lines,
        "// Model planetary gravity (Mars)",
        f"npc(16) = {config.NPC16_GRAVITY_MODEL_OPTION},          // oblate planet model",
        f"omega = {config.OMEGA_MARS},   // rotation rate of attracting planet",
        f"mu = {config.MU_MARS},      // gravitational constant of attracting planet",
        f"re = {config.RE_MARS},     // equatorial radius of planet",
        f"rp = {config.RP_MARS},     // polar radius of planet",
        f"re_grav = {config.RE_GRAV_MARS}, // PENDING verify: reference radius for the gravity model",
        f"j2 = {config.J2_MARS},   // Mars J2",
        f"j3 = {config.J3_MARS}, j4 = {config.J4_MARS}, j5 = {config.J5_MARS}, j6 = {config.J6_MARS}, j7 = {config.J7_MARS}, j8 = {config.J8_MARS}, // higher terms not modeled for Mars",
        "// Input vehicle characteristics -- Phase 1 (entry, full vehicle + aeroshell)",
        f"wgtsg = {wgtsg_entry:.6f},   // (N) total entry weight = total_mass * standard g",
        f"sref = {sref:.6f},          // (sq m) reference area = pi*(d/2)^2, d={diameter_m} m",
        f"lref = {lref},              // (m) reference length = diameter",
        "npc(8) = 2,           // use drag, lift, & side force coefficients",
        aero_data.cd_table_lines(),
        aero_data.cl_table_lines(),
        f"bnkpc = 'bnkpc', constant, 0, {config.BANK_ANGLE_DEG},   // PENDING verify: fixed bank angle syntax + sign convention",
        "event = 50,           // parachute deployment",
        "critr = 'mach',       // Mach-number trigger (NOT altitude or time), per spec",
        f"value = {config.CHUTE_DEPLOY_MACH},   // MSL's real chute-deploy Mach (Karlgaard et al.)",
        "mdl = 1,              // ignore the sign of the deriv. of critr",
        f"// Post-chute drag = chute (S0={chute_area:.3f} sq m, D0={chute_diameter:.3f} m) + body, combined",
        "// into one effective CD table referenced to the body's SREF -- see",
        "// aero_data.combined_post_chute_cd_table() for the derivation.",
        combined_cd_lines,
        "clt = 'clt', constant, 0, 0.0,   // lift ends at chute deploy, per spec",
        f"bnkpc = 'bnkpc', constant, 0, 0.0,   // bank moot once CL=0, zeroed for clarity",
        "event = 70,           // heat shield (aeroshell) separation",
        "critr = 'mach',",
        f"value = {config.HEATSHIELD_SEP_MACH},   // MSL's real heat-shield-sep Mach (Karlgaard et al.)",
        "mdl = 1,",
        f"wgtsg = {wgtsg_post_heatshield:.6f},   // (N) weight after dropping the author-assumed",
        f"                       // {config.HEATSHIELD_DROP_MASS_KG} kg heat-shield/aeroshell mass",
        "event = 100,          // powered-descent handoff",
        "critr = 'gdalt',",
        f"value = {config.HANDOFF_GDALT_M},    // 1.7 km above the Gale local surface ({config.GALE_SURFACE_GDALT_M} m areoid-referenced)",
        "mdl = 1,",
        "endprb = 1,",
        "endjob = 1,",
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
        python generate_input.py
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
