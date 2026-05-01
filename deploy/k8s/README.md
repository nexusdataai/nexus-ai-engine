# Kubernetes deployment — nexus-ai-engine

Production-shaped manifests for deploying the reference server as an
independent pod in EKS.

## Conventions

| What | Value |
|------|-------|
| Namespace                | `ai-engine` (single, fixed)                                       |
| ServiceAccount           | `ai-engine-role-sa` (single, fixed)                               |
| IAM role assumed via IRSA| `ai-engine-role` (created once by admin)                          |
| DynamoDB table           | `ai-engine-journeys-${ENV}` (per env)                             |
| S3 buckets               | `ai-engine-journeys-logs-${ENV}`, `ai-engine-journeys-reports-${ENV}` |
| Image (production)       | `${ECR_REGISTRY}/nexus-ai-engine:<git-sha>` or `:latest`           |
| Image (in-pod tests)     | `${ECR_REGISTRY}/nexus-ai-engine:<git-sha>-test` or `:latest-test` |

## How to apply

The recommended path is via the deploy script:

```bash
cd /opt/mycode/nexus/nexus-ai-engine
./deploy/deploy-and-test.sh --env dev --region us-east-1
```

Direct apply (advanced):

```bash
# Substitute placeholders, then apply
ENV=dev
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
IMAGE_TAG=$(git rev-parse --short HEAD)

mkdir -p /tmp/ai-engine-k8s
cp deploy/k8s/*.yaml /tmp/ai-engine-k8s/
sed -i "s|\${ENV}|${ENV}|g; \
        s|\${REGION}|us-east-1|g; \
        s|REPLACE_WITH_ECR_REGISTRY|${ECR_REGISTRY}|g; \
        s|REPLACE_WITH_IAM_ROLE_ARN|arn:aws:iam::${ACCOUNT_ID}:role/ai-engine-role|g" \
    /tmp/ai-engine-k8s/*.yaml

kubectl apply -k /tmp/ai-engine-k8s/
kubectl -n ai-engine rollout status deploy/nexus-ai-engine
```

## Prerequisite — admin-side setup (one time)

Before any deploy can succeed, an AWS administrator must run:

```bash
./deploy/admin/setup-admin-role.sh --region <region>
```

That creates:

- IAM role **`ai-engine-role`** with permissions on
  `ai-engine-journeys-*`, `ai-engine-*` resources.
- IAM trust policy that lets `system:serviceaccount:ai-engine:ai-engine-role-sa`
  assume the role via IRSA.
- VPC endpoints (s3, dynamodb, sts, ssm, ssm-messages, ec2, ecr.api,
  ecr.dkr, secretsmanager, logs, cognito-idp, athena, glue, events, eks)
  in the cluster's VPC so the pod can reach AWS services privately.

See [../iam/README.md](../iam/README.md) for full admin instructions.

## What you must replace before applying

| Placeholder | Replacement | Patched by |
|-------------|-------------|------------|
| `${ENV}`                       | `dev` / `stage` / `prod`                              | deploy-and-test.sh |
| `${REGION}`                    | AWS region (e.g. `us-east-1`, `ap-southeast-1`)        | deploy-and-test.sh |
| `REPLACE_WITH_ECR_REGISTRY`    | e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com`    | deploy-and-test.sh |
| `REPLACE_WITH_IAM_ROLE_ARN`    | `arn:aws:iam::<account>:role/ai-engine-role`           | deploy-and-test.sh |

## Files

- [namespace.yaml](namespace.yaml) — creates `ai-engine` namespace.
- [serviceaccount.yaml](serviceaccount.yaml) — `ai-engine-role-sa` with IRSA annotation placeholder.
- [configmap.yaml](configmap.yaml) — non-secret EngineConfig values; `${ENV}` and `${REGION}` patched at apply time.
- [deployment.yaml](deployment.yaml) — 2 replicas, probes on `/health` + `/readiness`, `readOnlyRootFilesystem`, drop ALL caps, topology spread; `tmp` and `reports` emptyDir volumes (the `reports` volume backs `make test-bdd` HTML output).
- [service.yaml](service.yaml) — ClusterIP on port 8000.
- [hpa.yaml](hpa.yaml) — CPU/memory autoscaler 2 → 10.
- [networkpolicy.yaml](networkpolicy.yaml) — deny-all ingress, allow from kube-system + same-app pods.
- [kustomization.yaml](kustomization.yaml) — wires everything together; `kubectl apply -k`.

No Ingress is shipped — ALB annotations are environment-specific. Add an
overlay in [nexus-deployer](../../../nexus-deployer/) per cluster.

## Verify after deploy

```bash
kubectl -n ai-engine get all
kubectl -n ai-engine port-forward svc/nexus-ai-engine 8000:8000 &
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/readiness
curl -fsS http://localhost:8000/version
```

## Run tests inside the pod

When deployed with the test image (`:<sha>-test`), every test tier is
runnable via `kubectl exec`:

```bash
POD=$(kubectl -n ai-engine get pod -l app.kubernetes.io/name=nexus-ai-engine -o jsonpath='{.items[0].metadata.name}')

kubectl -n ai-engine exec -it "$POD" -- make test-unit
kubectl -n ai-engine exec -it "$POD" -- make test-integration
kubectl -n ai-engine exec -it "$POD" -- make test-e2e
kubectl -n ai-engine exec -it "$POD" -- make test-journeys
kubectl -n ai-engine exec -it "$POD" -- make test-bdd
kubectl -n ai-engine exec -it "$POD" -- make test-endurance
```

`./deploy/deploy-and-test.sh` runs all tiers in sequence and aggregates
results — see its `--help` for options.
