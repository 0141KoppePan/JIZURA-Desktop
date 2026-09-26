"""Fetch, verify, and stage the fonts locked in assets/fonts/manifest.json."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from font_manifest import (
    ManifestError,
    REQUIRED_FAMILIES,
    cache_path,
    checked_relative,
    entries,
    legacy_cache_path,
    load_manifest,
    matches,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "fonts" / "manifest.json"
CACHE_ROOT = ROOT / ".cache" / "fonts"
Fetcher = Callable[[str, Path], None]


def fetch_url(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
        output.flush()
        os.fsync(output.fileno())


def _atomic_verified_copy(source: Path, destination: Path, entry: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        shutil.copyfile(source, temporary)
        if not matches(temporary, entry):
            raise ManifestError(f"cached file changed while copying: {entry['source_path']}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def resolved_cache(entry: dict, manifest: dict, cache_root: Path = CACHE_ROOT) -> Path | None:
    destination = cache_path(
        cache_root,
        manifest["source"],
        manifest["source_commit"],
        entry["source_path"],
    )
    if matches(destination, entry):
        return destination

    legacy = legacy_cache_path(cache_root, entry["source_path"])
    if matches(legacy, entry):
        _atomic_verified_copy(legacy, destination, entry)
        return destination
    return None


def download(
    entry: dict,
    manifest: dict,
    *,
    cache_root: Path = CACHE_ROOT,
    fetcher: Fetcher = fetch_url,
) -> Path:
    destination = cache_path(
        cache_root,
        manifest["source"],
        manifest["source_commit"],
        entry["source_path"],
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    url = (
        f"{manifest['source']}/raw/{manifest['source_commit']}/"
        + urllib.parse.quote(entry["source_path"], safe="/")
    )
    print(f"download {entry['source_path']}", flush=True)
    try:
        fetcher(url, temporary)
        if not matches(temporary, entry):
            from font_manifest import digest

            actual_hash, actual_size = digest(temporary) if temporary.is_file() else ("missing", 0)
            raise ManifestError(
                f"font lock mismatch for {entry['source_path']}: "
                f"got {actual_hash}/{actual_size}, expected {entry['sha256']}/{entry['size']}"
            )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def font_css(manifest: dict) -> str:
    blocks = [
        "/* Generated from assets/fonts/manifest.json. Do not edit. */",
        f"/* Google Fonts commit: {manifest['source_commit']} */",
    ]
    for family in manifest["families"]:
        escaped_name = family["name"].replace("'", "\\'")
        for face in family["faces"]:
            relative = Path(face["file"]).relative_to("assets/fonts").as_posix()
            blocks.extend(
                [
                    "@font-face {",
                    f"  font-family: '{escaped_name}';",
                    f"  src: url('{relative}') format('truetype');",
                    f"  font-style: {face['style']};",
                    f"  font-weight: {face['weight']};",
                    "  font-display: block;",
                    "}",
                ]
            )
    return "\n".join(blocks) + "\n"


def sync_fonts(
    output_root: Path | None = None,
    *,
    offline: bool = False,
    manifest_path: Path = MANIFEST_PATH,
    cache_root: Path = CACHE_ROOT,
    fetcher: Fetcher = fetch_url,
    required_families: frozenset[tuple[str, str]] = REQUIRED_FAMILIES,
) -> None:
    manifest = load_manifest(manifest_path, required_families=required_families)
    cached_entries: list[tuple[dict, Path]] = []
    for entry in entries(manifest):
        cached = resolved_cache(entry, manifest, cache_root)
        if cached is None:
            if offline:
                raise ManifestError(
                    "font is not available in the verified cache for commit "
                    f"{manifest['source_commit']}: {entry['source_path']}"
                )
            cached = download(entry, manifest, cache_root=cache_root, fetcher=fetcher)
        cached_entries.append((entry, cached))

    if output_root is not None:
        for entry, cached in cached_entries:
            destination = checked_relative(output_root, entry["output_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cached, destination)

        css_path = checked_relative(output_root, "assets/fonts/fonts.css")
        css_path.parent.mkdir(parents=True, exist_ok=True)
        css_path.write_text(font_css(manifest), encoding="utf-8", newline="\n")
        locked_manifest = checked_relative(output_root, "licenses/fonts/manifest.json")
        locked_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path, locked_manifest)

    font_bytes = sum(entry["size"] for entry in entries(manifest) if entry["kind"] == "font")
    print(f"Verified {len(manifest['families'])} font families ({font_bytes / 1024 / 1024:.1f} MiB)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="fail instead of downloading missing cache files")
    parser.add_argument("--output", type=Path, help="stage verified files below this directory")
    args = parser.parse_args()
    sync_fonts(args.output.resolve() if args.output else None, offline=args.offline)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ManifestError, urllib.error.URLError) as exc:
        print(f"font preparation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
