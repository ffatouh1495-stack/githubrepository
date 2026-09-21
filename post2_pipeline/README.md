# POST2 Phase 0 Pipeline — Mars EDL Aeroshell Trade Study

Automation pipeline for the Phase 0 fixed-wind validation run described in
the Phase 0 build spec: 2 designs × 4 diameters × 4 masses = **32 total
POST2 runs**, one run per scenario, same fixed wind for all 32. Purpose is
to validate the input templates, execution loop, and output parsing — not
to produce science-grade results yet.

## Current status: BLOCKED on Mars atmosphere data

**Do not run this pipeline yet.** `mars_environment.py` intentionally
raises `MarsEnvironmentNotReady` for every scenario until the Mars
atmosphere + wind syntax is confirmed and filled in. This mirrors a real
failure we already hit once: in the manual's Example 1A, forgetting to set
the atmosphere flag didn't produce an error — POST2 just silently ran with
zero density the whole way down. Getting Mars atmosphere wrong the same
way, 32 times, would waste a lot of runs. `batch_runner.py` will print
`blocked` and stop on the first scenario until this is resolved.

**To un-block:** once the Mars-GRAM data (or the manual's Mars/tabular
atmosphere section) is available, fill in
`mars_environment.build_environment_block()` with the real POST2 syntax,
then set `config.MARS_ATMOSPHERE_READY = True`. Nothing else in the
pipeline needs to change.

## Layout

```
post2_pipeline/
  config.py            Grid definition, Mars constants, mass model, all
                        the "turn this knob" values in one place.
  mars_environment.py  Mars atmosphere + wind block. PENDING (see above).
  aero_data.py         CD/CL-vs-Mach tables for rigid and inflatable.
  generate_input.py    Builds one .inp deck's text for a given
                        (design, diameter, payload_mass).
  run_post2.py          Subprocess wrapper around post2_windows_commercial.exe.
  parse_output.py       Parses a .out file into the required metrics.
  batch_runner.py       Loops all 32 scenarios; calls the above three in
                        sequence; writes per-run .inp/.out files and a
                        summary CSV.
  templates/            Human-readable *reference* decks (one per design,
                        at each design's baseline grid cell), for eyeballing
                        deck structure directly. NOT runnable -- the
                        atmosphere block is a placeholder comment.
                        Regenerate after changing generate_input.py with:
                        python generate_input.py
  results/              Created at run time (gitignored). One subfolder
                        per design, one .inp + .out file per scenario,
                        plus phase0_summary.csv.
```

## How each scenario is modeled (Phase 0 simplifications)

- **Mass model**: the grid's "payload mass" (900–3600 kg) is scaled to a
  total entry mass using MSL's real payload/entry-mass ratio
  (899/3257 ≈ 0.276), applied identically to both designs. At the
  jettison event, mass drops back to just the payload mass. This ratio is
  a placeholder — real aeroshell mass fractions differ between rigid and
  inflatable designs and should be revisited before Phase 1.
- **Aerodynamics**: `aero_data.py` has representative, literature-based
  CD-vs-Mach tables, not mission data. The rigid table's hypersonic CD
  (1.42) is deliberately the vehicle's *trimmed axial-force coefficient*
  (not the ~1.7 zero-AoA symmetric drag estimate) — that's what makes the
  900 kg / 4.5 m baseline cell reproduce MSL's published β ≈ 145 kg/m²
  (verified by hand: entry mass 3260.6 kg, Sref 15.90 m², CD 1.42 → β =
  144.4 kg/m²). CL is held at a constant L/D = 0.24 (MSL's real trimmed
  hypersonic value) across the whole table — a Phase 0 simplification,
  since real L/D isn't Mach-invariant. The inflatable table has no
  baseline to check against; it's flown ballistic (CL = 0) per common
  HIAD literature practice.
- **Jettison / decelerator-deploy trigger**: a POST2 event with
  `critr = 'dynp'` (dynamic pressure) — **not** altitude or time, per the
  spec. Rigid triggers at 750 Pa (MSL's approximate real supersonic-chute
  deploy dynamic pressure); inflatable triggers at 500 Pa (representative
  of the Mach ~0.9–2 release window described in the spec). Check each
  run's `deploy_mach` output against that window.
- **Post-jettison phase**: mass drops to payload-only, and CD is bumped to
  a flat 2.0 (`config.POST_JETTISON_CD`) on the *same* reference area.
  This is **not** a real parachute model — Phase 0 doesn't model canopy
  geometry or inflation dynamics at all. It exists only to validate that
  the trigger → phase swap → output parsing mechanics work end-to-end.
