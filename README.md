# FHIR Directory Neo4j

FHIR Directory Neo4j is an experimental toolkit for loading provider, payer,
network, and health-system directory data into a common Neo4j graph. The goal
is to support analysis across the major US healthcare directory formats rather
than tying the graph to a single publisher or exchange standard.

## Intended Data Sources

The project is intended to support:

- **NPD / NDH FHIR data:** National Provider Directory (NPD) work based on the
  FAST-backed HL7 [National Directory of Healthcare Providers & Services
  (NDH) Implementation Guide](https://build.fhir.org/ig/HL7/fhir-us-ndh/).
- **Payer Plan Net FHIR data:** payer provider directories represented using
  the HL7 Da Vinci
  [PDex Plan Net Implementation Guide](https://build.fhir.org/ig/HL7/davinci-pdex-plan-net/).
- **CMS machine-readable provider directories:** payer-published
  machine-readable JSON directory files.

## Current Status

This project is experimental/alpha. Support differs by source:

| Data source and format | Status |
| --- | --- |
| NDH/NPD FHIR NDJSON | Implemented |
| NDH/NPD FHIR Bundle JSON | Implemented |
| Da Vinci PDex Plan Net NDJSON | Implemented |
| Da Vinci PDex Plan Net Bundle JSON | Implemented |
| Recognized single-resource FHIR JSON | Implemented |
| CMS machine-readable JSON | Detection and schema groundwork only; import is not yet implemented |

Machine-readable JSON files are detected and reported, but are currently
skipped. The `MRNormalizer` interface and stable-key helpers are scaffolding
for the future normalizer.

## Supported FHIR Resources

- `Practitioner`
- `PractitionerRole`
- `Organization`
- `OrganizationAffiliation`
- `Location`
- `Endpoint`
- `HealthcareService`

Every imported FHIR node has a `primary_key`, `fhir_id`, `resource_type`, and
`source_format`. Recognized source-format values include `fhir_ndh`,
`fhir_plannet`, and `fhir_unknown`.

## Getting Started

Install the Python environment, download and start Neo4j, and apply the schema:

```bash
python3 download_install_neo4j_docker.py
```

The installer creates `.venv`, installs [requirements.txt](requirements.txt),
creates a secure `.env` when needed, starts the Docker service, waits for
Neo4j, and installs the graph schema. It preserves an existing `.env` and
database.

See [QUICKSTART.md](QUICKSTART.md) for setup and first-import instructions.
See [README_neo4j.md](README_neo4j.md) for the data model, file discovery,
import modes, and operational details.
See [DEPLOY.md](DEPLOY.md) to run it on a laptop or deploy it to AWS or Google
Cloud with your own credentials. `make help` lists the convenience commands
(`make install`, `make import`, `make check`, `make test`, `make smoke`,
`make deploy-aws`, `make deploy-gcp`).

For a source-derived import summary and repeatable InLaw sanity checks, run:

```bash
python import_and_check_fhir_directory.py --import-tag a_unique_source_tag
```

## License

This repository is released under [CC0 1.0 Universal](LICENSE).
