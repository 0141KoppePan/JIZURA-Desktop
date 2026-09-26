"""Create the Windows x64 ZIP distribution without installers or bootstrap downloads."""

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

from check_web import validate_web_assets


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXECUTABLE = DIST / "JIZURA-Desktop.exe"
ASSETS = ROOT / "frontend" / "dist"
ARCHIVE_ROOT = "JIZURA-Desktop"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def add_file(output: zipfile.ZipFile, source: Path, name: str, *, executable: bool = False) -> None:
    info = zip_info(name)
    info.external_attr = (0o755 if executable else 0o644) << 16
    with source.open("rb") as input_stream, output.open(info, "w", force_zip64=True) as output_stream:
        shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def main() -> int:
    if not EXECUTABLE.is_file():
        raise RuntimeError("build the application before packaging")

    # Packaging is an independent trust boundary: never package an executable
    # after staged licenses, fonts, CSS, or generated pages have been altered.
    validate_web_assets(ASSETS)

    app_version = text(ROOT / "APP_VERSION")
    upstream_version = text(ASSETS / "upstream-version.txt")
    readme = (ROOT / "packaging" / "README.ja.txt").read_text(encoding="utf-8")
    readme = readme.replace("@APP_VERSION@", app_version).replace("@UPSTREAM_VERSION@", upstream_version)
    build_info = {
        "application": "JIZURA Desktop",
        "application_version": app_version,
        "target": "windows-amd64",
        "upstream": "https://github.com/852wa/JIZURA",
        "upstream_version": upstream_version,
        "upstream_commit": "bae339e450512435b829a717248ea92ae5b44899",
    }

    archive = DIST / f"JIZURA-Desktop-{app_version}-windows-amd64.zip"
    temporary = archive.with_name(archive.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True, compresslevel=9) as output:
            add_file(output, EXECUTABLE, f"{ARCHIVE_ROOT}/JIZURA-Desktop.exe", executable=True)
            output.writestr(zip_info(f"{ARCHIVE_ROOT}/README.txt"), readme.encode("utf-8-sig"))
            output.writestr(
                zip_info(f"{ARCHIVE_ROOT}/build-info.json"),
                (json.dumps(build_info, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
            licenses = ASSETS / "licenses"
            for source in sorted(path for path in licenses.rglob("*") if path.is_file()):
                relative = source.relative_to(licenses).as_posix()
                add_file(output, source, f"{ARCHIVE_ROOT}/licenses/{relative}")
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"Created {archive.relative_to(ROOT)} ({archive.stat().st_size / 1024 / 1024:.1f} MiB)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"package failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
