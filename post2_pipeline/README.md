# POST2 Phase 0 Pipeline — Mars EDL Aeroshell Trade Study

Automation pipeline for the Phase 0 fixed-wind validation run: 2 designs ×
4 diameters × 4 masses = **32 total POST2 runs**, one run per scenario,
same fixed wind for all 32, ending at the MSL powered-descent handoff
point (not simulating powered descent/sky crane). Built against
`phase0_spec_for_claude_code1.md`.

## Current status: UNBLOCKED (pipeline-side) — needs a real run on Windows

Both data files are now in place and wired in:

- `data/mars_atmosphere_gale.csv` (146 rows, confirmed) — loaded by
  `mars_environment.py`, converted to English units, emitted as the
  `PREST`/`ATEMT`/`CST`/`DENST` tables.
- `data/msl_CD_vs_Mach_digitized.csv` (195 rows, Mach 2.0599–25.5634) —
  loaded by `aero_data.py`; `BODY_CD_TABLE`/`BODY_CL_TABLE` now come
  directly from this file (CL = CD × L_over_D at each digitized point),
  not the placeholder prose-endpoint interpolation. The flat-hold
  boundary regions (below Mach 2.0599, above Mach 25.5634) now use the
  file's own actual endpoint values (CD=1.464 / CD=1.4544) rather than
  the spec markdown's rounded summary-table endpoints (2.06/1.464,
  25.0/1.460) — the file supersedes the inline summary per spec ("read
  the file; do not retype values").
- Baseline sanity check (900 kg / 4.5 m rigid): ballistic coefficient
  comes out to **140.8 kg/m²** against MSL's published ~145 kg/m²
  (~3% off) — using the real digitized hypersonic CD (1.4544) directly,
  not tuned. Within the spec's own stated digitization uncertainty
  (±0.02–0.03 in CD).
- `config.MARS_ATMOSPHERE_READY` / `config.AERO_DATA_FROM_DIGITIZED_FILE`
  both auto-detect via `os.path.exists(...)` — both are now `True`.
- Verified end-to-end in this session: `generate_input.build_input_deck()`
  now produces a full, real 331-line deck (no placeholder blocks) for
  both designs with no exceptions; `templates/*.inp` are regenerated
  from this real data and are genuinely runnable, not placeholders.
  `batch_runner.run_one()` now proceeds past input generation and only
  fails on POST2 execution itself, because this Linux session has no
  POST2 executable — expected, since POST2 only runs on the Windows
  machine. **No actual POST2 run has happened yet** — the pipeline has
  not been validated against real POST2 output with this data.

This mirrors a failure already hit once in this project: in Example 1A,
forgetting to set the Earth atmosphere flag didn't error — POST2 just
silently ran with zero density. That specific risk is now closed (real
data, confirmed syntax), but it's still unverified against the real
executable — run the required single-case verification (rigid, 4.5 m,
900 kg) before trusting the full 32-run grid.

## Confirmed manual syntax (this unblock)

- **IOFLAG = 0 (English units)**, not 3 (metric, used in Examples 1A/1B).
  Manual sections 4.a and 6.a.4: input units cannot be mixed within a
  problem. The spec's entry state and planet constants are sourced in
  English units, so the whole deck now uses English units throughout —
  `ft`, `ft/s`, `ft^3/s^2`, `lbf`, `°R`, `lb/ft^2`, `slug/ft^3`. All
  conversions happen in `generate_input.py` (deck-writing direction) and
  `parse_output.py` (reading POST2's English-unit output back to SI for
  reporting) — the rest of the pipeline (grid definition, mass model,
  ballistic coefficient) stays in metric for consistency with the rest of
  the project's reporting.
- **NPC(5) = 1** (general/tabular atmosphere; NPC(5)=7 is deprecated,
  not used), tables `PREST`/`ATEMT`/`CST`/`DENST` indexed by `GDALT`
  (ft). Table syntax (manual 6.d): `NAME = "label" monovar GDALT 0
  <interp> xtrap alt1 val1 alt2 val2 ...` — `log_inp` for
  pressure/density (strictly positive), `lin_inp` for
  temperature/speed-of-sound. Table size is "limited only by swap
  space," so the full 146 points are used, not thinned.
- **ATMOSK(1) and ATMOSK(2) left at their default 1.0** — both are only
  used to *derive* CS/DENS from ATEM/PRES when CST/DENST aren't supplied
  directly; since this pipeline supplies CST and DENST explicitly, the
  manual doesn't say what (if anything) ATMOSK still affects. Per spec:
  verify in the first real test run that POST2's printed `dens` at 10,
  40, 80 km matches the table (now implemented —
  `parse_output.run_vacuum_checks()` check 1) rather than tuning ATMOSK
  to force a match if it doesn't.
- **NPC(6) = 1** (winds from tables, not NPC(6)=3's vector
  interpolation, irrelevant for a constant wind), tables `VWT` (ft/s),
  `AZW_T` (deg), `VWWT` (vertical, positive downward, set to 0
  everywhere). Mars-GRAM's own mean winds are **not** used — wind comes
  only from `config.WIND_SPEED_MPS`/`WIND_DIRECTION_DEG`.
- **Wind azimuth convention**: `AZWB` (azimuth bias) is left at its
  default 180.0, under which `AZW_T` is **meteorological** — "an azimuth
  value of zero in the wind table represents a wind blowing from the
  north." So `WIND_DIRECTION_DEG = 0.0` means the 10 m/s wind blows
  **from the north, toward the south**. If a different direction was
  intended, only `config.WIND_DIRECTION_DEG` needs to change.
- **Planet constants**: `MU`/`RE`/`RP` in ft-based units, `J2` dimensionless,
  `J3`–`J8` explicitly zero. `RE_GRAV` still **PENDING** ("likely equal
  to RE" per spec, not separately confirmed).

## Items still needing manual verification (non-blocking)

Lower-risk than the atmosphere/wind block — each degrades gracefully or
produces a visible POST2 error rather than a silent wrong-physics run —
but not confirmed, and flagged `PENDING verify` in code/deck comments:

- **Latitude input convention**: sourced entry latitude is geodetic
  (`GDLAT = -3.9186°`), but the only validated `npc(4)=2` input keyword
  (Examples 1A/1B) is `gclat` (**geocentric**). `config.py` converts by
  hand (`tan(gclat) = (1-f)² tan(gdlat)`, Mars flattening f≈0.0058860),
  giving `gclat = -3.8727°`. If POST2 has a geodetic-latitude input
  option instead, use `EI_GDLAT_DEG` directly.
- **Bank angle syntax**: ~~`bnkpc = 'bnkpc', constant, 0, 15.0,`~~ — tried
  this first (by analogy with `cdt`/`clt`) and the first real test run
  rejected it: `*** ERROR *** Unrecognized char data[bnkpc] in numerical
  input[bnkpc]`. `BNKPC` is a plain scalar input, not a named table (this
  matches Example 1B's output, where `BNKPC` printed as a bare 4-number
  array, not a table). Fixed to `bnkpc = 15.0,`. **Sign convention is
  still unconfirmed** — check the first successful run's printed `bnkang`
  against the expected direction before trusting lift-related results.
- **`ALTMIN` as a global safety net**: set to the handoff `GDALT` so a
  scenario that never separates its heat shield (a valid, expected
  outcome per spec) still terminates at the handoff altitude instead of
  falling through undetected. Inferred from where `ALTMIN` was printed in
  Example 1B's output (a global "Program Termination Parameters" block,
  separate from any per-event criteria) — not directly tested, since
  Examples 1A/1B never triggered it.
- **`NPC(16)` gravity-model option**: reusing `npc(16)=2`
  ("oblate planet model"), validated for Earth in Examples 1A/1B, not
  re-confirmed specifically for Mars (though the mechanism is
  planet-constant-agnostic).
- **Wind output variable name**: vacuum check #4 (wind tables active)
  isn't implemented yet — no confirmed POST2-printed variable name for
  wind speed/direction has been observed. Once a real run exists, check
  its printed variable list for a wind-related field and wire it up.

## Layout

```
post2_pipeline/
  config.py                   All constants: unit conversions, Mars
                               gravity (English units), fixed entry state,
                               mass model, chute scaling, event trigger
                               Mach numbers, grid definition (metric).
  mars_environment.py         Mars atmosphere + wind block. Syntax
                               CONFIRMED; blocked only on the data file.
  aero_data.py                Shared CD/L-D table, loaded from the real
                               digitized CSV (dimensionless -- unaffected
                               by IOFLAG) + placeholder chute CD (still
                               prose-based, see below),
                               + the post-chute combined-drag-table builder.
  generate_input.py           Builds one .inp deck's text (English units)
                               for a given (design, diameter, payload_mass).
  run_post2.py                Subprocess wrapper; runs each scenario from
                               its own working directory.
  parse_output.py             Parses a .out file (English-unit POST2
                               output) into SI-unit metrics, plus the 5
                               no-silent-vacuum-run checks.
  batch_runner.py             Loops all 32 scenarios; writes per-run
                               .inp/.out/.log, phase0_summary.csv, and
                               RUN_MANIFEST.csv.
  MATERIALS_AND_SOFTWARE.md   Every tool/library/data source and its version.
  data/                       mars_atmosphere_gale.csv (146 rows) and
                               msl_CD_vs_Mach_digitized.csv (195 rows) --
                               both SUPPLIED, in place.
  templates/                  Reference decks (one per design). Now built
                               from the real data -- genuinely runnable,
                               not placeholders. Regenerate with
                               `python generate_input.py`.
  results/                    Created at run time (gitignored). One
                               subfolder per design; phase0_summary.csv;
                               RUN_MANIFEST.csv; a copy of the atmosphere CSV.
```

## Modeling decisions (per spec)

- **Mass model**: total entry mass = 2,358 kg (fixed, both designs, every
  diameter) + payload mass. Heat-shield/aeroshell separation (Mach 0.7)
  drops a flat **385 kg**, an **author assumption**, not sourced — never
  described as sourced anywhere.
- **Aerodynamics**: ONE shared CD-vs-Mach table and ONE shared L/D-vs-Mach
  table for both designs, loaded directly from the real
  `msl_CD_vs_Mach_digitized.csv` (195 points, Mach 2.0599–25.5634),
  held flat at the file's own actual endpoint values (CD=1.464 below
  Mach 2.0599, CD=1.4544 above Mach 25.5634 — literal repeated-value
  table points, not relying on `xtrap` extrapolation semantics). CL at
  each point = CD × L_over_D from the file, so lift and drag stay
  mutually consistent as the spec requires. Lift is zero below Mach
  2.0599 (balance masses jettisoned near Mach 2.0, per spec).
