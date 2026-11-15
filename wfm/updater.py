"""Update the app when it starts (setting `auto_update`, on by default; the user's request, 2026-11-15).

In a folder made with `git clone`, the app pulls the latest main before it loads anything; if new code arrived, run.py
starts again on it. Never blocks a start: no git, a ZIP folder, no network, local changes or a slow server all just
mean "no update" (said in the log). Fast-forward only, so nothing of yours is ever overwritten.
"""
from __future__ import annotations

import subprocess

from .paths import ROOT


def update(repo=None, timeout: int = 30) -> tuple[bool, str]:
    """(code changed, what happened)."""
    repo = repo or ROOT
    if not (repo / '.git').exists():
        return False, 'not a git folder (ZIP download): update by downloading the ZIP again or with update.bat'
    git = lambda *a: subprocess.run(['git', '-C', str(repo), *a], capture_output=True, text=True, timeout=timeout)
    try:
        before = git('rev-parse', 'HEAD').stdout.strip()
        r = git('pull', '--ff-only', '--quiet', 'origin', 'main')
        if r.returncode != 0:
            return False, 'could not update: ' + ((r.stderr or r.stdout).strip().splitlines() or ['unknown'])[-1][:160]
        after = git('rev-parse', 'HEAD').stdout.strip()
        return (before != after), ('updated to the latest version' if before != after else 'already up to date')
    except FileNotFoundError:
        return False, 'git is not installed'
    except (OSError, subprocess.SubprocessError) as e:
        return False, f'could not update: {e}'
