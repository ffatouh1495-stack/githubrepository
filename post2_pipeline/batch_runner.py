"""
Phase 0 batch runner: exactly one POST2 run per grid cell (32 total),
fixed wind, no repeats, no randomization.

Usage (on the Windows machine with POST2 installed):
    python batch_runner.py

See README.md for setup and what each output file/folder means.
"""

import argparse
import csv
import os
import traceback

import config
import generate_input
import run_post2
import parse_output
from mars_environment import MarsEnvironmentNotReady

CSV_FIELDS = [
    "scenario_id", "design", "diameter_m", "payload_mass_kg",
    "wind_speed_mps", "wind_direction_deg",
    "inp_path", "out_path",
    "post2_warnings", "post2_errors", "status", "error_message",
    "peak_deceleration_g", "peak_dynamic_pressure_pa",
    "peak_heat_rate_w_cm2", "total_heat_load_j_cm2",
    "touchdown_velocity_mps", "total_descent_time_s",
    "deploy_altitude_m", "deploy_mach", "ballistic_coefficient_kg_m2",
]


def iter_scenarios():
    for design, spec in config.DESIGNS.items():
        for diameter_m in spec["diameters_m"]:
            for payload_mass_kg in config.PAYLOAD_MASSES_KG:
                yield design, diameter_m, payload_mass_kg


def run_one(design, diameter_m, payload_mass_kg, output_root, exe_path):
    sid = generate_input.scenario_id(design, diameter_m, payload_mass_kg)
    design_dir = os.path.join(output_root, design)
    os.makedirs(design_dir, exist_ok=True)

    inp_path = os.path.join(design_dir, f"d{diameter_m:g}_m{payload_mass_kg:g}.inp")
    out_path = os.path.join(design_dir, f"d{diameter_m:g}_m{payload_mass_kg:g}.out")

    row = {
        "scenario_id": sid,
        "design": design,
        "diameter_m": diameter_m,
        "payload_mass_kg": payload_mass_kg,
        "wind_speed_mps": config.WIND_SPEED_MPS,
        "wind_direction_deg": config.WIND_DIRECTION_DEG,
        "inp_path": inp_path,
        "out_path": out_path,
        "post2_warnings": None,
        "post2_errors": None,
        "status": "not_started",
        "error_message": "",
    }

    try:
        generate_input.write_input_deck(
            design, diameter_m, payload_mass_kg, inp_path,
            wind_speed_mps=config.WIND_SPEED_MPS,
            wind_direction_deg=config.WIND_DIRECTION_DEG,
        )
    except MarsEnvironmentNotReady as e:
        row["status"] = "blocked"
        row["error_message"] = str(e)
        return row
    except Exception as e:
        row["status"] = "input_generation_failed"
        row["error_message"] = f"{e}\n{traceback.format_exc()}"
        return row

    try:
        result = run_post2.run_post2(sid, inp_path, out_path, exe_path=exe_path)
    except Exception as e:
        row["status"] = "post2_execution_failed"
        row["error_message"] = f"{e}\n{traceback.format_exc()}"
        return row

    row["post2_warnings"] = result.warnings
    row["post2_errors"] = result.errors

    if not result.ok:
        row["status"] = "post2_reported_errors"
        row["error_message"] = f"returncode={result.returncode} stderr={result.stderr[:500]}"
        return row

    try:
        with open(out_path, "r", errors="replace") as f:
            out_text = f.read()
        metrics = parse_output.parse_metrics(out_text, design, diameter_m, payload_mass_kg)
    except Exception as e:
        row["status"] = "parse_failed"
        row["error_message"] = f"{e}\n{traceback.format_exc()}"
        return row

    row.update(metrics)
    row["status"] = "ok"
    return row


def main():
    parser = argparse.ArgumentParser(description="Phase 0 fixed-wind validation batch (32 runs).")
    parser.add_argument("--exe", default=config.POST2_EXE, help="Path to post2_windows_commercial.exe")
    parser.add_argument("--output-dir", default=config.OUTPUT_ROOT, help="Where .inp/.out files and the summary CSV go")
    parser.add_argument("--design", choices=list(config.DESIGNS), default=None,
                         help="Restrict to one design (for testing); default runs both (32 total)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    csv_path = os.path.join(args.output_dir, "phase0_summary.csv")

    scenarios = [
        (d, dia, m) for d, dia, m in iter_scenarios()
        if args.design is None or d == args.design
    ]

    print(f"Phase 0: {len(scenarios)} scenario(s) queued. Output dir: {args.output_dir}")

    rows = []
    for i, (design, diameter_m, payload_mass_kg) in enumerate(scenarios, start=1):
        sid = generate_input.scenario_id(design, diameter_m, payload_mass_kg)
        print(f"[{i}/{len(scenarios)}] {sid} ...", end=" ", flush=True)
        row = run_one(design, diameter_m, payload_mass_kg, args.output_dir, args.exe)
        rows.append(row)
        print(row["status"])
        if row["status"] == "blocked":
            print("  -> Mars atmosphere/wind block not ready yet. Stopping batch early.")
            break

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in CSV_FIELDS})

    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(rows)} scenarios completed successfully.")
    print(f"Summary CSV: {csv_path}")


if __name__ == "__main__":
    main()