- **Bank angle**: one fixed value (15°) for the whole entry phase, zeroed
  after chute deploy.
- **Parachute**: MSL disk-gap-band, canopy area scaled to hold MSL's
  chute loading (3,257 kg / 357.94 m²) constant. Chute mass (46.826 kg)
  is NOT scaled — already inside the fixed 2,358 kg. Chute CD-vs-Mach is
  a **placeholder** 4-point table from the spec's prose description of
  Fig. 9 — needs a real digitization and author sign-off before the real
  grid run. Post-chute drag = chute drag + body drag, folded into one
  effective CD-vs-Mach table referenced to the body's own `SREF`
  (`aero_data.combined_post_chute_cd_table()`); this ratio is
  unit-independent, computed in metric even though the deck itself is in
  English units.
- **Event chain**: entry → chute deploy (Mach 1.7) → heat-shield
  separation (Mach 0.7) → handoff (1.7 km above the Gale local surface,
  `GDALT = -2055 m` / `-6742.13 ft`). All state-based triggers, never
  fixed time. A scenario that never reaches Mach 0.7 before the handoff
  altitude is valid and expected — recorded with
  `heat_shield_separated = False`.
- **Entry state**: identical for all 32 runs (133.0 km altitude, not
  125 km; -15.489° inertial FPA; 19,948 ft/s inertial velocity; 93.2065°
  inertial heading; -3.9186° geodetic latitude, converted — see above;
  +126.72° E longitude). Never tuned per scenario.
