"""
MR (CMS Machine-Readable) provider directory JSON normalizer.

This module will implement fan-out normalization of MR format records into
canonical dicts that the existing graph Writers (importers) can consume.

MR format structure (one top-level JSON array):
  [
    {
      "npi": "1003015124",
      "type": "Individual",       // or "Organization"
      "name": {"first": "...", "last": "..."},
      "sex": "Female",
      "languages": ["English"],
      "plans": [
        {
          "maPlanId": "H4232-001-000",
          "accepting": "accepting",
          "specialty": ["207LH0002X"],
          "addresses": [
            {"address": "...", "city": "...", "state": "...",
             "zip": "...", "phone": "..."}
          ],
          "networks": ["H4232001"],
          "year": ["2027"]
        }
      ],
      "lastUpdatedOn": "2026-08-28"
    },
    ...
  ]

Fan-out: one MR record -> multiple (entity_type, canonical_dict) tuples:
  ('Practitioner',    {npi, name, sex, languages, source_format='mr_json',
                       primary_key=npi, fhir_id=None})

  For each plans[] entry:
    ('Organization',      {primary_key=network_code, name=network_code,
                           org_type='network', source_format='mr_json'})
    ('Organization',      {primary_key=ma_plan_id,   name=ma_plan_id,
                           org_type='plan',    source_format='mr_json'})
    ('PractitionerRole',  {primary_key=sha256(npi+plan_id),
                           npi, accepting, specialties, ma_plan_id,
                           network_codes, source_format='mr_json'})

    For each addresses[] entry:
      ('Location', {primary_key=sha256(npi+address+zip),
                    address, city, state, zip, phone,
                    source_format='mr_json'})

TODO: Implement this class when MR import work begins.
      The interface below is fixed -- do not change method signatures.
"""

import hashlib
from typing import Iterator, Tuple, Dict, Any

SOURCE_FORMAT = "mr_json"


class MRNormalizer:
    """
    Fan-out normalizer for CMS Machine-Readable provider directory JSON.

    Usage (future):
        normalizer = MRNormalizer()
        with open(mr_file) as f:
            records = json.load(f)
        for raw_record in records:
            for entity_type, canonical_dict in normalizer.normalize(raw_record):
                # route canonical_dict to the appropriate graph Writer
                writers[entity_type].write(canonical_dict)
    """

    def normalize(self, raw_record: Dict[str, Any]) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Normalize one MR raw record into (entity_type, canonical_dict) tuples.

        Args:
            raw_record: One entry from the top-level MR JSON array.

        Yields:
            Tuples of (entity_type_string, canonical_dict) where entity_type_string
            is one of: 'Practitioner', 'Organization', 'PractitionerRole', 'Location'.

        Raises:
            NotImplementedError: Until this method is implemented.
        """
        raise NotImplementedError(
            "MRNormalizer.normalize() is not yet implemented. "
            "Implement this when MR import work begins."
        )

    @staticmethod
    def location_key(npi: str, address: str, zip_code: str) -> str:
        """
        Compute a stable synthetic primary_key for an MR-sourced Location.

        Uses SHA-256 of the concatenated npi + normalised address + zip_code
        so the same provider at the same address always gets the same key,
        enabling idempotent re-imports without address normalisation.

        Args:
            npi:      Provider NPI string
            address:  Street address string (as-is from MR data)
            zip_code: ZIP code string

        Returns:
            Hex-encoded SHA-256 digest prefixed with 'mr_loc_'
        """
        raw = f"{npi}|{address.strip().upper()}|{zip_code.strip()}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"mr_loc_{digest}"

    @staticmethod
    def practitioner_role_key(npi: str, ma_plan_id: str) -> str:
        """
        Compute a stable synthetic primary_key for an MR-sourced PractitionerRole.

        Args:
            npi:       Provider NPI string
            ma_plan_id: MA plan ID string (e.g. "H4232-001-000")

        Returns:
            Hex-encoded SHA-256 digest prefixed with 'mr_role_'
        """
        raw = f"{npi}|{ma_plan_id.strip()}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"mr_role_{digest}"
