# Quick Start Guide

This guide starts Neo4j, creates the graph schema, and imports supported FHIR
provider-directory files.

## Prerequisites

- Docker with Docker Compose
- Python 3.9 or newer
- Internet access for installing the Python requirements and Docker image
- FHIR NDJSON, FHIR Bundle JSON, or recognized single-resource FHIR JSON files

## 1. Install and Start Neo4j

From the repository root:

```bash
python3 download_install_neo4j_docker.py
```

The installer:

- Creates or reuses `.venv` and restarts itself with that interpreter.
- Installs every package in `requirements.txt`.
- Creates `.env` with a secure generated password if it does not exist.
- Validates Docker and Docker Compose.
- Downloads and starts the Neo4j image.
- Waits for Neo4j to become healthy.
- Applies `schema/indexes.cypher`.
- Verifies Neo4j and the installed Python packages.

The script does not overwrite an existing `.env` or delete existing database
data. Use `--timeout SECONDS` to change the 180-second startup timeout.

Activate the environment for subsequent commands:

```bash
source .venv/bin/activate
```

On Windows, use `.venv\Scripts\activate` instead. A child Python process cannot
activate a virtual environment in its parent shell, so the installer runs
itself with `.venv` and prints this activation command for your shell.

Neo4j Browser is available at <http://localhost:7474>, and Bolt is available at
`bolt://localhost:7687`.

## 2. Manual Setup (Optional)

Use these steps only if the installer cannot be used:

```bash
cp example.env .env
# Edit .env and replace both matching password placeholders.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose --env-file .env pull neo4j
docker compose --env-file .env up -d neo4j
set -a
source .env
set +a
docker exec -i fhir_neo4j_analysis cypher-shell \
  -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < schema/indexes.cypher
```

Create the schema before importing so `MERGE` and relationship lookups can use
indexes.

## 3. Import FHIR Data

The scripts automatically load the repository-root `.env` file.

Set the default source directory once in `.env`:

```dotenv
FHIR_DIRECTORY_PATH=/absolute/path/to/fhir/directory
```

All import programs use this value when the positional directory is omitted.
An explicit command-line directory overrides the configured default.

### Import with repeatable sanity checks

The recommended validation workflow runs the safe importer twice, prints
source and processed counts, and executes the checks in
`sensible_data_checks/`:

```bash
python import_and_check_fhir_directory.py --import-tag a_unique_source_tag
```

Expected counts are calculated from the importable source resources. A second
safe pass reconciles relationships whose referenced nodes became available
during the first pass. The command exits nonzero if import counts differ or any
InLaw check fails.

### Safe, repeatable import

Use the idempotent importer unless the database is known to be empty:

```bash
python scripts/import_or_update_ndjson.py --batch-size 5000
```

### Faster initial import

For an empty database only, use `CREATE`-based import:

```bash
python scripts/import_ndjson_fast.py --batch-size 10000
```

Running the fast importer more than once can create duplicates or conflict
with uniqueness constraints.

Use `--limit` for a trial import and `--import-tag` to identify newly created
nodes:

```bash
python scripts/import_or_update_ndjson.py /path/to/directory \
  --limit 100 --import-tag trial_import
```

## Accepted Input Files

Discovery scans one directory for `*.ndjson`, `*.json`, and extensionless FHIR
endpoint-cache files. It supports multiple files per resource type and common
names such as:

- `Practitioner.ndjson`
- `Practitioners-1.json`
- `payer_PractitionerRoles-3.json`
- `OrganizationAffiliation.ndjson`
- `HealthcareServices.json`
- `Organization`
- `PractitionerRole`

Unrecognized JSON filenames and extensionless files are content-sniffed.
Extensionless files are accepted only when their FHIR content matches the
resource type implied by the filename. FHIR Bundles are unpacked from
`entry[].resource`. Source profiles are used to label nodes as
`fhir_ndh`, `fhir_plannet`, or `fhir_unknown`.

CMS machine-readable top-level JSON arrays are detected, but the importer
currently warns and skips them because normalization is not yet implemented.

Avoid ambiguous dot-separated names such as `Practitioner.Role.ndjson` and
`Organization.Affiliation.ndjson`.

## 4. Verify the Import

Open <http://localhost:7474> and run:

```cypher
MATCH (directory_node)
RETURN labels(directory_node) AS node_type,
       directory_node.source_format AS source_format,
       count(directory_node) AS node_count
ORDER BY node_count DESC;
```

## Common Commands

```bash
# Follow logs
docker compose logs -f neo4j

# Stop services
docker compose down

# Delete local database data and restart (destructive)
docker compose down
rm -rf data/ logs/
docker compose up -d
```

## Troubleshooting

- **Authentication failed:** verify that the password portion of `NEO4J_AUTH`
  matches `NEO4J_PASSWORD`. Existing Neo4j data retains its original password;
  changing `.env` alone does not reset it.
- **Cannot connect:** run `docker compose ps` and `docker compose logs neo4j`.
- **No supported files found:** confirm the files use `.ndjson` or `.json` and
  contain supported FHIR resources.
- **MR file skipped:** this is expected until `MRNormalizer.normalize()` is
  implemented.

For more detail, see [README_neo4j.md](README_neo4j.md).