#!/bin/bash

# nexus-ai-engine Admin Setup
#
# Creates the IAM role and VPC endpoints required for the nexus-ai-engine pod
# to run in a private EKS cluster.
#
# Creates:
#   - IAM role:  ai-engine-role
#   - IAM inline policy:  ai-engine-policy
#   - 14 region-templated VPC endpoints (gateway + interface)
#
# The Kubernetes ServiceAccount system:serviceaccount:ai-engine:ai-engine-role-sa
# can assume this role via IRSA. The deploy script (deploy-and-test.sh) creates
# the namespace and ServiceAccount and annotates it with the role ARN.
#
# Run by an AWS administrator with IAM + EC2 + EKS write permissions.
# Idempotent: safe to re-run; existing resources are detected and skipped or
# updated in place.

set -euo pipefail

# ── Directory dance (matches aws-login.sh / aws-eks-context.sh) ─────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ORIGINAL_DIR="$(pwd)"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
IAM_DIR="$REPO_ROOT/deploy/iam"
TMP_DIR="$(mktemp -d -t ai-engine-admin-XXXXXX)"

cleanup_tmp() {
    rm -rf "$TMP_DIR"
    cd "$ORIGINAL_DIR"
}
trap cleanup_tmp EXIT

# ── Source .env.local for AWS_PROFILE / AWS_REGION ──────────────────────
# Honor the same .env.local that aws-login.sh / aws-eks-context.sh use.
# Search order:
#   1. $REPO_ROOT/.env.local                     (nexus-ai-engine repo, if present)
#   2. $REPO_ROOT/../nexus-backend/.env.local    (sibling nexus-backend repo)
# Anything already exported in the parent shell wins.
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
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

# ── Configuration / defaults ────────────────────────────────────────────
ROLE_NAME="ai-engine-role"
POLICY_NAME="ai-engine-policy"
NAMESPACE="ai-engine"
SERVICE_ACCOUNT="ai-engine-role-sa"

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
AWS_PROFILE="${AWS_PROFILE:-default}"
CLUSTER_NAME=""
ACCOUNT_ID=""
OIDC_PROVIDER=""
VPC_ID=""
SUBNET_IDS=""
SG_ID=""
ROUTE_TABLE_IDS=""

DO_IAM=true
DO_VPC=true
DRY_RUN=false
CLEANUP=false

# ── Endpoint catalog ────────────────────────────────────────────────────
# Gateway endpoints attach to private route tables (free).
GATEWAY_SVCS=(s3 dynamodb)

# Interface endpoints attach to private subnets + cluster SG (paid).
INTERFACE_SVCS=(
    ec2
    sts
    ssm
    glue
    ecr.api
    ecr.dkr
    secretsmanager
    logs
    cognito-idp
    athena
    events
    eks
)

# Logged + skipped — these are not real VPC endpoint services.
SKIP_SVCS=(iam)

