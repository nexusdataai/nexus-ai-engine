#!/bin/bash

# nexus-ai-engine — deploy (provision + build + push + apply).
#
# Provisions AWS resources (DynamoDB table + S3 buckets), builds the
# test-enabled container image, pushes it to ECR, applies the K8s manifests
# into namespace `ai-engine`, and waits for the pod rollout. Does NOT run
# tests — use ./test.sh (or the ./deploy-and-test.sh wrapper) for that.
#
# Prerequisites:
#   - aws CLI logged in (./aws-login.sh or ./aws-sso-login.sh)
#   - kubectl context pointing at the right cluster (./aws-eks-context.sh)
#   - docker (or podman with `alias docker=podman`)
#   - Admin has already run ./deploy/admin/setup-admin-role.sh once for
#     this cluster (creates the IAM role + VPC endpoints).

set -euo pipefail

# ── Directory dance (matches aws-login.sh / aws-eks-context.sh) ─────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ORIGINAL_DIR="$(pwd)"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
TMP_DIR="$(mktemp -d -t ai-engine-deploy-XXXXXX)"

cleanup_tmp() {
    rm -rf "$TMP_DIR"
    cd "$ORIGINAL_DIR"
}
trap cleanup_tmp EXIT

# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

load_env_files
set_defaults

SKIP_PROVISION=false
SKIP_BUILD=false
SKIP_PUSH=false
SKIP_APPLY=false
DO_CLEANUP=false
DO_CLEANUP_AWS=false

# ── Argument parsing ────────────────────────────────────────────────────
print_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Provision AWS resources, build + push the test image, apply K8s manifests,
and wait for the nexus-ai-engine rollout. Does NOT run tests.

Options:
  --env ENV                Target environment (default: dev)
  --region REGION          AWS region (default: \$AWS_REGION or us-east-1)
  --profile NAME           AWS CLI profile (default: \$AWS_PROFILE from .env.local or 'default')
  --cluster NAME           EKS cluster (default: from kubectl current-context)
  --namespace NS           K8s namespace (default: ai-engine)
  --ecr-registry URI       ECR registry URI (default: <account>.dkr.ecr.<region>.amazonaws.com)
  --image-tag TAG          Image tag (default: <git-sha>-test)
  --skip-provision         Don't create DDB / S3 resources
  --skip-build             Don't rebuild the image (use existing tag)
  --skip-push              Don't push to ECR
  --skip-apply             Don't (re)apply manifests
  --cleanup                Delete K8s resources after deploy
  --cleanup-aws            Also delete the DDB table and S3 buckets (interactive confirm)
  --dry-run                Print what would be done; make no changes
  --help

Examples:
  $0 --env dev --region us-east-1
  $0 --env dev --skip-build --skip-push   # re-apply manifests with current image
  $0 --env dev --cleanup                  # tear down K8s after a deploy
EOF
}

# deploy.sh silently accepts (and discards) the test-only flags so the
# deploy-and-test.sh wrapper can pass a shared argv through both scripts
# without each complaining about the other's options.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)            ENV="$2"; shift 2 ;;
        --region)         REGION="$2"; shift 2 ;;
        --profile)        AWS_PROFILE="$2"; shift 2 ;;
        --cluster)        CLUSTER_NAME="$2"; shift 2 ;;
        --namespace)      NAMESPACE="$2"; shift 2 ;;
        --ecr-registry)   ECR_REGISTRY="$2"; shift 2 ;;
        --image-tag)      IMAGE_TAG="$2"; shift 2 ;;
        --skip-provision) SKIP_PROVISION=true; shift ;;
        --skip-build)     SKIP_BUILD=true; shift ;;
        --skip-push)      SKIP_PUSH=true; shift ;;
        --skip-apply)     SKIP_APPLY=true; shift ;;
        --cleanup)        DO_CLEANUP=true; shift ;;
        --cleanup-aws)    DO_CLEANUP_AWS=true; shift ;;
        --dry-run)        DRY_RUN=true; shift ;;
        --help|-h)        print_help; exit 0 ;;
        # Test-only flags (ignored here; test.sh handles them).
        --tests)          shift 2 ;;
        --skip-tests)     shift ;;
        *) echo "Unknown parameter: $1"; echo "Run '$0 --help' for usage."; exit 1 ;;
    esac
done

# ── Prereq checks ───────────────────────────────────────────────────────
echo "🔍 Verifying prerequisites ..."
require_cmd aws
require_cmd kubectl
if [ "$SKIP_BUILD" != "true" ] || [ "$SKIP_PUSH" != "true" ]; then
    require_cmd docker
fi

setup_aws_context
derive_vars
print_common_banner
print_dry_run_note

# ────────────────────────────────────────────────────────────────────────
# 1. Provision AWS resources (idempotent)
# ────────────────────────────────────────────────────────────────────────
if [ "$SKIP_PROVISION" = "true" ]; then
    echo "⏭️   Skipping AWS resource provisioning (--skip-provision)"
