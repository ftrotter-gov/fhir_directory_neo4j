"""Tests for bounded extraction through standard FHIR container shapes."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from importers.fhir_parser import FHIRParser  # noqa: E402


class FHIRParserTest(unittest.TestCase):
    """Validate direct, Bundle, Parameters, outcome, and contained parsing."""

    @staticmethod
    def _resource(*, resource_type: str, resource_id: str) -> dict:
        return {"resourceType": resource_type, "id": resource_id}

    def test_extracts_direct_resource(self) -> None:
        payload = self._resource(resource_type="Organization", resource_id="org-1")

        result = FHIRParser.extract_resources(payload=payload)

        self.assertEqual([payload], [record.resource for record in result.resources])
        self.assertEqual("$", result.resources[0].source_path)

    def test_extracts_mixed_bundle_and_reports_outcome(self) -> None:
        organization = self._resource(
            resource_type="Organization", resource_id="org-1"
        )
        practitioner = self._resource(
            resource_type="Practitioner", resource_id="prac-1"
        )
        payload = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {"resource": organization, "search": {"mode": "match"}},
                {
                    "resource": {
                        "resourceType": "OperationOutcome",
                        "issue": [
                            {
                                "severity": "warning",
                                "code": "processing",
                                "diagnostics": "A search parameter was ignored.",
                            }
                        ],
                    },
                    "search": {"mode": "outcome"},
                },
                {"resource": practitioner, "search": {"mode": "include"}},
            ],
        }

        result = FHIRParser.extract_resources(payload=payload)

        self.assertEqual(
            ["Organization", "Practitioner"],
            [record.resource_type for record in result.resources],
        )
        self.assertEqual("match", result.resources[0].search_mode)
        self.assertEqual("include", result.resources[1].search_mode)
        self.assertEqual("searchset", result.resources[0].bundle_type)
        self.assertEqual(1, len(result.diagnostics))
        self.assertEqual("processing", result.diagnostics[0].code)

    def test_reports_top_level_operation_outcome_without_resource(self) -> None:
        payload = {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": "not-found",
                    "details": {"text": "Requested endpoint does not exist."},
                }
            ],
        }

        result = FHIRParser.extract_resources(payload=payload)

        self.assertEqual([], result.resources)
        self.assertEqual("error", result.diagnostics[0].severity)
        self.assertEqual(
            "Requested endpoint does not exist.", result.diagnostics[0].message
        )

    def test_discovers_contained_resource_with_context(self) -> None:
        contained = self._resource(resource_type="Location", resource_id="local-1")
        payload = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "information", "code": "informational"}],
            "contained": [contained],
        }

        result = FHIRParser.extract_resources(payload=payload)

        self.assertEqual(1, len(result.resources))
        self.assertEqual(contained, result.resources[0].resource)
        self.assertTrue(result.resources[0].is_contained)
        self.assertEqual("OperationOutcome", result.resources[0].container_type)

    def test_extracts_parameters_and_nested_parts(self) -> None:
        payload = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "organization",
                    "resource": self._resource(
                        resource_type="Organization", resource_id="org-1"
                    ),
                },
                {
                    "name": "group",
                    "part": [
                        {
                            "name": "location",
                            "resource": self._resource(
                                resource_type="Location", resource_id="loc-1"
                            ),
                        }
                    ],
                },
            ],
        }

        result = FHIRParser.extract_resources(payload=payload)

        self.assertEqual(
            ["Organization", "Location"],
            [record.resource_type for record in result.resources],
        )
        self.assertTrue(
            all(record.container_type == "Parameters" for record in result.resources)
        )

    def test_reports_bundle_pagination(self) -> None:
        payload = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 25,
            "link": [{"relation": "next", "url": "https://example.test/page/2"}],
            "entry": [],
        }

        result = FHIRParser.extract_resources(payload=payload)

        self.assertEqual("pagination", result.diagnostics[0].code)
        self.assertIn("Bundle total is 25", result.diagnostics[0].message)

    def test_stops_at_maximum_depth(self) -> None:
        payload = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "part": [
                        {
                            "resource": self._resource(
                                resource_type="Organization", resource_id="too-deep"
                            )
                        }
                    ]
                }
            ],
        }

        result = FHIRParser.extract_resources(payload=payload, max_depth=1)

        self.assertEqual([], result.resources)
        self.assertEqual("maximum-depth", result.diagnostics[0].code)


if __name__ == "__main__":
    unittest.main()