"""Helpers for DynamoDB GSI queries on Scylla Alternator and schema variants."""

from __future__ import annotations

from typing import Any, Callable


def is_gsi_key_mismatch(exc: Exception) -> bool:
    """True when KeyConditionExpression references a non-index key attribute."""
    msg = str(exc)
    return "ValidationException" in msg and (
        "non-key attribute" in msg.lower()
        or "key condition" in msg.lower()
    )


def query_gsi1_pk(
    table: Any,
    gsi_pk: str,
    *,
    on_failure: Callable[[], list[dict]] | None = None,
) -> list[dict]:
    """Query GSI1 by ``GSI1PK``, falling back when the index keys differ."""
    try:
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": gsi_pk},
        )
        return list(response.get("Items", []))
    except Exception as exc:
        if on_failure is not None and is_gsi_key_mismatch(exc):
            return on_failure()
        raise
