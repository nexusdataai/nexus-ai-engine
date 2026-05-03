# shellcheck shell=bash
# =============================================================================
# _common.sh  —  shared preamble for deploy.sh / test.sh / deploy-and-test.sh.
#
# This file is SOURCED, not executed. Callers must:
#   1. Set `set -euo pipefail`
#   2. Export SCRIPT_DIR and REPO_ROOT before sourcing.
#   3. Create a TMP_DIR (mktemp -d ...) and trap its cleanup.
#   4. Call, in order:
#         load_env_files
#         set_defaults
#         <parse CLI args>
#         require_prereqs <cmds...>   # or call require_cmd individually
#         setup_aws_context
#         derive_vars
#         print_common_banner         # optional
#
# Keeping all of this in one file ensures deploy.sh, test.sh, and the thin
# deploy-and-test.sh wrapper behave identically around env-loading, AWS
# profile selection, and derived-variable defaults.
# =============================================================================

# Guard against double-sourcing.
if [ -n "${_NEXUS_AI_ENGINE_COMMON_LOADED:-}" ]; then
    return 0 2>/dev/null || true
fi
_NEXUS_AI_ENGINE_COMMON_LOADED=1

: "${SCRIPT_DIR:?SCRIPT_DIR must be set by the sourcing script}"
: "${REPO_ROOT:?REPO_ROOT must be set by the sourcing script}"

# ── .env.local loader ────────────────────────────────────────────────────
# deploy/.env.local (next to this file) carries S3 bucket + CloudFront
# coordinates used by test.sh's upload step. It is ALWAYS sourced when
# present.
#
# For AWS credentials / region we keep the original "first match wins"
# lookup so existing callers that rely on nexus-backend/.env.local are
# unaffected:
#   1. $REPO_ROOT/.env.local                   (nexus-ai-engine repo, if present)
#   2. $REPO_ROOT/../nexus-backend/.env.local  (sibling nexus-backend repo)
load_env_files() {
    if [ -f "$SCRIPT_DIR/.env.local" ]; then
        set -o allexport
        # shellcheck disable=SC1090
        source "$SCRIPT_DIR/.env.local"
        set +o allexport
        echo "📁 Loaded configuration from $SCRIPT_DIR/.env.local"
    fi
    local _envfile
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
}

# ── Default variable values ──────────────────────────────────────────────
# Safe to call before OR after the caller's arg parsing: uses `:=` so it
# only fills in blanks. In practice scripts call set_defaults BEFORE arg
# parsing so the parser can override, then setup_aws_context / derive_vars
# AFTER parsing to resolve anything the parser left empty.
set_defaults() {
    : "${ENV:=dev}"
    : "${REGION:=${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}}"
    : "${AWS_PROFILE:=default}"
    : "${CLUSTER_NAME:=}"
    : "${NAMESPACE:=ai-engine}"
    : "${SERVICE_ACCOUNT:=ai-engine-role-sa}"
    : "${ROLE_NAME:=ai-engine-role}"
    : "${IMAGE_NAME:=nexus-ai-engine}"
    : "${ECR_REGISTRY:=}"
    : "${IMAGE_TAG:=}"
    : "${ACCOUNT_ID:=}"
    : "${DRY_RUN:=false}"
}

# ── Helpers ──────────────────────────────────────────────────────────────
# DRY_RUN-aware command runner. `eval "$@"` is intentional: callers pass a
# single quoted string with embedded redirections / pipelines.
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

# ── AWS context setup ────────────────────────────────────────────────────
# Exports AWS_PROFILE / AWS_REGION / AWS_DEFAULT_REGION, drops stale
# AWS_ACCESS_KEY_* env vars that would otherwise override the profile,
# verifies the caller can call sts:GetCallerIdentity, and resolves
# CLUSTER_NAME from kubectl's current-context if not already set.
setup_aws_context() {
    export AWS_PROFILE
    export AWS_REGION="$REGION"
    export AWS_DEFAULT_REGION="$REGION"

    # AWS SDK credential precedence puts AWS_ACCESS_KEY_ID /
    # AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN env vars ABOVE AWS_PROFILE.
    # If the caller's shell has stale credentials from a previous session,
    # they silently override the profile and you get "security token
    # included in the request is invalid" even though
    # `aws sts get-caller-identity --profile <name>` works by hand.
    # When we have a profile to use, drop those env vars so the profile wins.
    if [ -n "$AWS_PROFILE" ]; then
        local var
        for var in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN; do
            if [ -n "${!var:-}" ]; then
                echo "   🧹 Unsetting stale $var (would override profile '$AWS_PROFILE')"
                unset "$var"
            fi
        done
    fi

    echo "   AWS profile:  $AWS_PROFILE"
    echo "   AWS region:   $REGION"

    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo "❌ AWS credentials are missing or expired for profile '$AWS_PROFILE'."
        echo ""
        echo "   Log in first:"
        echo "     ./aws-login.sh                # ADFS login"
        echo "     ./aws-sso-login.sh            # SSO login"
        echo ""
        echo "   Or pass an explicit profile:  --profile <name> ..."
        exit 1
    fi

    if [ -z "$CLUSTER_NAME" ]; then
        CLUSTER_NAME=$(kubectl config current-context 2>/dev/null || true)
        if [ -z "$CLUSTER_NAME" ]; then
            echo "❌ No kubectl context. Run ./aws-eks-context.sh or pass --cluster <name>."
            exit 1
        fi
    fi
}

# ── Derived variables ────────────────────────────────────────────────────
# Computes ACCOUNT_ID, ROLE_ARN, ECR_REGISTRY, IMAGE_TAG, DDB_TABLE,
# S3_LOGS, S3_REPORTS from the environment variables above. Call AFTER
# setup_aws_context (needs AWS_PROFILE / REGION to be correct).
derive_vars() {
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

    if [ -z "$ECR_REGISTRY" ]; then
        ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
    fi

    if [ -z "$IMAGE_TAG" ]; then
        local git_sha
        git_sha=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "local")
        IMAGE_TAG="${git_sha}-test"
    fi

    DDB_TABLE="ai-engine-journeys-${ENV}"
    S3_LOGS="ai-engine-journeys-logs-${ENV}"
    S3_REPORTS="ai-engine-journeys-reports-${ENV}"
}

# ── Info banner ──────────────────────────────────────────────────────────
# Prints the common "what am I about to do" banner. Each script prints its
# own script-specific lines (e.g. test.sh adds "Test tiers:") either right
# after this or inline.
print_common_banner() {
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
EOF
}

# Marks a DRY-RUN warning line if applicable. Scripts call this after all
# their banner lines have been printed.
print_dry_run_note() {
    if [ "$DRY_RUN" = "true" ]; then
        echo "   ⚠️  DRY-RUN — no AWS / kubectl / docker changes will be made."
    fi
    echo ""
}
