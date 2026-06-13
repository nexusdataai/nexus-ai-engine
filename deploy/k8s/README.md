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

## Prerequisite — SSM parameters per environment

The pod bootstraps `EngineConfig` from SSM Parameter Store at startup
(`nexus-ai-engine serve --ssm-prefix /ai-engine/${ENV}/`, wired in
[deployment.yaml](deployment.yaml)). Before applying the manifest for a
new environment, seed the parameters once:

```bash
./deploy/admin/seed-ssm-parameters.sh dev us-east-1
```

That writes the following keys under `/ai-engine/dev/`:

| Parameter | Default value |
|-----------|---------------|
| `dynamodb_transformation_table` | `ai-engine-journeys-dev`         |
| `dynamodb_prompts_table`        | `ai-engine-journeys-dev`         |
| `s3_journey_logs_bucket`        | `ai-engine-journeys-logs-dev`    |
| `s3_journey_reports_bucket`     | `ai-engine-journeys-reports-dev` |
| `environment`                   | `dev`                            |
| `max_concurrent_jobs`           | `10`                             |
| `capability_name`               | `call-processing`                |

Override any value before deploy by either editing the script or running
`aws ssm put-parameter --overwrite` directly. Per-key `DYNAMODB_*` /
`S3_*` environment variables on the Deployment still act as fallbacks for
any field absent from SSM (see `_SSM_TO_ENV_FALLBACK` in
[../../src/nexus_ai_engine/server/cli.py](../../src/nexus_ai_engine/server/cli.py)).

To disable SSM bootstrap entirely (for example, when bringing up a pod
against env-vars only), clear `SSM_PARAMETER_PREFIX` in
[configmap.yaml](configmap.yaml) — the CLI then falls back to its
original env-var-only path.

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
curl -fsS http://localhost:8000/api/v1/journeys/ | head -c 200
```

## Embedded UI (port-forward)

The pod ships a small React UI for browsing journeys, jobs, schedules, and
prompts. Open it from your laptop with:

```bash
kubectl -n ai-engine port-forward svc/nexus-ai-engine 8000:8000
```

Then visit `http://localhost:8000/ui` in a browser. See
[docs/UI.md](../../docs/UI.md) for the full feature list and architecture.

## Bundled demo stages (default ON)

The standalone deploy registers 7 synthetic stages at startup
(`order_to_cash`, `call_ingest`, `transcribe`, `analyze`, `demand_forecast`,
`inventory_opt`, `supply_risk`) so the embedded UI is immediately runnable
for performance / smoke testing without a host application registering
domain stages. Each step does bounded synthetic work — a random sleep
plus an `emit_log` per tick — and exercises the same `BaseStage` →
DynamoDB-LIVELOG → S3 → SSE path the production stages use.

To populate matching journeys after a fresh deploy:

```bash
POD=$(kubectl -n ai-engine get pod -l app.kubernetes.io/name=nexus-ai-engine -o jsonpath='{.items[0].metadata.name}')
kubectl -n ai-engine cp scripts/seed-sample-journeys.sh "$POD":/tmp/seed.sh
kubectl -n ai-engine exec "$POD" -- bash /tmp/seed.sh
```

The seed script invokes `nexus-ai-engine print-demo-journeys` inside the
pod to read the same canonical journey definitions the runtime registers
stage classes from — so the seeded stage_ids always match runnable demo
stages and clicking "Start Processing" in the v2 UI executes the steps
end-to-end.

**Disable the demos** once a host (e.g. `nexus-backend`) is registering
real domain stages — leaving demos on would shadow the real
implementations for any matching `stage_id`. Two ways:

| Where | How |
|-------|-----|
| ConfigMap (durable) | Set `REGISTER_DEMO_STAGES: "false"` in [configmap.yaml](configmap.yaml) and `kubectl rollout restart deploy/nexus-ai-engine -n ai-engine` |
| One-off | `kubectl set env -n ai-engine deploy/nexus-ai-engine REGISTER_DEMO_STAGES=false` |
| Per-invocation | Add `--no-register-demo-stages` to the args in [deployment.yaml](deployment.yaml) |

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
