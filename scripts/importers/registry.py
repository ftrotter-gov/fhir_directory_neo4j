"""
Format registry for multi-format FHIR and non-FHIR provider directory imports.

Responsibilities:
  - Detect the file format from extension and content
  - Derive the source_format string stamped on every Neo4j node
  - Provide the canonical STEM_MAP used by file discovery

FileFormat enum values:
  FHIR_NDJSON  - one FHIR resource JSON object per line (.ndjson)
  FHIR_BUNDLE  - single FHIR Bundle JSON object wrapping an entry[] array (.json)
  MR_JSON      - CMS Machine-Readable (MR) top-level JSON array (.json)
  UNKNOWN      - could not be determined; callers should warn and skip

Source format strings stamped on every node:
  "fhir_ndh"      - FHIR NDH IG (davinci-ndh profile)
  "fhir_plannet"  - FHIR Da Vinci PDex Plan Net IG
  "mr_json"       - CMS Machine-Readable provider directory JSON
  "fhir_unknown"  - FHIR data whose profile URL was not recognised
  "unknown"       - format could not be determined

Adding a new format:
  1. Add a value to FileFormat
  2. Update detect_format() with the new detection logic
  3. Update get_source_format_string() with the new profile/source string
  4. Add stem variants to STEM_MAP if needed
"""

import json
import re
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class FileFormat(Enum):
    FHIR_NDJSON = "fhir_ndjson"
    FHIR_BUNDLE = "fhir_bundle"
    MR_JSON     = "mr_json"
    UNKNOWN     = "unknown"


# Stem -> canonical FHIR resourceType. Keys are lowercase, underscore-free.
STEM_MAP: dict[str, str] = {
    "practitioner":              "Practitioner",
    "practitioners":             "Practitioner",
    "practitionerrole":          "PractitionerRole",
    "practitionerroles":         "PractitionerRole",
    "organization":              "Organization",
    "organizations":             "Organization",
    "organizationaffiliation":   "OrganizationAffiliation",
    "organizationaffiliations":  "OrganizationAffiliation",
    "location":                  "Location",
    "locations":                 "Location",
    "endpoint":                  "Endpoint",
    "endpoints":                 "Endpoint",
    "healthcareservice":         "HealthcareService",
    "healthcareservices":        "HealthcareService",
    "insuranceplan":             "InsurancePlan",
    "insuranceplans":            "InsurancePlan",
}

# Profile URL substrings -> source_format strings (checked in order)
_PROFILE_FORMAT_MAP: list[tuple[str, str]] = [
    ("davinci-pdex-plan-net", "fhir_plannet"),
    ("davinci-ndh",           "fhir_ndh"),
]


def detect_format(filepath: Path) -> FileFormat:
    """
    Detect the file format by extension and content peek.

    Logic:
      .ndjson  -> FHIR_NDJSON
      .json or extensionless, first char '[' -> MR_JSON
      .json or extensionless, resourceType == "Bundle" -> FHIR_BUNDLE
      .json or extensionless, other resourceType -> FHIR_NDJSON (single resource)
      anything else -> UNKNOWN
    """
    suffix = filepath.suffix.lower()
    if suffix == ".ndjson":
        return FileFormat.FHIR_NDJSON
    if suffix not in ("", ".json"):
        return FileFormat.UNKNOWN
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            head = fh.read(8192)
        stripped = head.lstrip()
        if not stripped:
            return FileFormat.UNKNOWN
        first_char = stripped[0]
        if first_char == "[":
            return FileFormat.MR_JSON
        if first_char == "{":
            resource_type = _peek_resource_type(head)
            if resource_type == "Bundle":
                return FileFormat.FHIR_BUNDLE
            if resource_type is not None:
                return FileFormat.FHIR_NDJSON
            return FileFormat.UNKNOWN
    except (OSError, UnicodeDecodeError):
        pass
    return FileFormat.UNKNOWN


