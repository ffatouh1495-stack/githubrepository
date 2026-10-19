# Materials, Software, and Data Sources

This file lists every piece of software, tool, library, and data source
used in the Phase 0 POST2 pipeline, for the research paper's Materials
section. Two environments are involved — **fill in the Windows-side rows
once the 32-run batch actually executes there** (marked TBD below); the
Linux-side rows record what was used to build and unit-test this pipeline
in the Claude Code session.

## Simulation software

| Item | Version | Role |
|---|---|---|
| POST2 (Program to Optimize Simulated Trajectories II) | v5.0.0, dated 07/15/24 | Trajectory simulation. Confirmed from this project's own Example 1B run output header. |
| POST2 executable path | `C:\Users\Faris Fatouh\Downloads\ALLPOST2FILES\POST2v500\post2_windows_commercial.exe` | Per spec; confirm unchanged before the grid run |
| Mars-GRAM 2010 | Release 1.0 (NASA MSFC) | Generated `mars_atmosphere_gale.csv` (already run by the author per spec; not re-run here). Settings used to generate it: TBD -- author to record (Ls=150.7 deg, dust optical depth 0.48, Gale Crater 4.6 S/137.4 E, 6 Aug 2012 05:18 UTC per spec text; confirm full settings list, e.g. perturbation seed/scale, used when generating the file). |

## Automation / development environment

| Item | Version | Role |
|---|---|---|
| Python (build/test, this session) | 3.11.15 | Used to write and unit-test the pipeline code in this Claude Code session |
| Python (Windows execution) | **TBD** | Record the actual interpreter version used when running `batch_runner.py` on the Windows machine |
| Python packages (Windows venv) | **TBD** | Record `pip list` output from the Windows environment that runs the batch -- the pipeline itself only uses the Python standard library (csv, subprocess, math, re, dataclasses, argparse), so this should be short, but confirm and record it anyway per spec |
| Node.js | v22.22.2 (this session) | Not used by the pipeline itself; record if relevant to the Claude Code tooling used |
| Claude Code | (this session) | Used to develop this pipeline; record version/session details if required for the paper |
| Operating system (build/test) | Linux 6.18.44 (this session) | Pipeline development/unit-testing |
| Operating system (Windows execution) | **TBD** | Record the actual Windows version running POST2 |

## Data files

| File | Source | Status |
|---|---|---|
| `data/mars_atmosphere_gale.csv` | Mars-GRAM 2010 v1.0 output, Gale Crater, 6 Aug 2012 05:18 UTC, nominal mean atmosphere (density/wind perturbations scaled to 0), Ls=150.7 deg, dust optical depth 0.48. 146 rows, 1 km steps, -5000 m to 140000 m (MOLA areoid-referenced). Speed-of-sound column computed as sqrt(1.30 * 8314.462/MolWeight * T) -- gamma=1.30 assumed, not a Mars-GRAM output. | **NOT YET SUPPLIED** -- pipeline is blocked on this (see `mars_environment.py`) |
| `data/msl_CD_vs_Mach_digitized.csv` | Digitized from Schoenenberger et al., "Assessment of the Reconstructed Aerodynamics of the Mars Science Laboratory Entry Vehicle," AAS 13-306 (NTRS 20130010088), Figs. 12a, 12b, 14. Columns: Mach_approx, velocity_mps, CA, alpha_deg, L_over_D, CD. | **NOT YET SUPPLIED** -- `aero_data.py` currently uses the summary CD table transcribed directly from the spec (author-supplied, used as given) plus a placeholder L/D interpolation between two cited endpoints. Replace once this file exists (`config.AERO_DATA_FROM_DIGITIZED_FILE`). |

## Key literature sources (constants, event triggers, models)

| Source | Used for |
|---|---|
| Karlgaard, Kutty, Schoenenberger, Shidner, "Mars Science Laboratory Entry, Descent, and Landing Trajectory and Atmosphere Reconstruction," AAS 13-307 (NTRS 20130010087) | Powered-descent handoff state (1.7 km / 78.9 m/s), chute-deploy Mach (1.7), heat-shield-sep Mach (0.7) |
| Way et al., NTRS 20090007730, Table 1 | MSL entry mass (3,257 kg), heat-shield-sep Mach cross-check (0.7) |
| Cruz et al., "Parachute Models Used in the Mars Science Laboratory Entry, Descent, and Landing Simulation," NTRS 20130012762 | Parachute scaling rule, chute mass (46.826 kg), opening load factor (1.407), Fig. 9 chute CD curve (placeholder digitization pending) |
| Brandenburg, Williams, Woffinden, Putnam, NASA JSC/UIUC paper, Table 1 | Fixed entry interface state (altitude, lat/long, inertial velocity/FPA/azimuth), bank angle (-15 deg) |
| Schoenenberger et al., AAS 13-306 (NTRS 20130010088) | Shared CD-vs-Mach table, L/D prose endpoints |

## Open items affecting this record

- `mars_atmosphere_gale.csv` and `msl_CD_vs_Mach_digitized.csv` not yet supplied -- see above.
- NPC(5)=1 tabular-atmosphere syntax, ATMOSK(1)/(2) behavior, and NPC(6) wind syntax not yet confirmed against the POST2 manual -- see `mars_environment.py`.
- The no-silent-vacuum-run verification (spec-required, run on every scenario) has not yet been executed against a real run -- results will be recorded in README.md once the Windows-side batch runs.
