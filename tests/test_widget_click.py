"""Public regression test for the bar widget click contract.

The production `BarWidget.qml` is driven inside the isolated Quickshell
preview. A fake native launcher records every invocation, so the test proves
that a left click reaches the official native launcher with `--toggle` and
that only the secondary gesture toggles the owned chat popup.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "tests" / "popup_preview" / "run_preview.py"


class WidgetClickTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle-dot-widget-click-")
        self.addCleanup(self.scratch.cleanup)
        self.marker = Path(self.scratch.name) / "launches.txt"
        self.launcher = Path(self.scratch.name) / "fake gentle-dot"
        self.launcher.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(self.marker) + '"\n'
        )
        self.launcher.chmod(0o755)

    def test_left_click_reaches_the_native_launcher_and_right_click_toggles_the_popup(
        self,
    ):
        result = subprocess.run(
            [
                sys.executable,
                str(PREVIEW),
                "--widget-click",
                str(self.launcher),
                str(self.marker),
            ],
            text=True,
            capture_output=True,
            timeout=30,
        )
        invocations = self.marker.read_text().split() if self.marker.exists() else []
        self.assertEqual(
            invocations,
            ["--toggle"],
            "the left click did not reach the native launcher exactly once with --toggle",
        )
        self.assertEqual(
            (result.returncode, result.stdout, result.stderr),
            (0, "T22_RESULT failures=0\n", ""),
        )


if __name__ == "__main__":
    unittest.main()
