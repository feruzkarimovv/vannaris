"""A test that never runs is worse than a test that fails.

`scripts/check-all.sh` opens by arguing that a check which could not run is not
a check that passed, and it counts skips separately so "all gates passed" can
never mean "nothing ran". That argument stops at the shell script: inside the
Python suite, a whole class of tests can go quiet with no skip, no error and no
change to the count anyone reads.

That is not hypothetical here. `TestCanonicalRun` in `tests/test_export_guards.py`
defined a fixture helper called `run`:

    class TestCanonicalRun(unittest.TestCase):
        @staticmethod
        def run(rid, week="2099-W01", ...):
            return {...}

`unittest.TestCase.run(result)` is the method the framework calls to execute a
test. Overriding it replaced the execution entry point with a dict factory, so
every test in that class was collected and then silently not run — ten
assertions about which run gets published, including the floors that decide
whether a degraded week reaches the site, reporting nothing at all. The suite
stayed green the entire time because green was all it could ever be.

So: no `unittest.TestCase` subclass in this directory may shadow a method the
framework needs. Read from the source rather than by importing, so a module that
fails to import is not silently exempt from the rule about silent exemptions.

    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent

# Shadowing any of these disables or corrupts execution rather than failing.
# `run` and `debug` are the entry points; the rest either report the result or
# make an assertion, and a helper quietly replacing one of those is the same
# bug wearing a different name.
RESERVED = {
    "run", "debug", "id", "subTest", "skipTest", "fail",
    "countTestCases", "defaultTestResult", "addCleanup", "doCleanups",
    "assertRaises", "assertEqual", "assertTrue", "assertFalse", "assertIn",
    "assertIsNone", "assertIsNotNone",
}


def testcase_classes(tree: ast.Module):
    """Classes that inherit from something named TestCase, however imported."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            "TestCase" in ast.unparse(base) for base in node.bases
        ):
            yield node


class TestNoTestIsSilentlyDisabled(unittest.TestCase):
    def test_no_test_class_shadows_a_framework_method(self):
        offences = []
        for path in sorted(TESTS.glob("test_*.py")):
            tree = ast.parse(path.read_text())
            for cls in testcase_classes(tree):
                for item in cls.body:
                    if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name in RESERVED):
                        offences.append(
                            f"{path.name}:{item.lineno} {cls.name}.{item.name} "
                            f"shadows unittest.TestCase.{item.name} — every test "
                            f"in {cls.name} will be collected and never executed"
                        )
        self.assertEqual(offences, [], "\n  " + "\n  ".join(offences))

    def test_the_rule_is_checked_against_real_files(self):
        # Guards the guard: a glob that matches nothing would pass the test
        # above for the same reason the bug it exists to catch passed.
        found = list(TESTS.glob("test_*.py"))
        self.assertGreater(len(found), 5, "the sweep found almost no test files")
        classes = sum(len(list(testcase_classes(ast.parse(p.read_text()))))
                      for p in found)
        self.assertGreater(classes, 20, "the sweep found almost no test classes")

    def test_the_rule_would_catch_the_bug_it_was_written_for(self):
        source = (
            "import unittest\n"
            "class TestSomething(unittest.TestCase):\n"
            "    @staticmethod\n"
            "    def run(rid, week='2099-W01'):\n"
            "        return {'id': rid}\n"
            "    def test_a_thing(self):\n"
            "        pass\n"
        )
        cls = next(testcase_classes(ast.parse(source)))
        shadowed = [i.name for i in cls.body
                    if isinstance(i, ast.FunctionDef) and i.name in RESERVED]
        self.assertEqual(shadowed, ["run"])


if __name__ == "__main__":
    unittest.main()