else
    echo "🛠️   Provisioning AWS resources"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Resource-existence checks distinguish three cases:
    #   1. check succeeded       -> resource exists, skip create
    #   2. error is "not found"  -> resource absent, create
    #   3. any other error       -> can't verify (usually AccessDenied / a
    #      region redirect); assume it exists, warn, and SKIP create so we
    #      do not double-create or fail with BucketAlreadyOwnedByYou /
    #      ResourceInUseException.

    # DynamoDB
    DDB_ERR_FILE="$TMP_DIR/ddb-check.err"
    if aws dynamodb describe-table --table-name "$DDB_TABLE" --region "$REGION" \
            >/dev/null 2>"$DDB_ERR_FILE"; then
        echo "   ✅ DynamoDB table $DDB_TABLE: already exists"
    elif grep -q "ResourceNotFoundException" "$DDB_ERR_FILE" 2>/dev/null; then
        echo "   ➕ Creating DynamoDB table $DDB_TABLE ..."
        run "aws dynamodb create-table \
            --region '$REGION' \
            --table-name '$DDB_TABLE' \
            --attribute-definitions \
                AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S \
                AttributeName=GSI1PK,AttributeType=S AttributeName=GSI1SK,AttributeType=S \
            --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE \
            --global-secondary-indexes \
                'IndexName=GSI1,KeySchema=[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
            --billing-mode PAY_PER_REQUEST \
            --tags Key=Project,Value=nexus-ai-engine Key=Environment,Value='$ENV' \
            >/dev/null"
        run "aws dynamodb wait table-exists --table-name '$DDB_TABLE' --region '$REGION'"
        echo "   ✅ DynamoDB table $DDB_TABLE: created"
    else
        echo "   ⚠️   DynamoDB table $DDB_TABLE: cannot verify (skipping create)."
        echo "       describe-table said: $(tr -d '\n' < "$DDB_ERR_FILE" | head -c 300)"
        echo "       If the table truly does not exist, grant dynamodb:DescribeTable"
        echo "       and re-run, or create it manually and pass --skip-provision."
    fi
    rm -f "$DDB_ERR_FILE"

    # S3 buckets
    create_bucket() {
        local bucket="$1"
        local err_file="$TMP_DIR/s3-check.${bucket}.err"
        if aws s3api head-bucket --bucket "$bucket" --region "$REGION" \
                >/dev/null 2>"$err_file"; then
            echo "   ✅ S3 bucket $bucket: already exists"
            rm -f "$err_file"
            return 0
        fi
        # head-bucket returns HTTP 404 when the bucket does not exist and
        # HTTP 403 / a redirect when the caller cannot see it. Only 404 is
        # a green light to create.
        if grep -Eq '404|Not Found' "$err_file" 2>/dev/null; then
            echo "   ➕ Creating S3 bucket $bucket ..."
            if [ "$REGION" = "us-east-1" ]; then
                run "aws s3api create-bucket --bucket '$bucket' --region '$REGION' >/dev/null"
            else
                run "aws s3api create-bucket --bucket '$bucket' --region '$REGION' --create-bucket-configuration LocationConstraint='$REGION' >/dev/null"
            fi
            run "aws s3api put-public-access-block --bucket '$bucket' --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
            run "aws s3api put-bucket-encryption --bucket '$bucket' --server-side-encryption-configuration '{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}'"
            run "aws s3api put-bucket-tagging --bucket '$bucket' --tagging 'TagSet=[{Key=Project,Value=nexus-ai-engine},{Key=Environment,Value=${ENV}}]'"
            echo "   ✅ S3 bucket $bucket: created"
        else
            echo "   ⚠️   S3 bucket $bucket: cannot verify (skipping create)."
            echo "       head-bucket said: $(tr -d '\n' < "$err_file" | head -c 300)"
            echo "       If the bucket truly does not exist, grant s3:ListBucket"
            echo "       and re-run, or create it manually and pass --skip-provision."
        fi
        rm -f "$err_file"
    }
    create_bucket "$S3_LOGS"
    create_bucket "$S3_REPORTS"
    echo ""
fi

# ── ECR repo (idempotent) ───────────────────────────────────────────────
if [ "$SKIP_PUSH" != "true" ]; then
    if ! aws ecr describe-repositories --region "$REGION" --repository-names "$IMAGE_NAME" >/dev/null 2>&1; then
        echo "➕ Creating ECR repository $IMAGE_NAME ..."
        run "aws ecr create-repository --region '$REGION' --repository-name '$IMAGE_NAME' --image-scanning-configuration scanOnPush=true >/dev/null"
    fi
fi

# ────────────────────────────────────────────────────────────────────────
# 2. Build image (test variant)
# ────────────────────────────────────────────────────────────────────────
if [ "$SKIP_BUILD" = "true" ]; then
    echo "⏭️   Skipping docker build (--skip-build)"
else
    echo "🔨 Building image with INCLUDE_TEST_DEPS=true"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    run "docker build --build-arg INCLUDE_TEST_DEPS=true \
        -t '${IMAGE_NAME}:${IMAGE_TAG}' \
        -t '${IMAGE_NAME}:latest-test' \
        '$REPO_ROOT'"
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 3. Push to ECR
# ────────────────────────────────────────────────────────────────────────
if [ "$SKIP_PUSH" = "true" ]; then
    echo "⏭️   Skipping docker push (--skip-push)"
