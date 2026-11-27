# FHIR Directory Neo4j — convenience wrapper (NPDV-528)
#
# Local:  make install   -> venv + Neo4j in Docker + schema
#         make import DATA=/path/to/ndjson
#         make check DATA=/path/to/ndjson     (import + InLaw sanity checks)
#         make test                           (unit tests)
#         make smoke                          (isolated end-to-end on 7475/7688)
# Cloud:  make deploy-aws ARGS="--region us-east-1"
#         make deploy-gcp ARGS="--project my-proj --zone us-central1-a"
#         make destroy-aws / make destroy-gcp
#
# See DEPLOY.md for the full guide.

SHELL := /bin/bash
PY    := $(shell [ -x ./.venv/bin/python ] && echo ./.venv/bin/python || echo python3)
DATA  ?=
ARGS  ?=

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Create venv, start Neo4j in Docker, apply schema
	python3 download_install_neo4j_docker.py

.PHONY: up
up: ## Start the Neo4j container (uses .env)
	docker compose --env-file .env up -d neo4j

.PHONY: down
down: ## Stop the Neo4j container
	docker compose --env-file .env down

.PHONY: logs
logs: ## Follow Neo4j logs
	docker compose logs -f neo4j

.PHONY: ps
ps: ## Show compose service status
	docker compose ps

.PHONY: schema
schema: ## Apply schema/indexes.cypher to the running container
	set -a; source .env; set +a; \
	docker exec -i "$${NEO4J_CONTAINER_NAME:-fhir_neo4j_analysis}" \
	  cypher-shell -u "$$NEO4J_USER" -p "$$NEO4J_PASSWORD" < schema/indexes.cypher

.PHONY: import
import: ## Safe idempotent import (DATA=/path, or FHIR_DIRECTORY_PATH in .env)
	$(PY) scripts/import_or_update_ndjson.py $(DATA) --batch-size 5000

.PHONY: import-fast
import-fast: ## Fast CREATE import for an EMPTY database (DATA=/path)
	$(PY) scripts/import_ndjson_fast.py $(DATA) --batch-size 10000

.PHONY: check
check: ## Import with source counts + InLaw sanity checks (DATA=/path)
	$(PY) import_and_check_fhir_directory.py $(if $(DATA),$(DATA),) --import-tag make_check

.PHONY: test
test: ## Run the unit test suite
	PYTHONPATH="$(CURDIR)" $(PY) -m unittest discover -s tests -p 'test_*.py'

.PHONY: smoke
smoke: ## Isolated end-to-end smoke on 7475/7688 (self-tears-down; add KEEP=1 to keep)
	scripts/smoke_e2e.sh $(if $(KEEP),--keep,)

.PHONY: deploy-aws
deploy-aws: ## Launch on AWS EC2 (ARGS="--region ... --instance-type ...")
	deploy/aws/launch.sh $(ARGS)

.PHONY: destroy-aws
destroy-aws: ## Tear down the AWS deployment (ARGS="--name ...")
	deploy/aws/destroy.sh $(ARGS)

.PHONY: deploy-gcp
deploy-gcp: ## Launch on GCP Compute Engine (ARGS="--project ... --zone ...")
	deploy/gcp/launch.sh $(ARGS)

.PHONY: destroy-gcp
destroy-gcp: ## Tear down the GCP deployment (ARGS="--name ...")
	deploy/gcp/destroy.sh $(ARGS)

.PHONY: clean
clean: ## Stop containers and delete local database data (destructive)
	docker compose --env-file .env down -v || true
	rm -rf data logs .smoke .env.smoke
