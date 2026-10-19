"""
Mars atmosphere + wind block for the POST2 input deck.

STATUS: PENDING on two things, both required before any real run:

1. DATA: config.MARS_ATMOSPHERE_CSV (mars_atmosphere_gale.csv) must exist.
   Per spec this is Mars-GRAM 2010 output, 146 rows, 1 km steps, -5000 m
   to 140000 m (areoid-referenced), columns Altitude(m), Pressure(Pa),
   Temperature(K), Speed of Sound(m/s), Density(kg/m^3), [Mol Weight,
   Gas Law Error -- ignored]. Not yet supplied by the author.

2. SYNTAX: the exact POST2 input syntax, confirmed against the manual, for:
   a. NPC(5) = 1 (general/tabular atmosphere switch) and the four table
      names POST2 expects for pressure/temperature/speed-of-sound/density
      (spec names them PREST, ATEMT, CST, DENST -- confirm exact keyword
      spelling, units, and whether the independent altitude variable
      needs to be in feet rather than meters), and the table-size limit
      (146 points -- if POST2's table limit is smaller, STOP and report
      to the author; do not silently thin or truncate).
   b. How ATMOSK(1) and ATMOSK(2) interact with a table atmosphere (spec:
      "With a table atmosphere they should be left at 1.0, but verify").
   c. NPC(6) (wind switch) and the VWT (wind speed vs. altitude) / AZW_T
      (wind azimuth vs. altitude) table names/syntax, and the azimuth
      convention (blows-toward vs. blows-from; what 0 deg references).

Why this is its own module and a hard gate (raises rather than guessing):
Example 1A silently produced zero density instead of an error when the
Earth atmosphere flag was left unset -- the run "succeeded" with garbage
physics. The spec is explicit that POST2 defaults to Earth/no-atmosphere
and that this failure mode is the single biggest risk in Phase 0 ("A run
with the atmosphere switch left at its default is a vacuum run and its
results are meaningless"). Guessing wrong on unit (feet vs. meters) or
table-name syntax here risks the same silent failure, 32 times over.

Once both the CSV and the manual-confirmed syntax are in hand:
  1. Place the CSV at config.MARS_ATMOSPHERE_CSV
  2. Fill in build_environment_block() below with the real NPC(5)=1 /
     PREST/ATEMT/CST/DENST / NPC(6) / VWT / AZW_T lines, reading the CSV
     via _load_atmosphere_table()
  3. Set config.MARS_ATMOSPHERE_READY = True
  4. Record ATMOSK(1)/(2) behavior, the azimuth convention, and the
     table-size check result in README.md (spec requirement)
"""

import csv
from typing import List, Tuple

import config


class MarsEnvironmentNotReady(RuntimeError):
    """Raised when a caller tries to build an input deck before the Mars
    atmosphere/wind syntax and data have been confirmed and filled in."""


def _load_atmosphere_table() -> List[Tuple[float, float, float, float, float]]:
    """Read config.MARS_ATMOSPHERE_CSV, return rows of
    (altitude_m, pressure_pa, temperature_k, speed_of_sound_mps, density_kgm3).
    Reads the CSV directly (never a PDF/spreadsheet copy), per spec, and
    uses only the first five columns (Mol Weight / Gas Law Error ignored).
    """
    rows = []
    with open(config.MARS_ATMOSPHERE_CSV, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            alt, pres, temp, cs, dens = (float(x) for x in row[:5])
            rows.append((alt, pres, temp, cs, dens))
    rows.sort(key=lambda r: r[0])
    if len(rows) != 146:
        raise MarsEnvironmentNotReady(
            f"Expected 146 rows in {config.MARS_ATMOSPHERE_CSV} per spec, got {len(rows)}. "
            "Stop and report to the author rather than silently proceeding."
        )
    return rows


def build_environment_block(wind_speed_mps: float, wind_direction_deg: float) -> List[str]:
    """
    Return the list of POST2 input lines for the Mars atmosphere + wind
    model, parameterized by wind speed/direction.

    Raises MarsEnvironmentNotReady until this function is filled in with
    manual-confirmed syntax AND config.MARS_ATMOSPHERE_CSV exists.
    """
    if not config.MARS_ATMOSPHERE_READY:
        raise MarsEnvironmentNotReady(
            "Mars atmosphere/wind syntax has not been confirmed yet, and/or "
            f"{config.MARS_ATMOSPHERE_CSV} has not been supplied. Fill in "
            "mars_environment.build_environment_block() per the module "
            "docstring, set config.MARS_ATMOSPHERE_READY = True, then "
            "re-run. Refusing to generate input decks with unverified "
            "atmosphere physics -- see the module docstring for why."
        )

    # Placeholder body -- replaced once syntax is confirmed. Sketch of what
    # this will look like (table NAMES/UNITS/independent-variable-units
    # are all unconfirmed guesses below, do not use as-is):
    #
    # table = _load_atmosphere_table()
    # lines = [
    #     "npc(5) = 1,           // general/tabular atmosphere",
    #     "atmosk(1) = 1.0,  atmosk(2) = 1.0,   // PENDING verify",
    #     "dtalt = ... ",  # altitude independent-variable table, units TBD
    #     "<PREST-equivalent keyword> = 'prest', monovar, <alt-var>, 0, lin_inp, xtrap,",
    #     *(f"{alt}, {pres}," for alt, pres, temp, cs, dens in table),
    #     ... same pattern for ATEMT, CST, DENST ...
    #     "npc(6) = 1,           // PENDING verify: wind switch",
    #     f"vwt = 'vwt', constant, 0, {wind_speed_mps},   // PENDING verify",
    #     f"azw_t = 'azw_t', constant, 0, {wind_direction_deg},   // PENDING verify azimuth convention",
    # ]
    raise NotImplementedError
