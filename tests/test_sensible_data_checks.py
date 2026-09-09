"""Structural tests for repeatable InLaw sensible data checks."""

import ast
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from import_and_check_fhir_directory import CHECK_FILES  # noqa: E402
from src.inlaw import InLaw  # noqa: E402


class SensibleDataChecksTest(unittest.TestCase):
    """Enforce one sanity check per check file and InLaw discoverability."""

    def test_each_check_file_contains_exactly_one_inlaw_check(self) -> None:
        check_directory = REPOSITORY_ROOT / "sensible_data_checks"
        actual_check_files = sorted(path.name for path in check_directory.glob("check_*.py"))
        self.assertEqual(sorted(CHECK_FILES), actual_check_files)

        for filename in CHECK_FILES:
            syntax_tree = ast.parse(
                (check_directory / filename).read_text(encoding="utf-8")
            )
            check_classes = [
                node
                for node in syntax_tree.body
                if isinstance(node, ast.ClassDef)
                and any(
                    isinstance(base, ast.Name) and base.id == "InLaw"
                    for base in node.bases
                )
            ]
            self.assertEqual(1, len(check_classes), filename)

    def test_inlaw_discovers_one_class_from_each_file(self) -> None:
        check_directory = REPOSITORY_ROOT / "sensible_data_checks"
        for filename in CHECK_FILES:
            classes = InLaw.get_classes_from_file(str(check_directory / filename))
            self.assertEqual(1, len(classes), filename)
            self.assertTrue(issubclass(classes[0], InLaw))


if __name__ == "__main__":
    unittest.main()