from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import package


class PipelineWiringTests(unittest.TestCase):
    def test_build_requires_web_verification(self) -> None:
        taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")
        build_section = taskfile.split("  build:", 1)[1].split("\n  package:", 1)[0]
        self.assertIn("deps: [verify:web]", build_section)

    def test_package_validates_before_reading_build_metadata(self) -> None:
        fake_executable = mock.Mock()
        fake_executable.is_file.return_value = True
        with mock.patch.object(package, "EXECUTABLE", fake_executable), mock.patch.object(
            package, "validate_web_assets", side_effect=RuntimeError("invalid stage")
        ) as validate, mock.patch.object(package, "text") as read_text:
            with self.assertRaisesRegex(RuntimeError, "invalid stage"):
                package.main()
        validate.assert_called_once_with(package.ASSETS)
        read_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
