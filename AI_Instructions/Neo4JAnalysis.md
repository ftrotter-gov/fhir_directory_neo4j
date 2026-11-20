# Development Plan for the Neo4j FHIR Directory Graph

> **Historical origin.** This plan was originally written as
> `AI_Instructions/Neo4JAnalysis.md` in the `FHIRTableSaw` repository, where it
> specified a self-contained `analysis_neo4j/` subproject. That subproject was
> later extracted into this standalone `fhir_directory_neo4j` repository. The
> text below has been retargeted to the repository root. Sections describing
> the original subdirectory layout have been updated; the design intent is
> unchanged.

## Purpose

Create a self-contained Neo4j analysis project for FHIR healthcare directory
data.

The goal is to keep all Neo4j-specific Docker, schema, and import logic in one
place, so the graph tooling can be operated, versioned, and reasoned about
independently of any upstream FHIR extraction pipeline.

---

## Basic Structure

The work lives at the root of this repository and contains:

- standard Neo4j Docker configuration (`docker-compose.yml`,
  `download_install_neo4j_docker.py`)
- import scripts (`scripts/`, `scripts/importers/`)
- Cypher schema and index definitions (`schema/indexes.cypher`)
- a README explaining startup, import, and reset steps (`README.md`,
  `QUICKSTART.md`, `README_neo4j.md`)
- representative example queries (`typical_cypher_querys/`, `docs/`)

This is a standalone repository. It does not require a parent `FHIRTableSaw`
checkout or Python environment.

---

## Docker Approach

Reuse the standard Neo4j Docker setup as much as possible.

That means:

- use the official Neo4j Docker image
- use Docker Compose rather than a heavily customized container
- mount the normal Neo4j data, logs, and import directories
- avoid custom Docker builds unless they become strictly necessary

The intent is to keep the deployment close to vanilla Neo4j so it is easy to understand, reproduce, and maintain.

---

## Import Scope

The project should include import scripts for NDH-compatible FHIR NDJSON resources for:

- Practitioner
- PractitionerRole
- Organization
- OrganizationAffiliation
- Endpoint
- Location

> **Scope since extraction.** `HealthcareService` has since been added as a
> seventh supported resource type. Supported input shapes have also broadened
> beyond NDH NDJSON to include NDH Bundle JSON, Da Vinci PDex Plan Net NDJSON
> and Bundle JSON, and recognized single-resource FHIR JSON. CMS
> machine-readable JSON is detected and reported but is not yet imported.
> Every imported node carries `primary_key`, `fhir_id`, `resource_type`, and
> `source_format`. See `README.md` for the current support matrix.

The scripts should scan a given directory and detect files based on exact resource-type filename prefixes.

Important matching rules:

- OrganizationAffiliation.ndjson must not be treated as Organization
- PractitionerRole.ndjson must not be treated as Practitioner

So matching should be exact by full resource type name, not loose prefix matching.

---

## LLM-Guided Script Generation

Before building the import scripts, the LLM should inspect the source data.

Instruction:

- for each supported resource type, read the first 10 lines of the corresponding NDJSON file in the given directory
- use those sample lines to understand the actual field structure
- then generate or refine the import logic based on what is actually present in the files

This should be done separately for:

- Practitioner
- PractitionerRole
- Organization
- OrganizationAffiliation
- Endpoint
- Location

The purpose is to ensure the import logic reflects the real NDJSON structure instead of relying only on assumptions about generic FHIR.

---

## Import Behavior

The import scripts should:

- locate the supported NDJSON files in a given directory
- parse them one JSON object per line
- create or merge nodes for each resource
- preserve core FHIR identity and reference information
- create relationships where FHIR references are available and useful

At minimum, the import should preserve:

- FHIR resource id
- identifier system and value pairs
- NPI values where present
- major cross-resource references

The scripts should be written so they can be rerun safely without creating uncontrolled duplication.

---

## Indexing Requirements

There should be indexes on:

- all FHIR identifiers
- all NPIs

That includes:

- resource-level FHIR ids
- identifier values and systems
- NPI values wherever they appear in the imported resources

The schema should make identifier lookup efficient both for general FHIR identifier searches and for NPI-specific searches.

---

## Development Phases

### Phase 1: Project setup

- establish the project layout
- add standard Neo4j Docker Compose files
- confirm local startup and persistence

### Phase 2: Source inspection

- identify the NDJSON files by exact resource type
- read the first 10 lines for each resource file
- use that inspection to design the import mappings

### Phase 3: Import implementation

- build import scripts for the six supported resource types
- ensure exact filename matching
- load nodes and core relationships

### Phase 4: Schema and indexing

- add constraints and indexes
- index all FHIR identifiers
- index all NPIs

### Phase 5: Validation

- confirm that OrganizationAffiliation is not misclassified as Organization
- confirm that PractitionerRole is not misclassified as Practitioner
- confirm identifiers and NPIs are queryable and indexed
- verify imports can be rerun safely

---

## Summary

This plan creates a Neo4j project that:

- stays self-contained and independently operable
- reuses standard Neo4j Docker as much as possible
- imports NDH-compatible FHIR NDJSON resources
- uses exact resource-type matching to avoid false imports
- instructs the LLM to read the first 10 lines of each NDJSON resource file before generating import logic
- adds indexes for all FHIR identifiers and all NPIs

## Related Documents

- [ImproveNeo4JModel.md](ImproveNeo4JModel.md) - the property-level data model
  refinement that followed this plan.
- [../IMPROVEMENTS_SUMMARY.md](../IMPROVEMENTS_SUMMARY.md) - historical record
  of how that model was implemented.
- [../README_neo4j.md](../README_neo4j.md) - current data model, file
  discovery, and import behavior.
