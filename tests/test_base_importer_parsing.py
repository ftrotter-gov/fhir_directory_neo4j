"""Integration tests between BaseImporter file readers and FHIRParser."""

import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


try:
    import neo4j  # noqa: F401
except ModuleNotFoundError:
    neo4j_module = types.ModuleType("neo4j")
    neo4j_module.GraphDatabase = object
    neo4j_module.Session = object
    neo4j_exceptions_module = types.ModuleType("neo4j.exceptions")
    neo4j_exceptions_module.AuthError = RuntimeError
    neo4j_exceptions_module.ServiceUnavailable = RuntimeError
    sys.modules["neo4j"] = neo4j_module
    sys.modules["neo4j.exceptions"] = neo4j_exceptions_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from importers.base import BaseImporter  # noqa: E402


class ParsingOnlyOrganizationImporter(BaseImporter):
    """Use BaseImporter readers without creating a Neo4j driver."""

    RESOURCE_TYPE = "Organization"
    NODE_LABEL = "Organization"

    def __init__(self) -> None:
        self.import_tag = None
        self.use_create = False


class BaseImporterParsingTest(unittest.TestCase):
    """Verify parser behavior as exposed through existing importer APIs."""

    def test_bundle_import_continues_past_operation_outcome(self) -> None:
        payload = {
            "resourceType": "Bundle",
            "type": "searchset",
            "link": [{"relation": "next", "url": "https://example.test/page/2"}],
            "entry": [
                {
                    "resource": {
                        "resourceType": "OperationOutcome",
                        "issue": [
                            {
                                "severity": "warning",
                                "code": "processing",
                                "diagnostics": "Search warning",
                            }
                        ],
                    }
                },
                {"resource": {"resourceType": "Organization", "id": "org-1"}},
                {"resource": {"resourceType": "Practitioner", "id": "prac-1"}},
            ],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            filepath = Path(temporary_directory) / "Organization.json"
            filepath.write_text(json.dumps(payload), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                resources = ParsingOnlyOrganizationImporter().read_file(
                    filepath=filepath
                )

        self.assertEqual(["org-1"], [resource["id"] for resource in resources])
        self.assertIn("[pagination]", stderr.getvalue())
        self.assertIn("[processing]", stderr.getvalue())

    def test_single_parameters_resource_is_unwrapped(self) -> None:
        payload = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "result",
                    "resource": {"resourceType": "Organization", "id": "org-1"},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            filepath = Path(temporary_directory) / "Organization"
            filepath.write_text(json.dumps(payload), encoding="utf-8")
            resources = ParsingOnlyOrganizationImporter().read_file(filepath=filepath)

        self.assertEqual(["org-1"], [resource["id"] for resource in resources])

    def test_contained_resource_is_not_imported_independently(self) -> None:
        payload = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "information", "code": "informational"}],
            "contained": [{"resourceType": "Organization", "id": "local-org"}],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            filepath = Path(temporary_directory) / "Organization"
            filepath.write_text(json.dumps(payload), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                resources = ParsingOnlyOrganizationImporter().read_file(
                    filepath=filepath
                )

        self.assertEqual([], resources)
        self.assertIn("no importable Organization", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()