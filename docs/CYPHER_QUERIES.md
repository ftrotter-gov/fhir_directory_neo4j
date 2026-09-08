# Cypher Queries for Directory Graph Analysis

These examples match the current graph properties and relationships. Nested
FHIR structures—including `identifiers`, Practitioner and Organization
`addresses`, Location `address`, and Practitioner `licenses`—are stored as JSON
strings. Parse those values in application code when precise nested filtering
is required.

## Basic Verification

### Count nodes by type and source

```cypher
MATCH (directory_node)
RETURN labels(directory_node) AS node_type,
       directory_node.source_format AS source_format,
       count(directory_node) AS node_count
ORDER BY node_count DESC;
```

Typical `source_format` values are `fhir_ndh`, `fhir_plannet`, and
`fhir_unknown`. The `mr_json` value is reserved for machine-readable directory
import, which is not yet implemented.

### Count relationships

```cypher
MATCH ()-[directory_relationship]->()
RETURN type(directory_relationship) AS relationship_type,
       count(directory_relationship) AS relationship_count
ORDER BY relationship_count DESC;
```

### Find records missing a universal primary key

```cypher
MATCH (directory_node)
WHERE directory_node.primary_key IS NULL
RETURN labels(directory_node) AS node_type,
       directory_node.fhir_id AS fhir_id
LIMIT 100;
```

## NPI Queries

Practitioners have a scalar `npi`; organizations can have an `npis` array.

### Find a practitioner by NPI

```cypher
MATCH (practitioner:Practitioner {npi: "1234567890"})
RETURN practitioner.fhir_id,
       practitioner.name,
       practitioner.source_format;
```

### Find an organization by NPI

```cypher
MATCH (organization:Organization)
WHERE "1234567890" IN organization.npis
RETURN organization.fhir_id,
       organization.name,
       organization.npis,
       organization.source_format;
```

### Search both practitioner and organization NPIs

```cypher
MATCH (directory_node)
WHERE directory_node.npi = "1234567890"
   OR "1234567890" IN directory_node.npis
RETURN labels(directory_node), directory_node;
```

## Practitioner and Network Queries

### Show a practitioner's working network

```cypher
MATCH (practitioner:Practitioner {npi: "1234567890"})
OPTIONAL MATCH (practitioner)-[:HAS_ROLE]->(role:PractitionerRole)
OPTIONAL MATCH (role)-[:WORKS_AT]->(organization:Organization)
OPTIONAL MATCH (role)-[:AT_LOCATION]->(location:Location)
OPTIONAL MATCH (role)-[:IN_NETWORK]->(network:Organization)
RETURN practitioner, role, organization, location, network;
```

### Find Plan Net roles accepting new patients

```cypher
MATCH (practitioner:Practitioner)-[:HAS_ROLE]->(role:PractitionerRole)
WHERE role.source_format = "fhir_plannet"
  AND role.accepting_patients = "newpt"
OPTIONAL MATCH (role)-[:IN_NETWORK]->(network:Organization)
RETURN practitioner.name,
       practitioner.npi,
       role.specialties,
       network.name
LIMIT 100;
```

### Find practitioners in a payer network

```cypher
MATCH (practitioner:Practitioner)-[:HAS_ROLE]->(role:PractitionerRole)
      -[:IN_NETWORK]->(network:Organization)
WHERE network.name CONTAINS "Network Name"
RETURN practitioner.name,
       practitioner.npi,
       role.specialties,
       network.name
LIMIT 100;
```

### Find practitioners by specialty

```cypher
MATCH (practitioner:Practitioner)
WHERE "207Q00000X" IN practitioner.specialties
RETURN practitioner.name,
       practitioner.npi,
       practitioner.specialties
LIMIT 100;
```

## Organization Queries

### Search by organization name

```cypher
MATCH (organization:Organization)
WHERE organization.name CONTAINS "Hospital"
RETURN organization.name,
       organization.npis,
       organization.source_format
LIMIT 100;
```

### Show organization hierarchy

```cypher
MATCH hierarchy = (child:Organization)-[:PART_OF*1..5]->(parent:Organization)
RETURN child.name,
       parent.name,
       length(hierarchy) AS hierarchy_depth
ORDER BY hierarchy_depth, child.name
LIMIT 100;
```

