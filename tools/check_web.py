"""Structural and cryptographic checks for generated JIZURA desktop web assets."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from font_manifest import ManifestError, verify_staged_assets


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_MANIFEST = ROOT / "assets" / "fonts" / "manifest.json"
EDITIONS = (".", "en", "zh-hant", "zh-hans", "ko", "id", "vi")
FORBIDDEN_FONT_HOSTS = (
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
)


def validate_web_assets(
    root: Path,
    *,
    manifest_path: Path = REPOSITORY_MANIFEST,
) -> dict[str, str]:
    root = root.resolve()
    failures: list[str] = []
    hashes: dict[str, str] = {}

    for edition in EDITIONS:
        page = root / ("index.html" if edition == "." else f"{edition}/index.html")
        if not page.is_file():
            failures.append(f"missing generated page: {page}")
            continue
        content = page.read_text(encoding="utf-8")
        if "JIZURA" not in content or "mp4-muxer v5.2.2" not in content:
            failures.append(f"page is missing expected JIZURA content: {page}")
        if 'href="/assets/fonts/fonts.css"' not in content:
            failures.append(f"bundled font stylesheet is not linked in {page}")
        for marker in FORBIDDEN_FONT_HOSTS:
            if marker in content:
                failures.append(f"external font host remains in {page}: {marker}")
        hashes[str(page.relative_to(root))] = hashlib.sha256(page.read_bytes()).hexdigest()

    required_notices = (
        "licenses/JIZURA-LICENSE.txt",
        "licenses/JIZURA-THIRD-PARTY-NOTICES.md",
        "licenses/mp4-muxer-LICENSE.txt",
        "licenses/fonts/manifest.json",
        "assets/fonts/fonts.css",
        "upstream-version.txt",
    )
    for relative in required_notices:
        if not (root / relative).is_file():
            failures.append(f"missing notice: {relative}")

    try:
        verify_staged_assets(manifest_path, root)
    except (OSError, ManifestError) as exc:
        failures.append(str(exc))

    if failures:
        raise ManifestError("web asset validation failed:\n- " + "\n- ".join(failures))
    return hashes


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/dist")
    try:
        hashes = validate_web_assets(root)
    except (OSError, ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for relative, checksum in sorted(hashes.items()):
        print(f"{checksum}  {relative}")
    print("Web asset checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
