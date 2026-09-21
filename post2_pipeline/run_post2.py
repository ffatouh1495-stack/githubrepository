"""
Thin subprocess wrapper around post2_windows_commercial.exe.

Only runs on the Windows machine where POST2 is installed. Parses the
"POST2 Completed with N Warnings and M Errors" summary line so the batch
runner can tell a clean run from a broken one without re-parsing the whole
output file.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import Optional

import config

_SUMMARY_RE = re.compile(
    r"POST2 Completed with (\d+) Warnings? and (\d+) Errors?", re.IGNORECASE
)


@dataclass
class Post2RunResult:
    scenario_id: str
    inp_path: str
    out_path: str
    returncode: int
    warnings: Optional[int]
    errors: Optional[int]
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and (self.errors == 0)


def run_post2(scenario_id: str, inp_path: str, out_path: str,
              exe_path: str = config.POST2_EXE, timeout_s: int = 300) -> Post2RunResult:
    """Run POST2 once on inp_path, writing to out_path. Does not raise on a
    nonzero POST2 error count -- callers should check result.ok and decide
    whether to continue the batch."""
    proc = subprocess.run(
        [exe_path, inp_path, out_path],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )

    warnings = errors = None
    combined = proc.stdout + proc.stderr
    match = _SUMMARY_RE.search(combined)
    if not match:
        # The summary line lives in the .out file, not stdout, in the runs
        # we've seen so far -- check there too.
        try:
            with open(out_path, "r", errors="replace") as f:
                text = f.read()
            match = _SUMMARY_RE.search(text)
        except OSError:
            pass
    if match:
        warnings, errors = int(match.group(1)), int(match.group(2))

    return Post2RunResult(
        scenario_id=scenario_id,
        inp_path=inp_path,
        out_path=out_path,
        returncode=proc.returncode,
        warnings=warnings,
        errors=errors,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
