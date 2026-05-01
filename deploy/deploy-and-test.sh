#!/bin/bash

# nexus-ai-engine — deploy + in-pod test runner
#
# Provisions AWS resources (DynamoDB table + S3 buckets), builds the
# test-enabled container image, pushes it to ECR, applies the K8s manifests
# into namespace `ai-engine`, waits for the pod to become ready, then runs
# every test tier inside the pod via `kubectl exec`.
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

# ── Source .env.local for AWS_PROFILE / AWS_REGION ──────────────────────
# Honor the same .env.local that aws-login.sh / aws-eks-context.sh use.
# Search order:
#   1. $REPO_ROOT/.env.local                (nexus-ai-engine repo, if present)
#   2. $REPO_ROOT/../nexus-backend/.env.local  (sibling nexus-backend repo)
# Anything already exported in the parent shell wins (set -o allexport only
# imports keys that are not already set).
for _envfile in "$REPO_ROOT/.env.local" "$REPO_ROOT/../nexus-backend/.env.local"; do
    if [ -f "$_envfile" ]; then
        set -o allexport
        # shellcheck disable=SC1090
        source "$_envfile"
        set +o allexport
        echo "📁 Loaded configuration from $_envfile"
        break
    fi
done

# ── Defaults ────────────────────────────────────────────────────────────
ENV="dev"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
AWS_PROFILE="${AWS_PROFILE:-default}"
CLUSTER_NAME=""
NAMESPACE="ai-engine"
SERVICE_ACCOUNT="ai-engine-role-sa"
ROLE_NAME="ai-engine-role"
IMAGE_NAME="nexus-ai-engine"
ECR_REGISTRY=""
IMAGE_TAG=""
ACCOUNT_ID=""

DEFAULT_TIERS="unit integration contract property e2e journeys bdd endurance"
TIERS=""

SKIP_PROVISION=false
SKIP_BUILD=false
SKIP_PUSH=false
SKIP_APPLY=false
DO_CLEANUP=false
DO_CLEANUP_AWS=false
DRY_RUN=false

# ── Argument parsing ────────────────────────────────────────────────────
print_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

End-to-end deploy + in-pod test runner for nexus-ai-engine.

Options:
  --env ENV                Target environment (default: dev)
  --region REGION          AWS region (default: \$AWS_REGION or us-east-1)
  --profile NAME           AWS CLI profile (default: \$AWS_PROFILE from .env.local or 'default')
  --cluster NAME           EKS cluster (default: from kubectl current-context)
  --namespace NS           K8s namespace (default: ai-engine)
  --ecr-registry URI       ECR registry URI (default: <account>.dkr.ecr.<region>.amazonaws.com)
  --image-tag TAG          Image tag (default: <git-sha>-test)
  --tests LIST             Comma- or space-separated test tiers
                           (default: $DEFAULT_TIERS)
                           Use 'none' to skip the in-pod test phase entirely.
  --skip-provision         Don't create DDB / S3 resources
  --skip-build             Don't rebuild the image (use existing tag)
  --skip-push              Don't push to ECR
  --skip-apply             Don't (re)apply manifests; just run tests against existing pod
  --cleanup                Delete K8s resources after tests
  --cleanup-aws            Also delete the DDB table and S3 buckets (interactive confirm)
  --dry-run                Print what would be done; make no changes
  --help

