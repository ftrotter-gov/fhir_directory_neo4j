# Sensible Data Checks

Each `check_*.py` file contains exactly one InLaw sanity check. Shared helper
functions live in `_check_helpers.py`, which contains no check class.

Run import and all checks together from the repository root:

```bash
python import_and_check_fhir_directory.py --import-tag a_unique_import_tag
```

Expected node counts are derived from the discovered source files rather than
hardcoded for one publisher.

The source directory defaults to `FHIR_DIRECTORY_PATH` in the repository
`.env`. A positional directory can still be supplied to override that value.

The checks use InLaw's programmatic runner with the Neo4j driver supplied as
the `engine`. InLaw 0.1.0 publishes its implementation under the import path
`src.inlaw`, so check files import `InLaw` from that installed package path.

The relationship inventory reports zero relationships as a valid result when
a partial paginated cache does not contain the resources referenced by its
roles and affiliations. It still fails if self-referential relationships are
found.