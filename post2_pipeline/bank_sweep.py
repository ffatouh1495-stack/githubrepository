"""
Task 2 (bank-angle fix verification): run a fixed-bank sweep on the
rigid_d4.5_m900 baseline ONLY -- not the full 32-scenario grid.

Usage (once Task 1's bank-angle fix is confirmed on a single run -- see
README "Bank angle (BNKPC/BNKANG) -- bugfix and open items"):
    python bank_sweep.py --exe "C:\\path\\to\\post2_windows_commercial.exe"

Default sweep: 0, 15, 30, 45, 60, 70 deg, fixed for the whole entry (same
scheme as the Phase 0 grid -- bank zeroed again at chute deploy). Override
with --angles, e.g. --angles 0,15,30 for a quick partial check.

Does NOT choose a final bank angle -- that's an author decision. This just
produces the comparison table (peak g/time, peak dynamic pressure, max
altitude after peak decel as a skip indicator, chute-deploy state,
handoff state, whether handoff was reached) for each angle so the author
can pick one against the MSL reference (Mach 1.7 at ~12.1 km above ground,
~E+259 s, no skip, handoff 1.7 km above ground at ~78.9 m/s -- Karlgaard
et al.; a few seconds of timing offset is expected since this project's
entry interface is 133 km vs. MSL's 125 km).
"""

import argparse
import csv
import os
import shutil

import config
import generate_input
import run_post2
import parse_output

BASELINE_DESIGN = "rigid"
BASELINE_DIAMETER_M = 4.5
BASELINE_PAYLOAD_KG = 900.0
DEFAULT_BANK_ANGLES_DEG = [0.0, 15.0, 30.0, 45.0, 60.0, 70.0]

FIELDNAMES = [
    "bank_angle_deg", "scenario_id", "status", "error_message",
    "post2_termination_mode", "max_abs_bnkang_deg",
    "handoff_reached", "last_event_number_reached",
    "peak_deceleration_g", "peak_deceleration_time_s", "peak_dynamic_pressure_pa",
    "max_altitude_after_peak_decel_m",
    "chute_deploy_time_s", "chute_deploy_altitude_m",
    "chute_deploy_altitude_above_surface_m", "chute_deploy_mach",
    "chute_deploy_velocity_relative_mps",
    "heat_shield_separated",
    "handoff_time_s", "handoff_velocity_relative_mps",
]


def run_one_bank(bank_deg: float, output_root: str, exe_path: str) -> dict:
    base_sid = generate_input.scenario_id(BASELINE_DESIGN, BASELINE_DIAMETER_M, BASELINE_PAYLOAD_KG)
    sid = f"{base_sid}_bank{bank_deg:g}"
    work_dir = os.path.join(output_root, "_work", sid)
    os.makedirs(work_dir, exist_ok=True)

    work_inp = os.path.join(work_dir, f"{sid}.inp")
    work_out = os.path.join(work_dir, f"{sid}.out")
    final_inp = os.path.join(output_root, f"{sid}.inp")
    final_out = os.path.join(output_root, f"{sid}.out")
    final_log = os.path.join(output_root, f"{sid}.log")

    row = {"bank_angle_deg": bank_deg, "scenario_id": sid, "status": "not_started", "error_message": ""}

    generate_input.write_input_deck(
        BASELINE_DESIGN, BASELINE_DIAMETER_M, BASELINE_PAYLOAD_KG, work_inp,
        bank_angle_deg=bank_deg,
    )

    result = run_post2.run_post2(sid, f"{sid}.inp", f"{sid}.out", cwd=work_dir, exe_path=exe_path)

    os.makedirs(output_root, exist_ok=True)
    shutil.copyfile(work_inp, final_inp)
    with open(final_log, "w") as f:
        f.write("=== stdout ===\n")
        f.write(result.stdout)
        f.write("\n=== stderr ===\n")
        f.write(result.stderr)

    row["post2_termination_mode"] = result.termination_mode

    if not os.path.exists(work_out):
        row["status"] = "post2_no_output_file"
        row["error_message"] = f"returncode={result.returncode}; {work_out} was not created"
        return row
    shutil.copyfile(work_out, final_out)

    if not result.ok:
        row["status"] = "post2_reported_errors"
        row["error_message"] = f"returncode={result.returncode} stderr={result.stderr[:500]}"
        return row

    try:
        with open(final_out, "r", errors="replace") as f:
            out_text = f.read()
        metrics = parse_output.parse_metrics(out_text, BASELINE_DIAMETER_M, BASELINE_PAYLOAD_KG)
    except Exception as e:
        row["status"] = "parse_failed"
        row["error_message"] = str(e)
        return row

    row["status"] = "ok" if metrics["handoff_reached"] else "handoff_not_reached"
    for key in (
        "max_abs_bnkang_deg", "handoff_reached", "last_event_number_reached",
        "peak_deceleration_g", "peak_deceleration_time_s", "peak_dynamic_pressure_pa",
        "max_altitude_after_peak_decel_m",
        "chute_deploy_time_s", "chute_deploy_altitude_m",
        "chute_deploy_altitude_above_surface_m", "chute_deploy_mach",
        "chute_deploy_velocity_relative_mps",
        "heat_shield_separated",
        "handoff_time_s", "handoff_velocity_relative_mps",
    ):
        row[key] = metrics[key]
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", default=config.POST2_EXE, help="Path to post2_windows_commercial.exe")
    parser.add_argument("--output-dir", default=os.path.join(config.OUTPUT_ROOT, "bank_sweep"),
                         help="Where this sweep's .inp/.out/.log files and summary CSV go")
    parser.add_argument("--angles", default=",".join(str(a) for a in DEFAULT_BANK_ANGLES_DEG),
                         help="Comma-separated bank angles in degrees, e.g. 0,15,30,45,60,70")
    args = parser.parse_args()
    angles = [float(a) for a in args.angles.split(",")]

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Bank sweep on {BASELINE_DESIGN}_d{BASELINE_DIAMETER_M:g}_m{BASELINE_PAYLOAD_KG:g} "
          f"ONLY: {len(angles)} angle(s) queued. Output dir: {args.output_dir}")

    rows = []
    for i, bank_deg in enumerate(angles, start=1):
        print(f"[{i}/{len(angles)}] bank={bank_deg:g} deg ...", end=" ", flush=True)
        row = run_one_bank(bank_deg, args.output_dir, args.exe)
        rows.append(row)
        print(row["status"])

    csv_path = os.path.join(args.output_dir, "bank_sweep_summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in FIELDNAMES})

    print(f"\nBank sweep summary: {csv_path}")


if __name__ == "__main__":
    main()
