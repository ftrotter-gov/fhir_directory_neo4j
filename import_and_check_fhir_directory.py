#!/usr/bin/env python3
"""Safely import a FHIR directory twice and run repeatable InLaw checks."""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from neo4j import GraphDatabase
from src.inlaw import InLaw

REPOSITORY_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from import_or_update_ndjson import (  # noqa: E402
    IMPORTER_MAP,
    import_resource_files,
    load_neo4j_config,
)
from importers import (  # noqa: E402
    discover_fhir_files,
    get_source_format_string,
    resolve_fhir_directory,
)


CHECK_FILES = [
    "check_expected_node_counts.py",
    "check_import_source_format.py",
    "check_required_node_properties.py",
    "check_practitioner_npis.py",
    "check_duplicate_primary_keys.py",
    "check_relationship_inventory.py",
]


def derive_expected_counts(
    *, files: Dict[str, List[Path]], limit: Optional[int]
) -> Dict[str, int]:
    """Count importable source resources with the production importer readers."""
    config = load_neo4j_config()
    expected_counts: Dict[str, int] = {}
    for resource_type, filepaths in files.items():
        if resource_type == "__mr__" or resource_type not in IMPORTER_MAP:
            continue
        remaining = limit if limit and limit > 0 else None
        resource_count = 0
        for filepath in filepaths:
            importer = IMPORTER_MAP[resource_type](
                neo4j_uri=config["uri"],
                neo4j_user=config["user"],
                neo4j_password=config["password"],
                source_format=get_source_format_string(filepath),
            )
            try:
                records = importer.read_file(filepath=filepath)
            finally:
                importer.close()
            if remaining is None:
                resource_count += len(records)
            else:
                selected_count = min(len(records), remaining)
                resource_count += selected_count
                remaining -= selected_count
                if remaining == 0:
                    break
        expected_counts[resource_type] = resource_count
    return expected_counts


def print_import_summary(
    *, expected_counts: Dict[str, int], imported_counts: Dict[str, int]
) -> None:
    """Print source and processed counts by resource type."""
    print("\nImport summary")
    print("=" * 72)
    print(f"{'Resource type':32} {'Source':>12} {'Processed':>12}")
    for resource_type in sorted(expected_counts):
        print(
            f"{resource_type:32} {expected_counts[resource_type]:>12} "
            f"{imported_counts.get(resource_type, 0):>12}"
        )


def run_sensible_data_checks(
    *, config: Dict[str, object], neo4j_config: Dict[str, str]
) -> Dict[str, object]:
    """Run each explicit one-check InLaw file against the Neo4j driver."""
    check_directory = REPOSITORY_ROOT / "sensible_data_checks"
    check_paths = [str(check_directory / filename) for filename in CHECK_FILES]
    driver = GraphDatabase.driver(
        neo4j_config["uri"],
        auth=(neo4j_config["user"], neo4j_config["password"]),
    )
    try:
        return InLaw.run_all(
            engine=driver,
            inlaw_files=check_paths,
            config=config,
            ignore_skip_test=True,
        )
    finally:
        driver.close()


def build_argument_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for repeatable import validation."""
    parser = argparse.ArgumentParser(
        description="Import supported FHIR files and run sensible Neo4j data checks."
    )
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        help="FHIR directory; defaults to FHIR_DIRECTORY_PATH from .env",
    )
    parser.add_argument("--import-tag", required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main(*, arguments: Optional[Sequence[str]] = None) -> int:
    """Run two safe import passes followed by all InLaw sanity checks."""
    parsed_arguments = build_argument_parser().parse_args(arguments)
    fhir_directory = resolve_fhir_directory(
        command_line_directory=parsed_arguments.directory,
        environment_path=REPOSITORY_ROOT / ".env",
    )
    print(f"Using FHIR directory: {fhir_directory}")
    files = discover_fhir_files(directory=fhir_directory)
    if not files:
        raise RuntimeError(
            "import_and_check_fhir_directory.py Error: No supported files discovered."
        )
    expected_counts = derive_expected_counts(
        files=files, limit=parsed_arguments.limit
    )

    first_pass_counts = import_resource_files(
        files=files,
        batch_size=parsed_arguments.batch_size,
        import_tag=parsed_arguments.import_tag,
        limit=parsed_arguments.limit,
    )
    print("\nRunning a second safe pass to reconcile resolvable relationships...")
    second_pass_counts = import_resource_files(
        files=files,
        batch_size=parsed_arguments.batch_size,
        import_tag=parsed_arguments.import_tag,
        limit=parsed_arguments.limit,
    )
    print_import_summary(
        expected_counts=expected_counts, imported_counts=second_pass_counts
    )
    if first_pass_counts != expected_counts or second_pass_counts != expected_counts:
        raise RuntimeError(
            "import_and_check_fhir_directory.py Error: Processed counts do not "
            "match source-derived expectations."
        )

    neo4j_config = load_neo4j_config()
    results = run_sensible_data_checks(
        config={
            "expected_counts": expected_counts,
            "import_tag": parsed_arguments.import_tag,
            "source_format": "fhir_plannet",
        },
        neo4j_config=neo4j_config,
    )
    if results.get("failed", 0) or results.get("errors", 0):
        raise RuntimeError(
            "import_and_check_fhir_directory.py Error: Sensible data checks failed."
        )
    print("\nImport and all sensible data checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as workflow_error:
        print(workflow_error, file=sys.stderr)
        raise SystemExit(1)