# FHIR Directory Neo4j Guide

FHIR Directory Neo4j loads healthcare directory data into Neo4j so providers,
organizations, payer networks, services, locations, and technical endpoints can
be explored as a connected graph.

## Project Scope

The long-term goal is a common graph for the major US provider-directory data
sources:

1. **NPD / NDH FHIR:** National Provider Directory (NPD) work using the
   FAST-backed HL7 National Directory of Healthcare Providers & Services (NDH)
   Implementation Guide.
2. **Da Vinci PDex Plan Net:** payer provider directories represented with the
   HL7 Da Vinci PDex Plan Net Implementation Guide.
3. **CMS machine-readable directories:** payer-published machine-readable JSON
   provider-directory files.

The current release imports supported NDH and Plan Net FHIR resources from
NDJSON, Bundle JSON, and recognized single-resource JSON. It detects
machine-readable JSON arrays, but normalization and graph import for that
format are not yet implemented.

This project is experimental/alpha. Expect the schema and import behavior to
change as additional directory sources are implemented.

## Current Support Matrix

| Source | Input | Status |
| --- | --- | --- |
| NPD / NDH | FHIR NDJSON | Implemented |
| NPD / NDH | FHIR Bundle JSON | Implemented |
| Da Vinci PDex Plan Net | FHIR NDJSON | Implemented |
| Da Vinci PDex Plan Net | FHIR Bundle JSON | Implemented |
| Recognized FHIR source | Single-resource JSON | Implemented |
| CMS machine-readable directory | Top-level JSON array | Detected and skipped; importer pending |

FHIR files without a recognized NDH or Plan Net profile can still be imported
and receive `source_format = "fhir_unknown"`.

## Supported FHIR Resources

- `Practitioner`
- `PractitionerRole`
- `Organization`
- `OrganizationAffiliation`
- `Location`
- `Endpoint`
- `HealthcareService`

Other FHIR resource types are not currently routed to an importer.

## Prerequisites

- Docker with Docker Compose
- Python 3.9 or newer
- Python package `neo4j>=5.14.0`
- A directory containing supported `.ndjson` or `.json` input files

This is a standalone repository. It does not require a parent FHIRTableSaw
checkout or Python environment.

## Automated Installation

Run the root-level installer:

```bash
python3 download_install_neo4j_docker.py
```

It performs the complete local setup:

1. Validates Python 3.9 or newer.
2. Creates or reuses `.venv`.
3. Restarts itself with the `.venv` Python interpreter.
4. Installs [requirements.txt](requirements.txt).
5. Creates `.env` with a secure generated password when it is absent.
6. Validates Docker, Docker Compose, and the Docker daemon.
7. Pulls and starts the Neo4j service.
8. Waits for the container health check.
9. Applies `schema/indexes.cypher`.
10. Verifies Cypher connectivity and Python dependency imports.

The installer is idempotent for normal reuse: it preserves an existing `.env`
and local database. It does not reset an existing Neo4j password or delete
data. Its default health timeout is 180 seconds and can be changed with
`--timeout SECONDS`.

After installation, activate the environment in the current shell:

```bash
source .venv/bin/activate
```

The installer cannot permanently activate `.venv` in the shell that launched
it because child processes cannot modify a parent shell. It instead restarts
itself with `.venv` and uses that interpreter for all Python installation and
verification work.

## Manual Environment Configuration

For manual installation or troubleshooting, copy the tracked template:

```bash
cp example.env .env
```

The template contains:

```dotenv
NEO4J_AUTH=neo4j/change_this_password
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_this_password
```

### Variable responsibilities

| Variable | Consumer | Purpose |
| --- | --- | --- |
| `NEO4J_AUTH` | Docker Compose / Neo4j image | Initializes the database username and password |
| `NEO4J_URI` | Python import scripts | Bolt connection URI; defaults to `bolt://localhost:7687` |
| `NEO4J_USER` | Python import scripts | Neo4j username; defaults to `neo4j` |
| `NEO4J_PASSWORD` | Python scripts and Docker health check | Required connection password |

The password portion of `NEO4J_AUTH` must match `NEO4J_PASSWORD`. Replace both
placeholder values before starting Neo4j. Do not commit `.env` or real secrets.

The Python scripts load `.env` from the repository root and apply its values to
the process environment. Existing Neo4j data retains the password with which it
was initialized; changing `.env` does not change an existing database password.

## Start Neo4j

```bash
docker compose up -d
docker compose logs neo4j
```

Services are exposed at:

- Neo4j Browser: <http://localhost:7474>
- Bolt: `bolt://localhost:7687`

Install all Python dependencies in the project environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Create the Schema

Apply constraints and indexes before importing:

```bash
set -a
source .env
set +a
docker exec -i fhir_neo4j_analysis cypher-shell \
  -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < schema/indexes.cypher
```

The schema includes FHIR ID constraints, universal primary-key constraints,
NPI and name indexes, relationship-reference indexes, import-tag indexes, and
source-format indexes.

## Import Modes

### Safe import and update

`import_or_update_ndjson.py` uses `MERGE` and is the default choice for repeat
imports and updates:

```bash
python scripts/import_or_update_ndjson.py /path/to/directory \
  --batch-size 5000 --import-tag payer_2026
```

Node import is idempotent by `primary_key`, and relationships use `MERGE`.
Properties present in a later import replace the corresponding stored values.

### Fast initial import

`import_ndjson_fast.py` uses `CREATE` and is intended only for an empty
database:

```bash
python scripts/import_ndjson_fast.py /path/to/directory \
  --batch-size 10000 --import-tag initial_load
```

Running this importer against existing records can create duplicates or fail
against uniqueness constraints.

Both scripts support `--limit NUMBER` for trial imports. The limit is applied
across all files discovered for each resource type.

