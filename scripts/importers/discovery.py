"""
File discovery for multi-format FHIR and non-FHIR provider directory imports.

discover_fhir_files() replaces the duplicated discover_ndjson_files() in both
import_ndjson_fast.py and import_or_update_ndjson.py.

Key differences from the old function:
  - Scans *.ndjson, *.json, and extensionless endpoint-cache files
  - Returns Dict[str, List[Path]] -- multiple files per resource type are grouped
  - Two-pass matching:
      Pass 1: normalise stem, look up in STEM_MAP
      Pass 2: content-sniff unmatched .json and extensionless files
  - MR_JSON files are collected under the special key '__mr__'
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .fhir_parser import FHIRParser
from .registry import FileFormat, STEM_MAP, detect_format, normalize_stem

_CONFUSING_STEMS: list[tuple[str, str]] = [
    ("practitionerrole",        "PractitionerRole"),
    ("organizationaffiliation",  "OrganizationAffiliation"),
]


def discover_fhir_files(*, directory: Path) -> Dict[str, List[Path]]:
    """
    Discover FHIR (and MR) provider directory files in directory.

    Returns a dict mapping resource type -> list of matching Paths.
    Special key '__mr__' holds MR_JSON files.
    """
    discovered: Dict[str, List[Path]] = {}

    if not directory.exists():
        print(f"Error: Directory does not exist: {directory}")
        return discovered
    if not directory.is_dir():
        print(f"Error: Path is not a directory: {directory}")
        return discovered

    all_files = sorted(
        filepath
        for filepath in directory.iterdir()
        if filepath.is_file() and filepath.suffix.lower() in ("", ".json", ".ndjson")
    )
    if not all_files:
        return discovered

    unmatched_files: List[Path] = []

    # Pass 1: name-based matching
    for filepath in all_files:
        normalised = normalize_stem(filepath.stem)

        if filepath.suffix.lower() == ".ndjson" and _is_confusing_ndjson(filepath):
            sys.exit(1)

        if normalised in STEM_MAP and filepath.suffix:
            resource_type = STEM_MAP[normalised]
            discovered.setdefault(resource_type, []).append(filepath)
            print(f"  Found (name): {resource_type} <- {filepath.name}")
        elif filepath.suffix.lower() in ("", ".json"):
            # Extensionless cache files must always be content-validated. Unmatched
            # JSON is also sniffed so arbitrary cache filenames remain supported.
            unmatched_files.append(filepath)
        else:
            print(f"  Warning: Skipping unrecognised file: {filepath.name}")

    # Pass 2: content sniffing for unmatched JSON and extensionless files
    for filepath in unmatched_files:
        file_format = detect_format(filepath)

        if file_format == FileFormat.MR_JSON:
            discovered.setdefault("__mr__", []).append(filepath)
            print(f"  Found (sniff-MR): __mr__ <- {filepath.name}")
            continue

        if file_format in (FileFormat.FHIR_BUNDLE, FileFormat.FHIR_NDJSON):
            resource_type = _sniff_resource_type(filepath, file_format)
            filename_resource_type = STEM_MAP.get(normalize_stem(filepath.name))
            if filename_resource_type and resource_type != filename_resource_type:
                print(
                    f"  Warning: Skipping {filepath.name}: filename implies "
                    f"{filename_resource_type}, but content contains {resource_type}."
                )
            elif resource_type and resource_type in STEM_MAP.values():
                discovered.setdefault(resource_type, []).append(filepath)
                print(f"  Found (sniff-FHIR): {resource_type} <- {filepath.name}")
            elif resource_type == "OperationOutcome":
                print(
                    f"  Warning: Skipping {filepath.name}: FHIR OperationOutcome "
                    "reported an upstream request error."
                )
            elif resource_type:
                print(
                    f"  Warning: Found FHIR resource type {resource_type} in "
                    f"{filepath.name}, but no importer is registered."
                )
            else:
                print(f"  Warning: Unknown resource type in: {filepath.name}")
            continue

        print(f"  Warning: Skipping unknown-format file: {filepath.name}")

    return discovered


def _is_confusing_ndjson(filepath: Path) -> bool:
    """Detect and report ambiguous dot-separated NDJSON filenames."""
    stem_lower = filepath.stem.lower().replace(".", "")
    for confusing_stem, correct_name in _CONFUSING_STEMS:
        if stem_lower == confusing_stem and "." in filepath.stem:
            print(f"\n{'!'*60}")
            print(f"ERROR: Ambiguous filename: {filepath.name}")
            print(f"Rename to: {correct_name}.ndjson or {correct_name}-1.json")
            print(f"{'!'*60}\n")
            return True
    return False


def _sniff_resource_type(filepath: Path, file_format: FileFormat) -> Optional[str]:
    """Return the first independently importable resource type in a FHIR file."""
    try:
        if file_format == FileFormat.FHIR_BUNDLE:
            with open(filepath, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            parse_result = FHIRParser.extract_resources(payload=payload)
            for diagnostic in parse_result.diagnostics:
                print(
                    f"  FHIR {diagnostic.severity} [{diagnostic.code}] in "
                    f"{filepath.name} at {diagnostic.source_path}: {diagnostic.message}"
                )
            for resource_record in parse_result.resources:
                if not resource_record.is_contained:
                    return resource_record.resource_type
            if any(
                diagnostic.code != "pagination"
                and diagnostic.code != "maximum-depth"
                for diagnostic in parse_result.diagnostics
            ):
                return "OperationOutcome"
            return None

        with open(filepath, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    payload = json.loads(line)
                    parse_result = FHIRParser.extract_resources(payload=payload)
                    for diagnostic in parse_result.diagnostics:
                        print(
                            f"  FHIR {diagnostic.severity} [{diagnostic.code}] in "
                            f"{filepath.name} at {diagnostic.source_path}: "
                            f"{diagnostic.message}"
                        )
                    for resource_record in parse_result.resources:
                        if not resource_record.is_contained:
                            return resource_record.resource_type
                    if isinstance(payload, dict):
                        return payload.get("resourceType")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return None
