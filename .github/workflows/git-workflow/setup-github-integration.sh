#!/bin/bash

# StarHub Backend GitHub Actions Integration Setup Script
# Uses the existing OIDC provider and creates IAM roles for all environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

print_header() {
    echo
    print_color $BLUE "=== $1 ==="
    echo
}

print_header "StarHub Backend GitHub Actions Integration Setup"

# Check if we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

if [ ! -f "$PROJECT_ROOT/update-backend.sh" ]; then
    print_color $RED "Error: Please run this script from the starhub-backend project"
    exit 1
fi

cd "$SCRIPT_DIR"

# AWS Profile configuration
AWS_PROFILE="${AWS_PROFILE:-external-access}"
AWS_REGION="${AWS_REGION:-us-east-1}"

print_color $YELLOW "Using AWS Profile: $AWS_PROFILE"
print_color $YELLOW "Using AWS Region: $AWS_REGION"

# Verify AWS credentials
print_color $YELLOW "Verifying AWS credentials..."
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" > /dev/null 2>&1; then
    print_color $RED "AWS credentials not valid. Please run aws-login or configure credentials."
    exit 1
fi
print_color $GREEN "✓ AWS credentials verified"

# Verify OIDC provider exists
print_color $YELLOW "Checking for existing GitHub OIDC provider..."
OIDC_PROVIDER_ARN=$(aws iam list-open-id-connect-providers --profile "$AWS_PROFILE" --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn" --output text)

if [ -z "$OIDC_PROVIDER_ARN" ]; then
    print_color $RED "GitHub OIDC provider not found. Please create it first."
    print_color $YELLOW "You can create it using AWS Console or CloudFormation."
    exit 1
fi

print_color $GREEN "✓ Found existing GitHub OIDC provider: $OIDC_PROVIDER_ARN"

# Get GitHub repository information
print_color $YELLOW "Please provide your GitHub repository information:"
read -p "GitHub username/organization [trilogy-group]: " GITHUB_ORG
GITHUB_ORG=${GITHUB_ORG:-trilogy-group}

read -p "Repository name [starhub-backend]: " GITHUB_REPO
GITHUB_REPO=${GITHUB_REPO:-starhub-backend}

print_header "Step 1: Deploy IAM Roles for All Environments"

# Define environments and their branch mappings
declare -A ENV_BRANCHES
ENV_BRANCHES["dev"]="dev"
ENV_BRANCHES["test"]="test"
ENV_BRANCHES["stage"]="stage"
ENV_BRANCHES["prod"]="main"

declare -A ROLE_ARNS

for ENV in dev test stage prod; do
    BRANCH="${ENV_BRANCHES[$ENV]}"
    STACK_NAME="github-actions-role-starhub-backend-${ENV}"
    
    print_color $YELLOW "Creating IAM role for $ENV environment (branch: $BRANCH)..."
    
    aws cloudformation deploy \
        --template-file ./github-role-only.yml \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            GitHubOrganization="$GITHUB_ORG" \
            GitHubRepository="$GITHUB_REPO" \
            BranchName="$BRANCH" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --no-fail-on-empty-changeset
    
    if [ $? -eq 0 ]; then
        ROLE_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query "Stacks[0].Outputs[?OutputKey=='GitHubActionsRoleArn'].OutputValue" \
            --output text \
            --region "$AWS_REGION" \
            --profile "$AWS_PROFILE")
        
        ROLE_ARNS[$ENV]="$ROLE_ARN"
        print_color $GREEN "✓ $ENV Role ARN: $ROLE_ARN"
    else
        print_color $RED "✗ Failed to create role for $ENV environment"
    fi
    echo
done

print_header "Step 2: GitHub Secrets Configuration"

print_color $YELLOW "Add the following secrets to your GitHub repository:"
print_color $BLUE "Go to: https://github.com/$GITHUB_ORG/$GITHUB_REPO/settings/secrets/actions"
echo

