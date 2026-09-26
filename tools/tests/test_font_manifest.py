from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from font_manifest import ManifestError, SOURCE, validate_manifest, verify_staged_assets


COMMIT = "a" * 40
REQUIRED = frozenset({("Test Sans", "testsans")})
CONTENTS = {
    "font": b"font-data",
    "license": b"license-data",
    "metadata": b"metadata-data",
}


def locked(kind: str, source: str, output: str) -> dict:
    content = CONTENTS[kind]
    return {
        "kind": kind,
        "source_path": source,
        "output_path": output,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def good_manifest() -> dict:
    font_output = "assets/fonts/files/testsans/TestSans-Regular.ttf"
    return {
        "schema_version": 1,
        "source": SOURCE,
        "source_commit": COMMIT,
        "families": [
            {
                "name": "Test Sans",
                "slug": "testsans",
                "faces": [{"file": font_output, "style": "normal", "weight": "400"}],
                "files": [
                    locked("font", "ofl/testsans/TestSans-Regular.ttf", font_output),
                    locked("license", "ofl/testsans/OFL.txt", "licenses/fonts/testsans-OFL.txt"),
                    locked("metadata", "ofl/testsans/METADATA.pb", "licenses/fonts/testsans-METADATA.pb"),
                ],
            }
        ],
    }


class ManifestValidationTests(unittest.TestCase):
    def test_accepts_complete_manifest(self) -> None:
        validate_manifest(good_manifest(), required_families=REQUIRED)

    def test_rejects_missing_font_license_or_metadata(self) -> None:
        for missing_kind in ("font", "license", "metadata"):
            with self.subTest(missing_kind=missing_kind):
                manifest = good_manifest()
                family = manifest["families"][0]
                family["files"] = [entry for entry in family["files"] if entry["kind"] != missing_kind]
                if missing_kind == "font":
                    family["faces"] = []
                with self.assertRaises(ManifestError):
                    validate_manifest(manifest, required_families=REQUIRED)

    def test_rejects_face_pointing_outside_family_fonts(self) -> None:
        manifest = good_manifest()
        manifest["families"][0]["faces"][0]["file"] = "assets/fonts/files/testsans/Other.ttf"
        with self.assertRaises(ManifestError):
            validate_manifest(manifest, required_families=REQUIRED)

    def test_rejects_duplicate_family_and_output(self) -> None:
        duplicate_family = good_manifest()
        duplicate_family["families"].append(copy.deepcopy(duplicate_family["families"][0]))
        with self.assertRaises(ManifestError):
            validate_manifest(duplicate_family, required_families=REQUIRED)

        duplicate_output = good_manifest()
        family = duplicate_output["families"][0]
        family["files"].append(copy.deepcopy(family["files"][0]))
        with self.assertRaises(ManifestError):
            validate_manifest(duplicate_output, required_families=REQUIRED)

    def test_rejects_wrong_exact_family_set_and_unsafe_values(self) -> None:
        with self.assertRaises(ManifestError):
            validate_manifest(good_manifest(), required_families=frozenset({("Other", "other")}))
        for field, value in (("source_commit", "main"), ("source_commit", "A" * 40)):
            manifest = good_manifest()
            manifest[field] = value
            with self.assertRaises(ManifestError):
                validate_manifest(manifest, required_families=REQUIRED)
        manifest = good_manifest()
        manifest["families"][0]["files"][0]["output_path"] = "../escape.ttf"
        with self.assertRaises(ManifestError):
            validate_manifest(manifest, required_families=REQUIRED)


class StagedAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "stage"
        self.manifest_path = Path(self.temporary.name) / "manifest.json"
        manifest = good_manifest()
        self.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for entry in manifest["families"][0]["files"]:
            output = self.root / entry["output_path"]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(CONTENTS[entry["kind"]])
        bundled = self.root / "licenses/fonts/manifest.json"
        bundled.parent.mkdir(parents=True, exist_ok=True)
        bundled.write_bytes(self.manifest_path.read_bytes())
        css = self.root / "assets/fonts/fonts.css"
        css.parent.mkdir(parents=True, exist_ok=True)
        css.write_text(
            "@font-face { src: url('files/testsans/TestSans-Regular.ttf') format('truetype'); }\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def verify(self) -> None:
        verify_staged_assets(self.manifest_path, self.root, required_families=REQUIRED)

    def test_accepts_valid_staged_assets(self) -> None:
        self.verify()

    def test_rejects_same_size_mutation(self) -> None:
        font = self.root / "assets/fonts/files/testsans/TestSans-Regular.ttf"
        font.write_bytes(b"FONT-data")
        self.assertEqual(font.stat().st_size, len(CONTENTS["font"]))
        with self.assertRaises(ManifestError):
            self.verify()

    def test_rejects_missing_staged_license(self) -> None:
        (self.root / "licenses/fonts/testsans-OFL.txt").unlink()
        with self.assertRaises(ManifestError):
            self.verify()

    def test_rejects_changed_bundled_manifest_and_broken_css(self) -> None:
        bundled = self.root / "licenses/fonts/manifest.json"
        bundled.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(ManifestError):
            self.verify()
        bundled.write_bytes(self.manifest_path.read_bytes())
        (self.root / "assets/fonts/fonts.css").write_text(
            "@font-face { src: url('files/testsans/missing.ttf'); }\n", encoding="utf-8"
        )
        with self.assertRaises(ManifestError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