Examples:
  $0 --env dev --region us-east-1
  $0 --env stage --tests unit,e2e
  $0 --env dev --skip-tests
  $0 --env dev --skip-build --skip-push   # redeploy and re-run tests with current image
  $0 --env dev --cleanup                  # tear down K8s resources after tests
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)            ENV="$2"; shift 2 ;;
        --region)         REGION="$2"; shift 2 ;;
        --profile)        AWS_PROFILE="$2"; shift 2 ;;
        --cluster)        CLUSTER_NAME="$2"; shift 2 ;;
        --namespace)      NAMESPACE="$2"; shift 2 ;;
        --ecr-registry)   ECR_REGISTRY="$2"; shift 2 ;;
        --image-tag)      IMAGE_TAG="$2"; shift 2 ;;
        --tests)          TIERS="$2"; shift 2 ;;
        --skip-tests)     TIERS="none"; shift ;;
        --skip-provision) SKIP_PROVISION=true; shift ;;
        --skip-build)     SKIP_BUILD=true; shift ;;
        --skip-push)      SKIP_PUSH=true; shift ;;
        --skip-apply)     SKIP_APPLY=true; shift ;;
        --cleanup)        DO_CLEANUP=true; shift ;;
        --cleanup-aws)    DO_CLEANUP_AWS=true; shift ;;
        --dry-run)        DRY_RUN=true; shift ;;
        --help|-h)        print_help; exit 0 ;;
        *) echo "Unknown parameter: $1"; echo "Run '$0 --help' for usage."; exit 1 ;;
    esac
done

# Normalize TIERS (support comma- or space-separated)
if [ -z "$TIERS" ]; then
    TIERS="$DEFAULT_TIERS"
fi
TIERS="${TIERS//,/ }"

# ── Helpers ─────────────────────────────────────────────────────────────
run() {
    if [ "$DRY_RUN" = "true" ]; then
        echo "    DRY-RUN: $*"
    else
        eval "$@"
    fi
}

require_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ Required command not found on PATH: $1"
        exit 1
    fi
}

# ── Prereq checks ───────────────────────────────────────────────────────
echo "🔍 Verifying prerequisites ..."
require_cmd aws
require_cmd kubectl
if [ "$SKIP_BUILD" != "true" ] || [ "$SKIP_PUSH" != "true" ]; then
    require_cmd docker
fi

# Export AWS_PROFILE so all aws / kubectl child processes inherit it.
# AWS CLI honors AWS_PROFILE env var when --profile is not passed; this
# avoids threading --profile through every aws call below.
export AWS_PROFILE
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

echo "   AWS profile:  $AWS_PROFILE"
echo "   AWS region:   $REGION"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "❌ AWS credentials are missing or expired for profile '$AWS_PROFILE'."
    echo ""
    echo "   Log in first:"
    echo "     ./aws-login.sh                # ADFS login"
    echo "     ./aws-sso-login.sh            # SSO login"
    echo ""
    echo "   Or pass an explicit profile:  $0 --profile <name> ..."
    exit 1
fi

if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME=$(kubectl config current-context 2>/dev/null || true)
    if [ -z "$CLUSTER_NAME" ]; then
        echo "❌ No kubectl context. Run ./aws-eks-context.sh or pass --cluster <name>."
        exit 1
    fi
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

if [ -z "$ECR_REGISTRY" ]; then
    ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
fi

if [ -z "$IMAGE_TAG" ]; then
    GIT_SHA=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "local")
    IMAGE_TAG="${GIT_SHA}-test"
fi

DDB_TABLE="ai-engine-journeys-${ENV}"
S3_LOGS="ai-engine-journeys-logs-${ENV}"
S3_REPORTS="ai-engine-journeys-reports-${ENV}"

cat <<EOF
   Environment:    $ENV
   Region:         $REGION
   Account:        $ACCOUNT_ID
   Cluster:        $CLUSTER_NAME
   Namespace:      $NAMESPACE
   ServiceAccount: $SERVICE_ACCOUNT  -> $ROLE_ARN
   ECR registry:   $ECR_REGISTRY
   Image:          ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
   DDB table:      $DDB_TABLE
   S3 logs:        $S3_LOGS
   S3 reports:     $S3_REPORTS
   Test tiers:     $TIERS
EOF

if [ "$DRY_RUN" = "true" ]; then
    echo "   ⚠️  DRY-RUN — no AWS / kubectl / docker changes will be made."
fi
echo ""

# ────────────────────────────────────────────────────────────────────────
# CLEANUP MODE (early exit if --cleanup-aws and no other action requested)
# Runs late, after the deploy/test phases below, but cleanup-only invocations
# still need to behave well.
# ────────────────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────────────────
# 1. Provision AWS resources (idempotent)
# ────────────────────────────────────────────────────────────────────────
if [ "$SKIP_PROVISION" = "true" ]; then
    echo "⏭️   Skipping AWS resource provisioning (--skip-provision)"