echo "┌──────────────────────────────────────────────────────────────────────────────────────────────┐"
echo "│                               AWS ROLE SECRETS                                                │"
echo "├──────────────────────────────────────────────────────────────────────────────────────────────┤"
printf "│ %-30s │ %-57s │\n" "Secret Name" "Value"
echo "├──────────────────────────────────────────────────────────────────────────────────────────────┤"
printf "│ %-30s │ %-57s │\n" "AWS_ROLE_TO_ASSUME_DEV" "${ROLE_ARNS[dev]}"
printf "│ %-30s │ %-57s │\n" "AWS_ROLE_TO_ASSUME_TEST" "${ROLE_ARNS[test]}"
printf "│ %-30s │ %-57s │\n" "AWS_ROLE_TO_ASSUME_STAGE" "${ROLE_ARNS[stage]}"
printf "│ %-30s │ %-57s │\n" "AWS_ROLE_TO_ASSUME_PROD" "${ROLE_ARNS[prod]}"
echo "└──────────────────────────────────────────────────────────────────────────────────────────────┘"
echo

# Save role ARNs to a file for reference
cat > ./role-arns-secrets.md << EOF
# StarHub Backend GitHub Actions Role ARNs

| Secret Name | Value |
|-------------|-------|
| AWS_ROLE_TO_ASSUME_DEV | ${ROLE_ARNS[dev]} |
| AWS_ROLE_TO_ASSUME_TEST | ${ROLE_ARNS[test]} |
| AWS_ROLE_TO_ASSUME_STAGE | ${ROLE_ARNS[stage]} |
| AWS_ROLE_TO_ASSUME_PROD | ${ROLE_ARNS[prod]} |

## Environment URLs

| Environment | API URL | ECS Cluster | ECS Service |
|-------------|---------|-------------|-------------|
| dev | https://call-api-dev.totogicore.com | call-processing-dev-cluster | call-processing-dev-service |
| test | https://call-api-test.totogicore.com | call-processing-test-cluster | call-processing-test-service |
| stage | https://call-api-stage.totogicore.com | call-processing-stage-cluster | call-processing-stage-service |
| prod | https://call-api.totogicore.com | call-processing-prod-cluster | call-processing-prod-service |
EOF

print_color $GREEN "✓ Role ARNs saved to: ./role-arns-secrets.md"

print_header "Step 3: Test the Integration"

print_color $YELLOW "To test the GitHub Actions integration:"
echo "1. Push code to the 'dev' branch"
echo "2. Check the Actions tab in your GitHub repository"
echo "3. Monitor the deployment progress"
echo

print_color $GREEN "✓ GitHub Actions integration setup complete!"

print_header "Next Steps"

print_color $YELLOW "1. Add the 4 AWS role secrets to GitHub (see table above)"
print_color $YELLOW "2. Ensure ECR repository exists: ai-job-engine"
print_color $YELLOW "3. For ECS deployment (existing workflows):"
echo "   - Ensure ECS clusters/services exist: call-processing-{env}-cluster/service"
print_color $YELLOW "4. For EKS deployment (deploy-eks-dev.yml workflow):"
echo "   - Grant GitHub Actions role access to EKS cluster:"
echo "     cd /path/to/starhub-deployer/kube-operator"
echo "     ./cluster-access.sh grant-github --repo backend --env dev"
echo "   - Create GitHub Environment 'eks-dev' with variables:"
echo "     EKS_CLUSTER_NAME, DEPLOY_ENV, and secret AWS_ROLE_TO_ASSUME_DEV"
print_color $YELLOW "5. Push your code to trigger the first deployment"
echo

print_header "Deployment Workflow"
print_color $BLUE "Your starhub-backend project is now configured for:"
echo ""
echo "ECS (existing):"
echo "  • Push to 'dev' branch    → Deploy to dev ECS"
echo "  • Push to 'test' branch   → Deploy to test ECS"
echo "  • Push to 'stage' branch  → Deploy to staging ECS"
echo "  • Push to 'main' branch   → Deploy to production ECS"
echo ""
echo "EKS/Kubernetes:"
echo "  • Push to 'dependabot/npm' branch → Deploy to dev EKS cluster (starhub-test1)"
echo

print_color $GREEN "StarHub Backend deployment ready! 🚀"