## File Discovery and Format Detection

The importer scans the supplied directory, but not its subdirectories, for
`*.ndjson` and `*.json` files.

### Name-based matching

Singular, plural, numeric-suffix, and one-prefix forms are recognized. Examples
include:

- `Practitioner.ndjson`
- `Practitioners-1.json`
- `payer_PractitionerRoles-3.json`
- `OrganizationAffiliations.json`
- `HealthcareServices.json`

Multiple files can map to the same resource type and are imported in sorted
filename order. Avoid ambiguous dot-separated names such as
`Practitioner.Role.ndjson` and `Organization.Affiliation.ndjson`.

### Content detection

Unmatched JSON filenames are inspected to identify:

- A FHIR Bundle object with `resourceType = "Bundle"`
- A single FHIR resource object
- A top-level machine-readable JSON array

FHIR Bundles are unpacked from `entry[].resource`. Each importer filters input
to its own FHIR `resourceType`.

### Source classification

The first resource profile found in a FHIR file determines the `source_format`
stamped on nodes from that file:

- `fhir_ndh` for recognized NDH profiles
- `fhir_plannet` for recognized Da Vinci Plan Net profiles
- `fhir_unknown` for FHIR data with an unrecognized or absent profile
- `mr_json` is reserved for future normalized machine-readable records

A file containing resources from mixed profiles is classified from its first
resource, so source files should not mix implementation-guide profiles.

## Graph Data Model

### Universal node properties

Every imported FHIR node includes:

- `primary_key`: currently the FHIR resource ID
- `fhir_id`: FHIR `Resource.id`
- `resource_type`: FHIR resource type
- `source_format`: source classification
- `import_tag`: optional provenance tag, set when a node is created

The universal `primary_key` supports future non-FHIR entities whose stable key
may be an NPI, network identifier, or deterministic hash instead of a FHIR ID.

Nested FHIR structures such as identifiers, addresses, and licenses are stored
as JSON strings because Neo4j properties cannot contain nested maps. Primitive
lists such as specialties, phone numbers, and languages remain Neo4j arrays.

### Principal relationships

```text
(Practitioner)-[:HAS_ROLE]->(PractitionerRole)
(Practitioner)-[:HAS_ENDPOINT {rank}]->(Endpoint)
(PractitionerRole)-[:WORKS_AT]->(Organization)
(PractitionerRole)-[:AT_LOCATION]->(Location)
(PractitionerRole)-[:HAS_ENDPOINT]->(Endpoint)
(PractitionerRole)-[:IN_NETWORK]->(Organization)

(Organization)-[:PART_OF]->(Organization)
(Organization)-[:HAS_ENDPOINT]->(Endpoint)
(Organization)-[:MANAGES]->(Location)
(Organization)-[:MANAGES]->(Endpoint)
(Organization)-[:HAS_AFFILIATION]->(OrganizationAffiliation)

(OrganizationAffiliation)-[:AFFILIATED_WITH]->(Organization)
(OrganizationAffiliation)-[:AT_LOCATION]->(Location)
(OrganizationAffiliation)-[:HAS_ENDPOINT]->(Endpoint)
(OrganizationAffiliation)-[:IN_NETWORK]->(Organization)

(Location)-[:PART_OF]->(Location)
(Location)-[:HAS_ENDPOINT]->(Endpoint)

(HealthcareService)-[:PROVIDED_BY]->(Organization)
(HealthcareService)-[:AT_LOCATION]->(Location)
```

Plan Net network organizations use the normal `Organization` label. Network
membership is represented by `IN_NETWORK` relationships.

## Import Ordering Limitation

The scripts import resources in a dependency-aware order, but relationships are
created while each file is imported. If a reference points to a node that has
not yet been loaded, that relationship is not created automatically later.
Rerunning the safe importer after all nodes exist can fill many such missing
relationships. A dedicated relationship-reconciliation pass is not currently
implemented.

## Machine-Readable Directory Status

Machine-readable provider-directory JSON is part of the intended project
scope, but it is not currently importable. The repository presently provides:

- Detection of top-level JSON arrays as machine-readable input
- A reserved `mr_json` source-format value
- An `MRNormalizer` interface
- Deterministic key helpers for future locations and practitioner roles
- Primary-key and source-format schema groundwork

The current CLI reports and skips these files. `MRNormalizer.normalize()` must
be implemented before machine-readable records can be loaded.

## Verify and Explore

Count nodes by label and source:

```cypher
MATCH (directory_node)
RETURN labels(directory_node) AS node_type,
       directory_node.source_format AS source_format,
       count(directory_node) AS node_count
ORDER BY node_count DESC;
```

Find an individual practitioner by NPI:

```cypher
MATCH (practitioner:Practitioner {npi: "1234567890"})
OPTIONAL MATCH path = (practitioner)-[*1..2]-(connected_node)
RETURN path
LIMIT 100;
```

Find organizations containing an NPI:

```cypher
MATCH (organization:Organization)
WHERE "1234567890" IN organization.npis
RETURN organization.fhir_id, organization.name, organization.npis;
```

See [docs/CYPHER_QUERIES.md](docs/CYPHER_QUERIES.md) and
[typical_cypher_querys](typical_cypher_querys/) for more examples.

## Operations

```bash
# View logs
docker compose logs -f neo4j

# Stop Neo4j
docker compose down

# Destructively reset local data
docker compose down
rm -rf data/ logs/
docker compose up -d
```

Back up the local database only while Neo4j is stopped:

```bash
docker compose down
tar -czf "neo4j_backup_$(date +%Y%m%d).tar.gz" data/
docker compose up -d
```

## License

This repository is released under [CC0 1.0 Universal](LICENSE).