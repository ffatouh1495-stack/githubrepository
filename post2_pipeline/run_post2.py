"""
Thin subprocess wrapper around post2_windows_commercial.exe.

Only runs on the Windows machine where POST2 is installed.

Invocation: `post2_windows_commercial.exe <input.inp> <output.out>`
(positional args) -- this is the form directly confirmed working in this
project's own tutorial session (Examples 1A/1B), not the `exe < input`
stdin-redirection form the spec's software section describes. Both may
work; positional args are used here because they're the one we've
actually seen succeed. Flag it if POST2 behaves differently than expected.

Runs each scenario from its own working directory (cwd), since POST2
writes extra files (e.g. "profil") into whatever directory it's run from,
and the spec requires that files from different runs never collide.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import Optional

import config

_SUMMARY_RE = re.compile(
    r"POST2 (Completed|Terminated Abnormally) with (\d+) Warnings? and (\d+) Errors?",
    re.IGNORECASE,
)

# A run that hits the ALTMIN global safety net (the designed handoff-altitude
# termination for scenarios that never separate the heat shield, or just as
# the final event-100 catch-all) prints "Terminated Abnormally" + a CHKTERM
# error rather than "Completed" -- confirmed against a real successful run
# (rigid_d4.5_m900). This is an expected, valid outcome per spec ("every run
# stops at the same altitude... do not stop a run early to avoid recording a
# failure"), not a genuine POST2 error, so it must not be lumped in with
# real parse/physics failures.
_ALTMIN_TERMINATION_RE = re.compile(r"Trajectory terminated by ALTMIN=", re.IGNORECASE)


@dataclass
class Post2RunResult:
    scenario_id: str
    inp_path: str
    out_path: str
    returncode: int
    warnings: Optional[int]
    errors: Optional[int]
    termination_mode: Optional[str]  # "completed" | "terminated_abnormally" | None
    altmin_triggered: bool
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        if self.returncode != 0:
            return False
        if self.errors == 0:
            return True
        # The ALTMIN safety net is itself counted as 1 "error" by POST2's
        # own tally -- treat that specific, designed termination as success.
        return self.altmin_triggered


def run_post2(scenario_id: str, inp_path: str, out_path: str, cwd: str,
              exe_path: str = config.POST2_EXE, timeout_s: int = 300) -> Post2RunResult:
    """Run POST2 once on inp_path (relative to cwd or absolute), writing to
    out_path, with the process's cwd set to `cwd` so side-effect files
    (profil, etc.) land in that scenario's own folder. Does not raise on a
    nonzero POST2 error count -- callers should check result.ok."""
    proc = subprocess.run(
        [exe_path, inp_path, out_path],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=cwd,
    )

    warnings = errors = termination_mode = None
    altmin_triggered = False
    combined = proc.stdout + proc.stderr
    out_text = None
    try:
        with open(out_path, "r", errors="replace") as f:
            out_text = f.read()
    except OSError:
        pass

    match = _SUMMARY_RE.search(combined) or (out_text and _SUMMARY_RE.search(out_text))
    if match:
        termination_mode = match.group(1).strip().lower().replace(" ", "_")
        warnings, errors = int(match.group(2)), int(match.group(3))

    if out_text is not None and _ALTMIN_TERMINATION_RE.search(out_text):
        altmin_triggered = True

    return Post2RunResult(
        scenario_id=scenario_id,
        inp_path=inp_path,
        out_path=out_path,
        returncode=proc.returncode,
        warnings=warnings,
        errors=errors,
        termination_mode=termination_mode,
        altmin_triggered=altmin_triggered,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