- **Entry conditions**: MSL's real values (γ = -15.49°, V = 5900 m/s,
  entry interface at 125 km) are used for every one of the 32 scenarios.
  The spec calls for re-checking dynamic feasibility per scenario since
  mass/diameter vary — Phase 0 does not do this automatically. If a run's
  output looks non-physical (skips out, never reaches the surface,
  implausible g-loads), that scenario's entry angle needs a manual
  feasibility check before trusting its numbers.
- **Gravity**: Mars oblate model (`npc(16)=2`) using standard published
  Mars constants (`config.py`), J2 only — higher-order zonal harmonics
  (J3–J8, which Earth's `npc(16)=2` example did include) are not modeled
  for Mars in Phase 0.
- **"g-load" convention**: peak deceleration is reported in standard Earth
  g (9.80665 m/s²), matching how Mars entry deceleration is conventionally
  reported in the literature (e.g. "MSL saw ~10 g"), not Mars surface
  gravity. Also note POST2 itself prints `GO = 9.80665` regardless of
  which planet's gravity model is active (confirmed in the Example 1B
  output) — it's a weight/mass bookkeeping constant, not the local
  gravitational acceleration driving the trajectory.

## Required metrics and how they're computed

| Metric | Source |
|---|---|
| Peak deceleration (g) | max over all rows of `sqrt(asxi²+asyi²+aszi²) / 9.80665` — sensed (non-gravitational) acceleration, i.e. what an accelerometer reads, not total acceleration including gravity |
| Peak dynamic pressure | max `dynp` |
| Peak stagnation heat rate | Sutton-Graves: `q = K·sqrt(ρ/Rn)·V³` computed per row from `dens` and `velr`, `K = 1.7415e-4`. `Rn` (nose radius) = a fixed fraction of the aeroshell radius per design (`config.NOSE_RADIUS_FRACTION`: 0.5 for rigid, matching MSL's actual 1.125 m / 2.25 m geometry; 0.7 for inflatable, since HIADs are blunter) |
| Total heat load | trapezoidal integration of the heat-rate series over time |
| Terminal/touchdown velocity | `velr` at the final row (gdalt ≈ 0) |
| Total descent time | final row's `time` |
| Parachute deploy altitude/Mach | `gdalt`/`mach` at the first row of the post-jettison phase |
| Ballistic coefficient | computed directly (not from POST2 output): `β = entry_mass / (CD_hypersonic × Sref)` |

`parse_output.py` reads the printed profile rows directly (the same
`time ... gdalt ... dynp ... mach ...` block format hand-verified against
the real Example 1B output) — it does not depend on anything Mars-specific,
so it's already been tested against that output (see
`git log` / dev notes) and needs no changes once real Mars runs exist.

`pinc = 1` is set in every generated deck (finer than the `pinc = 50` used
in the tutorial examples) specifically so there's enough row density for
peak-search and heat-load integration to be meaningful. This means each
`.out` file will be much larger than the earlier tutorial examples — fine
at 32 runs, but worth knowing before scaling this up in a later phase.

## How to run Phase 0 (once un-blocked)

This only runs on the Windows machine with POST2 installed
(`post2_windows_commercial.exe`). Copy this whole `post2_pipeline/` folder
there (or clone the repo), then:

```
cd post2_pipeline
python batch_runner.py
```

Optional flags:
- `--exe <path>` — override the POST2 executable path (default is set in
  `config.POST2_EXE`, currently pointed at the `ALLPOST2FILES\POST2v500`
  folder from the tutorial session)
- `--output-dir <path>` — override where results go (default `results/`)
- `--design rigid` or `--design inflatable` — run only one design's 16
  scenarios, useful for a first smoke test before committing to all 32

Each run writes:
- `results/<design>/d<diameter>_m<mass>.inp` — the exact input deck used
- `results/<design>/d<diameter>_m<mass>.out` — the full raw POST2 output,
  kept permanently (not discarded after parsing)
- one row in `results/phase0_summary.csv` with every computed metric, the
  scenario's parameters, the wind conditions used, and a `status` column
  (`ok`, `blocked`, `post2_reported_errors`, `parse_failed`, etc.) so a
  failed scenario is visible in the summary without having to open its
  `.out` file — though you still can, since it's saved either way.

The batch does **not** stop on an individual scenario's POST2 error — it
records the failure in that row's `status`/`error_message` and moves on,
so one bad grid cell doesn't block the other 31. It only stops early if
the Mars atmosphere block is still unset (`status = blocked`), since in
that case every remaining scenario would fail identically.

## Extending to Monte Carlo (future phase — not built yet)

`generate_input.build_input_deck()`, `run_post2.run_post2()`, and
`parse_output.parse_metrics()` are already separated as reusable functions
specifically so a future Monte Carlo runner can call
`build_input_deck(design, diameter, mass, wind_speed, wind_direction)`
many times per grid cell with dispersed wind (or other) inputs, without
touching this Phase 0 code. No randomization or repeated-run logic exists
yet, per the Phase 0 spec.
