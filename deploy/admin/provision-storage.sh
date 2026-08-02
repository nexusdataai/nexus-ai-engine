#!/usr/bin/env bash
# Provision Nexus AI Engine DynamoDB tables + S3 buckets (spec 050).
#
# Usage:
#   deploy/admin/provision-storage.sh <env> [region]
#
# Example:
#   deploy/admin/provision-storage.sh prod us-east-1
#
# Uses CloudFormation stack ai-engine-storage-{env}. Idempotent on re-run.

set -euo pipefail

ENV="${1:-}"
REGION="${2:-${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}}"
export AWS_PROFILE="${AWS_PROFILE:-external-access}"

if [[ -z "$ENV" ]]; then
  echo "Usage: $0 <env> [region]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/../cloudformation/ai-engine-storage.yaml"
STACK_NAME="ai-engine-storage-${ENV}"

echo "Verifying AWS credentials (profile=${AWS_PROFILE}, region=${REGION})..."
aws sts get-caller-identity --region "$REGION" --query Arn --output text

echo "Deploying stack ${STACK_NAME}..."
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --parameter-overrides "Environment=${ENV}" \
  --no-fail-on-empty-changeset \
  --tags "nexus:component=ai-engine" "nexus:environment=${ENV}"

echo
echo "Stack outputs:"
aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

echo
echo "Next: seed SSM parameters"
echo "  deploy/admin/seed-ssm-parameters.sh ${ENV} ${REGION}"
