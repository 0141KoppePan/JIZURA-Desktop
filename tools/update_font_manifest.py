"""Regenerate the reviewed font lock manifest from a fixed Google Fonts commit."""

from __future__ import annotations

import json
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
    SOURCE,
    cache_path,
    digest,
    load_manifest,
    matches,
    validate_manifest,
)
from font_selection import FAMILIES, SOURCE_COMMIT


ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / ".cache" / "fonts"
MANIFEST = ROOT / "assets" / "fonts" / "manifest.json"
Fetcher = Callable[[str, Path], None]


def fetch_url(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
        output.flush()
        os.fsync(output.fileno())


def _required_families(selected_families: list[dict]) -> frozenset[tuple[str, str]]:
    return frozenset((family["name"], family["slug"]) for family in selected_families)


def _trusted_entries(
    manifest_path: Path,
    source_commit: str,
    required_families: frozenset[tuple[str, str]],
) -> dict[str, dict]:
    if not manifest_path.is_file():
        return {}
    try:
        current = load_manifest(manifest_path, required_families=required_families)
    except ManifestError:
        return {}
    if current["source"] != SOURCE or current["source_commit"] != source_commit:
        return {}
    return {
        entry["source_path"]: entry
        for family in current["families"]
        for entry in family["files"]
    }


def fetch_for_manifest(
    source_path: str,
    *,
    source_commit: str,
    cache_root: Path,
    trusted_entry: dict | None,
    fetcher: Fetcher,
) -> Path:
    destination = cache_path(cache_root, SOURCE, source_commit, source_path)
    if trusted_entry is not None and matches(destination, trusted_entry):
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    url = (
        f"{SOURCE}/raw/{source_commit}/"
        + urllib.parse.quote(source_path, safe="/")
    )
    print(f"download {source_path}", flush=True)
    try:
        fetcher(url, temporary)
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise ManifestError(f"download produced an empty file: {source_path}")
        # Read the complete file before promotion. The resulting hash is what the
        # new lock records; an untrusted file merely existing in the cache is never used.
        digest(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _file_entry(
    source_path: str,
    output_path: str,
    kind: str,
    *,
    source_commit: str,
    cache_root: Path,
    trusted: dict[str, dict],
    fetcher: Fetcher,
) -> dict:
    cached = fetch_for_manifest(
        source_path,
        source_commit=source_commit,
        cache_root=cache_root,
        trusted_entry=trusted.get(source_path),
        fetcher=fetcher,
    )
    sha256, size = digest(cached)
    return {
        "kind": kind,
        "source_path": source_path,
        "output_path": output_path,
        "size": size,
        "sha256": sha256,
    }


def generate_manifest(
    *,
    selected_families: list[dict] = FAMILIES,
    source_commit: str = SOURCE_COMMIT,
    cache_root: Path = CACHE_ROOT,
    manifest_path: Path = MANIFEST,
    fetcher: Fetcher = fetch_url,
) -> dict:
    required = _required_families(selected_families)
    trusted = _trusted_entries(manifest_path, source_commit, required)
    families = []
    for selected in selected_families:
        slug = selected["slug"]
        files = []
        faces = []
        for selected_font in selected["fonts"]:
            filename = selected_font["filename"]
            source_path = f"ofl/{slug}/{filename}"
            output_filename = filename.replace("[wght]", "-Variable")
            output_path = f"assets/fonts/files/{slug}/{output_filename}"
            files.append(
                _file_entry(
                    source_path,
                    output_path,
                    "font",
                    source_commit=source_commit,
                    cache_root=cache_root,
                    trusted=trusted,
                    fetcher=fetcher,
                )
            )
            faces.append(
                {
                    "file": output_path,
                    "style": selected_font["style"],
                    "weight": selected_font["weight"],
                }
            )

        license_slug = selected["license_slug"]
        license_path = f"ofl/{license_slug}/OFL.txt"
        files.append(
            _file_entry(
                license_path,
                f"licenses/fonts/{slug}-OFL.txt",
                "license",
                source_commit=source_commit,
                cache_root=cache_root,
                trusted=trusted,
                fetcher=fetcher,
            )
        )
        metadata_path = f"ofl/{slug}/METADATA.pb"
        files.append(
            _file_entry(
                metadata_path,
                f"licenses/fonts/{slug}-METADATA.pb",
                "metadata",
                source_commit=source_commit,
                cache_root=cache_root,
                trusted=trusted,
                fetcher=fetcher,
            )
        )
        families.append(
            {
                "name": selected["name"],
                "slug": slug,
                "faces": faces,
                "files": files,
            }
        )

    manifest = {
        "schema_version": 1,
        "source": SOURCE,
        "source_commit": source_commit,
        "families": families,
    }
    validate_manifest(manifest, required_families=required)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_name(manifest_path.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def main() -> int:
    manifest = generate_manifest()
    total = sum(
        item["size"]
        for family in manifest["families"]
        for item in family["files"]
        if item["kind"] == "font"
    )
    print(
        f"wrote {MANIFEST.relative_to(ROOT)} "
        f"({len(manifest['families'])} families, {total / 1024 / 1024:.1f} MiB fonts)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ManifestError, urllib.error.URLError) as exc:
        print(f"font manifest update failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
