"""Three-way match: Opportunity → Delivery → AR Invoice via VDL HTTP."""

from __future__ import annotations

from nexus_tool_sdk import ToolRuntime, VirtualFilter

from nexus_ai_engine.contracts.journey_dsl import RiskClass
from nexus_ai_engine.contracts.tool_descriptor import (
    CapabilityArgumentSpec,
    CapabilityDescriptor,
    PermissionScope,
    ToolAuthor,
    ToolDescriptor,
    ToolSLO,
)
from nexus_ai_engine.contracts.tool_request import ToolRequest
from nexus_ai_engine.tools.base.tool import Tool

QTY_TOLERANCE = 0.02
PRICE_TOLERANCE = 0.05


async def _match_order_delivery_invoice(runtime: ToolRuntime, opportunity_id: str) -> dict:
    opp = await runtime.vdl.query_one(
        "Opportunity",
        filters=[VirtualFilter(field="Opportunity_ID", operator="eq", value=opportunity_id)],
    )
    if not opp:
        return {"match_status": "order_not_found", "opportunity_id": opportunity_id}

    line_resp = await runtime.vdl.query(
        "Opportunity_Line_Item",
        filters=[VirtualFilter(field="Opportunity_ID", operator="eq", value=opportunity_id)],
        limit=100,
    )
    order_qty = sum(int(r.get("Quantity", r.get("Qty", 0))) for r in line_resp.rows)
    order_amount = sum(float(r.get("Total_Price", r.get("Unit_Price", 0))) for r in line_resp.rows)
    if not line_resp.rows:
        order_amount = float(opp.get("Total_Value", opp.get("Amount", 0)))

    del_resp = await runtime.vdl.query(
        "Delivery_Document",
        filters=[VirtualFilter(field="Sales_Order_ID", operator="eq", value=opportunity_id)],
        limit=10,
    )
    deliveries = del_resp.rows
    delivered_qty = sum(int(r.get("Qty", r.get("Quantity", 0))) for r in deliveries)
    delivery_id = deliveries[0].get("Delivery_ID", "") if deliveries else ""

    if not deliveries:
        return {
            "match_status": "missing_delivery",
            "opportunity_id": opportunity_id,
            "order_qty": order_qty,
            "order_amount": order_amount,
            "delivered_qty": 0,
            "invoiced_amount": 0,
            "discrepancies": ["No delivery found"],
        }

    inv_resp = await runtime.vdl.query(
        "AR_Invoice",
        filters=[VirtualFilter(field="Linked_Delivery_ID", operator="eq", value=delivery_id)],
        limit=10,
    )
    invoices = inv_resp.rows
    invoiced_amount = sum(float(r.get("Total_Amount", r.get("Amount", 0))) for r in invoices)
    invoice_id = invoices[0].get("Invoice_ID", "") if invoices else ""

    if not invoices:
        return {
            "match_status": "missing_invoice",
            "opportunity_id": opportunity_id,
            "order_qty": order_qty,
            "order_amount": order_amount,
            "delivered_qty": delivered_qty,
            "delivery_id": delivery_id,
            "invoiced_amount": 0,
            "discrepancies": ["No invoice found for delivery"],
        }

    discrepancies: list[str] = []
    if order_qty > 0 and abs(delivered_qty - order_qty) / order_qty > QTY_TOLERANCE:
        discrepancies.append(
            f"Quantity mismatch: ordered {order_qty}, delivered {delivered_qty} "
            f"(>{QTY_TOLERANCE * 100}% tolerance)"
        )
    if order_amount > 0 and abs(invoiced_amount - order_amount) / order_amount > PRICE_TOLERANCE:
        discrepancies.append(
            f"Amount mismatch: order ${order_amount:.2f}, invoiced ${invoiced_amount:.2f} "
            f"(>{PRICE_TOLERANCE * 100}% tolerance)"
        )

    if not discrepancies:
        status = "matched"
    elif any("Quantity" in d for d in discrepancies):
        status = "quantity_mismatch"
    else:
        status = "price_mismatch"

    return {
        "match_status": status,
        "opportunity_id": opportunity_id,
        "order_qty": order_qty,
        "order_amount": order_amount,
        "delivered_qty": delivered_qty,
        "delivery_id": delivery_id,
        "invoiced_amount": invoiced_amount,
        "invoice_id": invoice_id,
        "discrepancies": discrepancies,
        "line_items": len(line_resp.rows),
    }


class O2cMatchOrderDeliveryInvoiceTool(Tool):
    """Perform three-way match for an order via ontology VDL."""

    tool_id = "o2c_match_order_delivery_invoice"
    version = "1.0.0"

    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id=self.tool_id,
            version=self.version,
            display_name="O2C Three-Way Match",
            description=(
                "Compare Opportunity qty/amount with SAP Delivery qty and Oracle AR Invoice amount. "
                "Tolerance: qty ±2%, amount ±5%."
            ),
            category="o2c",
            author=ToolAuthor(team="finance-ontology", contact="o2c@nexus.ai"),
            provider="tools-o2c",
            permission_scope=PermissionScope.TENANT,
            capabilities=[
                CapabilityDescriptor(
                    name="match_order_delivery_invoice",
                    display_name="Match Order / Delivery / Invoice",
                    description="Three-way match for a single opportunity",
                    risk_class=RiskClass.READ,
                    reversible=True,
                    idempotent=True,
                    supports_dry_run=True,
                    arguments=[
                        CapabilityArgumentSpec(
                            name="opportunity_id",
                            type="string",
                            required=True,
                            description="Salesforce Opportunity ID (e.g. OPP-00123)",
                            json_schema={"type": "string"},
                        )
                    ],
                    output_schema={
                        "type": "object",
                        "properties": {
                            "match_status": {"type": "string"},
                            "opportunity_id": {"type": "string"},
                            "discrepancies": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    required_permissions=[],
                    permission_scope=PermissionScope.TENANT,
                    typical_latency_ms=500,
                    p99_latency_ms=5000,
                )
            ],
            slo=ToolSLO(availability_target=0.995, p95_latency_ms=2000),
            tags=["o2c", "match", "finance"],
        )

    async def _dispatch(self, request: ToolRequest, runtime: ToolRuntime) -> dict:
        opportunity_id = str(request.arguments.get("opportunity_id", "")).strip()
        if not opportunity_id:
            from nexus_ai_engine.tools.base.tool import ToolExecutionError

            raise ToolExecutionError(
                "invalid_arguments",
                "opportunity_id is required",
                retryable=False,
            )
        return await _match_order_delivery_invoice(runtime, opportunity_id)