- **Gravity**: Mars oblate model (`npc(16)=2`), J2 only; J3–J8 explicitly
  zeroed.
- **Atmosphere table range**: -5,000 m to 140,000 m (-16,404.2 ft to
  459,317.6 ft), areoid-referenced, uncorrected for the ~0.43 km
  areoid-to-ellipsoid offset, per spec.
- **No heating**: Sutton-Graves/heat-rate calculation removed entirely.

## Required outputs → where they come from

| Output | Source |
|---|---|
| Payload / vehicle / total entry mass | computed directly (metric) |
| Ballistic coefficient | `total_mass / (CD_hypersonic × SREF)` (metric) |
| Peak deceleration (g) | max `sqrt(asxi²+asyi²+aszi²) / 32.174049` (ft/s², standard g) |
| Peak dynamic pressure | max `dynp`, converted lb/ft² → Pa |
| Velocity (inertial & relative), altitude above local surface, Mach at handoff | last row's `veli`/`velr` (ft/s→m/s), `gdalt` (ft→m) `- (-3755)`, `mach` |
| Total time (entry interface → handoff) | last row's `time` |
| Chute deploy altitude/Mach/dynp/velocity | first row of the post-deploy phase |
| Heat shield separation altitude/Mach/velocity | first row of the post-separation phase (`None` if Mach 0.7 never reached) |
| Chute opening force (informational) | `F = dynp_at_deploy(Pa) × S0(m²) × 1.407 × CD_chute(deploy_mach)`, N |

