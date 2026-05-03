# StarHub Backend GitHub Actions Integration

This guide explains how to set up and use GitHub Actions for automated deployment of the StarHub Backend (AI Job Engine) to AWS ECS.

## Table of Contents

1. [Overview](#overview)
2. [Workflow Structure](#workflow-structure)
3. [Quick Setup](#quick-setup)
4. [GitHub Secrets Configuration](#github-secrets-configuration)
5. [Environment Configuration](#environment-configuration)
6. [Deployment Process](#deployment-process)
7. [Troubleshooting](#troubleshooting)

## Overview

The StarHub Backend project uses GitHub Actions for:
- **Automated deployments** to ECS via Docker/ECR
- **Multi-environment support** (dev/test/stage/prod)
- **Security through OIDC** authentication (no long-lived AWS keys)
- **Flexible deployment options** (full, skip-build, no-cache)

### Architecture

```
GitHub Actions (Push/PR/Manual)
        ↓
    OIDC Authentication
        ↓
    AWS IAM Role
        ↓
    update-backend.sh <env>
        ↓
┌─────────────────────────────────┐
│  1. Docker build                │
│  2. Push to ECR                 │
│  3. ECS update-service          │
│  4. (optional) Wait for stable  │
└─────────────────────────────────┘
        ↓
    https://call-api-<env>.totogicore.com
```

### Workflow Files

```
.github/workflows/
├── deploy-dev.yml      # Development (dev branch)
├── deploy-test.yml     # Test (test branch)
├── deploy-stage.yml    # Staging (stage branch)
├── deploy-prod.yml     # Production (main branch)
└── README.md           # Workflow documentation
```

## Workflow Structure

### Development Workflow (`deploy-dev.yml`)
- **Trigger**: Push to `dev` branch or manual dispatch
- **Environment**: Development
- **URL**: https://call-api-dev.totogicore.com
- **Approval**: None required

### Test Workflow (`deploy-test.yml`)
- **Trigger**: Push to `test` branch or manual dispatch
- **Environment**: Test
- **URL**: https://call-api-test.totogicore.com
- **Approval**: None required

### Staging Workflow (`deploy-stage.yml`)
- **Trigger**: Push to `stage` branch or manual dispatch
- **Environment**: Staging
- **URL**: https://call-api-stage.totogicore.com
- **Approval**: None required

### Production Workflow (`deploy-prod.yml`)
- **Trigger**: Push to `main` branch, release, or manual dispatch
- **Environment**: Production
- **URL**: https://call-api.totogicore.com
- **Approval**: Manual confirmation required (`DEPLOY_TO_PRODUCTION`)
- **Features**: Security scan before deployment

## Quick Setup

### Prerequisites
- AWS CLI configured with appropriate permissions
- GitHub repository for starhub-backend
- Access to AWS account (764119721991) for IAM role creation
- Existing GitHub OIDC provider in AWS

### Automated Setup (Recommended)

```bash
cd /opt/mycode/trilogy/starhub-backend/deploy/git-workflow
chmod +x setup-github-integration.sh
./setup-github-integration.sh
```

The script will:
1. Deploy IAM roles for all 4 environments via CloudFormation
2. Generate the exact GitHub secrets you need
3. Save role ARNs to `role-arns-secrets.md`

### Manual Setup

1. **Deploy IAM Role for each environment**:
   ```bash
   # For dev environment
   aws cloudformation deploy \
     --template-file ./deploy/git-workflow/github-role-only.yml \
     --stack-name github-actions-role-starhub-backend-dev \
     --parameter-overrides \
       GitHubOrganization=YOUR_GITHUB_ORG \
       GitHubRepository=starhub-backend \
       BranchName=dev \
     --capabilities CAPABILITY_NAMED_IAM \
     --region ap-southeast-1
   ```

2. **Get Role ARN**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name github-actions-role-starhub-backend-dev \
     --query "Stacks[0].Outputs[?OutputKey=='GitHubActionsRoleArn'].OutputValue" \
     --output text
   ```

3. **Repeat for test, stage, prod** (changing BranchName accordingly)

## GitHub Secrets Configuration

Go to: `https://github.com/YOUR_ORG/starhub-backend/settings/secrets/actions`

### Required AWS Role Secrets

| Secret Name | Environment | Description |
|-------------|-------------|-------------|
| `AWS_ROLE_TO_ASSUME_DEV` | Development | IAM role ARN for dev deployments |
| `AWS_ROLE_TO_ASSUME_TEST` | Test | IAM role ARN for test deployments |
| `AWS_ROLE_TO_ASSUME_STAGE` | Staging | IAM role ARN for stage deployments |
| `AWS_ROLE_TO_ASSUME_PROD` | Production | IAM role ARN for prod deployments |

### Example Role ARN Values

```
AWS_ROLE_TO_ASSUME_DEV   = arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-dev
AWS_ROLE_TO_ASSUME_TEST  = arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-test
AWS_ROLE_TO_ASSUME_STAGE = arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-stage
AWS_ROLE_TO_ASSUME_PROD  = arn:aws:iam::764119721991:role/GitHubActions-starhub-backend-prod
```

## Environment Configuration

| Environment | API URL | ECS Cluster | ECS Service |
|-------------|---------|-------------|-------------|
| dev | call-api-dev.totogicore.com | call-processing-dev-cluster | call-processing-dev-service |
| test | call-api-test.totogicore.com | call-processing-test-cluster | call-processing-test-service |
| stage | call-api-stage.totogicore.com | call-processing-stage-cluster | call-processing-stage-service |
| prod | call-api.totogicore.com | call-processing-prod-cluster | call-processing-prod-service |

## Deployment Process

### Development Deployment

```bash
# Push to dev branch triggers automatic deployment
git checkout dev
git add .
git commit -m "feat: add new API endpoint"
git push origin dev
```

### Staging Deployment

```bash
# Merge dev to stage
git checkout stage
git merge dev
git push origin stage
```

### Production Deployment

```bash
# Merge stage to main
git checkout main
git merge stage
git push origin main
```

Or trigger manually:
1. Go to **Actions** tab
2. Select **Deploy to Production**
3. Click **Run workflow**
4. Type `DEPLOY_TO_PRODUCTION` in confirmation field
5. Click **Run workflow**

### Manual Deployment Options

| Option | Description |
|--------|-------------|
| `full` | Complete deployment (Docker build + ECR push + ECS update) |
| `skip-build` | Use existing ECR image (just update ECS service) |
| `no-cache` | Force Docker rebuild without cache |

Additional options:
- **Wait for deployment**: Check to wait for ECS service stability

## Troubleshooting

### "Could not load credentials from any providers"

**Cause**: Missing or incorrect AWS role configuration

**Solution**:
1. Verify GitHub secrets are set correctly
2. Check IAM role exists:
   ```bash
   aws iam get-role --role-name GitHubActions-starhub-backend-dev
   ```
3. Verify OIDC trust policy includes your repository

### "ECS cluster not found"

**Cause**: ECS cluster doesn't exist or is not active

**Solution**: Ensure cluster exists:
```bash
aws ecs describe-clusters --clusters call-processing-dev-cluster --region ap-southeast-1
```

### "ECS service not found"

**Cause**: ECS service doesn't exist

**Solution**: Ensure service exists:
```bash
aws ecs describe-services \
  --cluster call-processing-dev-cluster \
  --services call-processing-dev-service \
  --region ap-southeast-1
```

### "ECR login failed"

**Cause**: IAM role missing ECR permissions

**Solution**: Verify the IAM role has ECR permissions:
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:PutImage`
- etc.

### "Docker build failed"

**Cause**: Dockerfile errors or dependency issues

**Solution**:
1. Run `docker build .` locally to see errors
2. Fix Dockerfile issues
3. Use `--no-cache` option to force clean build

## Best Practices

### Security
- Use OIDC instead of long-lived AWS keys
- Production deployments require manual confirmation
- Security scan (safety, ruff) runs before production deployment

### Deployment Flow
- Always deploy: dev → test → stage → prod
- Use pull requests for code review
- Test in lower environments before production

### Monitoring
- Check GitHub Actions logs for deployment status
- Monitor ECS service events during deployment
- Verify API health check after deployment

---

## Support

If you encounter issues:
1. Check this README for common solutions
2. Review GitHub Actions logs for specific errors
3. Run `./update-backend.sh <env> --dry-run` locally to preview
4. Verify AWS credentials and permissions
