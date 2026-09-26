"""Build JIZURA web assets from an unmodified, pinned upstream submodule."""

from __future__ import annotations

import shutil
import subprocess
import sys
import os
from pathlib import Path

from fetch_fonts import sync_fonts


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream" / "JIZURA"
WORK = ROOT / "build" / "work" / "jizura"
OUTPUT = ROOT / "frontend" / "dist"
PATCH_DIRECTORY = ROOT / "patches" / "jizura"
EXPECTED_COMMIT = "bae339e450512435b829a717248ea92ae5b44899"
EDITIONS = ("en", "zh-hant", "zh-hans", "ko", "id", "vi")


def run(*args: str, cwd: Path = ROOT) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout, file=sys.stderr, end="")
        raise
    return result.stdout.strip()


def ensure_inside_repo(path: Path) -> None:
    path.resolve().relative_to(ROOT.resolve())


def reset_directory(path: Path) -> None:
    ensure_inside_repo(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def verify_upstream() -> None:
    if not (UPSTREAM / "build.py").is_file():
        raise RuntimeError("JIZURA submodule is missing; run 'git submodule update --init'")
    commit = run("git", "rev-parse", "HEAD", cwd=UPSTREAM)
    if commit != EXPECTED_COMMIT:
        raise RuntimeError(f"unexpected JIZURA commit: {commit} (expected {EXPECTED_COMMIT})")
    dirty = run("git", "status", "--porcelain", cwd=UPSTREAM)
    if dirty:
        raise RuntimeError("JIZURA submodule has local changes; refusing to build from a dirty source")


def copy_upstream() -> None:
    reset_directory(WORK)
    shutil.copytree(
        UPSTREAM,
        WORK,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git"),
    )


def apply_patches() -> None:
    series = PATCH_DIRECTORY / "series"
    patch_names = [
        line.strip()
        for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for patch_name in patch_names:
        patch = (PATCH_DIRECTORY / patch_name).resolve()
        patch.relative_to(PATCH_DIRECTORY.resolve())
        if not patch.is_file():
            raise RuntimeError(f"patch listed in series does not exist: {patch_name}")
        run("git", "apply", "--check", "--unidiff-zero", str(patch), cwd=WORK)
        run("git", "apply", "--unidiff-zero", str(patch), cwd=WORK)


def build_upstream() -> None:
    output = run(sys.executable, "build.py", cwd=WORK)
    if output:
        print(output)


def collect_assets() -> None:
    reset_directory(OUTPUT)
    shutil.copy2(WORK / "index.html", OUTPUT / "index.html")
    for edition in EDITIONS:
        source = WORK / edition
        if not (source / "index.html").is_file():
            raise RuntimeError(f"upstream build did not create {edition}/index.html")
        shutil.copytree(source, OUTPUT / edition)

    licenses = OUTPUT / "licenses"
    licenses.mkdir()
    shutil.copy2(WORK / "LICENSE", licenses / "JIZURA-LICENSE.txt")
    shutil.copy2(WORK / "THIRD_PARTY_NOTICES.md", licenses / "JIZURA-THIRD-PARTY-NOTICES.md")
    shutil.copy2(WORK / "vendor" / "LICENSE.mp4-muxer.txt", licenses / "mp4-muxer-LICENSE.txt")
    shutil.copy2(WORK / "VERSION", OUTPUT / "upstream-version.txt")


def collect_fonts() -> None:
    sync_fonts(OUTPUT, offline=os.environ.get("JIZURA_OFFLINE") == "1")


def main() -> int:
    verify_upstream()
    copy_upstream()
    apply_patches()
    build_upstream()
    collect_assets()
    collect_fonts()
    print(f"Prepared JIZURA {EXPECTED_COMMIT[:12]} in {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"prepare failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
