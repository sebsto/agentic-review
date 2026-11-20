"""Unit tests for the script helpers. Run: python3 -m unittest scripts/test_scripts.py"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import mode_for, parse_pr_url  # noqa: E402
from llm import extract_json  # noqa: E402
from post import diff_lines  # noqa: E402
from validate import check, load_schema  # noqa: E402

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

    def test_extract_json(self) -> None:
        self.assertEqual(extract_json('```json\n[{"a": 1}]\n```'), [{"a": 1}])
        self.assertEqual(extract_json("[]"), [])

    def test_finding_schema(self) -> None:
        schema = load_schema("finding")
        good = {"id": "c1", "finder": "concurrency", "file": "A.swift", "line": 3,
                "title": "t", "explanation": "e", "evidence": "x"}
        self.assertEqual(check(good, schema), [])
        self.assertTrue(check({**good, "finder": "style"}, schema))
        self.assertTrue(check({**good, "line": 0}, schema))
        self.assertTrue(check({**good, "extra": 1}, schema))
        self.assertTrue(check({k: v for k, v in good.items() if k != "evidence"}, schema))


if __name__ == "__main__":
    unittest.main()
