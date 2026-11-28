#!/usr/bin/env bash
#
# Tear down an AWS deployment created by deploy/aws/launch.sh (NPDV-528).
# Terminates the instance and deletes its security group.
#
#   deploy/aws/destroy.sh [--name NAME]
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

echo "Terminating instance $INSTANCE_ID in $REGION..."
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"
echo "Deleting security group $SG_ID..."
# Retry briefly: the SG can stay 'in use' for a moment after termination.
for _ in 1 2 3 4 5; do
  if aws ec2 delete-security-group --region "$REGION" --group-id "$SG_ID" 2>/dev/null; then
    break
  fi
  sleep 10
done
rm -f "$STATE_FILE"
echo "Done."