else
    echo "🛠️   Provisioning AWS resources"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # DynamoDB
    if aws dynamodb describe-table --table-name "$DDB_TABLE" --region "$REGION" >/dev/null 2>&1; then
        echo "   ✅ DynamoDB table $DDB_TABLE: already exists"
    else
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
    fi

    # S3 buckets
    create_bucket() {
        local bucket="$1"
        if aws s3api head-bucket --bucket "$bucket" --region "$REGION" >/dev/null 2>&1; then
            echo "   ✅ S3 bucket $bucket: already exists"
            return 0
        fi
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
# 5. In-pod tests
# ────────────────────────────────────────────────────────────────────────
declare -A RESULTS
declare -A DURATIONS
TESTS_FAILED=0
TESTS_TOTAL=0

if [ "$TIERS" = "none" ]; then
    echo "⏭️   Skipping in-pod tests (--skip-tests / --tests=none)"
else
    echo "🧪 Running in-pod tests"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    POD=""
    if [ "$DRY_RUN" != "true" ]; then
        POD=$(kubectl -n "$NAMESPACE" get pod -l app.kubernetes.io/name=nexus-ai-engine \
              -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
        if [ -z "$POD" ]; then
            echo "❌ No nexus-ai-engine pod found in namespace $NAMESPACE."
            exit 1
        fi
        echo "   Target pod: $POD"
    fi
    echo ""

    mkdir -p "$REPO_ROOT/reports"

    for TIER in $TIERS; do
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        echo "▶️   tier: ${TIER}"
        START=$(date +%s)
        STATUS="PASS"
        if [ "$DRY_RUN" = "true" ]; then
            echo "    DRY-RUN: kubectl -n $NAMESPACE exec -i \$POD -- make test-${TIER}"
        else
            if kubectl -n "$NAMESPACE" exec -i "$POD" -- make "test-${TIER}"; then
                STATUS="PASS"
            else
                STATUS="FAIL"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
        fi
        END=$(date +%s)
        RESULTS[$TIER]=$STATUS
        DURATIONS[$TIER]=$((END - START))
        echo "    [$STATUS] ${TIER}  (${DURATIONS[$TIER]}s)"
        echo ""

        # Pull BDD HTML report off the pod
        if [ "$TIER" = "bdd" ] && [ "$DRY_RUN" != "true" ] && [ "$STATUS" = "PASS" ]; then
            kubectl -n "$NAMESPACE" cp "${POD}:/app/reports/bdd.html" \
                "$REPO_ROOT/reports/bdd-${ENV}.html" 2>/dev/null || true
        fi
    done

    echo "🧪 In-pod test results"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    for TIER in $TIERS; do
        printf "   %-13s %-5s %4ss\n" "$TIER" "${RESULTS[$TIER]:-?}" "${DURATIONS[$TIER]:-0}"
    done
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    PASSED=$((TESTS_TOTAL - TESTS_FAILED))
    echo "   Total: ${PASSED}/${TESTS_TOTAL} passed"
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# 6. Cleanup (optional)
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
# 7. Final summary
# ────────────────────────────────────────────────────────────────────────
echo "🎯 Deploy complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "   Environment:  %s\n" "$ENV"
printf "   Region:       %s\n" "$REGION"
printf "   Cluster:      %s\n" "$CLUSTER_NAME"
printf "   Namespace:    %s\n" "$NAMESPACE"
printf "   Image:        %s/%s:%s\n" "$ECR_REGISTRY" "$IMAGE_NAME" "$IMAGE_TAG"
if [ "$TIERS" != "none" ]; then
    printf "   Tests:        %d/%d passed\n" "$((TESTS_TOTAL - TESTS_FAILED))" "$TESTS_TOTAL"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$TESTS_FAILED" -gt 0 ]; then
    echo "❌ One or more test tiers failed."
    exit 1
fi

echo "✅ Done!"