# ── Argument parsing ────────────────────────────────────────────────────
print_help() {
    cat <<EOF
Usage: $0 [OPTIONS]

Creates the ai-engine-role IAM role and (by default) the regional VPC endpoints
required for the nexus-ai-engine pod to run in a private EKS cluster.

Run as an AWS administrator with IAM + EC2 + EKS write permissions.

Options:
  --region REGION          AWS region (default: \$AWS_REGION or us-east-1)
  --profile NAME           AWS CLI profile (default: \$AWS_PROFILE from .env.local or 'default')
  --cluster NAME           EKS cluster name (default: from kubectl current-context)
  --account-id ID          AWS account ID (default: aws sts get-caller-identity)
  --oidc-provider URL      OIDC provider, no https:// prefix (default: from cluster)
  --vpc-id ID              VPC id for endpoints (default: from cluster)
  --subnet-ids LIST        Comma-separated subnet ids for interface endpoints
                           (default: cluster's private subnets)
  --sg-id ID               Security group for interface endpoints
                           (default: cluster security group)
  --route-table-ids LIST   Route tables for gateway endpoints
                           (default: route tables of the supplied subnets)
  --iam-only               Skip VPC endpoint creation
  --vpc-only               Skip IAM role creation
  --dry-run                Print the AWS commands; do not execute
  --cleanup                Reverse: delete role + policy + endpoints
                           (production targets require interactive confirm)
  --help                   Show this help

Environment variables:
  AWS_REGION / AWS_DEFAULT_REGION   Default region

Examples:
  $0 --region ap-southeast-1
  $0 --region ap-southeast-1 --iam-only
  $0 --region us-east-1 --vpc-only
  $0 --region ap-southeast-1 --dry-run
  $0 --region ap-southeast-1 --cleanup
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --region)            REGION="$2"; shift 2 ;;
        --profile)           AWS_PROFILE="$2"; shift 2 ;;
        --cluster)           CLUSTER_NAME="$2"; shift 2 ;;
        --account-id)        ACCOUNT_ID="$2"; shift 2 ;;
        --oidc-provider)     OIDC_PROVIDER="$2"; shift 2 ;;
        --vpc-id)            VPC_ID="$2"; shift 2 ;;
        --subnet-ids)        SUBNET_IDS="$2"; shift 2 ;;
        --sg-id)             SG_ID="$2"; shift 2 ;;
        --route-table-ids)   ROUTE_TABLE_IDS="$2"; shift 2 ;;
        --iam-only)          DO_VPC=false; shift ;;
        --vpc-only)          DO_IAM=false; shift ;;
        --dry-run)           DRY_RUN=true; shift ;;
        --cleanup)           CLEANUP=true; shift ;;
        --help|-h)           print_help; exit 0 ;;
        *) echo "Unknown parameter: $1"; echo "Run '$0 --help' for usage."; exit 1 ;;
    esac
done

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

if [ "$DO_VPC" = "true" ] || [ -z "$CLUSTER_NAME" ]; then
    require_cmd kubectl
fi

# Export AWS_PROFILE / AWS_REGION so all aws / kubectl child processes
# inherit them. AWS CLI honors AWS_PROFILE when --profile is not passed.
export AWS_PROFILE
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

# AWS SDK credential precedence puts AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
# / AWS_SESSION_TOKEN env vars ABOVE AWS_PROFILE. If the caller's shell has
# stale credentials from a previous session, they silently override the
# profile and you get "security token included in the request is invalid"
# even though `aws sts get-caller-identity --profile <name>` works by hand.
# When we have a profile to use, drop those env vars so the profile wins.
if [ -n "$AWS_PROFILE" ]; then
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
    echo "   Or pass an explicit profile:  $0 --profile <name> ..."
    exit 1
fi

# ── Auto-detect missing values ──────────────────────────────────────────
if [ -z "$ACCOUNT_ID" ]; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

if [ -z "$CLUSTER_NAME" ]; then
    # Derive from current kubectl context (which aws-eks-context.sh aliases to the cluster name)
    CLUSTER_NAME=$(kubectl config current-context 2>/dev/null || true)
    if [ -z "$CLUSTER_NAME" ]; then
        echo "❌ --cluster not provided and no current kubectl context."
        echo "   Run aws-eks-context.sh first or pass --cluster <name>."
        exit 1
    fi
fi

echo "   Region:        $REGION"
echo "   Account:       $ACCOUNT_ID"
echo "   Cluster:       $CLUSTER_NAME"

if [ "$DO_IAM" = "true" ] || [ -z "$OIDC_PROVIDER" ] || [ "$DO_VPC" = "true" ]; then
    if ! CLUSTER_DESC=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" --output json 2>&1); then
        echo "❌ Could not describe EKS cluster '$CLUSTER_NAME' in $REGION:"
        echo "$CLUSTER_DESC"
        exit 1
    fi

    if [ -z "$OIDC_PROVIDER" ]; then
        OIDC_PROVIDER=$(echo "$CLUSTER_DESC" \
            | sed -n 's|.*"issuer": *"https://\([^"]*\)".*|\1|p' \
            | head -1)
    fi
fi

if [ "$DO_IAM" = "true" ]; then
    echo "   OIDC:          $OIDC_PROVIDER"
fi

