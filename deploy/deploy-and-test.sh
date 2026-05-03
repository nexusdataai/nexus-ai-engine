#!/bin/bash

# nexus-ai-engine — deploy + test orchestrator (thin wrapper).
#
# Runs ./deploy.sh first, then ./test.sh with the same arguments. Provided
# for backward compatibility with callers that previously ran the combined
# script; new code should prefer calling deploy.sh and test.sh directly
# (you can deploy once and then re-run tests against the same pod without
# re-building the image).
#
# Both sub-scripts accept the full superset of flags and silently discard
# the ones that don't apply to them, so passing "$@" through to both is safe.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

print_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Thin orchestrator that runs ./deploy.sh then ./test.sh with the same
arguments. See ./deploy.sh --help and ./test.sh --help for the full flag
reference.

Common options (accepted by both phases):
  --env ENV                Target environment (default: dev)
  --region REGION          AWS region
  --profile NAME           AWS CLI profile
  --cluster NAME           EKS cluster
  --namespace NS           K8s namespace
  --ecr-registry URI       ECR registry URI
  --image-tag TAG          Image tag
  --dry-run                Print what would be done; make no changes
  --help

Deploy-phase options:
  --skip-provision / --skip-build / --skip-push / --skip-apply
  --cleanup / --cleanup-aws

Test-phase options:
  --tests LIST             Comma- or space-separated test tiers
  --skip-tests             Skip the in-pod test phase

Examples:
  $0 --env dev --region us-east-1
  $0 --env dev --skip-build --skip-push --tests unit,e2e
  $0 --env dev --skip-tests                # deploy only
  ./deploy.sh --env dev                    # deploy only (preferred)
  ./test.sh --env dev --tests unit         # test only (preferred)
EOF
}

case "${1:-}" in
    --help|-h) print_help; exit 0 ;;
esac

echo "▶ Phase 1 of 2: deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/deploy.sh" "$@"
echo ""
echo "▶ Phase 2 of 2: test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/test.sh" "$@"
