#!/usr/bin/env bash
#
# Launch the FHIR Directory Neo4j browser on a single AWS EC2 instance (NPDV-528).
#
# Uses YOUR AWS credentials (whatever `aws sts get-caller-identity` resolves to).
# Creates a security group locked to your current public IP, finds the latest
# Ubuntu 22.04 AMI, and boots an instance that self-installs via deploy/startup.sh.
#
# Prerequisites: AWS CLI v2 configured (aws configure / SSO), permission to
# create security groups and run EC2 instances.
#
# Teardown: deploy/aws/destroy.sh [--name NAME]
#
set -euo pipefail

NAME="fhir-neo4j"
REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="r6i.large"      # 2 vCPU / 16 GiB (memory matters for Neo4j)
DISK_GB="50"                   # raise to 200+ for the full NPD download
ALLOW_CIDR=""                  # default: your current public IP /32
KEY_NAME=""                   # optional EC2 key pair for SSH (port 22)
REPO_URL="https://github.com/ftrotter-gov/fhir_directory_neo4j.git"
GIT_REF="main"
DATA_URL=""

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --instance-type) INSTANCE_TYPE="$2"; shift 2;;
    --disk-gb) DISK_GB="$2"; shift 2;;
    --allow-cidr) ALLOW_CIDR="$2"; shift 2;;
    --key-name) KEY_NAME="$2"; shift 2;;
    --repo-url) REPO_URL="$2"; shift 2;;
    --git-ref) GIT_REF="$2"; shift 2;;
    --data-url) DATA_URL="$2"; shift 2;;
    -h|--help) usage 0;;
    *) echo "Unknown arg: $1" >&2; usage 1;;
  esac
done

command -v aws >/dev/null || { echo "aws CLI not found" >&2; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STARTUP="$SCRIPT_DIR/../startup.sh"
[ -f "$STARTUP" ] || { echo "missing $STARTUP" >&2; exit 1; }

echo "AWS identity: $(aws sts get-caller-identity --query Arn --output text)"
if [ -z "$ALLOW_CIDR" ]; then
  myip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  ALLOW_CIDR="${myip}/32"
fi
echo "Region=$REGION  Type=$INSTANCE_TYPE  Disk=${DISK_GB}GB  AllowCIDR=$ALLOW_CIDR"

echo "Resolving latest Ubuntu 22.04 AMI..."
AMI_ID="$(aws ssm get-parameters --region "$REGION" \
  --names /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
  --query 'Parameters[0].Value' --output text)"
[ -n "$AMI_ID" ] && [ "$AMI_ID" != "None" ] || { echo "AMI lookup failed" >&2; exit 1; }
echo "AMI: $AMI_ID"

VPC_ID="$(aws ec2 describe-vpcs --region "$REGION" \
  --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
[ "$VPC_ID" != "None" ] || { echo "No default VPC; pass a subnet/SG manually." >&2; exit 1; }

SG_NAME="${NAME}-sg-$(date +%s)"
echo "Creating security group $SG_NAME in $VPC_ID"
SG_ID="$(aws ec2 create-security-group --region "$REGION" \
  --group-name "$SG_NAME" --description "FHIR Neo4j browser ($NAME)" \
  --vpc-id "$VPC_ID" --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
  --ip-permissions \
    "IpProtocol=tcp,FromPort=7474,ToPort=7474,IpRanges=[{CidrIp=$ALLOW_CIDR,Description=neo4j-http}]" \
    "IpProtocol=tcp,FromPort=7687,ToPort=7687,IpRanges=[{CidrIp=$ALLOW_CIDR,Description=neo4j-bolt}]" >/dev/null
if [ -n "$KEY_NAME" ]; then
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$ALLOW_CIDR,Description=ssh}]" >/dev/null
fi

# Build user-data: an exports preamble followed by the shared bootstrap script.
USERDATA="$(mktemp)"
{
  echo "#!/usr/bin/env bash"
  echo "export FHIR_REPO_URL=$(printf %q "$REPO_URL")"
  echo "export FHIR_GIT_REF=$(printf %q "$GIT_REF")"
  [ -n "$DATA_URL" ] && echo "export FHIR_DATA_URL=$(printf %q "$DATA_URL")"
  cat "$STARTUP"
} > "$USERDATA"

KEY_ARG=(); [ -n "$KEY_NAME" ] && KEY_ARG=(--key-name "$KEY_NAME")
echo "Launching instance..."
INSTANCE_ID="$(aws ec2 run-instances --region "$REGION" \
  --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
  --security-group-ids "$SG_ID" "${KEY_ARG[@]}" \
  --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$DISK_GB,VolumeType=gp3}" \
  --user-data "file://$USERDATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=project,Value=npdv528-fhir-neo4j}]" \
  --count 1 --query 'Instances[0].InstanceId' --output text)"
rm -f "$USERDATA"
echo "Instance: $INSTANCE_ID — waiting for running state..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
PUBLIC_DNS="$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicDnsName' --output text)"

STATE_DIR="$SCRIPT_DIR/.state"; mkdir -p "$STATE_DIR"
cat > "$STATE_DIR/$NAME" <<STATE
REGION=$REGION
INSTANCE_ID=$INSTANCE_ID
SG_ID=$SG_ID
STATE

cat <<DONE

================= deployed =================
Name:        $NAME
Instance:    $INSTANCE_ID   ($INSTANCE_TYPE, ${DISK_GB}GB)
Public DNS:  $PUBLIC_DNS
Neo4j Browser (ready in ~3-6 min while it self-installs):
   http://$PUBLIC_DNS:7474    (restricted to $ALLOW_CIDR)
   user: neo4j
Password:  generated on the box. Retrieve with SSH (needs --key-name):
   ssh ubuntu@$PUBLIC_DNS 'sudo grep ^NEO4J_PASSWORD= /opt/fhir_directory_neo4j/.env'
   (or EC2 Instance Connect / SSM Session Manager)
Bootstrap log on the box: /var/log/fhir-neo4j-deploy.log
Tear down:  deploy/aws/destroy.sh --name $NAME
============================================
DONE
