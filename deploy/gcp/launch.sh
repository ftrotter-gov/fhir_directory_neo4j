#!/usr/bin/env bash
#
# Launch the FHIR Directory Neo4j browser on a single GCP Compute Engine VM (NPDV-528).
#
# Uses YOUR gcloud credentials and project. Creates a firewall rule locked to
# your current public IP and boots an Ubuntu 22.04 VM that self-installs via
# deploy/startup.sh.
#
# Prerequisites: gcloud CLI authenticated (gcloud auth login) with a project set
# (gcloud config set project PROJECT), Compute Engine API enabled, permission to
# create instances and firewall rules.
#
# Teardown: deploy/gcp/destroy.sh [--name NAME]
#
set -euo pipefail

NAME="fhir-neo4j"
PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
ZONE="us-central1-a"
MACHINE_TYPE="e2-standard-4"   # 4 vCPU / 16 GiB
DISK_GB="50"                   # raise to 200+ for the full NPD download
ALLOW_CIDR=""                  # default: your current public IP /32
REPO_URL="https://github.com/ftrotter-gov/fhir_directory_neo4j.git"
GIT_REF="main"
DATA_URL=""

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --project) PROJECT="$2"; shift 2;;
    --zone) ZONE="$2"; shift 2;;
    --machine-type) MACHINE_TYPE="$2"; shift 2;;
    --disk-gb) DISK_GB="$2"; shift 2;;
    --allow-cidr) ALLOW_CIDR="$2"; shift 2;;
    --repo-url) REPO_URL="$2"; shift 2;;
    --git-ref) GIT_REF="$2"; shift 2;;
    --data-url) DATA_URL="$2"; shift 2;;
    -h|--help) usage 0;;
    *) echo "Unknown arg: $1" >&2; usage 1;;
  esac
done

command -v gcloud >/dev/null || { echo "gcloud CLI not found" >&2; exit 1; }
[ -n "$PROJECT" ] || { echo "No project set (gcloud config set project ... or --project)" >&2; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STARTUP="$SCRIPT_DIR/../startup.sh"
[ -f "$STARTUP" ] || { echo "missing $STARTUP" >&2; exit 1; }

if [ -z "$ALLOW_CIDR" ]; then
  myip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  ALLOW_CIDR="${myip}/32"
fi
TAG="${NAME}-neo4j"
echo "Project=$PROJECT  Zone=$ZONE  Type=$MACHINE_TYPE  Disk=${DISK_GB}GB  AllowCIDR=$ALLOW_CIDR"

echo "Creating firewall rule ${NAME}-fw (tag $TAG)..."
gcloud compute firewall-rules create "${NAME}-fw" \
  --project "$PROJECT" --direction INGRESS --action ALLOW \
  --rules tcp:7474,tcp:7687 --source-ranges "$ALLOW_CIDR" --target-tags "$TAG" >/dev/null

# Build the startup-script: exports preamble + shared bootstrap.
STARTUP_FILE="$(mktemp)"
{
  echo "#!/usr/bin/env bash"
  echo "export FHIR_REPO_URL=$(printf %q "$REPO_URL")"
  echo "export FHIR_GIT_REF=$(printf %q "$GIT_REF")"
  [ -n "$DATA_URL" ] && echo "export FHIR_DATA_URL=$(printf %q "$DATA_URL")"
  cat "$STARTUP"
} > "$STARTUP_FILE"

echo "Creating instance $NAME..."
gcloud compute instances create "$NAME" \
  --project "$PROJECT" --zone "$ZONE" --machine-type "$MACHINE_TYPE" \
  --image-family ubuntu-2204-lts --image-project ubuntu-os-cloud \
  --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced \
  --tags "$TAG" \
  --metadata-from-file "startup-script=$STARTUP_FILE" >/dev/null
rm -f "$STARTUP_FILE"

EXTERNAL_IP="$(gcloud compute instances describe "$NAME" --project "$PROJECT" --zone "$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"

STATE_DIR="$SCRIPT_DIR/.state"; mkdir -p "$STATE_DIR"
cat > "$STATE_DIR/$NAME" <<STATE
PROJECT=$PROJECT
ZONE=$ZONE
NAME=$NAME
STATE

cat <<DONE

================= deployed =================
Name:        $NAME   ($MACHINE_TYPE, ${DISK_GB}GB)
External IP: $EXTERNAL_IP
Neo4j Browser (ready in ~3-6 min while it self-installs):
   http://$EXTERNAL_IP:7474   (restricted to $ALLOW_CIDR)
   user: neo4j
Password:  generated on the box. Retrieve with:
   gcloud compute ssh $NAME --project $PROJECT --zone $ZONE \\
     --command 'sudo grep ^NEO4J_PASSWORD= /opt/fhir_directory_neo4j/.env'
Bootstrap log on the box: /var/log/fhir-neo4j-deploy.log
Tear down:  deploy/gcp/destroy.sh --name $NAME
============================================
DONE
