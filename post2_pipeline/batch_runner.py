"""
Phase 0 batch runner: exactly one POST2 run per grid cell (32 total),
fixed wind, no repeats, no randomization.

Usage (on the Windows machine with POST2 installed):
    python batch_runner.py

See README.md for setup, the required pre-grid single-case verification,
and what each output file/folder means.
"""

import argparse
import csv
import datetime
import os
import shutil
import traceback

import config
import generate_input
import run_post2
import parse_output
from mars_environment import MarsEnvironmentNotReady

SUMMARY_CSV_FIELDS = [
    "scenario_id", "design", "diameter_m",
    "payload_mass_kg", "vehicle_mass_kg", "total_entry_mass_kg",
    "wind_speed_mps", "wind_direction_deg",
    "inp_path", "out_path", "log_path",
    "post2_warnings", "post2_errors", "post2_termination_mode", "status", "error_message",

    "ballistic_coefficient_kg_m2",
    "peak_deceleration_g", "peak_deceleration_time_s", "peak_dynamic_pressure_pa",
    "max_altitude_after_peak_decel_m", "max_abs_bnkang_deg",
    "last_event_number_reached", "handoff_reached",

    "chute_deploy_time_s", "chute_deploy_altitude_m",
    "chute_deploy_altitude_above_surface_m", "chute_deploy_mach",
    "chute_deploy_dynp_pa", "chute_deploy_velocity_relative_mps", "chute_opening_force_n",

    "heat_shield_separated", "heat_shield_sep_altitude_m",
    "heat_shield_sep_mach", "heat_shield_sep_velocity_relative_mps",

    "handoff_time_s", "handoff_gdalt_m", "handoff_altitude_above_surface_m",
    "handoff_velocity_inertial_mps", "handoff_velocity_relative_mps",
    "handoff_mach", "handoff_phase",

    "vacuum_check_atmosphere_active", "vacuum_check_decelerates",
    "vacuum_check_mars_gravity", "vacuum_check_wind_active_CHECKED",
    "vacuum_check_within_table_range",
]

MANIFEST_CSV_FIELDS = [
    "scenario_id", "design", "diameter_m", "payload_mass_kg",
    "inp_path", "out_path", "log_path",
    "post2_exe", "atmosphere_csv", "run_datetime_utc", "status",
]


def iter_scenarios():
    for design, spec in config.DESIGNS.items():
        for diameter_m in spec["diameters_m"]:
            for payload_mass_kg in config.PAYLOAD_MASSES_KG:
                yield design, diameter_m, payload_mass_kg