### Show organization affiliations and networks

```cypher
MATCH (primary_organization:Organization)
      -[:HAS_AFFILIATION]->(affiliation:OrganizationAffiliation)
OPTIONAL MATCH (affiliation)-[:AFFILIATED_WITH]->(participating_organization:Organization)
OPTIONAL MATCH (affiliation)-[:IN_NETWORK]->(network:Organization)
RETURN primary_organization.name,
       affiliation.codes,
       participating_organization.name,
       network.name
LIMIT 100;
```

## HealthcareService Queries

### Find services provided by organizations

```cypher
MATCH (service:HealthcareService)-[:PROVIDED_BY]->(organization:Organization)
RETURN organization.name,
       service.categories,
       service.specialties,
       service.phones
LIMIT 100;
```

### Find services and their locations

```cypher
MATCH (service:HealthcareService)-[:AT_LOCATION]->(location:Location)
RETURN service.categories,
       service.specialties,
       location.name,
       location.address
LIMIT 100;
```

## Endpoint Queries

### Search FHIR and Direct endpoints by domain

```cypher
MATCH (endpoint:Endpoint)
WHERE endpoint.FHIR_address CONTAINS "example.com"
   OR endpoint.Direct_address CONTAINS "example.com"
RETURN endpoint.fhir_id,
       endpoint.FHIR_address,
       endpoint.Direct_address,
       endpoint.rank;
```

### Find ranked practitioner endpoints

```cypher
MATCH (practitioner:Practitioner)-[relationship:HAS_ENDPOINT]->(endpoint:Endpoint)
WHERE practitioner.npi = "1234567890"
RETURN practitioner.name,
       endpoint.FHIR_address,
       endpoint.Direct_address,
       relationship.rank
ORDER BY relationship.rank;
```

## Geographic Exploration

Addresses are JSON strings. The following `CONTAINS` checks are convenient for
interactive exploration but are not a substitute for parsing JSON in an
application or promoting frequently queried fields to first-class properties.

### Find practitioners with a serialized state value

```cypher
MATCH (practitioner:Practitioner)
WHERE practitioner.addresses CONTAINS '"state": "WY"'
RETURN practitioner.name, practitioner.npi, practitioner.addresses
LIMIT 100;
```

### Find roles at locations with a serialized state value

```cypher
MATCH (practitioner:Practitioner)-[:HAS_ROLE]->(role:PractitionerRole)
      -[:AT_LOCATION]->(location:Location)
WHERE location.address CONTAINS '"state": "WY"'
RETURN practitioner.name, practitioner.npi, location.name, location.address
LIMIT 100;
```

### Find locations with coordinates

```cypher
MATCH (location:Location)
WHERE location.latitude IS NOT NULL
  AND location.longitude IS NOT NULL
RETURN location.name,
       location.address,
       location.latitude,
       location.longitude
LIMIT 100;
```

## Data Quality Queries

### Find roles without practitioner relationships

```cypher
MATCH (role:PractitionerRole)
WHERE NOT EXISTS((role)<-[:HAS_ROLE]-(:Practitioner))
RETURN role.fhir_id, role.practitioner_reference
LIMIT 100;
```

### Find unresolved organization affiliations

```cypher
MATCH (affiliation:OrganizationAffiliation)
WHERE NOT EXISTS((affiliation)<-[:HAS_AFFILIATION]-(:Organization))
   OR NOT EXISTS((affiliation)-[:AFFILIATED_WITH]->(:Organization))
RETURN affiliation.fhir_id,
       affiliation.organization_reference,
       affiliation.participating_organization_reference
LIMIT 100;
```

### Count disconnected nodes by label

```cypher
MATCH (directory_node)
WHERE NOT (directory_node)--()
RETURN labels(directory_node) AS node_type,
       count(directory_node) AS disconnected_count
ORDER BY disconnected_count DESC;
```

## Query Optimization

- Apply [schema/indexes.cypher](../schema/indexes.cypher) before importing.
- Filter by indexed labels and properties early.
- Use `EXPLAIN` or `PROFILE` when tuning a query.
- Use `LIMIT` while exploring paths.
- Parse serialized JSON outside Neo4j for reliable nested-field logic.