All reported values are converted back to SI in `parse_output.py` for
consistency with the rest of the project's metric reporting — the raw
`.out` file itself stays in POST2's native English units (IOFLAG=0).

`pinc = 1` in every generated deck so deploy/separation states are
captured precisely.

## No-silent-vacuum-run verification

Required before the 32-run grid: run ONE test case (rigid, 4.5 m,
900 kg) and check:

1. Atmosphere active (dynamic pressure nonzero; density at 10/40/80 km
   matches the table) — **implemented**: interpolates the loaded
   atmosphere table and compares against each test case's closest printed
   `dens` row, 5% tolerance (`vacuum_check_atmosphere_active`).
2. Vehicle decelerates from drag — **implemented**
   (`vacuum_check_decelerates`: peak g > 0.1 and velocity drops > 30%).
3. Gravity ≈ 3.71 m/s² near the surface — **implemented**
   (`vacuum_check_mars_gravity`, computed as `MU/gcrad²` at the final
   row, a J2-free approximation).
4. Wind tables active — **not implemented** (no confirmed output
   variable name for wind yet — see "Items still needing verification").
5. Trajectory stays within the atmosphere table range — **implemented**
   (`vacuum_check_within_table_range`).

`batch_runner.py` runs all 4 implemented checks on every scenario, not
just the single verification case, and marks a run's `status` as
`vacuum_check_failed` rather than `ok` if any fails.

**Results of the actual single-test-case verification**: not yet run —
pipeline is blocked on the atmosphere CSV. Fill in once run on the
Windows machine (dynamic pressure/density match, deceleration/velocity
drop, gravity near surface, wind active, within table range, and whether
the trajectory ends near Gale Crater touchdown at -4.59°/137.44° E).

## How to run (once un-blocked)

Only runs on the Windows machine with POST2 installed. Copy this whole
`post2_pipeline/` folder there (including `data/` once populated), then:

```
cd post2_pipeline
python batch_runner.py
```

Per spec, confirm the pipeline can reproduce `problem1a`'s result first
(using the reference `problem1a.inp`/`.out` already in the POST2 folder)
before trusting the grid runs — not automated by this pipeline.

Flags: `--exe <path>`, `--output-dir <path>`, `--design rigid`/`inflatable`
(useful for the required single-case smoke test first).

Each run writes `results/<design>/<scenario_id>.inp`, `.out`, `.log`
(stdout+stderr), executed from its own scratch working directory so
side-effect files POST2 writes (e.g. `profil`) never collide. `results/`
also gets a copy of the atmosphere CSV, `phase0_summary.csv`, and
`RUN_MANIFEST.csv`.

The batch does not stop on an individual scenario's POST2 error or a
failed vacuum check — it records the failure and moves on. It only stops
early if the Mars atmosphere block is still unset.

## Extending to Monte Carlo (future phase — not built yet)

`generate_input.build_input_deck()`, `run_post2.run_post2()`, and
`parse_output.parse_metrics()` stay separated as reusable functions
specifically so a future Monte Carlo runner can call them many times per
grid cell with dispersed inputs, without touching this Phase 0 code.
