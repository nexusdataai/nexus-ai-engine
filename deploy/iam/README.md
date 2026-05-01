# Admin IAM setup for nexus-ai-engine

One-time setup performed by an AWS administrator before the deployment team
can run `deploy/deploy-and-test.sh` (or the GitHub Actions deploy workflow).

The admin script creates:

- **IAM role** `ai-engine-role` with an inline permission policy modeled on
  [nexus-deployer's app-policy-set.json](../../../nexus-deployer/kube-operator/permissions/app-policy-set.json).
- **VPC endpoints** so the pod can reach AWS services privately. See
  [vpc-endpoints.md](vpc-endpoints.md).

The Kubernetes ServiceAccount that assumes the role is
`system:serviceaccount:ai-engine:ai-engine-role-sa` (created at deploy time
by the deploy script, not here).

## Prerequisites

The admin running this script needs:

1. **AWS credentials** with IAM + EC2 + EKS write permissions in the target
   account. Run [`./aws-login.sh`](../../../nexus-backend/aws-login.sh) (or
   `aws-sso-login.sh`) first.
2. **`kubectl` context** pointing at the target EKS cluster. Run
   [`./aws-eks-context.sh`](../../../nexus-backend/aws-eks-context.sh) first.
3. **OIDC provider registered in IAM** for the EKS cluster. The script
   verifies this and prints the exact remediation command if not registered.
   Reference: nexus-deployer's [ADMIN-SETUP.md Step 1](../../../nexus-deployer/kube-operator/permissions/ADMIN-SETUP.md).

## Quick start

```bash
cd /opt/mycode/nexus/nexus-ai-engine

# Both IAM role + VPC endpoints (default)
./deploy/admin/setup-admin-role.sh --region ap-southeast-1

# Only IAM
./deploy/admin/setup-admin-role.sh --region ap-southeast-1 --iam-only

# Only VPC endpoints
./deploy/admin/setup-admin-role.sh --region ap-southeast-1 --vpc-only

# Preview without making changes
./deploy/admin/setup-admin-role.sh --region ap-southeast-1 --dry-run

# Tear down (interactive confirm in production)
./deploy/admin/setup-admin-role.sh --region ap-southeast-1 --cleanup
```

The script auto-detects:

- AWS account ID via `aws sts get-caller-identity`.
- EKS cluster name from `kubectl config current-context`.
- OIDC provider, VPC, subnets, and cluster security group via
  `aws eks describe-cluster`.

Override any of these with `--cluster`, `--account-id`, `--oidc-provider`,
`--vpc-id`, `--subnet-ids`, `--sg-id`, `--route-table-ids`.

## What the script does

### IAM stage

1. Verifies AWS credentials and the OIDC provider is registered.
2. Substitutes `${ACCOUNT_ID}`, `${OIDC_PROVIDER}`, `${REGION}` placeholders
   into the policy templates.
3. Idempotently creates or updates `ai-engine-role`:
   - If the role exists, updates its trust policy in place.
   - Always re-applies the inline permission policy so policy edits land.
4. Prints the role ARN. The deploy script will annotate the
   ServiceAccount `ai-engine-role-sa` with this ARN at deploy time.

### VPC endpoint stage

For each endpoint listed in [vpc-endpoints.md](vpc-endpoints.md):

- Looks up an existing endpoint matching `(service-name, vpc-id)`.
- If absent, creates it with project tags (`Name`, `Project`, `ManagedBy`).
- Gateway endpoints (`s3`, `dynamodb`) attach to the cluster's private route
  tables.
- Interface endpoints attach to the cluster's private subnets and the
  cluster security group, with `--private-dns-enabled`.
- `com.amazonaws.<region>.iam` is logged and skipped — IAM is a global
  service with no regional VPC endpoint.

## Files in this directory

- [`ai-engine-policy.json`](ai-engine-policy.json) — inline permission policy
  template. Wildcards `ai-engine-*` resources so a single role works across
  all environments (dev / stage / prod).
- [`ai-engine-trust-policy.json`](ai-engine-trust-policy.json) — trust policy
  template. Locks to exactly
  `system:serviceaccount:ai-engine:ai-engine-role-sa`.
- [`vpc-endpoints.md`](vpc-endpoints.md) — documented endpoint inventory.
- [`../admin/setup-admin-role.sh`](../admin/setup-admin-role.sh) — the
  admin script that consumes the templates.

## Verify after running

```bash
# Role exists and trust policy matches
aws iam get-role --role-name ai-engine-role \
    --query "Role.{Arn:Arn, Trust:AssumeRolePolicyDocument}" --output table

# Inline policy attached
aws iam get-role-policy --role-name ai-engine-role --policy-name ai-engine-policy

# All endpoints up
aws ec2 describe-vpc-endpoints \
    --filters "Name=tag:Project,Values=nexus-ai-engine" \
    --query "VpcEndpoints[].{State:State,Service:ServiceName,Type:VpcEndpointType}" \
    --output table
```

Then hand off to the deployment team to run
[`deploy-and-test.sh`](../deploy-and-test.sh).