if [ "$DO_VPC" = "true" ]; then
    if [ -z "$VPC_ID" ]; then
        VPC_ID=$(echo "$CLUSTER_DESC" | sed -n 's|.*"vpcId": *"\([^"]*\)".*|\1|p' | head -1)
    fi
    if [ -z "$SUBNET_IDS" ]; then
        SUBNET_IDS=$(echo "$CLUSTER_DESC" \
            | tr ',' '\n' \
            | sed -n 's|.*"\(subnet-[a-z0-9]*\)".*|\1|p' \
            | sort -u \
            | tr '\n' ',' | sed 's/,$//')
    fi
    if [ -z "$SG_ID" ]; then
        SG_ID=$(echo "$CLUSTER_DESC" \
            | sed -n 's|.*"clusterSecurityGroupId": *"\(sg-[a-z0-9]*\)".*|\1|p' \
            | head -1)
    fi
    if [ -z "$ROUTE_TABLE_IDS" ] && [ -n "$SUBNET_IDS" ]; then
        ROUTE_TABLE_IDS=$(aws ec2 describe-route-tables \
            --region "$REGION" \
            --filters "Name=association.subnet-id,Values=$(echo "$SUBNET_IDS" | tr ',' ' ')" \
            --query 'RouteTables[].RouteTableId' \
            --output text 2>/dev/null | tr '\t' ',' | sed 's/,$//' || true)
        # Fall back to all RTs in the VPC if none associated to those subnets directly
        if [ -z "$ROUTE_TABLE_IDS" ]; then
            ROUTE_TABLE_IDS=$(aws ec2 describe-route-tables \
                --region "$REGION" \
                --filters "Name=vpc-id,Values=$VPC_ID" \
                --query 'RouteTables[].RouteTableId' \
                --output text 2>/dev/null | tr '\t' ',' | sed 's/,$//' || true)
        fi
    fi

    echo "   VPC:           $VPC_ID"
    echo "   Subnets:       $SUBNET_IDS"
    echo "   Security grp:  $SG_ID"
    echo "   Route tables:  $ROUTE_TABLE_IDS"
fi

if [ "$DRY_RUN" = "true" ]; then
    echo "   ⚠️  DRY-RUN — no AWS resources will be modified."
fi
echo ""

