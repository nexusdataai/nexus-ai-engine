# VPC endpoints for nexus-ai-engine

The nexus-ai-engine pod runs inside a private EKS cluster and reaches AWS
services through region-local VPC endpoints. The admin script
[`deploy/admin/setup-admin-role.sh`](../admin/setup-admin-role.sh) provisions
these endpoints alongside the IAM role.

## Endpoint inventory

Region-templated. Replace `<region>` with the actual AWS region (e.g.
`ap-southeast-1`, `us-east-1`).

### Gateway endpoints (free, route-table based)

Provisioned on every private route table in the cluster's VPC.

| # | Service name | Type |
|---|--------------|------|
| 1 | `com.amazonaws.<region>.s3`         | Gateway |
| 2 | `com.amazonaws.<region>.dynamodb`   | Gateway |

### Interface endpoints (paid, ENI-based)

Provisioned across the cluster's private subnets, attached to the cluster
security group, with `--private-dns-enabled` so SDK calls transparently route
through the endpoint.

| # | Service name | Type |
|---|--------------|------|
| 3  | `com.amazonaws.<region>.ec2`             | Interface |
| 4  | `com.amazonaws.<region>.sts`             | Interface |
| 5  | `com.amazonaws.<region>.ssm`             | Interface |
| 6  | `com.amazonaws.<region>.glue`            | Interface |
| 7  | `com.amazonaws.<region>.ecr.api`         | Interface |
| 8  | `com.amazonaws.<region>.ecr.dkr`         | Interface |
| 9  | `com.amazonaws.<region>.secretsmanager`  | Interface |
| 10 | `com.amazonaws.<region>.logs`            | Interface |
| 11 | `com.amazonaws.<region>.cognito-idp`     | Interface |
| 12 | `com.amazonaws.<region>.athena`          | Interface |
| 13 | `com.amazonaws.<region>.events`          | Interface |
| 14 | `com.amazonaws.<region>.eks`             | Interface |

## Note on `com.amazonaws.<region>.iam`

You may have seen `com.amazonaws.<region>.iam` listed alongside the others.
**This is not a real VPC endpoint service** — IAM is a global service and
AWS does not publish a regional VPC endpoint for it. The admin script
detects and skips this entry with a clear log message.

If pods need to reach IAM (e.g. `aws iam get-role`), the call goes out via
the cluster's NAT gateway / outbound path. For most workloads that's fine,
because IRSA (the role-assumption call to STS) uses the `sts` interface
endpoint which **is** in the list above.

## Tagging

Every endpoint created by the admin script carries the following tags so it
is easy to find and audit:

| Tag key | Value |
|---------|-------|
| `Name`        | `ai-engine-<service>-<region>` |
| `Project`     | `nexus-ai-engine`              |
| `ManagedBy`   | `setup-admin-role.sh`          |

## Idempotency

The script checks for an existing endpoint per `(service-name, vpc-id)`
tuple before creating. Existing endpoints are detected and skipped — the
script does not modify them. Use `--cleanup` to delete project-tagged
endpoints when retiring an environment.
