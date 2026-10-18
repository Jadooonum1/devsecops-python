#!/usr/bin/env bash
# Run the real terraform/ code against the moto AWS emulator (no AWS account,
# no cost). A git-ignored *_override.tf points the AWS provider at moto; the
# .tf files themselves are untouched, so the same code applies to real AWS.
#
#   ./emulator/run.sh plan | apply | destroy | down
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=5050            # macOS AirPlay already listens on 5000
NAME=shelflend-moto
OVERRIDE=emulator_override.tf

start_moto() {
  if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --name "$NAME" -p "$PORT:5000" \
      -e MOTO_IAM_LOAD_MANAGED_POLICIES=true motoserver/moto:5.1.22 >/dev/null
  fi
  for _ in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/moto-api/" >/dev/null && break; sleep 1; done
}

write_override() {
  cat > "$OVERRIDE" <<HCL
provider "aws" {
  region                      = "ap-south-1"
  access_key                  = "moto"
  secret_key                  = "moto"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true
  endpoints {
    ec2 = "http://127.0.0.1:$PORT"
    eks = "http://127.0.0.1:$PORT"
    iam = "http://127.0.0.1:$PORT"
    sts = "http://127.0.0.1:$PORT"
  }
}
HCL
}

export TF_DATA_DIR=.terraform-emulator TF_VAR_api_allowed_cidrs='["0.0.0.0/0"]'
case "${1:-plan}" in
  plan)    start_moto; write_override; terraform init -input=false -upgrade=false >/dev/null
           terraform plan -state=emulator.tfstate -out=emulator.tfplan ;;
  apply)   start_moto; write_override; terraform apply -state=emulator.tfstate emulator.tfplan ;;
  destroy) start_moto; write_override; terraform destroy -state=emulator.tfstate -auto-approve ;;
  down)    docker rm -f "$NAME"; rm -f "$OVERRIDE" emulator.tfplan ;;
  *) echo "usage: $0 plan|apply|destroy|down" >&2; exit 2 ;;
esac
