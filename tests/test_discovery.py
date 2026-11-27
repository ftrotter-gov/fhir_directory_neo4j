"""Tests for FHIR file discovery, including extensionless endpoint caches."""

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

from importers.discovery import discover_fhir_files  # noqa: E402
from importers.registry import (  # noqa: E402
    FileFormat,
    detect_format,
    get_source_format_string,
)


class DiscoveryTest(unittest.TestCase):
    """Verify content-safe discovery of supported and unsupported files."""

    @staticmethod
    def _fhir_resource(*, resource_type: str) -> dict:
        return {
            "resourceType": resource_type,
            "id": "example-id",
            "meta": {
                "profile": [
                    "http://hl7.org/fhir/us/davinci-pdex-plan-net/"
                    f"StructureDefinition/plannet-{resource_type}"
                ]
            },
        }

    @staticmethod
    def _write_json(*, path: Path, content: dict) -> None:
        path.write_text(json.dumps(content), encoding="utf-8")

    def _write_bundle(self, *, path: Path, resource_type: str) -> None:
        self._write_json(
            path=path,
            content={
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {"resource": self._fhir_resource(resource_type=resource_type)}
                ],
            },
        )

    def test_discovers_extensionless_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            filepath = directory / "Organization"
            self._write_bundle(path=filepath, resource_type="Organization")

            discovered = discover_fhir_files(directory=directory)

            self.assertEqual({"Organization": [filepath]}, discovered)
            self.assertEqual(FileFormat.FHIR_BUNDLE, detect_format(filepath))
            self.assertEqual("fhir_plannet", get_source_format_string(filepath))

    def test_discovers_extensionless_single_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            filepath = directory / "PractitionerRole"
            self._write_json(
                path=filepath,
                content=self._fhir_resource(resource_type="PractitionerRole"),
            )

            discovered = discover_fhir_files(directory=directory)

            self.assertEqual({"PractitionerRole": [filepath]}, discovered)
            self.assertEqual(FileFormat.FHIR_NDJSON, detect_format(filepath))

    def test_skips_extensionless_filename_content_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            self._write_bundle(
                path=directory / "Organization", resource_type="Practitioner"
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                discovered = discover_fhir_files(directory=directory)

            self.assertEqual({}, discovered)
            self.assertIn("filename implies Organization", output.getvalue())
            self.assertIn("content contains Practitioner", output.getvalue())

    def test_skips_operation_outcome_with_specific_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            self._write_json(
                path=directory / "Network",
                content={
                    "resourceType": "OperationOutcome",
                    "issue": [{"diagnostics": "Unknown resource type Network"}],
                },
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                discovered = discover_fhir_files(directory=directory)

            self.assertEqual({}, discovered)
            self.assertIn("upstream request error", output.getvalue())

    def test_discovers_cms_bulk_download_numeric_prefix_ndjson(self) -> None:
        """The official CMS NPD bulk download names files 'NN-ResourceType.ndjson'.

        The numeric ordering prefix must be stripped, and 08-OrganizationAffiliation
        must never be matched as Organization.
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            organization_path = directory / "01-Organization.ndjson"
            affiliation_path = directory / "08-OrganizationAffiliation.ndjson"
            organization_path.write_text(
                json.dumps(self._fhir_resource(resource_type="Organization")) + "\n",
                encoding="utf-8",
            )
            affiliation_path.write_text(
                json.dumps(
                    self._fhir_resource(resource_type="OrganizationAffiliation")
                )
                + "\n",
                encoding="utf-8",
            )

            discovered = discover_fhir_files(directory=directory)

            self.assertEqual(
                {
                    "Organization": [organization_path],
                    "OrganizationAffiliation": [affiliation_path],
                },
                discovered,
            )

    def test_skips_unsupported_insurance_plan_with_specific_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            self._write_bundle(
                path=directory / "InsurancePlan", resource_type="InsurancePlan"
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                discovered = discover_fhir_files(directory=directory)

            self.assertEqual({}, discovered)
            self.assertIn("FHIR resource type InsurancePlan", output.getvalue())
            self.assertIn("no importer is registered", output.getvalue())

    def test_preserves_json_and_ndjson_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bundle_path = directory / "Location.json"
            ndjson_path = directory / "Practitioner.ndjson"
            self._write_bundle(path=bundle_path, resource_type="Location")
            ndjson_path.write_text(
                json.dumps(self._fhir_resource(resource_type="Practitioner")) + "\n",
                encoding="utf-8",
            )

            discovered = discover_fhir_files(directory=directory)

            self.assertEqual([bundle_path], discovered["Location"])
            self.assertEqual([ndjson_path], discovered["Practitioner"])

    def test_ignores_unrelated_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "Organization.txt").write_text(
                json.dumps(self._fhir_resource(resource_type="Organization")),
                encoding="utf-8",
            )

            self.assertEqual({}, discover_fhir_files(directory=directory))


if __name__ == "__main__":
    unittest.main()