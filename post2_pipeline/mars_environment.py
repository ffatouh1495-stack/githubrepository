"""
Mars atmosphere + wind block for the POST2 input deck.

STATUS: PENDING. Do not use this pipeline for real runs until
build_environment_block() below is filled in with verified syntax.

Why this is its own module: getting the Earth atmosphere flag wrong in
Example 1A silently produced zero density (no atmosphere at all) instead of
an error -- the run "succeeded" with garbage physics. Mars atmosphere in
POST2 needs the same care, and the exact flag/keyword syntax (built-in
Mars model vs. a user-supplied tabular atmosphere fed by Mars-GRAM output)
hasn't been confirmed against the manual yet.

Once you have the Mars-GRAM data and/or the manual's Mars atmosphere
section, paste it in and this module gets filled in to:
  1. Set config.MARS_ATMOSPHERE_READY = True
  2. Return the actual npc(5)/table lines from build_environment_block()

Two likely shapes this will take (fill in whichever matches your manual):

(a) Built-in Mars atmosphere flag, e.g.:
    npc(5) = <N>,  // Mars atmosphere model
    (analogous to npc(5) = 2 for 1962 US Standard Atmosphere in Ex. 1A/1B)

(b) User-supplied tabular atmosphere fed from Mars-GRAM output, e.g.:
    npc(5) = <N>,  // tabular/user atmosphere
    <atmosphere-table-keyword> = 'marsatm', monovar, gdalt, 0, lin_inp, xtrap,
    <alt_1>, <dens_1>, <pres_1>, ...
    (exact keyword/table shape TBD from the manual)

Wind (also pending, same reasoning): POST2's wind-input syntax hasn't been
confirmed either. Mars-GRAM output often includes wind profiles alongside
density/pressure/temperature, so the data request already in flight may
answer both at once.
"""

from typing import List

import config


class MarsEnvironmentNotReady(RuntimeError):
    """Raised when a caller tries to build an input deck before the Mars
    atmosphere/wind syntax has been confirmed and filled in below."""


def build_environment_block(wind_speed_mps: float, wind_direction_deg: float) -> List[str]:
    """
    Return the list of POST2 input lines for the Mars atmosphere + wind
    model, parameterized by wind speed/direction.

    Raises MarsEnvironmentNotReady until this function is filled in.
    """
    if not config.MARS_ATMOSPHERE_READY:
        raise MarsEnvironmentNotReady(
            "Mars atmosphere/wind syntax has not been confirmed yet. "
            "Paste the Mars-GRAM data / manual section, fill in "
            "mars_environment.build_environment_block(), set "
            "config.MARS_ATMOSPHERE_READY = True, then re-run. "
            "Refusing to generate input decks with unverified atmosphere "
            "physics -- see the module docstring for why."
        )

    # Placeholder body -- replaced once syntax is confirmed.
    raise NotImplementedError
