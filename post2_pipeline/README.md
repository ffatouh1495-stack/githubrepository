# POST2 Phase 0 Pipeline — Mars EDL Aeroshell Trade Study

Automation pipeline for the Phase 0 fixed-wind validation run: 2 designs ×
4 diameters × 4 masses = **32 total POST2 runs**, one run per scenario,
same fixed wind for all 32, ending at the MSL powered-descent handoff
point (not simulating powered descent/sky crane). Built against
`phase0_spec_for_claude_code1.md`.

## Current status: 32-RUN GRID INVALIDATED — bank angle was never applied

**The full 32-run grid completed (32/32 `status: ok`) but the author's own
analysis of the raw `.out`/`.log` files found that `bnkang` was 0.0 at
every integration step in all 32 runs**, despite `bnkpc = 15.0,` being in
every `.inp` deck. With bank at 0, lift points straight up for the whole
entry instead of being rolled off-vertical, so every vehicle skips badly
(dives in, pulls out, climbs back up tens of km, falls again much later)
instead of flying a realistic entry. This invalidates all 32 runs'
physics — the pipeline mechanics (file I/O, event sequencing, status
classification) are sound, but the trajectories themselves are wrong.
**Do not use the first 32-run grid's results.**

Root cause and fix: see "Bank angle (BNKPC/BNKANG) — bugfix and open
items" below. **Status: fix applied, syntax now confirmed against the
POST2 manual text (`BNKPC(i)` polynomial coefficients) — still needs one
real test run to confirm against actual POST2 output before the bank
sweep (Task 2) or a grid re-run.**

## Bank angle (BNKPC/BNKANG) — bugfix and open items

**Symptom** (from the author's analysis of all 32 `.out`/`.log` files):
`BNKPC` echoed as `[0.0, 0.0, 0.0, 0.0]` and `bnkang` printed as `0.0` at
every step, in every run, despite `bnkpc = 15.0,` in every `.inp` deck.
POST2 accepted that line without any syntax error — it was silently
ignored rather than rejected, exactly the "silent wrong-physics" failure
mode this project has tried hardest to avoid. Consequences in the data:
baseline (`rigid_d4.5_m900`) climbs from ~20 km back up to ~33.6 km after
peak deceleration instead of flying a controlled descent; the 15 m HIAD
climbs to ~50 km; chute deploy (Mach 1.7) happens at t=444 s / 5.5 km
instead of MSL's real ~E+259 s / 12.1 km (Karlgaard et al.); and only 1 of
16 rigid runs (`d4.5_m900`) even got through chute deploy → heat-shield
sep → handoff before hitting the `ALTMIN` safety net early.

**Fix, now CONFIRMED against the manual text** (`generate_input.py`
changed `bnkpc = {value},` to `bnkpc(1) = {value},`). The author supplied
the manual's own entries:

> `ALPARG`/`BETARG`/`BNKARG`: names of the variables used as arguments in
> the cubic polynomials for angle of attack, sideslip, and bank. Used if
> `IGUID(1)=-1` or `0`. (default argument: `TIMES`)
>
> `ALPHA`/`BETA`/`BNKANG` (deg, default 0.0): the initial values of angle
> of attack, sideslip, and bank, respectively.
>
> `ALPPC(i)`, `BETPC(i)`, `BNKPC(i)`, i=1,4 (decimal, default 0.0): angle
> of attack (`ALPHA`), sideslip (`BETA`), and bank (`BNKANG`) polynomial
> coefficients, respectively, where i=1 is the constant term, i=2 the
> linear (rate) term, i=3 the quadratic term, i=4 the cubic term.

So `BNKANG(t) = BNKPC(1) + BNKPC(2)·t + BNKPC(3)·t² + BNKPC(4)·t³`, with
the argument defaulting to time (`TIMES`) whenever `IGUID(1)` is `-1` or
`0` — its default, which this deck never touches. Setting only
`BNKPC(1)` (elements 2–4 stay at their own default `0.0`) gives exactly a
**constant** bank angle for the whole phase, with no `IGUID` flag needed.
This also explains the original bug: the broken deck's bare
`bnkpc = <val>,` (no index) matches neither the scalar `BNKANG` variable
name nor the indexed `BNKPC(i)` array, so POST2 silently matched nothing.

**Attempt 2 (`bnkpc(1) = {value},`, indexed single-element) was tested
against a real run and CONFIRMED NOT TO WORK** — `max_abs_bnkang_deg`
came back `0.0` and the skip (`max_altitude_after_peak_decel_m`) was
unchanged at ~33,594 m, identical to the original bug. The line was again
silently accepted with no error and no effect, same symptom as the
original bare `bnkpc = <val>,` form.

**Attempt 3 (current)**: sets both the direct initial value (`bnkang =
{value},`, per the manual's separate `ALPHA`/`BETA`/`BNKANG` entry) AND
the full 4-value `BNKPC` array as one comma-separated literal
(`bnkpc = {value}, 0.0, 0.0, 0.0,`) instead of indexed element access —
on the theory that POST2's free-form parser wants the whole array
assigned at once (matching how other multi-value inputs are written
elsewhere in this deck), since indexed access was silently accepted but
inert both times it was tried. **STILL UNVERIFIED** — needs another real
test run:
```
python batch_runner.py --only rigid_d4.5_m900 --exe "<path to post2_windows_commercial.exe>"
```
then check the new `max_abs_bnkang_deg` and `max_altitude_after_peak_decel_m`
columns in `phase0_summary.csv` directly (faster than reading the raw
`.out`):
```
python -c "import csv; r=list(csv.DictReader(open('results/phase0_summary.csv')))[0]; print('max_abs_bnkang_deg =', r['max_abs_bnkang_deg']); print('max_altitude_after_peak_decel_m =', r['max_altitude_after_peak_decel_m'])"
```
`max_abs_bnkang_deg` should read ~15, not `0.0`, and the skip altitude
should drop well below ~33,594 m. If this attempt also fails, the next
thing needed is the manual's `IGUID(1)` entry itself (its full value
list and default) — the `ALPARG`/`BETARG`/`BNKARG` text already supplied
only describes what happens *if* `IGUID(1)` is `-1` or `0`, not what
`IGUID(1)` actually defaults to or what other values mean, so it's worth
checking whether guidance is active at all without explicitly setting it.

**Sign convention**: per the manual, positive `BNKANG` banks to the
right. Doesn't affect vertical-plane behavior (peak g, skip magnitude,
Mach-1.7 state, handoff state) — only lateral/crossrange drift — but
should be recorded once confirmed rather than left as an unstated
assumption.

