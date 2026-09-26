"""Fail when checked Go source needs formatting, without changing the worktree."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sources = sorted(str(path.relative_to(ROOT)) for path in ROOT.glob("*.go"))
    result = subprocess.run(
        ["gofmt", "-l", *sources],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    unformatted = result.stdout.strip()
    if unformatted:
        print("Go files need gofmt:", file=sys.stderr)
        print(unformatted, file=sys.stderr)
        return 1
    print("Go formatting check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
