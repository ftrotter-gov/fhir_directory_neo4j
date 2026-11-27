"""Da Vinci PDex Plan-Net coverage tests (NPDV-528).

The public CMS NPD bulk download is entirely NDH-profiled, so these tests use the
HL7 Da Vinci PDex Plan-Net IG example resources (vendored under
tests/fixtures/plannet/) to exercise the fhir_plannet source_format path and the
Plan-Net-specific cross-references that NDH data does not contain.

All checks are DB-free: discovery and registry need no Neo4j, and InsurancePlan
mapping is validated through the static build_plan_record() helper.
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

from importers.discovery import discover_fhir_files  # noqa: E402
from importers.registry import get_source_format_string  # noqa: E402
from importers.insurance_plan import InsurancePlanImporter  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "plannet"

EXPECTED_TYPES = {
    "Practitioner",
    "PractitionerRole",
    "Organization",
    "OrganizationAffiliation",
    "Location",
    "Endpoint",
    "HealthcareService",
    "InsurancePlan",
}


def _read_ndjson(resource_type: str) -> list:
    path = FIXTURE_DIR / f"{resource_type}.ndjson"
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class PlanNetFixtureTest(unittest.TestCase):
    def test_fixtures_present(self) -> None:
        self.assertTrue(FIXTURE_DIR.is_dir(), f"missing fixture dir: {FIXTURE_DIR}")
        for resource_type in EXPECTED_TYPES:
            self.assertTrue(
                (FIXTURE_DIR / f"{resource_type}.ndjson").is_file(),
                f"missing fixture: {resource_type}.ndjson",
            )

    def test_discovery_finds_all_plannet_resource_types(self) -> None:
        discovered = discover_fhir_files(directory=FIXTURE_DIR)
        self.assertEqual(EXPECTED_TYPES, set(discovered.keys()))

    def test_source_format_is_plannet_for_every_fixture(self) -> None:
        for resource_type in EXPECTED_TYPES:
            path = FIXTURE_DIR / f"{resource_type}.ndjson"
            self.assertEqual(
                "fhir_plannet",
                get_source_format_string(path),
                f"{resource_type} should classify as fhir_plannet",
            )

    def test_insurance_plan_refs_resolve_into_organization_set(self) -> None:
        """Plan-Net InsurancePlan ownedBy/network must point at real Organizations."""
        org_ids = {org["id"] for org in _read_ndjson("Organization")}
        plans = _read_ndjson("InsurancePlan")
        self.assertTrue(plans, "expected at least one InsurancePlan fixture")

        saw_owner = saw_network = False
        for resource in plans:
            record = InsurancePlanImporter.build_plan_record(
                resource=resource, source_format="fhir_plannet"
            )
            self.assertIsNotNone(record)
            if record["owned_by_id"]:
                saw_owner = True
                self.assertIn(record["owned_by_id"], org_ids)
            for net_id in record["network_ids"]:
                saw_network = True
                self.assertIn(net_id, org_ids)

        self.assertTrue(saw_owner, "no InsurancePlan ownedBy reference exercised")
        self.assertTrue(saw_network, "no InsurancePlan network reference exercised")

    def test_organization_affiliation_has_plannet_network(self) -> None:
        """network[] on OrganizationAffiliation is the Plan-Net addition (IN_NETWORK)."""
        affiliations = _read_ndjson("OrganizationAffiliation")
        self.assertTrue(
            any(resource.get("network") for resource in affiliations),
            "expected at least one OrganizationAffiliation with a network[]",
        )


if __name__ == "__main__":
    unittest.main()
