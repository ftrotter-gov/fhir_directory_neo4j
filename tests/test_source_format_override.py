"""Tests for the --source-format override mapping.

The official CMS National Provider Directory bulk download ships NDH FHIR
resources with no meta.profile, so profile-based detection stamps every node
"fhir_unknown". The override lets an operator declare the correct source_format
for such an import.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from importers.registry import (  # noqa: E402
    SOURCE_FORMAT_OVERRIDES,
    resolve_source_format_override,
)


class SourceFormatOverrideTest(unittest.TestCase):
    def test_none_passthrough_preserves_profile_detection(self) -> None:
        self.assertIsNone(resolve_source_format_override(None))

    def test_ndh_maps_to_canonical_stamp(self) -> None:
        self.assertEqual("fhir_ndh", resolve_source_format_override("ndh"))

    def test_plannet_maps_to_canonical_stamp(self) -> None:
        self.assertEqual("fhir_plannet", resolve_source_format_override("plannet"))

    def test_unknown_maps_to_canonical_stamp(self) -> None:
        self.assertEqual("fhir_unknown", resolve_source_format_override("unknown"))

    def test_unrecognised_choice_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_source_format_override("not-a-format")

    def test_every_choice_maps_to_a_recognised_canonical_value(self) -> None:
        canonical_values = {
            "fhir_ndh",
            "fhir_plannet",
            "fhir_unknown",
            "mr_json",
            "unknown",
        }
        for choice, canonical in SOURCE_FORMAT_OVERRIDES.items():
            self.assertIn(canonical, canonical_values, msg=choice)


if __name__ == "__main__":
    unittest.main()
