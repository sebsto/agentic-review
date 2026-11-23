"""Unit tests for the script helpers. Run: python3 -m unittest scripts/test_scripts.py"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import mode_for, parse_pr_url  # noqa: E402
from classify import added_lines  # noqa: E402
from eval import merge_results  # noqa: E402
from find import as_finding_list  # noqa: E402
from llm import extract_json  # noqa: E402
from merge import merge  # noqa: E402
from report import build_review  # noqa: E402
from run import all_failed  # noqa: E402
from verify import decide  # noqa: E402
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

    def test_added_lines(self) -> None:
        self.assertEqual(added_lines(DIFF), {("A.swift", 2), ("A.swift", 3)})

    def test_merge_dedupes_and_keeps_longest_evidence(self) -> None:
        def item(i, line, title, evidence):
            return {"id": i, "finder": "security", "file": "A.swift", "line": line,
                    "title": title, "explanation": "e", "evidence": evidence}
        merged = merge([
            item("a-1", 10, "token logged in plain text", "short"),
            item("b-1", 11, "plain text token logged", "much longer evidence"),
            item("a-1", 40, "other problem", "x"),
        ])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["evidence"], "much longer evidence")
        self.assertEqual(len({m["id"] for m in merged}), 2)

    def test_quorum(self) -> None:
        self.assertTrue(decide([{"real": True}, {"real": True}, {"real": False}]))
        self.assertFalse(decide([{"real": True}, {"real": False}, {"real": False}]))

    def test_report(self) -> None:
        self.assertEqual(build_review([])["body"], "No issues found.")
        finding = {"id": "x", "file": "A.swift", "line": 2, "title": "t", "explanation": "e",
                   "suggested_fix": "fix()", "class": "blocking"}
        review = build_review([finding, {**finding, "id": "y", "class": "pre-existing"}])
        self.assertTrue(review["body"].startswith("1 blocking, 0 nit, 1 pre-existing."))
        self.assertEqual(len(review["comments"]), 1)
        self.assertIn("```suggestion\nfix()\n```", review["comments"][0]["body"])


class AllFailedTests(unittest.TestCase):
    def test_all_errors_is_failure(self):
        self.assertTrue(all_failed({"a": "boom", "b": "boom"}))

    def test_one_success_is_not_failure(self):
        self.assertFalse(all_failed({"a": "boom", "b": (0, 1)}))


class FindingListTests(unittest.TestCase):
    def test_list_is_kept(self):
        self.assertEqual(as_finding_list([{"file": "a"}]), [{"file": "a"}])

    def test_wrapped_list(self):
        self.assertEqual(as_finding_list({"findings": [{"file": "a"}]}), [{"file": "a"}])

    def test_single_finding_object(self):
        self.assertEqual(as_finding_list({"file": "a", "line": 1}), [{"file": "a", "line": 1}])

    def test_object_without_findings(self):
        self.assertEqual(as_finding_list({"summary": "none"}), [])


class MergeResultsTests(unittest.TestCase):
    def test_new_result_replaces_same_id_and_keeps_others(self):
        old = [{"id": "a", "pass": False}, {"id": "b", "pass": True}]
        new = [{"id": "a", "pass": True}, {"id": "c", "pass": True}]
        self.assertEqual(
            merge_results(old, new),
            [{"id": "a", "pass": True}, {"id": "b", "pass": True}, {"id": "c", "pass": True}],
        )


if __name__ == "__main__":
    unittest.main()
