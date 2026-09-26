from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from fetch_fonts import resolved_cache, sync_fonts
from font_manifest import ManifestError, SOURCE, cache_path
from update_font_manifest import generate_manifest


COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
REQUIRED = frozenset({("Test Sans", "testsans")})
SELECTED = [
    {
        "name": "Test Sans",
        "slug": "testsans",
        "license_slug": "testsans",
        "fonts": [{"filename": "TestSans-Regular.ttf", "weight": "400", "style": "normal"}],
    }
]
PATHS = (
    "ofl/testsans/TestSans-Regular.ttf",
    "ofl/testsans/OFL.txt",
    "ofl/testsans/METADATA.pb",
)


def content(commit: str, source_path: str) -> bytes:
    return f"{commit}:{source_path}".encode()


def fetcher_for(commit: str, calls: list[str] | None = None):
    def fetch(url: str, destination: Path) -> None:
        if calls is not None:
            calls.append(url)
        marker = f"/raw/{commit}/"
        if marker not in url:
            raise AssertionError(f"wrong commit URL: {url}")
        source_path = urllib.parse.unquote(url.split(marker, 1)[1])
        destination.write_bytes(content(commit, source_path))

    return fetch


class FontCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache"
        self.manifest = self.root / "manifest.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def generate(self, commit: str) -> dict:
        return generate_manifest(
            selected_families=SELECTED,
            source_commit=commit,
            cache_root=self.cache,
            manifest_path=self.manifest,
            fetcher=fetcher_for(commit),
        )

    def test_same_source_path_is_isolated_by_commit(self) -> None:
        self.generate(COMMIT_A)
        self.generate(COMMIT_B)
        source_path = PATHS[0]
        self.assertEqual(
            cache_path(self.cache, SOURCE, COMMIT_A, source_path).read_bytes(),
            content(COMMIT_A, source_path),
        )
        self.assertEqual(
            cache_path(self.cache, SOURCE, COMMIT_B, source_path).read_bytes(),
            content(COMMIT_B, source_path),
        )

    def test_sync_downloads_only_from_manifest_commit(self) -> None:
        manifest = self.generate(COMMIT_A)
        for source_path in PATHS:
            cache_path(self.cache, SOURCE, COMMIT_A, source_path).unlink()
        calls: list[str] = []
        sync_fonts(
            manifest_path=self.manifest,
            cache_root=self.cache,
            fetcher=fetcher_for(COMMIT_A, calls),
            required_families=REQUIRED,
        )
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(f"/raw/{manifest['source_commit']}/" in url for url in calls))

    def test_offline_rejects_cache_from_another_commit(self) -> None:
        self.generate(COMMIT_A)
        manifest_b = self.generate(COMMIT_B)
        self.manifest.write_text(json.dumps(manifest_b, indent=2) + "\n", encoding="utf-8")
        for source_path in PATHS:
            cache_path(self.cache, SOURCE, COMMIT_B, source_path).unlink()
        with self.assertRaises(ManifestError):
            sync_fonts(
                offline=True,
                manifest_path=self.manifest,
                cache_root=self.cache,
                required_families=REQUIRED,
            )

    def test_bad_hash_and_interrupted_download_are_rejected(self) -> None:
        manifest = self.generate(COMMIT_A)
        entry = manifest["families"][0]["files"][0]
        target = cache_path(self.cache, SOURCE, COMMIT_A, entry["source_path"])
        target.write_bytes(b"corrupt")

        def bad_hash(_url: str, destination: Path) -> None:
            destination.write_bytes(b"x" * entry["size"])

        with self.assertRaises(ManifestError):
            sync_fonts(
                manifest_path=self.manifest,
                cache_root=self.cache,
                fetcher=bad_hash,
                required_families=REQUIRED,
            )
        self.assertEqual(target.read_bytes(), b"corrupt")
        self.assertFalse(target.with_name(target.name + ".part").exists())

        target.unlink()

        def interrupted(_url: str, destination: Path) -> None:
            destination.write_bytes(b"partial")
            raise OSError("simulated interruption")

        with self.assertRaises(OSError):
            sync_fonts(
                manifest_path=self.manifest,
                cache_root=self.cache,
                fetcher=interrupted,
                required_families=REQUIRED,
            )
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + ".part").exists())

    def test_legacy_cache_migrates_only_when_lock_matches(self) -> None:
        manifest = self.generate(COMMIT_A)
        entry = manifest["families"][0]["files"][0]
        target = cache_path(self.cache, SOURCE, COMMIT_A, entry["source_path"])
        legacy = self.cache / "source" / entry["source_path"]
        target.unlink()
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_bytes(content(COMMIT_A, entry["source_path"]))
        self.assertEqual(resolved_cache(entry, manifest, self.cache), target)
        self.assertEqual(target.read_bytes(), legacy.read_bytes())

        target.unlink()
        legacy.write_bytes(b"bad")
        self.assertIsNone(resolved_cache(entry, manifest, self.cache))
        self.assertFalse(target.exists())

    def test_manifest_update_refetches_untrusted_existing_cache_and_is_atomic(self) -> None:
        for source_path in PATHS:
            target = cache_path(self.cache, SOURCE, COMMIT_B, source_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"untrusted-existing")
        calls: list[str] = []
        generate_manifest(
            selected_families=SELECTED,
            source_commit=COMMIT_B,
            cache_root=self.cache,
            manifest_path=self.manifest,
            fetcher=fetcher_for(COMMIT_B, calls),
        )
        self.assertEqual(len(calls), 3)

        previous = self.manifest.read_bytes()
        count = 0

        def fail_late(url: str, destination: Path) -> None:
            nonlocal count
            count += 1
            if count == 2:
                destination.write_bytes(b"partial")
                raise OSError("stop")
            fetcher_for(COMMIT_A)(url.replace(COMMIT_B, COMMIT_A), destination)

        with self.assertRaises(OSError):
            generate_manifest(
                selected_families=SELECTED,
                source_commit=COMMIT_A,
                cache_root=self.cache,
                manifest_path=self.manifest,
                fetcher=fail_late,
            )
        self.assertEqual(self.manifest.read_bytes(), previous)
        self.assertFalse(self.manifest.with_name(self.manifest.name + ".part").exists())


if __name__ == "__main__":
    unittest.main()