**`bank_sweep.py`** (new this session): runs `rigid_d4.5_m900` ONLY (not
the full grid) across bank = 0/15/30/45/60/70 deg (configurable via
`--angles`), and writes `results/bank_sweep/bank_sweep_summary.csv` with,
per angle: peak deceleration (g and time), peak dynamic pressure, max
altitude reached after peak deceleration (skip indicator — should be flat
near peak-decel altitude for a non-skipping entry), chute-deploy state
(time/altitude/altitude-above-surface/Mach/velocity), heat-shield-sep
state, handoff state (time/velocity), `handoff_reached`, and
`last_event_number_reached`. It does not choose a bank angle — that
stays an author decision, to be made with your mentor and recorded as an
explicit assumption, not inferred by the pipeline.

## Previous status (now superseded): VALIDATED — single-case verification passed (rigid_d4.5_m900)

`rigid_d4.5_m900` ran successfully end-to-end on the Windows machine and
now reports `status: ok` in `phase0_summary.csv`, with all 4 implemented
"no-silent-vacuum-run" checks passing (atmosphere active, decelerates,
Mars gravity, within atmosphere table range). Three real bugs were found
and fixed along the way (see "Bugs found from real POST2 output" below).
All three phases executed, both Mach-triggered events fired at their
correct Mach numbers, and the run terminated via the `ALTMIN` global
safety net exactly at the intended handoff altitude (-6,742.13 ft, i.e.
1.7 km above the Gale local surface) with the heat shield already
separated. Gravity constants, entry state, atmosphere/wind tables, vehicle
weight/sref/lref, and the combined post-chute drag table all printed back
exactly matching what `generate_input.py` wrote — confirming nearly all of
the previously-unvalidated guessed syntax on the first full attempt.
Sanity check: handoff relative velocity 85.6 m/s vs. MSL's real reference
value of 78.9 m/s (Karlgaard et al.) — about 8% high, plausible for a
single fixed-wind run with this project's placeholder chute CD table (not
yet a true digitization of Cruz et al. Fig. 9 — see below) and the
`ALTMIN`-triggered termination firing one integration step after the
nominal handoff criterion.

