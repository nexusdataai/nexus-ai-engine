#!/bin/bash

# nexus-ai-engine SSM Parameter Seeder
#
# Populates AWS SSM Parameter Store with the EngineConfig values the pod's
# `nexus-ai-engine serve --ssm-prefix /ai-engine/${ENV}/` command reads at
# startup. Run once per environment by an admin who has
# ssm:PutParameter on /ai-engine/* (the IAM policy in
# deploy/iam/ai-engine-policy.json grants this to the ai-engine-role).
#
# Naming convention:
#   /ai-engine/{env}/dynamodb_transformation_table  →  ai-engine-journeys-{env}
#   /ai-engine/{env}/dynamodb_executions_table      →  ai-engine-executions-{env}
#   /ai-engine/{env}/dynamodb_prompts_table         →  ai-engine-prompts-{env}
#   /ai-engine/{env}/s3_journey_logs_bucket         →  ai-engine-journey-logs-{env}
#   /ai-engine/{env}/s3_journey_reports_bucket      →  ai-engine-journey-reports-{env}
#
# After seeding, the pod can be deployed with `kubectl apply -k deploy/k8s/`
# and will resolve its EngineConfig automatically. Override per-key by
# setting the matching DYNAMODB_* / S3_* env var on the Deployment.
#
# Usage:
#   deploy/admin/seed-ssm-parameters.sh <env> [region]
# Example:
#   deploy/admin/seed-ssm-parameters.sh dev us-east-1
#
# AWS profile defaults to `ptr-tech` (Skyvera SSO profile). Override by
# exporting AWS_PROFILE before invoking, e.g.:
#   AWS_PROFILE=other-profile deploy/admin/seed-ssm-parameters.sh dev

set -euo pipefail

ENV="${1:-}"
REGION="${2:-${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}}"
# Default to the ptr-tech SSO profile so engineers don't have to remember to
# export it every time. Honor an explicit AWS_PROFILE override from the
# caller's environment.
export AWS_PROFILE="${AWS_PROFILE:-ptr-tech}"

if [[ -z "$ENV" ]]; then
    echo "Usage: $0 <env> [region]" >&2
    echo "  env should match the EKS namespace suffix (e.g. dev, staging, prod)." >&2
    exit 2
fi

PREFIX="/ai-engine/${ENV}/"

# ── Preflight: confirm credentials work BEFORE touching SSM ────────────
# Without this we'd fail one PutParameter call at a time and leave the
# operator guessing at the cause (UnrecognizedClientException is opaque).
echo "Verifying AWS credentials (profile=${AWS_PROFILE}, region=${REGION})..."
if ! caller=$(aws sts get-caller-identity --region "$REGION" --output text --query 'Arn' 2>&1); then
    cat <<EOF >&2

ERROR: AWS credentials are missing, expired, or invalid.

  aws sts get-caller-identity output:
    ${caller}

  Common fixes (current profile: ${AWS_PROFILE}):
    * SSO not logged in:   aws sso login --profile ${AWS_PROFILE}
    * Wrong profile:       AWS_PROFILE=<other-profile> $0 ${ENV} ${REGION}
    * Static keys:         export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...
    * Wrong region:        re-run with the correct region as arg 2 (current: ${REGION})
    * EC2/EKS instance:    ensure IRSA / instance role is attached and has sts:GetCallerIdentity

  Then re-run:
    $0 ${ENV} ${REGION}

EOF
    exit 3
fi
echo "  authenticated as: ${caller}"

declare -A PARAMS=(
    [dynamodb_transformation_table]="ai-engine-journeys-${ENV}"
    [dynamodb_executions_table]="ai-engine-executions-${ENV}"
    [dynamodb_prompts_table]="ai-engine-prompts-${ENV}"
    [s3_journey_logs_bucket]="ai-engine-journey-logs-${ENV}"
    [s3_journey_reports_bucket]="ai-engine-journey-reports-${ENV}"
    [environment]="${ENV}"
    [max_concurrent_jobs]="10"
    [capability_name]="call-processing"
)

echo "Seeding SSM parameters under ${PREFIX} in region ${REGION}..."

for key in "${!PARAMS[@]}"; do
    value="${PARAMS[$key]}"
    name="${PREFIX}${key}"
    echo "  put ${name} = ${value}"
    aws ssm put-parameter \
        --region "$REGION" \
        --name "$name" \
        --value "$value" \
        --type "String" \
        --overwrite >/dev/null
done

echo
echo "Done. Verify with:"
echo "  aws ssm get-parameters-by-path --region ${REGION} --path ${PREFIX} --recursive --query 'Parameters[].[Name,Value]' --output table"
