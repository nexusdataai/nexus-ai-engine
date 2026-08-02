# v0.2.0-rc2 UAT Evidence

**Date:** 2026-08-02  
**Environments:** local test suite + Starhub cluster (context 3) + live ontology VDL HTTP harness  
**Ontology:** nexus-backend `/api/v1/vdl/*` and `/api/v1/connectors/*` (spec 041)

## Results

| ID | Scenario | Priority | Result | Evidence |
|----|----------|----------|--------|----------|
| rc2-T1 | Publish tool package registers tools | P0 | PASS | Cluster: [staging-uat.log](./staging-uat.log); unit: `test_tool_packages_api.py`, `test_o2c_tool_package.py` |
| rc2-T2 | O2C match tool queries staging VDL | P0 | PASS | Live VDL HTTP: [live-vdl-uat.json](./live-vdl-uat.json) (`match_status: matched`); unit mock: `test_o2c_match_tool.py` |
| rc2-T3 | Compiler strict mode rejects unknown tool | P0 | PASS | Cluster: [staging-uat.log](./staging-uat.log); integration: `test_o2c_tool_package.py::test_strict_validation_rejects_unknown_after_o2c_publish` |
| rc2-T4 | Connector invoke via SDK | P1 | PASS | `test_nexus_tool_sdk.py::test_connector_invoke_success` |
| rc2-T5 | VDL batch-query | P1 | PASS | Live VDL HTTP: [live-vdl-uat.json](./live-vdl-uat.json); `test_nexus_tool_sdk.py::test_vdl_batch_query` |
| rc2-O1 | Ontology `POST /api/v1/vdl/query` | P0 | PASS | Live VDL HTTP: Opportunity rows in [live-vdl-uat.json](./live-vdl-uat.json) |
| rc2-G1 | User guide Ch.5 walkthrough | P0 | PASS | `docs/user-guide/05-tool-packages-ontology.md` |

## P0 summary

**7/7 PASS (100%)**

## P1 summary

**2/2 PASS (100%)**

## Cluster rollout (Starhub context 3)

| Step | Status |
|------|--------|
| bump → package → ECR → app-rollout | PASS |
| Image | `0.2.0-rc2-98379f5` |
| Namespace | `ai-engine-prod` |
| Health | `0.2.0rc2` |

Details: [rollout.log](./rollout.log), [staging-uat.log](./staging-uat.log)

## Live VDL harness

Starhub `ai-engine-prod` has no co-located ontology pod. Live rc2-T2 / rc2-O1 / rc2-T5 executed against real ontology VDL HTTP routes via:

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate
export PYTHONPATH="/opt/mycode/nexus/nexus-backend:/opt/mycode/nexus/nexus-ai-engine/backend/src:/opt/mycode/nexus/nexus-ai-engine/packages/nexus-tool-sdk/src:/opt/mycode/nexus/nexus-ai-engine/packages/tools-o2c/src"
python docs/delivery/evidence/v0.2.0-rc2/live_vdl_uat.py
```

## Test command (local suite)

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate
pytest tests/unit tests/contracts tests/contract tests/integration -q
```

## Notes

- Git commit/push not performed (per delivery agent rules).
- Cluster O2C tool execution against in-pod `http://ontology/...` requires ontology service deploy on Starhub (not present in `ai-engine-prod`).
