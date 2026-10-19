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

    warnings = errors = None
    combined = proc.stdout + proc.stderr
    match = _SUMMARY_RE.search(combined)
    if not match:
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
