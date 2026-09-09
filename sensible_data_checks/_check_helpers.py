"""Shared query helpers for sensible data checks; this file defines no check."""

from typing import Any, Dict


def run_single_record_query(*, engine, query: str, parameters: Dict[str, Any]):
    """Run a Cypher query and return its single record as a dictionary."""
    with engine.session() as session:
        record = session.run(query, **parameters).single()
    return dict(record) if record else {}


def imported_node_filter() -> str:
    """Return the standard import-tag predicate used by checks."""
    return "directory_node.import_tag = $import_tag"