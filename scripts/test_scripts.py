"""Unit tests for the script helpers. Run: python3 -m unittest scripts/test_scripts.py"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import mode_for, parse_pr_url  # noqa: E402
from post import diff_lines  # noqa: E402

DIFF = """diff --git a/A.swift b/A.swift
--- a/A.swift
+++ b/A.swift
@@ -1,3 +1,4 @@
 keep
-old
+new
+added
 tail
"""


class Tests(unittest.TestCase):
    def test_parse_pr_url(self) -> None:
        self.assertEqual(
            parse_pr_url("https://github.com/sebsto/wispr/pull/120"), ("sebsto/wispr", 120)
        )
        with self.assertRaises(ValueError):
            parse_pr_url("https://github.com/sebsto/wispr/issues/1")

    def test_mode(self) -> None:
        self.assertEqual(mode_for("sebsto/orthanc"), "auto")
        self.assertEqual(mode_for("sebsto/soto"), "draft")
        self.assertEqual(mode_for("someone/unknown"), "draft")

    def test_diff_lines(self) -> None:
        self.assertEqual(
            diff_lines(DIFF),
            {("A.swift", 1), ("A.swift", 2), ("A.swift", 3), ("A.swift", 4)},
        )


if __name__ == "__main__":
    unittest.main()
