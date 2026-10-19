"""Rendered Quickshell checks for the owned popup using only synthetic data."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'tests' / 'popup_preview' / 'run_preview.py'


class PopupPreviewTests(unittest.TestCase):
    def test_production_panel_renders_in_the_isolated_sdk_harness(self):
        result = subprocess.run([sys.executable, str(PREVIEW)], text=True,
                                capture_output=True, timeout=15)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, 'T11_RESULT failures=0\n', ''))


if __name__ == '__main__':
    unittest.main()
