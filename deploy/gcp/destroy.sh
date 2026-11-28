#!/usr/bin/env bash
#
# Tear down a GCP deployment created by deploy/gcp/launch.sh (NPDV-528).
# Deletes the instance and its firewall rule.
#
#   deploy/gcp/destroy.sh [--name NAME]
#
set -euo pipefail

NAME="fhir-neo4j"
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="$SCRIPT_DIR/.state/$NAME"
[ -f "$STATE_FILE" ] || { echo "No state file for '$NAME' at $STATE_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
. "$STATE_FILE"

echo "Deleting instance $NAME in $ZONE ($PROJECT)..."
gcloud compute instances delete "$NAME" --project "$PROJECT" --zone "$ZONE" --quiet
echo "Deleting firewall rule ${NAME}-fw..."
gcloud compute firewall-rules delete "${NAME}-fw" --project "$PROJECT" --quiet || true
rm -f "$STATE_FILE"
echo "Done."
