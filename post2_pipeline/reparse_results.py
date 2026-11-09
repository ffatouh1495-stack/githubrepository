"""
Re-parse existing .out files into a fresh phase0_summary.csv, WITHOUT
re-running POST2. Use this whenever parse_output.py changes (new metrics,
bugfixes) but the underlying POST2 runs are still valid and you don't
want to pay for a full re-run.

Usage:
    python reparse_results.py
    python reparse_results.py --only rigid_d4.5_m900
    python reparse_results.py --output-dir results

Looks for results/<design>/<scenario_id>.out for every scenario in the
grid (or just the one named via --only) and re-parses whichever ones it
finds. Scenarios with no .out file on disk are skipped (reported, not
treated as an error) -- run batch_runner.py for those instead.
"""

import argparse
import csv
import os

import config
import generate_input
import parse_output
import batch_runner


def reparse_one(design, diameter_m, payload_mass_kg, output_root):
    sid = generate_input.scenario_id(design, diameter_m, payload_mass_kg)
    design_dir = os.path.join(output_root, design)
    out_path = os.path.join(design_dir, f"{sid}.out")
    inp_path = os.path.join(design_dir, f"{sid}.inp")
    log_path = os.path.join(design_dir, f"{sid}.log")

    row = {
        "scenario_id": sid, "design": design, "diameter_m": diameter_m,
        "payload_mass_kg": payload_mass_kg,
        "wind_speed_mps": config.WIND_SPEED_MPS,
        "wind_direction_deg": config.WIND_DIRECTION_DEG,
        "inp_path": inp_path, "out_path": out_path, "log_path": log_path,
        "status": "not_found", "error_message": "",
    }

    if not os.path.exists(out_path):
        row["error_message"] = f"{out_path} not found -- run batch_runner.py for this scenario"
        return row

    try:
        with open(out_path, "r", errors="replace") as f:
            out_text = f.read()
        metrics = parse_output.parse_metrics(out_text, diameter_m, payload_mass_kg)
    except Exception as e:
        row["status"] = "parse_failed"
        row["error_message"] = str(e)
        return row

    metrics.pop("vacuum_checks_detail", None)
    row.update(metrics)

    implemented_checks_pass = (
        metrics["vacuum_check_atmosphere_active"]
        and metrics["vacuum_check_decelerates"]
        and metrics["vacuum_check_mars_gravity"]
        and metrics["vacuum_check_within_table_range"]
    )
    if not metrics["handoff_reached"]:
        row["status"] = "handoff_not_reached"
    elif not implemented_checks_pass:
        row["status"] = "vacuum_check_failed"
    else:
        row["status"] = "ok"
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=config.OUTPUT_ROOT,
                         help="Where results/<design>/<scenario_id>.out already live")
    parser.add_argument("--only", default=None, metavar="SCENARIO_ID",
                         help="Re-parse exactly one scenario by its scenario_id")
    args = parser.parse_args()

    if args.only:
        scenarios = [
            (d, dia, m) for d, dia, m in batch_runner.iter_scenarios()
            if generate_input.scenario_id(d, dia, m) == args.only
        ]
        if not scenarios:
            all_ids = [generate_input.scenario_id(d, dia, m) for d, dia, m in batch_runner.iter_scenarios()]
            parser.error(f"--only {args.only!r} matched no scenario. Valid scenario_ids:\n  " + "\n  ".join(all_ids))
    else:
        scenarios = list(batch_runner.iter_scenarios())

    print(f"Re-parsing {len(scenarios)} scenario(s) from existing .out files in {args.output_dir} ...")

    rows = []
    found = 0
    for i, (design, diameter_m, payload_mass_kg) in enumerate(scenarios, start=1):
        sid = generate_input.scenario_id(design, diameter_m, payload_mass_kg)
        print(f"[{i}/{len(scenarios)}] {sid} ...", end=" ", flush=True)
        row = reparse_one(design, diameter_m, payload_mass_kg, args.output_dir)
        rows.append(row)
        print(row["status"])
        if row["status"] != "not_found":
            found += 1

    summary_csv_path = os.path.join(args.output_dir, "phase0_summary.csv")
    with open(summary_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=batch_runner.SUMMARY_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in batch_runner.SUMMARY_CSV_FIELDS})

    print(f"\nRe-parsed {found}/{len(rows)} scenario(s) (others had no .out file on disk).")
    print(f"Summary CSV rewritten: {summary_csv_path}")


if __name__ == "__main__":
    main()