# ────────────────────────────────────────────────────────────────────────
# CLEANUP MODE
# ────────────────────────────────────────────────────────────────────────
if [ "$CLEANUP" = "true" ]; then
    echo "🧹 Cleanup mode."

    if [ "$DRY_RUN" != "true" ]; then
        echo ""
        echo "   This will DELETE:"
        [ "$DO_IAM" = "true" ] && echo "     - IAM role: $ROLE_NAME (and inline policy $POLICY_NAME)"
        [ "$DO_VPC" = "true" ] && echo "     - All VPC endpoints in vpc $VPC_ID tagged Project=nexus-ai-engine"
        echo ""
        read -r -p "Type 'DELETE' to confirm: " CONFIRM
        if [ "$CONFIRM" != "DELETE" ]; then
            echo "   Aborted."
            exit 1
        fi
    fi

    if [ "$DO_IAM" = "true" ]; then
        echo ""
        echo "🗑️   Deleting IAM role $ROLE_NAME ..."
        if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
            run "aws iam delete-role-policy --role-name '$ROLE_NAME' --policy-name '$POLICY_NAME' 2>/dev/null || true"
            # Detach any attached managed policies (none expected, but be safe)
            ATTACHED=$(aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || true)
            for ARN in $ATTACHED; do
                run "aws iam detach-role-policy --role-name '$ROLE_NAME' --policy-arn '$ARN'"
            done
            run "aws iam delete-role --role-name '$ROLE_NAME'"
            echo "   ✅ Role deleted."
        else
            echo "   ⚠️  Role $ROLE_NAME does not exist; skipping."
        fi
    fi

    if [ "$DO_VPC" = "true" ]; then
        echo ""
        echo "🗑️   Deleting VPC endpoints ..."
        IDS=$(aws ec2 describe-vpc-endpoints \
            --region "$REGION" \
            --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Project,Values=nexus-ai-engine" \
            --query 'VpcEndpoints[].VpcEndpointId' \
            --output text 2>/dev/null | tr '\t' ' ' || true)
        if [ -n "$IDS" ] && [ "$IDS" != "None" ]; then
            run "aws ec2 delete-vpc-endpoints --region '$REGION' --vpc-endpoint-ids $IDS"
            echo "   ✅ Submitted deletion for: $IDS"
        else
            echo "   ⚠️  No project-tagged VPC endpoints found in $VPC_ID."
        fi
    fi

    echo ""
    echo "✅ Cleanup complete."
    exit 0
fi

# ────────────────────────────────────────────────────────────────────────
# IAM STAGE
# ────────────────────────────────────────────────────────────────────────
if [ "$DO_IAM" = "true" ]; then
    echo "🔐 IAM stage"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Verify OIDC provider is registered in IAM
    OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
    if ! aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
        echo "❌ OIDC provider is not registered in IAM:"
        echo "     $OIDC_ARN"
        echo ""
        echo "   Register it (admin only) — see deploy/iam/README.md prerequisites."
        echo "   Quick fix:"
        echo ""
        echo "     THUMBPRINT=\$(echo | openssl s_client -servername oidc.eks.${REGION}.amazonaws.com \\"
        echo "       -connect oidc.eks.${REGION}.amazonaws.com:443 2>/dev/null \\"
        echo "       | openssl x509 -fingerprint -sha1 -noout \\"
        echo "       | sed 's/sha1 Fingerprint=//;s/://g' | tr '[:upper:]' '[:lower:]')"
        echo "     aws iam create-open-id-connect-provider \\"
        echo "       --url \"https://${OIDC_PROVIDER}\" \\"
        echo "       --client-id-list sts.amazonaws.com \\"
        echo "       --thumbprint-list \"\${THUMBPRINT}\""
        exit 1
    fi
    echo "   ✅ OIDC provider registered."

    # Substitute placeholders into the templates
    TRUST_TPL="$IAM_DIR/ai-engine-trust-policy.json"
    POLICY_TPL="$IAM_DIR/ai-engine-policy.json"

    if [ ! -f "$TRUST_TPL" ] || [ ! -f "$POLICY_TPL" ]; then
        echo "❌ Policy templates missing under $IAM_DIR"
        exit 1
    fi

    TRUST_RENDERED="$TMP_DIR/trust.json"
    POLICY_RENDERED="$TMP_DIR/policy.json"

    sed -e "s|\${ACCOUNT_ID}|${ACCOUNT_ID}|g" \
        -e "s|\${OIDC_PROVIDER}|${OIDC_PROVIDER}|g" \
        "$TRUST_TPL" > "$TRUST_RENDERED"

    sed -e "s|\${REGION}|${REGION}|g" \
        -e "s|\${ACCOUNT_ID}|${ACCOUNT_ID}|g" \
        "$POLICY_TPL" > "$POLICY_RENDERED"

    # Sanity check the rendered JSON parses
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "import json; json.load(open('$TRUST_RENDERED'))" || { echo "❌ Rendered trust policy is invalid JSON"; exit 1; }
        python3 -c "import json; json.load(open('$POLICY_RENDERED'))" || { echo "❌ Rendered permission policy is invalid JSON"; exit 1; }
    fi

    # Idempotent role creation
    if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
        echo "   ℹ️  Role $ROLE_NAME exists — updating trust policy in place."
        run "aws iam update-assume-role-policy --role-name '$ROLE_NAME' --policy-document file://$TRUST_RENDERED"
    else
        echo "   ➕ Creating role $ROLE_NAME ..."
        run "aws iam create-role \
            --role-name '$ROLE_NAME' \
            --assume-role-policy-document file://$TRUST_RENDERED \
            --description 'IAM role assumed via IRSA by the nexus-ai-engine pod (sa: $NAMESPACE/$SERVICE_ACCOUNT)' \
            --tags Key=Project,Value=nexus-ai-engine Key=ManagedBy,Value=setup-admin-role.sh"
    fi

    # Always (re)apply the inline permission policy
    echo "   📎 Applying inline policy $POLICY_NAME ..."
    run "aws iam put-role-policy \
        --role-name '$ROLE_NAME' \
        --policy-name '$POLICY_NAME' \
        --policy-document file://$POLICY_RENDERED"

    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
    echo "   ✅ Role ready: $ROLE_ARN"
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# VPC ENDPOINT STAGE
# ────────────────────────────────────────────────────────────────────────
if [ "$DO_VPC" = "true" ]; then
    echo "🌐 VPC endpoint stage"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ -z "$VPC_ID" ]; then
        echo "❌ Could not resolve VPC id."
        exit 1
    fi

    PROJECT_TAGS="ResourceType=vpc-endpoint,Tags=[{Key=Project,Value=nexus-ai-engine},{Key=ManagedBy,Value=setup-admin-role.sh}]"

    create_or_skip_endpoint() {
        local svc="$1"
        local svc_name="com.amazonaws.${REGION}.${svc}"
        local kind="$2"   # Gateway | Interface

        local existing
        existing=$(aws ec2 describe-vpc-endpoints \
            --region "$REGION" \
            --filters "Name=service-name,Values=${svc_name}" "Name=vpc-id,Values=${VPC_ID}" \
            --query 'VpcEndpoints[0].VpcEndpointId' \
            --output text 2>/dev/null || true)

        if [ -n "$existing" ] && [ "$existing" != "None" ]; then
            echo "   ✅ ${svc_name}: already exists ($existing)"
            return 0
        fi

        local name_tag="ai-engine-${svc//./-}-${REGION}"
        local tags="ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=${name_tag}},{Key=Project,Value=nexus-ai-engine},{Key=ManagedBy,Value=setup-admin-role.sh}]"

        if [ "$kind" = "Gateway" ]; then
            if [ -z "$ROUTE_TABLE_IDS" ]; then
                echo "   ⚠️  ${svc_name}: no route tables found; skipping."
                return 0
            fi
            local rts
            rts=$(echo "$ROUTE_TABLE_IDS" | tr ',' ' ')
            echo "   ➕ ${svc_name}: creating gateway endpoint on route tables $rts"
            run "aws ec2 create-vpc-endpoint \
                --region '$REGION' \
                --vpc-id '$VPC_ID' \
                --service-name '$svc_name' \
                --vpc-endpoint-type Gateway \
                --route-table-ids $rts \
                --tag-specifications '$tags' \
                >/dev/null"
        else
            if [ -z "$SUBNET_IDS" ] || [ -z "$SG_ID" ]; then
                echo "   ⚠️  ${svc_name}: subnets or SG missing; skipping."
                return 0
            fi
            local subs
            subs=$(echo "$SUBNET_IDS" | tr ',' ' ')
            echo "   ➕ ${svc_name}: creating interface endpoint in $subs (sg=$SG_ID)"
            run "aws ec2 create-vpc-endpoint \
                --region '$REGION' \
                --vpc-id '$VPC_ID' \
                --service-name '$svc_name' \
                --vpc-endpoint-type Interface \
                --subnet-ids $subs \
                --security-group-ids '$SG_ID' \
                --private-dns-enabled \
                --tag-specifications '$tags' \
                >/dev/null"
        fi
    }

    # Handle skipped services
    for svc in "${SKIP_SVCS[@]}"; do
        echo "   ⏭️  com.amazonaws.${REGION}.${svc}: not a real VPC endpoint service (IAM is global). Skipping."
    done

    # Gateway endpoints
    for svc in "${GATEWAY_SVCS[@]}"; do
        create_or_skip_endpoint "$svc" Gateway
    done

    # Interface endpoints
    for svc in "${INTERFACE_SVCS[@]}"; do
        create_or_skip_endpoint "$svc" Interface
    done

    echo "   ✅ VPC endpoint stage complete."
    echo ""
fi

# ────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────
echo "🎯 Admin setup ready"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "   Region:       %s\n" "$REGION"
printf "   Cluster:      %s\n" "$CLUSTER_NAME"
printf "   Account:      %s\n" "$ACCOUNT_ID"
if [ "$DO_IAM" = "true" ]; then
    printf "   IAM role:     arn:aws:iam::%s:role/%s\n" "$ACCOUNT_ID" "$ROLE_NAME"
    printf "   ServiceAcct:  system:serviceaccount:%s:%s\n" "$NAMESPACE" "$SERVICE_ACCOUNT"
fi
if [ "$DO_VPC" = "true" ]; then
    printf "   VPC:          %s (endpoints created/verified)\n" "$VPC_ID"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if [ "$DO_IAM" = "true" ]; then
    echo "Next:"
    echo "   The deploy script will create namespace '$NAMESPACE' and"
    echo "   ServiceAccount '$SERVICE_ACCOUNT', and annotate it with:"
    echo ""
    echo "     eks.amazonaws.com/role-arn: arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
    echo ""
fi
echo "✅ Done!"