def run_one(design, diameter_m, payload_mass_kg, output_root, exe_path):
    sid = generate_input.scenario_id(design, diameter_m, payload_mass_kg)
    design_dir = os.path.join(output_root, design)
    work_dir = os.path.join(design_dir, "_work", sid)
    os.makedirs(work_dir, exist_ok=True)

    work_inp = os.path.join(work_dir, f"{sid}.inp")
    work_out = os.path.join(work_dir, f"{sid}.out")
    final_inp = os.path.join(design_dir, f"{sid}.inp")
    final_out = os.path.join(design_dir, f"{sid}.out")
    final_log = os.path.join(design_dir, f"{sid}.log")

    row = {
        "scenario_id": sid, "design": design, "diameter_m": diameter_m,
        "payload_mass_kg": payload_mass_kg,
        "wind_speed_mps": config.WIND_SPEED_MPS,
        "wind_direction_deg": config.WIND_DIRECTION_DEG,
        "inp_path": final_inp, "out_path": final_out, "log_path": final_log,
        "post2_warnings": None, "post2_errors": None,
        "status": "not_started", "error_message": "",
        "_run_datetime_utc": datetime.datetime.utcnow().isoformat() + "Z",
    }

    try:
        generate_input.write_input_deck(
            design, diameter_m, payload_mass_kg, work_inp,
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
        result = run_post2.run_post2(sid, f"{sid}.inp", f"{sid}.out", cwd=work_dir, exe_path=exe_path)
    except Exception as e:
        row["status"] = "post2_execution_failed"
        row["error_message"] = f"{e}\n{traceback.format_exc()}"
        shutil.copyfile(work_inp, final_inp)
        return row

    os.makedirs(design_dir, exist_ok=True)
    shutil.copyfile(work_inp, final_inp)
    with open(final_log, "w") as f:
        f.write("=== stdout ===\n")
        f.write(result.stdout)
        f.write("\n=== stderr ===\n")
        f.write(result.stderr)

    row["post2_warnings"] = result.warnings
    row["post2_errors"] = result.errors
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
        metrics = parse_output.parse_metrics(out_text, diameter_m, payload_mass_kg)
    except Exception as e:
        row["status"] = "parse_failed"
        row["error_message"] = f"{e}\n{traceback.format_exc()}"
        return row

    vacuum_checks_detail = metrics.pop("vacuum_checks_detail")
    row.update(metrics)

    implemented_checks_pass = (
        metrics["vacuum_check_atmosphere_active"]
        and metrics["vacuum_check_decelerates"]
        and metrics["vacuum_check_mars_gravity"]
        and metrics["vacuum_check_within_table_range"]
    )
    # Reaching the handoff point (chute deployed, then heat shield
    # separated, before the run ended) is a harder requirement than the 4
    # vacuum checks above and gates first: a run that skips and never gets
    # the heat shield off is a failure regardless of whether the
    # atmosphere/gravity/density checks happen to pass along the way.
    if not metrics["handoff_reached"]:
        row["status"] = "handoff_not_reached"
    elif not implemented_checks_pass:
        row["status"] = "vacuum_check_failed"
    else:
        row["status"] = "ok"
    row["_vacuum_checks_detail"] = vacuum_checks_detail
    return row


def main():
    parser = argparse.ArgumentParser(description="Phase 0 fixed-wind validation batch (32 runs).")
    parser.add_argument("--exe", default=config.POST2_EXE, help="Path to post2_windows_commercial.exe")
    parser.add_argument("--output-dir", default=config.OUTPUT_ROOT, help="Where .inp/.out/.log files and the summary/manifest CSVs go")
    parser.add_argument("--design", choices=list(config.DESIGNS), default=None,
                         help="Restrict to one design (for testing); default runs both (32 total)")
    parser.add_argument("--only", default=None, metavar="SCENARIO_ID",
                         help="Run exactly one scenario by its scenario_id, e.g. "
                              "rigid_d4.5_m900 (the required single-case verification "
                              "before the full 32-run grid). Overrides --design.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if os.path.exists(config.MARS_ATMOSPHERE_CSV):
        shutil.copyfile(
            config.MARS_ATMOSPHERE_CSV,
            os.path.join(args.output_dir, os.path.basename(config.MARS_ATMOSPHERE_CSV)),
        )

    if args.only:
        scenarios = [
            (d, dia, m) for d, dia, m in iter_scenarios()
            if generate_input.scenario_id(d, dia, m) == args.only
        ]
        if not scenarios:
            all_ids = [generate_input.scenario_id(d, dia, m) for d, dia, m in iter_scenarios()]
            parser.error(
                f"--only {args.only!r} matched no scenario. Valid scenario_ids:\n  "
                + "\n  ".join(all_ids)
            )
    else:
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

    summary_csv_path = os.path.join(args.output_dir, "phase0_summary.csv")
    with open(summary_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in SUMMARY_CSV_FIELDS})

    manifest_csv_path = os.path.join(args.output_dir, "RUN_MANIFEST.csv")
    with open(manifest_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "scenario_id": row["scenario_id"], "design": row["design"],
                "diameter_m": row["diameter_m"], "payload_mass_kg": row["payload_mass_kg"],
                "inp_path": row["inp_path"], "out_path": row["out_path"], "log_path": row["log_path"],
                "post2_exe": args.exe, "atmosphere_csv": config.MARS_ATMOSPHERE_CSV,
                "run_datetime_utc": row.get("_run_datetime_utc"), "status": row["status"],
            })

    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(rows)} scenarios completed successfully.")
    print(f"Summary CSV: {summary_csv_path}")
    print(f"Run manifest: {manifest_csv_path}")


if __name__ == "__main__":
    main()
