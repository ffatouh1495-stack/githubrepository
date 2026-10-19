# POST2 Phase 0 Pipeline — Mars EDL Aeroshell Trade Study

Automation pipeline for the Phase 0 fixed-wind validation run: 2 designs ×
4 diameters × 4 masses = **32 total POST2 runs**, one run per scenario,
same fixed wind for all 32, ending at the MSL powered-descent handoff
point (not simulating powered descent/sky crane). Built against
`phase0_spec_for_claude_code.md`.

## Current status: BLOCKED

**Do not run this pipeline yet.** Two things are missing:

1. **Data files not yet supplied**: `data/mars_atmosphere_gale.csv`
   (Mars-GRAM atmosphere table) and `data/msl_CD_vs_Mach_digitized.csv`
   (full digitized CD/L-over-D table). The spec says "the author will
   supply" both.
2. **POST2 syntax not yet confirmed against the manual**: the tabular-
   atmosphere table names/units (`NPC(5)=1`, `PREST`/`ATEMT`/`CST`/`DENST`),
   `ATMOSK(1)`/`(2)` behavior, and the wind table syntax
   (`NPC(6)`, `VWT`, `AZW_T`, azimuth convention).

`mars_environment.py` raises `MarsEnvironmentNotReady` for every scenario
until both are resolved, so `batch_runner.py` stops immediately with
`status: blocked`. This mirrors a failure already hit once in this
project: in Example 1A, forgetting to set the Earth atmosphere flag didn't
error — POST2 just silently ran with zero density. The spec is explicit
that this is the single biggest risk in Phase 0.

**To un-block:** supply the two data files under `data/`, confirm the
syntax items above against the POST2 manual (the install folder's
`manuals` directory, or `inputs_windows` / `problem1a.inp`/`.out` as
worked examples), fill in `mars_environment.build_environment_block()`,
set `config.MARS_ATMOSPHERE_READY = True`, and set
`config.AERO_DATA_FROM_DIGITIZED_FILE = True` once the aero CSV is wired
into `aero_data.py`. See each file's module docstring for exactly what's
needed.

## Other items still needing manual verification (non-blocking)

These have a best-effort implementation already in place (clearly marked
`PENDING verify` in code comments and in the generated `.inp` decks), but
aren't confirmed against the manual. Getting one of these wrong is lower-
risk than the atmosphere/wind block (it degrades gracefully or produces a
visible POST2 error, not a silent wrong-physics run), so they don't block
the pipeline, but should be checked against the manual before trusting
results:

- **Latitude input convention**: the spec's sourced entry latitude is
  geodetic (`GDLAT = -3.9186`), but the only validated `npc(4)=2` input
  keyword from this project's own Examples 1A/1B is `gclat`
  (**geocentric**). `config.py` converts geodetic→geocentric by hand
  (`tan(gclat) = (1-f)² tan(gdlat)`, Mars flattening f≈0.0058860),
  producing `gclat = -3.8727°`. If POST2 actually has a geodetic-latitude
  input option, use `EI_GDLAT_DEG` directly instead.
- **Bank angle syntax**: implemented as `bnkpc = 'bnkpc', constant, 0, 15.0,`
  by analogy with the validated `cdt`/`clt` table mechanism. The "Use
  Angle of Attack, Sideslip, and Bank Commands" block seen in prior output
  suggests `ALPPC`/`BETPC`/`BNKPC` are genuine input keywords, but a
  constant-table command for a fixed bank angle hasn't been directly
  validated, and neither has the sign convention (spec: "confirm the sign
  convention in the POST2 manual").
- **`ALTMIN` as a global safety net**: set to the handoff GDALT
  (-2055 m) so a scenario that never separates its heat shield (Mach
  never reaches 0.7 — a valid, expected outcome per spec) still
  terminates at the handoff altitude instead of falling through toward
  the true surface undetected by the sequential event chain. Inferred
  from where `ALTMIN` was printed in Example 1B's "Program Termination
  Parameters" block (separate from any per-event criteria, suggesting a
  global/phase-independent check), not directly tested — Examples 1A/1B
  never actually triggered it. If this assumption is wrong, a run that
  never reaches Mach 0.7 could run past the handoff altitude undetected;
  check for this specifically on the first real test run (does the
  trajectory actually stop at `gdalt ≈ -2055` if it never separates?).
- **`RE_GRAV` for Mars**: set equal to `RE_MARS`, per the spec's own
  "likely equal to RE" — unconfirmed.

## Layout

