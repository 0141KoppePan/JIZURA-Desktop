"""Shared validation and path handling for the locked Google Fonts manifest."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Iterable

from font_selection import FAMILIES


SOURCE = "https://github.com/google/fonts"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SLUG_RE = re.compile(r"[a-z0-9]+")
WEIGHT_RE = re.compile(r"[1-9]00(?: [1-9]00)?")
CSS_URL_RE = re.compile(r"url\(['\"]?([^)'\"]+)['\"]?\)")
REQUIRED_FAMILIES = frozenset((family["name"], family["slug"]) for family in FAMILIES)


class ManifestError(RuntimeError):
    """The font lock or its staged files are invalid."""


def digest(path: Path) -> tuple[str, int]:
    checksum = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
            size += len(chunk)
    return checksum.hexdigest(), size


def checked_relative(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ManifestError("path must be a non-empty string")
    if "\\" in relative:
        raise ManifestError(f"path must use forward slashes: {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ManifestError(f"unsafe relative path: {relative!r}")
    candidate = (base / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise ManifestError(f"path escapes its root: {relative!r}") from exc
    return candidate


def cache_path(cache_root: Path, source: str, commit: str, source_path: str) -> Path:
    if source != SOURCE:
        raise ManifestError(f"unsupported font source: {source!r}")
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        raise ManifestError(f"source_commit must be a lowercase 40-character SHA-1: {commit!r}")
    return checked_relative(cache_root / commit, source_path)


def legacy_cache_path(cache_root: Path, source_path: str) -> Path:
    return checked_relative(cache_root / "source", source_path)


def matches(path: Path, entry: dict) -> bool:
    if not path.is_file() or path.stat().st_size != entry["size"]:
        return False
    sha256, _ = digest(path)
    return sha256 == entry["sha256"]


def _require_dict(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def _require_list(value: object, label: str) -> list:
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{label} must be a non-empty array")
    return value


def validate_manifest(
    manifest: object,
    *,
    required_families: frozenset[tuple[str, str]] = REQUIRED_FAMILIES,
) -> dict:
    manifest = _require_dict(manifest, "manifest")
    if manifest.get("schema_version") != 1:
        raise ManifestError("font manifest schema_version must be 1")
    if manifest.get("source") != SOURCE:
        raise ManifestError(f"font manifest source must be {SOURCE}")
    commit = manifest.get("source_commit")
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        raise ManifestError("font manifest source_commit must be a lowercase 40-character SHA-1")

    families = _require_list(manifest.get("families"), "families")
    seen_families: set[tuple[str, str]] = set()
    seen_outputs: set[str] = set()
    for family_index, raw_family in enumerate(families):
        family = _require_dict(raw_family, f"families[{family_index}]")
        name = family.get("name")
        slug = family.get("slug")
        if not isinstance(name, str) or not name.strip():
            raise ManifestError(f"families[{family_index}].name must be a non-empty string")
        if not isinstance(slug, str) or SLUG_RE.fullmatch(slug) is None:
            raise ManifestError(f"invalid family slug: {slug!r}")
        identity = (name, slug)
        if identity in seen_families:
            raise ManifestError(f"duplicate font family: {name!r}/{slug!r}")
        if any(existing[0] == name or existing[1] == slug for existing in seen_families):
            raise ManifestError(f"duplicate family name or slug: {name!r}/{slug!r}")
        seen_families.add(identity)

        files = _require_list(family.get("files"), f"{name}.files")
        font_outputs: set[str] = set()
        kind_counts = {"font": 0, "license": 0, "metadata": 0}
        for file_index, raw_entry in enumerate(files):
            entry = _require_dict(raw_entry, f"{name}.files[{file_index}]")
            kind = entry.get("kind")
            if kind not in kind_counts:
                raise ManifestError(f"invalid file kind in {name}: {kind!r}")
            source_path = entry.get("source_path")
            output_path = entry.get("output_path")
            checked_relative(Path("."), source_path)
            checked_relative(Path("."), output_path)
            if not source_path.startswith("ofl/"):
                raise ManifestError(f"source path is outside ofl/: {source_path}")
            expected_prefix = (
                f"assets/fonts/files/{slug}/" if kind == "font" else f"licenses/fonts/{slug}-"
            )
            if not output_path.startswith(expected_prefix):
                raise ManifestError(f"unexpected {kind} output for {slug}: {output_path}")
            if output_path in seen_outputs:
                raise ManifestError(f"duplicate font output: {output_path}")
            seen_outputs.add(output_path)
            size = entry.get("size")
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                raise ManifestError(f"invalid size for {source_path}: {size!r}")
            sha256 = entry.get("sha256")
            if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
                raise ManifestError(f"invalid SHA-256 for {source_path}")
            kind_counts[kind] += 1
            if kind == "font":
                font_outputs.add(output_path)

        if kind_counts["font"] < 1 or kind_counts["license"] != 1 or kind_counts["metadata"] != 1:
            raise ManifestError(
                f"{name} requires one or more fonts and exactly one license and metadata file"
            )

        faces = _require_list(family.get("faces"), f"{name}.faces")
        face_files: set[str] = set()
        for face_index, raw_face in enumerate(faces):
            face = _require_dict(raw_face, f"{name}.faces[{face_index}]")
            face_file = face.get("file")
            if face_file not in font_outputs:
                raise ManifestError(f"{name} face refers to a font outside the family: {face_file!r}")
            style = face.get("style")
            if style not in ("normal", "italic", "oblique"):
                raise ManifestError(f"invalid face style in {name}: {style!r}")
            weight = face.get("weight")
            if not isinstance(weight, str) or WEIGHT_RE.fullmatch(weight) is None:
                raise ManifestError(f"invalid face weight in {name}: {weight!r}")
            if face_file in face_files:
                raise ManifestError(f"duplicate face file in {name}: {face_file}")
            face_files.add(face_file)
        if face_files != font_outputs:
            missing = sorted(font_outputs - face_files)
            raise ManifestError(f"{name} has font files without faces: {missing}")

    if seen_families != required_families:
        missing = sorted(required_families - seen_families)
        extra = sorted(seen_families - required_families)
        raise ManifestError(f"font family set mismatch; missing={missing}, extra={extra}")
    return manifest


def load_manifest(
    path: Path,
    *,
    required_families: frozenset[tuple[str, str]] = REQUIRED_FAMILIES,
) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read font manifest {path}: {exc}") from exc
    return validate_manifest(raw, required_families=required_families)


def entries(manifest: dict) -> Iterable[dict]:
    for family in manifest["families"]:
        yield from family["files"]


def verify_staged_assets(
    manifest_path: Path,
    output_root: Path,
    *,
    required_families: frozenset[tuple[str, str]] = REQUIRED_FAMILIES,
) -> dict:
    manifest = load_manifest(manifest_path, required_families=required_families)
    for entry in entries(manifest):
        output = checked_relative(output_root, entry["output_path"])
        if not matches(output, entry):
            actual = digest(output) if output.is_file() else ("missing", 0)
            raise ManifestError(
                f"locked staged asset mismatch for {entry['output_path']}: "
                f"got {actual[0]}/{actual[1]}, expected {entry['sha256']}/{entry['size']}"
            )

    bundled = checked_relative(output_root, "licenses/fonts/manifest.json")
    if not bundled.is_file() or bundled.read_bytes() != manifest_path.read_bytes():
        raise ManifestError("bundled font manifest is missing or differs from the repository lock")

    css_path = checked_relative(output_root, "assets/fonts/fonts.css")
    if not css_path.is_file():
        raise ManifestError("bundled font stylesheet is missing")
    css = css_path.read_text(encoding="utf-8")
    css_outputs: set[str] = set()
    for reference in CSS_URL_RE.findall(css):
        relative = (PurePosixPath("assets/fonts") / PurePosixPath(reference)).as_posix()
        checked_relative(output_root, relative)
        if not checked_relative(output_root, relative).is_file():
            raise ManifestError(f"font CSS refers to a missing file: {reference}")
        css_outputs.add(relative)
    expected_fonts = {
        entry["output_path"] for entry in entries(manifest) if entry["kind"] == "font"
    }
    if css_outputs != expected_fonts:
        raise ManifestError(
            f"font CSS references differ from the manifest; "
            f"missing={sorted(expected_fonts - css_outputs)}, extra={sorted(css_outputs - expected_fonts)}"
        )
    return manifest
