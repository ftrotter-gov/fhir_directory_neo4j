# Deployment Guide

FHIR Directory Neo4j is a self-contained, Dockerized graph browser for NPD / NDH
FHIR directory data. It runs the same way everywhere: a single Neo4j container,
a Python importer, and a Cypher schema. This guide covers three targets:

1. [Laptop (local)](#1-laptop-local) — the default; runs from one set of files.
2. [Amazon Web Services (EC2)](#2-amazon-web-services-ec2)
3. [Google Cloud (Compute Engine)](#3-google-cloud-compute-engine)

All three use the same bootstrap, so a graph that works on your laptop works
identically in the cloud.

```
            ┌─────────────────────────────────────────────┐
            │  host (laptop VM, EC2 instance, or GCE VM)    │
            │                                               │
  NDJSON ──▶│  python importer ──▶  Neo4j (Docker)  ◀── you │──▶ Browser :7474
  files     │                        + schema/indexes        │   Bolt    :7687
            └─────────────────────────────────────────────┘
```

Prerequisites everywhere: **Docker + Docker Compose** and **Python 3.9+**. The
cloud launchers install both for you.

---

## 1. Laptop (local)

One command creates a virtualenv, generates a random Neo4j password, starts
Neo4j in Docker, and applies the schema:

```bash
python3 download_install_neo4j_docker.py      # or: make install
```

Then open the Browser at <http://localhost:7474> (user `neo4j`; the password is
in the generated `.env`). Import a directory of FHIR NDJSON/JSON files:

```bash
make import DATA=/path/to/ndjson          # safe, idempotent (MERGE)
# or, for an empty database, the faster CREATE path:
make import-fast DATA=/path/to/ndjson
# or import + source-count reconciliation + InLaw sanity checks:
make check DATA=/path/to/ndjson
```

`make help` lists every target. See [QUICKSTART.md](QUICKSTART.md) for details.

### Prove it end-to-end (single set of files)

The repository ships a small Da Vinci Plan-Net sample under
`tests/fixtures/plannet/`. `make smoke` stands up an **isolated** instance on
ports **7475/7688** (so it never disturbs a database already on 7474/7687),
imports that sample, asserts the InsurancePlan and network relationships exist,
and tears itself down:

```bash
make smoke            # self-cleans
make smoke KEEP=1     # leave it running on http://localhost:7475 to explore
```

### Running more than one instance on a host

Container name, ports, memory, and data directories are all overridable in
`.env`, so a second instance can run beside the first:

```dotenv
NEO4J_CONTAINER_NAME=fhir_neo4j_second
NEO4J_HTTP_PORT=7476
NEO4J_BOLT_PORT=7689
NEO4J_DATA_DIR=./data-second
NEO4J_LOGS_DIR=./logs-second
NEO4J_IMPORT_DIR=./import-second
NEO4J_HEAP_MAX=4G
NEO4J_PAGECACHE=4G
```

---

## 2. Amazon Web Services (EC2)

Deploys a single EC2 instance that self-installs on first boot via
`deploy/startup.sh`. Uses **your** AWS credentials — nothing is hard-coded.

### Prerequisites
- AWS CLI v2, configured (`aws configure`, SSO, or env vars). Verify with
  `aws sts get-caller-identity`.
- IAM permission to create a security group and run an EC2 instance.
- A default VPC in the target region (the launcher uses it). To SSH, create/own
  an EC2 key pair and pass `--key-name`.

### Launch
```bash
deploy/aws/launch.sh                       # or: make deploy-aws
# common options:
deploy/aws/launch.sh \
  --region us-east-1 \
  --instance-type r6i.large \              # 16 GiB; size up for full data
  --disk-gb 50 \                           # raise to 200+ for the full NPD download
  --allow-cidr 203.0.113.4/32 \            # default: your current public IP /32
  --key-name my-keypair \                  # optional, enables SSH on :22
  --git-ref main \                         # branch/tag/sha to deploy
  --data-url https://example.com/state.tar.gz   # optional: auto-import on boot
```

The launcher creates a security group that exposes **7474/7687 only to
`--allow-cidr`** (your IP by default), finds the latest Ubuntu 22.04 AMI, boots
the instance, and prints the Browser URL. Self-install takes ~3–6 minutes.

### Get the password / watch progress
```bash
# password (needs --key-name, or use EC2 Instance Connect / SSM):
ssh ubuntu@<public-dns> 'sudo grep ^NEO4J_PASSWORD= /opt/fhir_directory_neo4j/.env'
# bootstrap log:
ssh ubuntu@<public-dns> 'sudo tail -f /var/log/fhir-neo4j-deploy.log'
```

### Tear down (deletes instance + security group)
```bash
deploy/aws/destroy.sh --name fhir-neo4j    # or: make destroy-aws
```

---

## 3. Google Cloud (Compute Engine)

Same model on a GCE VM, using **your** gcloud credentials and project.

### Prerequisites
- `gcloud` authenticated (`gcloud auth login`) with a project set
  (`gcloud config set project PROJECT`).
- Compute Engine API enabled; permission to create instances and firewall rules.

### Launch
```bash
deploy/gcp/launch.sh                        # or: make deploy-gcp
deploy/gcp/launch.sh \
  --project my-project \
  --zone us-central1-a \
  --machine-type e2-standard-4 \            # 16 GiB; size up for full data
  --disk-gb 50 \
  --allow-cidr 203.0.113.4/32 \
  --git-ref main \
  --data-url https://example.com/state.tar.gz
```

The launcher creates a firewall rule scoped to `--allow-cidr` (your IP by
default) and boots the VM. Get the password / watch progress:

```bash
gcloud compute ssh <name> --zone <zone> \
  --command 'sudo grep ^NEO4J_PASSWORD= /opt/fhir_directory_neo4j/.env'
gcloud compute ssh <name> --zone <zone> \
  --command 'sudo tail -f /var/log/fhir-neo4j-deploy.log'
```

### Tear down (deletes instance + firewall rule)
```bash
deploy/gcp/destroy.sh --name fhir-neo4j     # or: make destroy-gcp
```

---

## Getting data

- **NDH / NPD (official CMS bulk download):** <https://directory.cms.gov/downloads>.
  Files are named `NN-ResourceType.ndjson` (e.g. `01-Organization.ndjson`). The
  full set is large (~tens of GB raw); point `--disk-gb` and memory accordingly.
  The bulk files carry no `meta.profile`, so pass the importer's source-format
  override to tag them as NDH where available.
- **Da Vinci PDex Plan-Net:** payer-published directories, or the HL7 IG example
  set vendored under `tests/fixtures/plannet/` for a quick trial.

To auto-import on first boot, host a `.tar.gz` / `.zip` of NDJSON files at a URL
the instance can reach and pass `--data-url`. Otherwise SSH in afterward and run
`make import DATA=...`.

## Sizing (full NPD download)

| Target | Suggested |
| --- | --- |
| vCPU / RAM | 4 vCPU / 16–32 GiB (`r6i.large`/`r6i.xlarge`, `e2-standard-4/8`) |
| Disk | 200+ GB SSD (raw NDJSON + graph store + logs) |
| Neo4j memory | `NEO4J_HEAP_MAX` ≈ 50% RAM, `NEO4J_PAGECACHE` ≈ 30% RAM (the cloud bootstrap sets these automatically from instance RAM) |

A full ~6.4M-node NDH import completes in well under an hour on this class of
instance. Use `make import-fast` for the initial load into an empty database.

Neo4j caps a single transaction's memory at ~70% of heap, so running the
post-import InLaw sanity checks (`make check`) across the full dataset needs a
larger `NEO4J_HEAP_MAX` than the laptop default — the cloud bootstrap's
RAM-based sizing handles this; on a laptop, raise `NEO4J_HEAP_MAX` before
`make check` at full scale.

## Security

- Neo4j always requires authentication; the password is randomly generated per
  deployment and stored only in `.env` on the host.
- The launchers restrict 7474/7687 to your current IP (`--allow-cidr`). Widen it
  deliberately, never to `0.0.0.0/0` for anything sensitive.
- The Browser/Bolt ports are plaintext HTTP/Bolt. For anything beyond a personal
  trial, prefer an SSH tunnel (`ssh -L 7474:localhost:7474 ...`) or put the
  instance behind a VPN / load balancer with TLS instead of opening the ports.
- Treat all loaded data as the directory data it is — this tool is for public /
  directory FHIR data, not PII/PHI.

## Internal CMS note

The ticket also envisions an internal flavor that spins up automatically each
time a new NDJSON is exported from Foundry. That is a separate, credential-gated
deployment effort layered on top of this bootstrap and is intentionally out of
scope for this guide.