```
post2_pipeline/
  config.py                   All constants: Mars gravity, fixed entry
                               state, mass model, chute scaling, event
                               trigger Mach numbers, grid definition.
  mars_environment.py         Mars atmosphere + wind block. BLOCKED, see above.
  aero_data.py                Shared CD/L-D table (author-supplied values)
                               + placeholder L/D + placeholder chute CD,
                               + the post-chute combined-drag-table builder.
  generate_input.py           Builds one .inp deck's text/mass/BC for a
                               given (design, diameter, payload_mass).
  run_post2.py                Subprocess wrapper; runs each scenario from
                               its own working directory.
  parse_output.py             Parses a .out file into the required metrics
                               plus the 5 no-silent-vacuum-run checks.
  batch_runner.py             Loops all 32 scenarios; writes per-run
                               .inp/.out/.log, phase0_summary.csv, and
                               RUN_MANIFEST.csv.
  MATERIALS_AND_SOFTWARE.md   Every tool/library/data source and its version.
  data/                       mars_atmosphere_gale.csv and
                               msl_CD_vs_Mach_digitized.csv go here once supplied.
  templates/                  Human-readable *reference* decks (one per
                               design), NOT runnable (placeholder env block).
                               Regenerate with `python generate_input.py`.
  results/                    Created at run time (gitignored). One
                               subfolder per design; phase0_summary.csv;
                               RUN_MANIFEST.csv; a copy of the atmosphere CSV.
```

## Modeling decisions (per spec)

- **Mass model**: total entry mass = 2,358 kg (fixed, both designs, every
  diameter — MSL's 3,257 kg entry mass minus 899 kg rover) + payload mass.
  Heat-shield/aeroshell separation (Mach 0.7) drops a flat **385 kg**,
  explicitly an **author assumption**, not sourced — never describe it as
  sourced anywhere. Same 385 kg for both rigid and inflatable.
- **Aerodynamics**: ONE shared CD-vs-Mach table and ONE shared L/D-vs-Mach
  table for both designs (deliberate — isolates diameter/mass as the only
  variables). CD table is the spec's own supplied values (Schoenenberger
  et al., digitized), held flat at 1.464 below Mach 2.06 and 1.460 above
  Mach 25 (implemented as literal repeated-value table points, not by
  relying on POST2's `xtrap` extrapolation behavior, which hasn't been
  confirmed). L/D is currently a **placeholder** linear interpolation
  between the two prose-cited endpoints (0.29 near Mach 2, 0.24 at Mach
  25) — replace once `msl_CD_vs_Mach_digitized.csv` exists. Lift is zero
  below Mach 2.06 (balance masses jettisoned near there, per spec).
- **Bank angle**: one fixed value (15°, Brandenburg et al.) for the whole
  entry phase, zeroed after chute deploy (moot once CL=0, zeroed anyway
  for clarity).
- **Parachute**: MSL disk-gap-band, canopy area scaled to hold MSL's chute
  loading (3,257 kg / 357.94 m²) constant: `S0 = 357.94 × (total_mass /
  3257)`. Chute mass (46.826 kg) is NOT scaled — it's already inside the
  fixed 2,358 kg. Chute CD-vs-Mach is a **placeholder** 4-point table (see
  "Current status" above) — needs a real digitization of Cruz et al. Fig.
  9 and author sign-off before the real (non-Phase-0-validation) grid run.
  Post-chute drag = chute drag + body drag, folded into one effective
  CD-vs-Mach table referenced to the body's own `SREF` (see
  `aero_data.combined_post_chute_cd_table()` for the derivation) — body
  drag's last digitized value (1.464) is held flat for all Mach below
  2.06, including through and after heat-shield separation, per spec.
- **Event chain**: entry → chute deploy (Mach 1.7, Karlgaard et al.) →
  heat-shield separation (Mach 0.7) → handoff (1.7 km above the Gale local
  surface, i.e. `GDALT = -2055 m` since Gale's surface sits at -3755 m
  relative to the MOLA areoid). All three triggers are state-based
  (Mach or altitude), never fixed time, per spec. A scenario that never
  reaches Mach 0.7 before the handoff altitude is valid and expected —
  recorded with `heat_shield_separated = False`, not forced.
- **Entry state**: identical for all 32 runs (Brandenburg et al. Table 1):
  133.0 km altitude (not 125 km), -15.489° inertial FPA, 6080.15 m/s
  inertial velocity, 93.2065° inertial heading, -3.9186° geodetic latitude
  (converted, see "non-blocking" section above), +126.72° E longitude.
  Never tuned per scenario, even for a scenario that skips out or impacts
  — that's a valid recorded result, not something to "fix."
- **Gravity**: Mars oblate model (`npc(16)=2`, the same flag validated for
  Earth in Examples 1A/1B), J2 only (1.96045e-3); J3-J8 explicitly zeroed.
- **Atmosphere table range**: -5,000 m to 140,000 m (areoid-referenced).
  The areoid-to-ellipsoid offset (~0.43 km) is NOT corrected, per spec —
  all GDALT values are used as given, consistently, throughout.
- **No heating**: Sutton-Graves/heat-rate calculation from the Phase 0 v1
  build has been removed entirely — the author decided to drop it.

