#!/usr/bin/env bash
#
# End-to-end laptop smoke test (NPDV-528).
#
# Brings up a fully ISOLATED Neo4j instance (its own container name, ports, and
# data directories), applies the schema, imports the vendored Da Vinci Plan-Net
# fixture set, and asserts the graph contains the expected nodes and the
# InsurancePlan / Plan-Net relationships. Never touches a default instance on
# 7474/7687, a user's .env, or ./data.
#
#   scripts/smoke_e2e.sh [--keep]
#
#     --keep   leave the smoke instance running afterwards (default: tear down)
#
set -euo pipefail

cd "$(dirname "$0")/.."              # repo root
# Defaults can be overridden (e.g. to run beside an instance already on 7475).
PROJECT="${SMOKE_PROJECT:-fhir-neo4j-smoke}"
CONTAINER="${SMOKE_CONTAINER:-fhir_neo4j_smoke}"
HTTP_PORT="${SMOKE_HTTP_PORT:-7475}"
BOLT_PORT="${SMOKE_BOLT_PORT:-7688}"
ENV_FILE="${SMOKE_ENV_FILE:-.env.smoke}"
FIXTURES="tests/fixtures/plannet"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

cleanup() {
  if [ "$KEEP" -eq 0 ]; then
    echo "--- tearing down smoke instance ---"
    docker compose --env-file "$ENV_FILE" -p "$PROJECT" down -v >/dev/null 2>&1 || true
    rm -rf .smoke "$ENV_FILE"
  else
    echo "--- leaving smoke instance running (http://localhost:$HTTP_PORT) ---"
  fi
}
trap cleanup EXIT

command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }

PASSWORD="$(python3 -c 'import secrets,string; a=string.ascii_letters+string.digits; print("".join(secrets.choice(a) for _ in range(32)))')"
umask 077
mkdir -p .smoke/data .smoke/logs .smoke/import
cat > "$ENV_FILE" <<ENV
NEO4J_AUTH=neo4j/${PASSWORD}
NEO4J_URI=bolt://localhost:${BOLT_PORT}
NEO4J_USER=neo4j
NEO4J_PASSWORD=${PASSWORD}
NEO4J_CONTAINER_NAME=${CONTAINER}
NEO4J_HTTP_PORT=${HTTP_PORT}
NEO4J_BOLT_PORT=${BOLT_PORT}
NEO4J_DATA_DIR=./.smoke/data
NEO4J_LOGS_DIR=./.smoke/logs
NEO4J_IMPORT_DIR=./.smoke/import
ENV

echo "--- starting isolated Neo4j ($CONTAINER on $HTTP_PORT/$BOLT_PORT) ---"
docker compose --env-file "$ENV_FILE" -p "$PROJECT" up -d neo4j

echo "--- waiting for health ---"
for _ in $(seq 1 60); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo missing)"
  [ "$status" = "healthy" ] && break
  case "$status" in exited|dead|unhealthy) echo "container state: $status" >&2; exit 1;; esac
  sleep 2
done
[ "$status" = "healthy" ] || { echo "Neo4j did not become healthy" >&2; exit 1; }

echo "--- applying schema ---"
docker exec -i "$CONTAINER" cypher-shell -u neo4j -p "$PASSWORD" < schema/indexes.cypher >/dev/null

# Choose a Python with the neo4j driver; build .venv if needed.
PYBIN=""
for cand in ./.venv/bin/python python3; do
  if "$cand" -c "import neo4j" >/dev/null 2>&1; then PYBIN="$cand"; break; fi
done
if [ -z "$PYBIN" ]; then
  echo "--- creating .venv and installing requirements ---"
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
  PYBIN="./.venv/bin/python"
fi

echo "--- importing Plan-Net fixtures ---"
NEO4J_URI="bolt://localhost:${BOLT_PORT}" NEO4J_USER=neo4j NEO4J_PASSWORD="$PASSWORD" \
  "$PYBIN" scripts/import_or_update_ndjson.py "$FIXTURES" --batch-size 1000 --import-tag smoke

echo "--- verifying graph ---"
q() { docker exec "$CONTAINER" cypher-shell -u neo4j -p "$PASSWORD" --format plain "$1" | tail -1; }
ins=$(q "MATCH (n:InsurancePlan) RETURN count(n);")
owned=$(q "MATCH (:InsurancePlan)-[r:OWNED_BY]->(:Organization) RETURN count(r);")
net=$(q "MATCH (:InsurancePlan)-[r:HAS_NETWORK]->(:Organization) RETURN count(r);")
innet=$(q "MATCH (:OrganizationAffiliation)-[r:IN_NETWORK]->(:Organization) RETURN count(r);")
plannet=$(q "MATCH (n) WHERE n.source_format='fhir_plannet' RETURN count(n);")

echo "InsurancePlan nodes=$ins  OWNED_BY=$owned  HAS_NETWORK=$net  IN_NETWORK=$innet  plannet_nodes=$plannet"
fail=0
[ "$ins" -ge 2 ]     || { echo "FAIL: expected >=2 InsurancePlan"; fail=1; }
[ "$owned" -ge 2 ]   || { echo "FAIL: expected >=2 OWNED_BY"; fail=1; }
[ "$net" -ge 1 ]     || { echo "FAIL: expected >=1 HAS_NETWORK"; fail=1; }
[ "$innet" -ge 1 ]   || { echo "FAIL: expected >=1 IN_NETWORK"; fail=1; }
[ "$plannet" -ge 40 ] || { echo "FAIL: expected >=40 fhir_plannet nodes"; fail=1; }
[ "$fail" -eq 0 ] || { echo "SMOKE FAILED"; exit 1; }

echo "SMOKE PASSED ✅"