Per spec, the required single-case verification before the 32-run grid is
now complete. Remaining open items (chute CD digitization, wind-active
check #4, a few PENDING-verify constants) are non-blocking — see below.

## Pipeline cleanups from the full-32-run review (this session)

The author's review of all 32 `.out`/`.log` files also surfaced pipeline
classification gaps (separate from the bank-angle physics bug above):

- **`status` didn't require reaching the handoff point.** A run that
  skipped and never separated its heat shield before hitting `ALTMIN`
  could still show `status: ok` if the 4 implemented vacuum checks
  happened to pass — it never actually checked whether the vehicle got
  through the intended event sequence. **Fixed**: `parse_metrics()` now
  computes `handoff_reached` (`True` only if both chute deploy and
  heat-shield separation occurred before the run ended), and
  `batch_runner.py`'s status logic gates on it first — `handoff_not_reached`
  is now a distinct, explicit failure status, checked before the vacuum
  checks, not folded into `vacuum_check_failed` or missed entirely.
- **No record of which POST2 event the run actually reached.** Added
  `last_event_number_reached`, parsed from CHKTERM's own `ESN=` value
  when a run terminates via `ALTMIN` (more reliable than relying on
  "Begin Phase" markers, since `ALTMIN` and the event-100 criterion can
  race and ALTMIN sometimes wins by one integration step even on an
  otherwise-correct run — this is the race condition behind "Terminated
  Abnormally" showing up on runs where event 100 effectively fired in the
  same step").
- **New per-run diagnostic fields** (all in `phase0_summary.csv` now):
  `peak_deceleration_time_s`, `max_altitude_after_peak_decel_m` (the skip
  indicator — how high the vehicle climbed back up after peak
  deceleration; should stay flat/near-zero for a non-skipping entry),
  `max_abs_bnkang_deg` (confirms whether a nonzero bank was actually
  applied, once the fix above is verified), `chute_deploy_time_s`, and
  `chute_deploy_altitude_above_surface_m`.
- **ALTMIN-vs-event-100 race**: rather than trying to tune `ALTMIN` to sit
  just below the handoff altitude (unreliable — `dt=1.0` s integration
  steps can cover hundreds of ft of altitude, so a small margin doesn't
  reliably avoid the race), classification now relies on the physical
  signals above (`handoff_reached`, `last_event_number_reached`) instead
  of which message POST2 happened to print. `ALTMIN` itself is unchanged.

## Bugs found from real POST2 output (fixed)

- **`bnkpc` table syntax** (see "Items still needing manual verification"
  below for detail) — fixed.
- **Summary-line regex didn't recognize `ALTMIN`-triggered terminations.**
  POST2 reports a normal event-100 handoff as `"POST2 Completed with N
  Warnings and M Errors."`, but a run that terminates via the `ALTMIN`
  global safety net (the designed behavior whenever the integrator reaches
  the handoff altitude via the checked-termination path rather than the
  event-100 criterion landing exactly) instead prints `"POST2 Terminated
  Abnormally with N Warnings and M Errors."`, preceded by a `*** CHKTERM
  ERROR *** ... Trajectory terminated by ALTMIN=...` line. The real
  `rigid_d4.5_m900` run hit exactly this path (5 warnings, 1 error — the
  CHKTERM "error" counts the ALTMIN hit itself). `run_post2.py`'s and
  `parse_output.py`'s `_SUMMARY_RE` only matched the "Completed" phrasing,
  so `Post2RunResult.ok` came back `False` and `batch_runner.py` mis-filed
  this successful, intended outcome as `post2_reported_errors`. **Fixed**:
  both regexes now match either phrasing and capture which one fired;
  `Post2RunResult` gained `termination_mode` and `altmin_triggered` fields
  (the latter set by scanning the `.out` text for the CHKTERM/ALTMIN line),
  and `.ok` now treats an `ALTMIN`-triggered "Terminated Abnormally" as a
  valid outcome rather than a failure — matching the spec's own
  instruction that "every run stops at the same altitude... do not stop a
  run early to avoid recording a failure." `post2_termination_mode` is now
  also recorded per-scenario in `phase0_summary.csv` for transparency (so
  a genuinely-abnormal, non-`ALTMIN` termination is still visible, just no
  longer conflated with the expected one).
- **Relative-path bug hid the `ALTMIN` confirmation re-read.** The fix
  above re-opens the `.out` file to confirm the "error" really is the
  `ALTMIN` safety net (not a genuine POST2 error) by scanning for the
  `Trajectory terminated by ALTMIN=` line. But `run_post2()` re-opened it
  using `out_path` exactly as passed in by `batch_runner.py` — a bare
  filename like `rigid_d4.5_m900.out`, relative to the scenario's own
  scratch work directory, which is only the *subprocess's* cwd, not this
  Python process's own cwd. The re-open silently failed (`OSError`,
  caught and ignored), so `altmin_triggered` never got set even on the
  real, confirmed run, and the status stayed `post2_reported_errors`.
  **Fixed**: `out_path` is now resolved against `cwd` by hand before
  re-opening, and the `ALTMIN` line is also checked against the captured
  console output as a second source.
- **Altitude-sampling artifact in the density cross-check (vacuum check
  #1).** The check compared the atmosphere table's density *at* each
  target altitude (10/40/80 km) against the single nearest *printed*
  row's density — but POST2 only prints rows at whatever altitude the
  trajectory happens to be at each integration step, not at round-km
  marks. On the real run this left a ~486 m gap at the 40 km mark, and
  since density falls off fast with altitude, that gap alone produced a
  ~5.6% apparent mismatch (just over the 5% tolerance) even though 10 km
  and 80 km both matched to <1% and the atmosphere was clearly active
  (nonzero dynamic pressure). **Fixed**: interpolates the printed density
  between the two rows bracketing each target altitude instead of using
  the nearest single row, so the comparison is like-for-like at the same
  altitude on both sides.

## Previous status: UNBLOCKED (pipeline-side) — needs a real run on Windows

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

## Known simplifications

- **Chute opening is instant** — the combined post-chute-deploy drag table
  (`aero_data.combined_post_chute_cd_table`) applies full chute CD from
  the moment of deployment, with no inflation ramp/transient. This
  overstates the deceleration spike right at deploy and understates how
  long it takes the chute to reach full drag. Left as-is for Phase 0 (and
  the bank-angle work) — would need a time- or Mach-indexed ramp-up table
  to model properly.
- **Parachute CD-vs-Mach table is still a 4-point placeholder** built from
  the spec's prose description of Cruz et al. Fig. 9, not a true
  digitization of the figure. Affects post-chute-deploy drag magnitude.
- **Wind-active vacuum check (#4) is not implemented** — see "Items still
  needing manual verification."

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

**Results of the actual single-test-case verification** (`rigid_d4.5_m900`,
after the `bnkpc` fix and the three parsing/status bugs above): **PASSED —
`status: ok`** in `phase0_summary.csv`. Ran to completion via the `ALTMIN`
safety net at the intended handoff altitude, heat shield separated
beforehand at Mach 0.7 as designed, chute-deploy event fired at Mach 1.7.

| Metric | Value |
|---|---|
| `status` | `ok` |
| `post2_termination_mode` | `terminated_abnormally` (expected — the `ALTMIN` safety-net path, see above) |
| `ballistic_coefficient_kg_m2` | 140.85 (vs. MSL's published ~145 kg/m², ~3% off) |
| `peak_deceleration_g` | 10.10 |
| `peak_dynamic_pressure_pa` | 13,518.9 |
| `handoff_gdalt_m` | -2055.01 (matches the 1.7 km-above-Gale-surface target) |
| `handoff_velocity_relative_mps` | 85.57 (vs. MSL's reference 78.9 m/s, ~8% high) |
| `handoff_mach` | 0.350 |
| `vacuum_check_atmosphere_active` | **True** (density cross-match at 10/40/80 km all <1% error after the interpolation fix above) |
| `vacuum_check_decelerates` | True |
| `vacuum_check_mars_gravity` | True |
| `vacuum_check_within_table_range` | True |
| `vacuum_check_wind_active_CHECKED` | False — **still not implemented** (no confirmed wind output variable name yet) |

The ~8% handoff-velocity gap and ~3% ballistic-coefficient gap are both
within the uncertainty this project already flagged (placeholder chute CD
table, digitization tolerance) — not a sign of a remaining bug. The
touchdown-proximity comparison (Gale Crater -4.59°/137.44° E) has not been
separately computed yet.

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