## Required outputs → where they come from

| Output | Source |
|---|---|
| Payload / vehicle / total entry mass | computed directly (not from POST2 output) |
| Ballistic coefficient | `total_mass / (CD_hypersonic × SREF)`, `SREF = π(d/2)²` |
| Peak deceleration (g) | max over all rows of `sqrt(asxi²+asyi²+aszi²) / 9.80665` (sensed, non-gravitational acceleration) |
| Peak dynamic pressure | max `dynp` |
| Velocity (inertial & relative), altitude above local surface, Mach at handoff | last row's `veli`, `velr`, `gdalt - (-3755)`, `mach` |
| Total time (entry interface → handoff) | last row's `time` |
| Chute deploy altitude/Mach/dynp/velocity | first row of the post-deploy phase |
| Heat shield separation altitude/Mach/velocity | first row of the post-separation phase (absent/`None` if Mach 0.7 never reached) |
| Chute opening force (informational) | `F = dynp_at_deploy × S0 × 1.407 × CD_chute(deploy_mach)` |

`pinc = 1` in every generated deck (fine row density) so deploy/separation
states are captured precisely rather than only every 50 s.

## No-silent-vacuum-run verification

Required by spec before the 32-run grid: run ONE test case (rigid, 4.5 m,
900 kg) and check:

1. Atmosphere active (dynamic pressure nonzero; density at ~10/40/80 km
   matches the table) — **partially implemented**: `parse_output.py`
   confirms `dynp > 0`, but the direct table cross-match isn't implemented
   yet (needs the atmosphere CSV to be loadable — pending).
2. Vehicle decelerates from drag (peak deceleration clearly nonzero,
   velocity drops substantially) — **implemented** (`vacuum_check_decelerates`).
3. Planet constants took effect (gravity ≈ 3.71 m/s² near the surface) —
   **implemented** (`vacuum_check_mars_gravity`, computed as `MU_MARS /
   gcrad²` at the final row, so it's a J2-free approximation — expect it
   to be close to but not exactly 3.71).
4. Wind tables active — **not implemented yet** (needs to know which
   variable name(s) POST2 actually prints for wind, pending atmosphere/wind
   syntax confirmation).
5. Trajectory stays within the -5,000 to 140,000 m table range —
   **implemented** (`vacuum_check_within_table_range`).

`batch_runner.py` runs all 5 (as far as implemented) on every scenario,
not just the single verification case, and marks a run's `status` as
`vacuum_check_failed` rather than `ok` if any implemented check fails —
it is never silently recorded as valid.

**Results of the actual single-test-case verification**: not yet run
(pipeline is blocked — see "Current status"). Fill in once it's been run
on the Windows machine:
- Dynamic pressure nonzero: TBD
- Density match at 10/40/80 km: TBD
- Peak deceleration / velocity drop: TBD
- Gravity near surface: TBD
- Wind active: TBD
- Within table range: TBD
- Trajectory ends near Gale Crater touchdown (-4.59°, 137.44° E)?: TBD

## How to run (once un-blocked)

Only runs on the Windows machine with POST2 installed. Copy this whole
`post2_pipeline/` folder there (including `data/` once populated), then:

```
cd post2_pipeline
python batch_runner.py
```

Per spec, confirm the pipeline can reproduce `problem1a`'s result first
(using the reference `problem1a.inp`/`.out` already in the POST2 folder)
before trusting the grid runs — this pipeline doesn't automate that
reproduction check itself.

Flags:
- `--exe <path>` — override the POST2 executable path
- `--output-dir <path>` — override where results go (default `results/`)
- `--design rigid` / `--design inflatable` — run only one design's 16
  scenarios (useful for the required single-case smoke test first)

Each run writes `results/<design>/<scenario_id>.inp`, `.out`, and `.log`
(stdout+stderr), executed from its own scratch working directory
(`results/<design>/_work/<scenario_id>/`) so side-effect files POST2
writes (e.g. `profil`) never collide between runs. `results/` also gets a
copy of the atmosphere CSV, `phase0_summary.csv` (one row per run, every
required metric), and `RUN_MANIFEST.csv` (paths + POST2/atmosphere file
used + run timestamp + status, for full traceability back to raw files).

The batch does not stop on an individual scenario's POST2 error or a
failed vacuum check — it records the failure in that row and moves on, so
one bad grid cell doesn't block the other 31. It only stops early if the
Mars atmosphere/wind block is still unset, since every remaining scenario
would then fail identically.

## Extending to Monte Carlo (future phase — not built yet)

`generate_input.build_input_deck()`, `run_post2.run_post2()`, and
`parse_output.parse_metrics()` stay separated as reusable functions
specifically so a future Monte Carlo runner can call them many times per
grid cell with dispersed inputs, without touching this Phase 0 code. No
randomization or repeated-run logic exists yet, per the spec.