else
    echo "📤 Pushing image to ECR"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    run "aws ecr get-login-password --region '$REGION' | docker login --username AWS --password-stdin '$ECR_REGISTRY'"
    run "docker tag '${IMAGE_NAME}:${IMAGE_TAG}' '${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}'"
    run "docker tag '${IMAGE_NAME}:latest-test' '${ECR_REGISTRY}/${IMAGE_NAME}:latest-test'"
    run "docker push '${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}'"
    run "docker push '${ECR_REGISTRY}/${IMAGE_NAME}:latest-test'"
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 4. Apply K8s manifests
# ────────────────────────────────────────────────────────────────────────
if [ "$SKIP_APPLY" = "true" ]; then
    echo "⏭️   Skipping kubectl apply (--skip-apply)"
else
    echo "📋 Applying K8s manifests"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Verify the IAM role exists (admin must have run setup-admin-role.sh).
    if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
        echo "⚠️  IAM role '$ROLE_NAME' does not exist."
        echo "   The admin must run ./deploy/admin/setup-admin-role.sh once before deploying."
        echo "   Continuing anyway — the pod will fail to authenticate to AWS until the role exists."
    fi

    # Render manifests with substitutions
    cp "$REPO_ROOT"/deploy/k8s/*.yaml "$TMP_DIR/"
    sed -i.bak \
        -e "s|\${ENV}|${ENV}|g" \
        -e "s|\${REGION}|${REGION}|g" \
        -e "s|REPLACE_WITH_ECR_REGISTRY|${ECR_REGISTRY}|g" \
        -e "s|REPLACE_WITH_IAM_ROLE_ARN|${ROLE_ARN}|g" \
        "$TMP_DIR"/*.yaml
    rm -f "$TMP_DIR"/*.bak

    # Patch image tag for this run via a kustomize transform
    if [ -f "$TMP_DIR/kustomization.yaml" ]; then
        # Replace newTag: latest with the actual tag
        sed -i.bak -e "s|newTag: latest|newTag: ${IMAGE_TAG}|g" "$TMP_DIR/kustomization.yaml"
        rm -f "$TMP_DIR/kustomization.yaml.bak"
    fi

    run "kubectl apply -k '$TMP_DIR'"

    # Belt-and-braces: explicitly annotate the SA in case kustomize did not
    # carry the annotation through (older kubectl versions).
    run "kubectl annotate sa '$SERVICE_ACCOUNT' -n '$NAMESPACE' \
        eks.amazonaws.com/role-arn='${ROLE_ARN}' --overwrite"

    echo ""
    echo "⏳ Waiting for rollout ..."
    run "kubectl -n '$NAMESPACE' rollout status deploy/nexus-ai-engine --timeout=180s"
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 5. Cleanup (optional)
# ────────────────────────────────────────────────────────────────────────
if [ "$DO_CLEANUP" = "true" ]; then
    echo "🧹 Tearing down K8s resources"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ -d "$TMP_DIR" ] && [ -f "$TMP_DIR/kustomization.yaml" ]; then
        run "kubectl delete -k '$TMP_DIR' --ignore-not-found"
    else
        run "kubectl delete -n '$NAMESPACE' deploy,svc,hpa,cm,sa,networkpolicy -l app.kubernetes.io/name=nexus-ai-engine --ignore-not-found"
    fi
    echo ""
fi

if [ "$DO_CLEANUP_AWS" = "true" ]; then
    echo ""
    echo "🧹 Tearing down AWS resources for env=$ENV"
    if [ "$DRY_RUN" != "true" ]; then
        echo ""
        read -r -p "Type 'DELETE-${ENV}' to confirm DDB + S3 deletion: " CONFIRM
        if [ "$CONFIRM" != "DELETE-${ENV}" ]; then
            echo "   Aborted."
            exit 1
        fi
    fi
    run "aws dynamodb delete-table --region '$REGION' --table-name '$DDB_TABLE' >/dev/null 2>&1 || true"
    for B in "$S3_LOGS" "$S3_REPORTS"; do
        run "aws s3 rm 's3://${B}' --recursive --region '$REGION' >/dev/null 2>&1 || true"
        run "aws s3api delete-bucket --bucket '${B}' --region '$REGION' 2>/dev/null || true"
    done
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 6. Summary
# ────────────────────────────────────────────────────────────────────────
echo "🎯 Deploy complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "   Environment:  %s\n" "$ENV"
printf "   Region:       %s\n" "$REGION"
printf "   Cluster:      %s\n" "$CLUSTER_NAME"
printf "   Namespace:    %s\n" "$NAMESPACE"
printf "   Image:        %s/%s:%s\n" "$ECR_REGISTRY" "$IMAGE_NAME" "$IMAGE_TAG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deploy done. Run ./test.sh next to execute the test tiers."
