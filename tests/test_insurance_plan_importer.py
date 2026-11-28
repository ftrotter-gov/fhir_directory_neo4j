"""Unit tests for the InsurancePlan importer field mapping (NPDV-528).

These exercise InsurancePlanImporter.build_plan_record() directly, so no live
Neo4j connection is required. The neo4j module is stubbed when absent, matching
the approach in test_base_importer_parsing.py.
"""

import json
import sys
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

from importers.insurance_plan import InsurancePlanImporter  # noqa: E402


class InsurancePlanBuildRecordTest(unittest.TestCase):
    def test_maps_full_resource(self) -> None:
        resource = {
            "resourceType": "InsurancePlan",
            "id": "plan-1",
            "status": "active",
            "name": "Acme Gold PPO",
            "alias": ["Gold PPO", "AGPPO"],
            "type": [
                {"coding": [{"code": "medical", "display": "Medical"}]},
                {"text": "Dental"},
            ],
            "period": {"start": "2026-01-01", "end": "2026-12-31"},
            "ownedBy": {"reference": "Organization/org-99"},
            "network": [
                {"reference": "Organization/net-1"},
                {"reference": "Organization/net-2"},
            ],
            "identifier": [
                {"system": "http://example.org/plans", "value": "P-001"}
            ],
        }

        record = InsurancePlanImporter.build_plan_record(
            resource=resource, source_format="fhir_plannet", import_tag="run-x"
        )

        self.assertIsNotNone(record)
        self.assertEqual("plan-1", record["fhir_id"])
        self.assertEqual("plan-1", record["primary_key"])
        self.assertEqual("fhir_plannet", record["source_format"])
        self.assertEqual("InsurancePlan", record["resource_type"])
        self.assertEqual("active", record["status"])
        self.assertEqual("Acme Gold PPO", record["name"])
        self.assertEqual(["Gold PPO", "AGPPO"], record["alias"])
        self.assertEqual(["Medical", "Dental"], record["plan_types"])
        self.assertEqual("2026-01-01", record["period_start"])
        self.assertEqual("2026-12-31", record["period_end"])
        self.assertEqual("org-99", record["owned_by_id"])
        self.assertEqual(["net-1", "net-2"], record["network_ids"])
        self.assertEqual("run-x", record["import_tag"])
        self.assertEqual(
            [{"system": "http://example.org/plans", "value": "P-001"}],
            json.loads(record["identifiers"]),
        )

    def test_returns_none_without_id(self) -> None:
        self.assertIsNone(
            InsurancePlanImporter.build_plan_record(
                resource={"resourceType": "InsurancePlan", "status": "active"}
            )
        )

    def test_normalizes_scalar_alias_to_list(self) -> None:
        record = InsurancePlanImporter.build_plan_record(
            resource={"resourceType": "InsurancePlan", "id": "p", "alias": "Solo"}
        )
        self.assertEqual(["Solo"], record["alias"])

    def test_handles_missing_optional_fields(self) -> None:
        record = InsurancePlanImporter.build_plan_record(
            resource={"resourceType": "InsurancePlan", "id": "p"}
        )
        self.assertEqual([], record["alias"])
        self.assertEqual([], record["plan_types"])
        self.assertEqual([], record["network_ids"])
        self.assertIsNone(record["owned_by_id"])
        self.assertIsNone(record["period_start"])
        self.assertIsNone(record["period_end"])
        self.assertIsNone(record["identifiers"])
        self.assertEqual("fhir_unknown", record["source_format"])

    def test_type_coding_falls_back_to_code_when_no_display(self) -> None:
        record = InsurancePlanImporter.build_plan_record(
            resource={
                "resourceType": "InsurancePlan",
                "id": "p",
                "type": [{"coding": [{"code": "vision"}]}],
            }
        )
        self.assertEqual(["vision"], record["plan_types"])

    def test_skips_malformed_network_entries(self) -> None:
        record = InsurancePlanImporter.build_plan_record(
            resource={
                "resourceType": "InsurancePlan",
                "id": "p",
                "network": [{"reference": "Organization/n1"}, "not-a-dict", {}],
            }
        )
        self.assertEqual(["n1"], record["network_ids"])


if __name__ == "__main__":
    unittest.main()
