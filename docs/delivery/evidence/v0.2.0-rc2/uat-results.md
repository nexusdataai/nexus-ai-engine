# v0.2.0-rc2 UAT Evidence

**Date:** 2026-08-02  
**Environment:** local test suite + in-process API harness  
**Ontology:** nexus-backend `/api/v1/vdl/*` and `/api/v1/connectors/*` promoted (spec 041)

## Results

| ID | Scenario | Priority | Result | Evidence |
|----|----------|----------|--------|----------|
| rc2-T1 | Publish tool package registers tools | P0 | PASS | `test_tool_packages_api.py`, `test_o2c_tool_package.py` |
| rc2-T2 | O2C match tool queries VDL (mock transport) | P0 | PASS | `test_o2c_match_tool.py` 3/3 |
| rc2-T3 | Compiler strict mode rejects unknown tool | P0 | PASS | `test_o2c_tool_package.py::test_strict_validation_rejects_unknown_after_o2c_publish` |
| rc2-T4 | Connector invoke via SDK | P1 | PASS | `test_nexus_tool_sdk.py::test_connector_invoke_success` |
| rc2-T5 | VDL batch-query | P1 | PASS | `test_nexus_tool_sdk.py::test_vdl_batch_query` |
| rc2-O1 | Ontology `POST /api/v1/vdl/query` | P0 | PASS | `ontology_vdl_api.py` mounted; contract test `test_contract_vdl_query_shape` |
| rc2-G1 | User guide Ch.5 walkthrough | P0 | PASS | `docs/user-guide/05-tool-packages-ontology.md` |

## P0 summary

**7/7 PASS (100%)**

## P1 summary

**2/2 PASS (100%)**

## Test command

```bash
cd /opt/mycode/nexus/nexus-ai-engine
source .venv/bin/activate
pytest tests/unit tests/contracts tests/contract tests/integration -q
```

## Notes

- Staging cluster rollout deferred; local harness validates API contracts and dispatch path.
- O2C live VDL against Starhub staging requires ontology pod with O2C entity mappings (follow rc1 cluster context `./set-context.sh 3`).