# Friendly --source-format CLI choices mapped to the canonical node stamp. Lets
# operators correctly tag inputs that carry no meta.profile -- notably the
# official CMS National Provider Directory bulk download, whose NDH resources
# omit meta.profile entirely and would otherwise all import as "fhir_unknown".
SOURCE_FORMAT_OVERRIDES: Dict[str, str] = {
    "ndh": "fhir_ndh",
    "plannet": "fhir_plannet",
    "unknown": "fhir_unknown",
}


def resolve_source_format_override(choice: Optional[str]) -> Optional[str]:
    """Map a --source-format CLI choice to its canonical source_format stamp."""
    if choice is None:
        return None
    try:
        return SOURCE_FORMAT_OVERRIDES[choice]
    except KeyError as error:
        raise ValueError(
            f"Unknown source-format override {choice!r}; "
            f"choose from {sorted(SOURCE_FORMAT_OVERRIDES)}"
        ) from error


def get_source_format_string(filepath: Path, file_format: Optional[FileFormat] = None) -> str:
    """
    Return the source_format string to stamp on every node from this file.

    For FHIR files the string derives from meta.profile[0] of the first resource.
    For MR files it is always "mr_json".

    Returns one of: "fhir_plannet", "fhir_ndh", "mr_json", "fhir_unknown", "unknown".
    """
    if file_format is None:
        file_format = detect_format(filepath)
    if file_format == FileFormat.MR_JSON:
        return "mr_json"
    if file_format == FileFormat.UNKNOWN:
        return "unknown"
    try:
        profile_url = _peek_first_profile(filepath, file_format)
        if profile_url:
            for substring, fmt_string in _PROFILE_FORMAT_MAP:
                if substring in profile_url:
                    return fmt_string
        return "fhir_unknown"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "fhir_unknown"


def normalize_stem(stem: str) -> str:
    """
    Normalise a filename stem for STEM_MAP lookup.

    Steps:
      1. Lowercase
      2. Strip one leading word_prefix if the remainder resolves in STEM_MAP
         e.g. "bob_practitioners" -> "practitioners"
      3. Strip trailing dash-number suffix e.g. "-1", "-23"
      4. Remove underscores e.g. "practitioner_roles" -> "practitionerroles"

    Examples:
      "bob_PractitionerRoles-3" -> "practitionerroles"
      "Practitioners-1"         -> "practitioners"
      "HealthcareServices"      -> "healthcareservices"
      "01-Organization"         -> "organization"
      "08-OrganizationAffiliation" -> "organizationaffiliation"
    """
    s = stem.lower()
    # Strip a leading numeric ordering prefix such as "01-" used by the official
    # CMS National Provider Directory bulk download (e.g. "01-Organization",
    # "08-OrganizationAffiliation"). Only strip when the remainder resolves to a
    # known resource type, so "08-OrganizationAffiliation" is never mistaken for
    # "Organization".
    leading_number = re.match(r"^\d+-(.+)$", s)
    if leading_number:
        remainder = leading_number.group(1)
        candidate = re.sub(r"-\d+$", "", remainder).replace("_", "")
        if candidate in STEM_MAP:
            s = remainder
    if "_" in s:
        _, remainder = s.split("_", 1)
        candidate = re.sub(r"-\d+$", "", remainder).replace("_", "")
        if candidate in STEM_MAP:
            s = remainder
    s = re.sub(r"-\d+$", "", s)
    return s.replace("_", "")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _peek_resource_type(text: str) -> Optional[str]:
    """Extract the top-level "resourceType" string from a JSON text chunk."""
    match = re.search(r'"resourceType"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else None


def _peek_first_profile(filepath: Path, file_format: FileFormat) -> Optional[str]:
    """Return the first meta.profile URL found in the file."""
    with open(filepath, "r", encoding="utf-8") as fh:
        head = fh.read(16384)
    if file_format == FileFormat.FHIR_BUNDLE:
        match = re.search(r'"profile"\s*:\s*\[\s*"([^"]+)"', head)
        return match.group(1) if match else None
    # FHIR_NDJSON: parse first non-empty line
    for line in head.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            profiles = obj.get("meta", {}).get("profile", [])
            if profiles:
                return profiles[0]
        except json.JSONDecodeError:
            pass
        break
    return None
