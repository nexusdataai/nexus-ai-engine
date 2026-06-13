#!/bin/bash

# nexus test-reports portal — one-shot publisher.
#
# Uploads deploy/portal/index.html to
#   s3://$S3_BUCKET_NAME/$S3_REPORTS_PREFIX/index.html
# and creates a CloudFront invalidation for /index.html so the next
# page-load shows the fresh portal.
#
# Run this ONLY when the portal HTML itself changes — component test
# runs (deploy/test.sh) write under their own $COMPONENT sub-prefix and
# do NOT touch the root portal.
#
# Prerequisites:
#   - aws CLI logged in
#   - deploy/.env.local populated with S3_BUCKET_NAME, S3_REPORTS_PREFIX,
#     S3_REPORTS_REGION, CLOUDFRONT_DISTRIBUTION_ID, CLOUDFRONT_DOMAIN

set -euo pipefail

PORTAL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEPLOY_DIR="$( cd "$PORTAL_DIR/.." && pwd )"
REPO_ROOT="$( cd "$DEPLOY_DIR/.." && pwd )"
ORIGINAL_DIR="$(pwd)"

cleanup() { cd "$ORIGINAL_DIR"; }
trap cleanup EXIT

# _common.sh expects SCRIPT_DIR + REPO_ROOT to be set to the deploy/
# folder + repo root before sourcing. Assign them as plain shell vars
# rather than via the inline-prefix syntax (which does not reliably
# propagate to `source` because source is a bash builtin, not an
# externally executed command).
SCRIPT_DIR="$DEPLOY_DIR"
# shellcheck source=../_common.sh
source "$DEPLOY_DIR/_common.sh"

load_env_files
set_defaults

DRY_RUN="${DRY_RUN:-false}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h)
            cat <<EOF
Usage: $0 [--dry-run]

Publishes deploy/portal/index.html to the shared CloudFront-fronted
S3 bucket as the root tabbed portal. Reads bucket/distribution config
from deploy/.env.local.
EOF
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

PORTAL_HTML="$PORTAL_DIR/index.html"
if [ ! -f "$PORTAL_HTML" ]; then
    echo "❌ Portal HTML not found at $PORTAL_HTML"
    exit 1
fi

missing=""
[ -z "${S3_BUCKET_NAME:-}" ]             && missing="$missing S3_BUCKET_NAME"
[ -z "${CLOUDFRONT_DISTRIBUTION_ID:-}" ] && missing="$missing CLOUDFRONT_DISTRIBUTION_ID"
[ -z "${CLOUDFRONT_DOMAIN:-}" ]          && missing="$missing CLOUDFRONT_DOMAIN"
if [ -n "$missing" ]; then
    echo "❌ Missing required env:$missing"
    echo "   Populate them in $DEPLOY_DIR/.env.local and retry."
    exit 1
fi

S3_REPORTS_PREFIX="${S3_REPORTS_PREFIX:-test-reports}"
S3_REPORTS_REGION="${S3_REPORTS_REGION:-us-east-1}"
S3_KEY="$S3_REPORTS_PREFIX/index.html"

echo "📤 Publishing tabbed portal"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Source:          $PORTAL_HTML"
echo "   Destination:     s3://$S3_BUCKET_NAME/$S3_KEY"
echo "   Region:          $S3_REPORTS_REGION"
echo "   CloudFront dist: $CLOUDFRONT_DISTRIBUTION_ID"
echo "   CloudFront host: $CLOUDFRONT_DOMAIN"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    echo "   ⚠️  DRY-RUN — skipping aws s3 cp + CloudFront invalidation"
    echo "🌐 Would publish to: https://$CLOUDFRONT_DOMAIN/index.html"
    exit 0
fi

aws s3 cp "$PORTAL_HTML" "s3://$S3_BUCKET_NAME/$S3_KEY" \
    --content-type "text/html; charset=utf-8" \
    --cache-control "no-cache" \
    --region "$S3_REPORTS_REGION" \
    >/dev/null

echo "🔄 Creating CloudFront invalidation for /index.html ..."
INVALIDATION_ID="$(aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
    --paths "/index.html" \
    --query 'Invalidation.Id' \
    --output text)"
echo "   Invalidation ID: $INVALIDATION_ID"

WAIT=0
MAX_WAIT=180
while true; do
    STATUS="$(aws cloudfront get-invalidation \
        --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
        --id "$INVALIDATION_ID" \
        --query 'Invalidation.Status' \
        --output text 2>/dev/null || echo InProgress)"
    if [ "$STATUS" = "Completed" ]; then
        echo "   ✅ Invalidation completed (${WAIT}s)"
        break
    fi
    if [ "$WAIT" -ge "$MAX_WAIT" ]; then
        echo "   ⚠️  Still $STATUS after ${MAX_WAIT}s — portal will be live shortly."
        break
    fi
    sleep 5
    WAIT=$((WAIT + 5))
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Portal: https://$CLOUDFRONT_DOMAIN/index.html"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
