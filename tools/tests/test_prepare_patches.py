from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare


class PatchApplicationTests(unittest.TestCase):
    def test_applies_patch_inside_parent_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            work = root / "build" / "work" / "jizura"
            work.mkdir(parents=True)
            source = work / "sample.txt"
            source.write_text("before\n", encoding="utf-8")
            patches = root / "patches"
            patches.mkdir()
            (patches / "series").write_text("change.patch\n", encoding="utf-8")
            (patches / "change.patch").write_text(
                "diff --git a/sample.txt b/sample.txt\n"
                "--- a/sample.txt\n+++ b/sample.txt\n"
                "@@ -1 +1 @@\n-before\n+after\n",
                encoding="utf-8",
            )
            with mock.patch.object(prepare, "WORK", work), mock.patch.object(
                prepare, "PATCH_DIRECTORY", patches
            ):
                prepare.apply_patches()
                self.assertEqual(source.read_text(encoding="utf-8"), "after\n")
                # A second application must fail, not silently skip the patch.
                with self.assertRaises(subprocess.CalledProcessError):
                    prepare.apply_patches()


if __name__ == "__main__":
    unittest.main()
