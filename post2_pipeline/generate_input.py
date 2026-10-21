"""
Build a single POST2 .inp deck for one (design, diameter, payload_mass)
scenario, per the Phase 0 spec event chain:

  event 1   entry (fixed state, full vehicle mass, body lift+drag table,
            fixed bank angle)        -- trigger: mach = CHUTE_DEPLOY_MACH
  event 50  chute deployed (mass unchanged; drag becomes chute+body
            combined, lift zeroed)   -- trigger: mach = HEATSHIELD_SEP_MACH
  event 70  heat shield separated (mass -= HEATSHIELD_DROP_MASS_KG; same
            combined drag table continues)
  event 100 handoff (altitude above local surface = 1.7 km) -- termination

UNITS: IOFLAG = 0 (English), per the spec's manual-confirmed unit rules
(input units cannot be mixed within a problem). All length/velocity/
gravity/weight values written into the deck are converted to ft/ft-s/
ft^3-s^2/lbf here; aerodynamic tables (Mach-indexed, dimensionless) and
all angles are unaffected by unit system.

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

ALTMAX_FT = 5.0e6 * config.FT_PER_M  # generous skip-out catch, converted from the metric value used in Examples 1A/1B


def total_entry_mass_kg(payload_mass_kg: float) -> float:
    return config.FIXED_VEHICLE_MASS_KG + payload_mass_kg


def post_heatshield_mass_kg(payload_mass_kg: float) -> float:
    return total_entry_mass_kg(payload_mass_kg) - config.HEATSHIELD_DROP_MASS_KG


def reference_area_m2(diameter_m: float) -> float:
    return math.pi * (diameter_m / 2.0) ** 2


def ballistic_coefficient(diameter_m: float, payload_mass_kg: float) -> float:
    """beta = total_mass / (CD_hypersonic * SREF), per spec. Computed in
    metric throughout (unit-independent ratio), matching MSL's published
    ~145 kg/m^2 figure for comparison."""
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
    bank_angle_deg: float = config.BANK_ANGLE_DEG,
    _preview: bool = False,
) -> str:
    """
    Return the full text of a POST2 .inp deck for one scenario.

    Raises mars_environment.MarsEnvironmentNotReady until
    data/mars_atmosphere_gale.csv exists.

    `bank_angle_deg` overrides config.BANK_ANGLE_DEG for the entry phase
    (event 1) only -- bank is always zeroed again at chute deploy
    (event 50) regardless. Used by bank_sweep.py for the Task 2
    bank-angle sweep on the baseline scenario.
    """
    if design not in config.DESIGNS:
        raise ValueError(f"Unknown design {design!r}; expected one of {list(config.DESIGNS)}")

    if _preview:
        env_lines = [
            "// >>> PLACEHOLDER -- data/mars_atmosphere_gale.csv not present.",
            "// >>> Table SYNTAX is confirmed (see mars_environment.py); only",
            "// >>> the data file is missing. This reference file is NOT runnable.",
            f"// >>> wind_speed_mps={wind_speed_mps}, wind_direction_deg={wind_direction_deg}",
        ]
    else:
        env_lines = mars_environment.build_environment_block(wind_speed_mps, wind_direction_deg)

    sref_m2 = reference_area_m2(diameter_m)
    sref_ft2 = sref_m2 * config.FT2_PER_M2
    lref_ft = diameter_m * config.FT_PER_M
    m_total = total_entry_mass_kg(payload_mass_kg)
    m_post_heatshield = post_heatshield_mass_kg(payload_mass_kg)
    wgtsg_entry_lbf = m_total * config.KG_TO_LBF
    wgtsg_post_heatshield_lbf = m_post_heatshield * config.KG_TO_LBF
    chute_area_m2 = config.chute_area_m2(m_total)
    chute_diameter_m = config.chute_diameter_m(m_total)
    sid = scenario_id(design, diameter_m, payload_mass_kg)

    # Ratio in the combined-drag-table derivation is unit-independent, so
    # the metric areas are used directly for it; only the deck's own
    # `sref=` line (below) needs the ft^2 conversion.
    combined_cd_lines = aero_data.combined_post_chute_cd_table_lines(chute_area_m2, sref_m2)

    lines = [
        "srchm = 0,           // no search or optimization",
        f"ioflag = {config.IOFLAG},           // English units (IOFLAG=0) -- CONFIRMED, manual 4.a/6.a.4",
        "ipro = -1,           // print final trajectory only",
        "opt = 0,             // no optimization",
        f"title = 'Phase0 {sid}',",
        "event = 1,            // event or phase number",
        "fesn = 100,           // final event number",
        "maxtim = 5000.0,      // maximum allowable time",
        f"altmax = {ALTMAX_FT:.1f},    // maximum allowable altitude, ft (skip-out catch)",
        f"altmin = {config.HANDOFF_GDALT_FT:.2f},   // ft; PENDING verify: global safety-net so a run",
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
        f"gdalt = {config.EI_ALTITUDE_FT},     // initial geodetic altitude, ft (133.0 km, NOT 125 km -- see README)",
        f"long = {config.EI_LONG_DEG},        // initial east longitude, deg",
        f"gclat = {config.EI_GCLAT_DEG},  // deg; PENDING verify: geocentric-latitude equivalent of",
        f"                      // the sourced GDLAT={config.EI_GDLAT_DEG} -- see config.py",
        "npc(3) = 2,           // input gammai, veli, azveli (inertial)",
        f"gammai = {config.EI_GAMMAI_DEG},     // initial inertial flight path angle, deg",
        f"azveli = {config.EI_AZVELI_DEG},     // initial inertial heading, deg",
        f"veli = {config.EI_VELI_FTS},    // initial inertial velocity, ft/s",
        "// Mars atmosphere + wind (CONFIRMED syntax, manual 6.a.4 -- see mars_environment.py)",
        *env_lines,
        "// Model planetary gravity (Mars)",
        f"npc(16) = {config.NPC16_GRAVITY_MODEL_OPTION},          // oblate planet model",
        f"omega = {config.OMEGA_MARS},   // rotation rate of attracting planet, rad/s",
        f"mu = {config.MU_MARS_FT3_S2},      // gravitational constant, ft^3/s^2",
        f"re = {config.RE_MARS_FT},     // equatorial radius, ft",
        f"rp = {config.RP_MARS_FT},     // polar radius, ft",
        f"re_grav = {config.RE_GRAV_MARS_FT}, // ft; PENDING verify: reference radius for the gravity model",
        f"j2 = {config.J2_MARS},   // Mars J2",
        f"j3 = {config.J3_MARS}, j4 = {config.J4_MARS}, j5 = {config.J5_MARS}, j6 = {config.J6_MARS}, j7 = {config.J7_MARS}, j8 = {config.J8_MARS}, // higher terms not modeled for Mars",
        "// Input vehicle characteristics -- Phase 1 (entry, full vehicle + aeroshell)",
        f"wgtsg = {wgtsg_entry_lbf:.6f},   // lbf; total entry weight = total_mass_kg * {config.KG_TO_LBF}",
        f"sref = {sref_ft2:.6f},          // sq ft; reference area = pi*(d/2)^2, d={diameter_m} m",
        f"lref = {lref_ft:.6f},              // ft; reference length = diameter",
        "npc(8) = 2,           // use drag, lift, & side force coefficients",
        aero_data.cd_table_lines(),
        aero_data.cl_table_lines(),
        f"bnkpc(1) = {bank_angle_deg},   // deg; PENDING verify -- a real 32-run grid showed BNKANG",
        "                      // stayed 0.0 in every .out despite this line (as bare `bnkpc = <val>,`,",
        "                      // which POST2 silently accepted but did not apply -- BNKPC echoed as",
        "                      // [0,0,0,0] regardless). BNKPC is echoed as a 4-element array (polynomial",
        "                      // coefficients), so this now targets element 1 (the constant/c0 term)",
        "                      // explicitly by index. UNVERIFIED until a real run's .out is checked for",
        "                      // a nonzero echoed BNKPC and nonzero printed bnkang -- see README. If this",
        "                      // still doesn't work, the next things to try are `bnkang = <val>,` as a",
        "                      // direct initial value, or an IGUID(1) guidance-mode flag (manual 6.a,",
        "                      // BNKPC/BNKANG/IGUID(1) entries) that may need to be set before POST2",
        "                      // will read BNKPC into bnkang at all.",
        "                      // Sign convention: PENDING -- manual states positive BNKANG banks right;",
        "                      // doesn't affect vertical-plane behavior (peak g, skip, Mach-1.7 state),",
        "                      // only lateral drift, but record the sign once confirmed.",
        "event = 50,           // parachute deployment",
        "critr = 'mach',       // Mach-number trigger (NOT altitude or time), per spec",
        f"value = {config.CHUTE_DEPLOY_MACH},   // MSL's real chute-deploy Mach (Karlgaard et al.)",
        "mdl = 1,              // ignore the sign of the deriv. of critr",
        f"// Post-chute drag = chute (S0={chute_area_m2:.3f} sq m, D0={chute_diameter_m:.3f} m) + body, combined",
        "// into one effective CD table referenced to the body's SREF -- see",
        "// aero_data.combined_post_chute_cd_table() for the derivation (unit-independent ratio).",
        combined_cd_lines,
        "clt = 'clt', constant, 0, 0.0,   // lift ends at chute deploy, per spec",
        f"bnkpc(1) = 0.0,   // bank moot once CL=0, zeroed for clarity",
        "event = 70,           // heat shield (aeroshell) separation",
        "critr = 'mach',",
        f"value = {config.HEATSHIELD_SEP_MACH},   // MSL's real heat-shield-sep Mach (Karlgaard et al.)",
        "mdl = 1,",
        f"wgtsg = {wgtsg_post_heatshield_lbf:.6f},   // lbf; weight after dropping the author-assumed",
        f"                       // {config.HEATSHIELD_DROP_MASS_KG} kg heat-shield/aeroshell mass",
        "event = 100,          // powered-descent handoff",
        "critr = 'gdalt',",
        f"value = {config.HANDOFF_GDALT_FT:.2f},    // ft; 1.7 km above the Gale local surface ({config.GALE_SURFACE_GDALT_M} m areoid-referenced)",
        "mdl = 1,",
        "endprb = 1,",
        "endjob = 1,",
    ]
    return "\n".join(lines) + "\n"


def write_input_deck(design: str, diameter_m: float, payload_mass_kg: float, out_path: str,
                      wind_speed_mps: float = config.WIND_SPEED_MPS,
                      wind_direction_deg: float = config.WIND_DIRECTION_DEG,
                      bank_angle_deg: float = config.BANK_ANGLE_DEG) -> None:
    text = build_input_deck(design, diameter_m, payload_mass_kg, wind_speed_mps, wind_direction_deg, bank_angle_deg)
    with open(out_path, "w", newline="\r\n") as f:
        f.write(text)


def make_reference_templates(templates_dir: str = "templates") -> None:
    """Write reference decks (one per design) for eyeballing the structure
    directly, using the baseline grid cell for each design. Uses the real
    atmosphere/wind data when available (full, runnable deck); falls back
    to the non-runnable placeholder preview if the atmosphere CSV isn't
    present yet. Regenerate with:
        python generate_input.py
    """
    import os
    from mars_environment import MarsEnvironmentNotReady

    os.makedirs(templates_dir, exist_ok=True)
    samples = {
        "rigid": (4.5, 900.0),
        "inflatable": (9.0, 1800.0),
    }
    for design, (diameter_m, payload_mass_kg) in samples.items():
        try:
            text = build_input_deck(design, diameter_m, payload_mass_kg)
        except MarsEnvironmentNotReady:
            text = build_input_deck(design, diameter_m, payload_mass_kg, _preview=True)
        path = os.path.join(templates_dir, f"{design}_template.inp")
        with open(path, "w", newline="\r\n") as f:
            f.write(text)


if __name__ == "__main__":
    make_reference_templates()
