# Kubernetes deployment — nexus-ai-engine

This directory ships a minimal, production-shaped pod deployment for the
reference server so the library can be exercised as an independent pod.

## Quick apply

```bash
# From repo root
kubectl apply -k deploy/k8s/
kubectl -n nexus-ai-engine-dev rollout status deploy/nexus-ai-engine
kubectl -n nexus-ai-engine-dev port-forward svc/nexus-ai-engine 8000:8000
curl -fsS http://localhost:8000/health
```

`make k8s-apply` and `make k8s-smoke` wrap the above.

## What you need before a real cluster apply

All of the following reuse nexus-backend's existing AWS account and EKS
cluster. Nothing below is provisioned by this repo; coordinate with the
nexus-deployer team.

### AWS

1. **ECR repository** — `nexus-ai-engine` (distinct from nexus-backend's
   `ai-job-engine`). One-time:
   ```bash
   aws ecr create-repository --repository-name nexus-ai-engine --image-scanning-configuration scanOnPush=true
   ```
2. **IAM role for IRSA** — the pod needs DynamoDB + S3 permissions matching
   the scope of the routes it serves. For the extraction's early phases
   (1–4) the 501 stubs do not need AWS access at all; leave the placeholder.
   Starting in phase 5 wire the role ARN into
   `serviceaccount.yaml → metadata.annotations.eks.amazonaws.com/role-arn`.
3. **IAM OIDC role for GitHub Actions** — reuse
   `secrets.AWS_ROLE_TO_ASSUME_DEV` from nexus-backend's deploy workflow.

### Kubernetes

- **Cluster:** `nexus-dev` (shared with nexus-backend). Namespace
  `nexus-ai-engine-dev` is created by `namespace.yaml`.
- **Ingress / ALB:** intentionally not included here. Add an overlay in
  [nexus-deployer](https://github.com/nexusdataai/nexus-deployer) with the
  cluster-specific ALB annotations, hostnames, and certificate ARNs.
- **Image pull secret:** the cluster must already be configured with an
  image pull credential for the ECR registry (IRSA for the node group or
  `imagePullSecrets` on the service account).

### Secrets

Non-secret values live in `configmap.yaml`. Secret values (API keys, role
ARN overrides, etc.) belong in a separate Kubernetes Secret named
`nexus-ai-engine-secrets`. Once present, uncomment the `secretRef` block
under `envFrom` in `deployment.yaml`. Never commit secret values.

## Placeholders you must replace

Before `kubectl apply` against a real cluster:

| File | Placeholder | Replacement |
|------|-------------|-------------|
| `serviceaccount.yaml` | `REPLACE_WITH_IAM_ROLE_ARN` | The IAM role ARN assumed via IRSA |
| `deployment.yaml`     | `REPLACE_WITH_ECR_REGISTRY` | e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com` |
| `kustomization.yaml`  | `REPLACE_WITH_ECR_REGISTRY` | Same registry URI |

The GitHub Actions deploy workflow (`.github/workflows/deploy-eks.yml`)
patches these at deploy time using `kubectl set image` so committed YAML
stays generic.
