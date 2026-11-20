# AI Instructions

This directory holds the design and specification documents that guided the
construction of this repository's Neo4j import tooling. They are kept here so
the reasoning behind the graph data model stays with the code that implements
it.

## Provenance

The Neo4j tooling in this repository began as the `analysis_neo4j/`
subdirectory of the [`FHIRTableSaw`](https://github.com/ftrotter-gov/FHIRTableSaw)
repository and was later extracted into this standalone project. The two
documents below originated in `FHIRTableSaw/AI_Instructions/` and have been
carried over because the code here directly implements them.

Only the Neo4j-relevant instruction documents were brought across. Documents
that are specific to FHIRTableSaw's relational / SQL-on-FHIR pipeline,
reporting stack, or data-expectation framework were intentionally left behind.

## Contents

| Document | Status | Purpose |
| --- | --- | --- |
| [Neo4JAnalysis.md](Neo4JAnalysis.md) | Historical charter, largely realized | The original project plan: Docker approach, import scope, exact resource-type matching rules, and indexing requirements. Retargeted from the original subproject framing to this repository root. |
| [ImproveNeo4JModel.md](ImproveNeo4JModel.md) | Active specification, implemented | The property-level data model: coherent address objects, telecom separation, `{system, value}` identifier pairing, NPI cardinality by resource type, qualification parsing into specialties / degrees / licenses, non-English language capture, and Endpoint address classification with rank. |

## How These Relate to the Code

- **Exact resource-type matching** (`Neo4JAnalysis.md`) is implemented in
  `scripts/importers/discovery.py`. `OrganizationAffiliation` must never be
  matched as `Organization`, and `PractitionerRole` must never be matched as
  `Practitioner`.
- **Identifier and NPI indexing** (`Neo4JAnalysis.md`) is implemented in
  `schema/indexes.cypher`.
- **Node property shapes** (`ImproveNeo4JModel.md`) are implemented across
  `scripts/importers/base.py` and the per-resource importer modules.

## Reading Order

1. [Neo4JAnalysis.md](Neo4JAnalysis.md) for the overall project intent.
2. [ImproveNeo4JModel.md](ImproveNeo4JModel.md) for the detailed field mapping
   rules.
3. [../README_neo4j.md](../README_neo4j.md) for how the implementation actually
   behaves today, which supersedes both documents where they disagree.
