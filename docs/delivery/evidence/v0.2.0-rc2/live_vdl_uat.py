#!/usr/bin/env python3
"""Live rc2 VDL + O2C tool UAT against real ontology HTTP routes (in-process bootstrap)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI

BACKEND_ROOT = os.environ.get(
    "NEXUS_BACKEND_ROOT", "/opt/mycode/nexus/nexus-backend"
)
ENGINE_ROOT = os.environ.get(
    "NEXUS_AI_ENGINE_ROOT", "/opt/mycode/nexus/nexus-ai-engine"
)
for root in (BACKEND_ROOT, f"{ENGINE_ROOT}/backend/src", f"{ENGINE_ROOT}/packages/tools-o2c/src"):
    if root not in sys.path:
        sys.path.insert(0, root)

os.environ.setdefault("USE_LOCALSTACK", "true")
os.environ.setdefault("SFDC_SIMULATOR_BUCKET", "")
os.environ.setdefault("SAP_SIMULATOR_BUCKET", "")
os.environ.setdefault("ORACLE_ERP_SIMULATOR_BUCKET", "")


class FakeSimulator:
    def __init__(self) -> None:
        self.loaded = True
        self._tables: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    async def ensure_loaded(self) -> None:
        return None

    async def _get_table_data(self, schema: str, table: str) -> List[Dict[str, Any]]:
        return list(self._tables.get((schema, table), []))

    async def execute_query(self, request):
        from src.models.fdw_models import QueryMetadata, QueryResponse
        from src.services.base_simulator_service import BaseSimulatorService

        rows = await self._get_table_data(request.schema_name, request.table)
        if request.filters:
            for filt in request.filters:
                col = filt.column
                op = filt.operator.value if hasattr(filt.operator, "value") else str(filt.operator)
                rows = [r for r in rows if BaseSimulatorService._match_filter(r, col, op, filt.value)]
        if request.offset:
            rows = rows[request.offset:]
        if request.limit:
            rows = rows[: request.limit]
        return QueryResponse(
            rows=rows,
            metadata=QueryMetadata(
                duration_ms=1.0,
                table_queried=f"{request.schema_name}.{request.table}",
                row_count=len(rows),
            ),
        )


def _seed_o2c_simulators() -> Dict[str, FakeSimulator]:
    sims = {
        "simulator": FakeSimulator(),
        "oracle": FakeSimulator(),
        "sap": FakeSimulator(),
        "external": FakeSimulator(),
    }
    sims["simulator"]._tables[("sfdc_itxp2dev", "Opportunity")] = [
        {
            "Opportunity_ID": "OPP-UAT-001",
            "Account_ID": "ACC-UAT-1",
            "Stage": "Closed Won",
            "Amount": 5000.0,
            "Total_Value": 5000.0,
            "Close_Date": "2026-07-01",
        }
    ]
    sims["simulator"]._tables[("sfdc_itxp2dev", "Opportunity_Line_Item")] = [
        {
            "Line_Item_ID": "OLI-1",
            "Opportunity_ID": "OPP-UAT-001",
            "Product_ID": "MAT-1",
            "Quantity": 100,
            "Unit_Price": 50.0,
            "Total_Price": 5000.0,
        }
    ]
    sims["sap"]._tables[("sap_s4hana", "Delivery_Document")] = [
        {
            "Delivery_ID": "DEL-UAT-001",
            "Sales_Order_ID": "OPP-UAT-001",
            "Qty": 100,
            "Quantity": 100,
        }
    ]
    sims["oracle"]._tables[("oracle_erp", "Oracle_AR_Invoice")] = [
        {
            "Invoice_ID": "INV-UAT-001",
            "Customer_ID": "ACC-UAT-1",
            "Linked_Delivery_ID": "DEL-UAT-001",
            "Total_Amount": 5000.0,
            "Amount": 5000.0,
            "Status": "Open",
        }
    ]
    return sims


class InMemoryMappingService:
    """Minimal mapping-rule store for live UAT without DynamoDB."""

    def __init__(self) -> None:
        self._rules: Dict[str, Any] = {}

    async def list_all(self, virtual_entity: str | None = None, source_type: str | None = None):
        from src.models.mapping_rule_models import MappingRuleResponse

        items = list(self._rules.values())
        if virtual_entity:
            items = [r for r in items if r.virtual_entity == virtual_entity]
        if source_type:
            items = [r for r in items if getattr(r.source_type, "value", r.source_type) == source_type]
        return items

    async def create(self, request):
        from src.models.mapping_rule_models import MappingRuleResponse, MappingRuleStatus

        rule_id = str(uuid4())
        resp = MappingRuleResponse(
            id=rule_id,
            name=request.name,
            virtual_entity=request.virtual_entity,
            source_type=request.source_type,
            source_system=request.source_system,
            source_table=request.source_table,
            source_schema=request.source_schema,
            field_maps=request.field_maps,
            status=MappingRuleStatus.draft,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._rules[rule_id] = resp
        return resp

    async def update(self, rule_id: str, request):
        from src.models.mapping_rule_models import MappingRuleStatus

        existing = self._rules[rule_id]
        if request.status is not None:
            existing.status = request.status
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        return existing


async def _ensure_mapping_rules(mapping_service: InMemoryMappingService) -> None:
    from src.models.mapping_rule_models import (
        FieldMap,
        MappingRuleCreateRequest,
        MappingRuleSourceType,
        MappingRuleStatus,
        MappingRuleUpdateRequest,
    )

    existing = {r.virtual_entity for r in await mapping_service.list_all()}
    rules = [
        ("Opportunity", "sfdc_itxp2dev", "Opportunity", {"Opportunity_ID": "Opportunity_ID", "Total_Value": "Amount", "Stage": "Stage"}),
        ("Opportunity_Line_Item", "sfdc_itxp2dev", "Opportunity_Line_Item", {"Opportunity_ID": "Opportunity_ID", "Quantity": "Quantity", "Total_Price": "Total_Price"}),
        ("OpportunityLineItem", "sfdc_itxp2dev", "Opportunity_Line_Item", {"Opportunity_ID": "Opportunity_ID", "Quantity": "Quantity", "Total_Price": "Total_Price"}),
        ("Delivery_Document", "sap_s4hana", "Delivery_Document", {"Delivery_ID": "Delivery_ID", "Sales_Order_ID": "Sales_Order_ID", "Qty": "Qty"}),
        ("Delivery", "sap_s4hana", "Delivery_Document", {"Delivery_ID": "Delivery_ID", "Sales_Order_ID": "Sales_Order_ID", "Qty": "Qty"}),
        ("AR_Invoice", "oracle_erp", "Oracle_AR_Invoice", {"Invoice_ID": "Invoice_ID", "Linked_Delivery_ID": "Linked_Delivery_ID", "Total_Amount": "Total_Amount"}),
        ("Invoice", "oracle_erp", "Oracle_AR_Invoice", {"Invoice_ID": "Invoice_ID", "Linked_Delivery_ID": "Linked_Delivery_ID", "Total_Amount": "Total_Amount"}),
    ]
    for virtual_entity, schema, table, field_map in rules:
        if virtual_entity in existing:
            continue
        fmaps = [FieldMap(source_field=s, target_field=t) for s, t in field_map.items()]
        rule = await mapping_service.create(
            MappingRuleCreateRequest(
                name=f"UAT: {virtual_entity}",
                virtual_entity=virtual_entity,
                source_schema=schema,
                source_table=table,
                source_system=schema,
                source_type=MappingRuleSourceType.FDW,
                field_maps=fmaps,
            )
        )
        await mapping_service.update(rule.id, MappingRuleUpdateRequest(status=MappingRuleStatus.active))


async def _build_app() -> FastAPI:
    import src.apis.fdw_api as fdw_api
    from src.apis import control_plane_api, ontology_connectors_api, ontology_vdl_api
    from src.services.virtual_query_service import VirtualQueryService

    sims = _seed_o2c_simulators()
    fdw_api._simulators = sims  # noqa: SLF001

    mapping_service = InMemoryMappingService()
    await _ensure_mapping_rules(mapping_service)

    vq = VirtualQueryService(mapping_service=mapping_service, simulators=sims)
    control_plane_api.configure_virtual_query(vq)

    app = FastAPI(title="rc2-live-vdl-uat")
    app.include_router(ontology_vdl_api.router)
    app.include_router(ontology_connectors_api.router)
    return app


async def _run_uat(base_url: str) -> Dict[str, Any]:
    from nexus_tool_sdk import ExecutionContext, ToolRuntime
    from o2c_tools.match import O2cMatchOrderDeliveryInvoiceTool

    from nexus_ai_engine.contracts.tool_request import ToolRequest, ToolRequestMode

    tenant = uuid4()
    exec_id = uuid4()
    ctx = ExecutionContext(tenant_id=tenant, trace_id="rc2-live-uat", execution_id=exec_id)
    results: Dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat(), "base_url": base_url}

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as http:
        # rc2-O1
        o1 = await http.post(
            "/api/v1/vdl/query",
            json={"virtualEntity": "Opportunity", "limit": 5},
            headers={"X-Nexus-Tenant-Id": str(tenant)},
        )
        results["rc2-O1"] = {"status": o1.status_code, "body": o1.json() if o1.status_code == 200 else o1.text}
        assert o1.status_code == 200 and o1.json().get("rows"), "rc2-O1 failed"

        # rc2-T5 batch-query
        t5 = await http.post(
            "/api/v1/vdl/batch-query",
            json={
                "queries": [
                    {"virtualEntity": "Opportunity", "limit": 2, "queryId": "q1"},
                    {"virtualEntity": "Delivery_Document", "limit": 2, "queryId": "q2"},
                ]
            },
            headers={"X-Nexus-Tenant-Id": str(tenant)},
        )
        results["rc2-T5"] = {"status": t5.status_code, "body": t5.json() if t5.status_code == 200 else t5.text}
        assert t5.status_code == 200, "rc2-T5 failed"

        # rc2-T2 O2C match via ToolRuntime -> real VDL HTTP
        tool = O2cMatchOrderDeliveryInvoiceTool()
        runtime = ToolRuntime.create(
            context=ctx,
            vdl_base_url=f"{base_url}/api/v1/vdl",
            connector_base_url=f"{base_url}/api/v1/connectors",
            http=http,
        )
        req = ToolRequest(
            id=uuid4(),
            version=1,
            created_at=datetime.now(timezone.utc),
            tenant_id=tenant,
            trace_id="rc2-live-uat",
            tool_id="o2c_match_order_delivery_invoice",
            tool_version="1.0.0",
            capability="match_order_delivery_invoice",
            mode=ToolRequestMode.READ,
            idempotency_key="uat:1",
            caller_execution_id=exec_id,
            caller_node_id=uuid4(),
            caller_planner_result_id=uuid4(),
            arguments={"opportunity_id": "OPP-UAT-001"},
        )
        t2 = await tool.execute(req, runtime)
        results["rc2-T2"] = {
            "status": t2.status.value,
            "match_status": t2.result.get("match_status") if t2.result else None,
            "result": t2.result,
            "error": t2.error.model_dump() if t2.error else None,
        }
        assert t2.status.value == "ok" and t2.result.get("match_status") == "matched", (
            f"rc2-T2 failed: {results['rc2-T2']}"
        )

        # rc2-T4 connector invoke — skipped if connector runtime not wired
        results["rc2-T4"] = {"status": "skipped", "note": "connector runtime not bootstrapped in minimal UAT app"}

    return results


async def main() -> int:
    app = await _build_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=8081, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    for _ in range(30):
        try:
            async with httpx.AsyncClient() as probe:
                if (await probe.get("http://127.0.0.1:8081/api/v1/vdl/health")).status_code == 200:
                    break
        except Exception:
            await asyncio.sleep(0.2)
    else:
        print("FAIL: ontology UAT server did not start", file=sys.stderr)
        return 1

    results = await _run_uat("http://127.0.0.1:8081")
    server.should_exit = True
    await serve_task

    out_path = Path(__file__).resolve().parent / "live-vdl-uat.json"
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "rc2-T2"}, indent=2))
    print("rc2-T2 match_status:", results["rc2-T2"]["match_status"])
    print("written:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
