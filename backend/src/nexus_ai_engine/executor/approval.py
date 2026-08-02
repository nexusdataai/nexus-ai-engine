"""Approval engine stub — auto-approves in rc1 (docs/spec/020)."""

from __future__ import annotations

from uuid import UUID


class ApprovalEngine:
    """In-process stub: approvals resolve immediately as approved."""

    def __init__(self) -> None:
        self._pending: dict[UUID, str] = {}

    def request(self, execution_id: UUID, node_id: UUID, reason: str) -> UUID:
        approval_id = UUID(int=node_id.int % (2**128))
        self._pending[approval_id] = reason
        return approval_id

    def is_resolved(self, approval_id: UUID) -> bool:
        return True

    def outcome(self, approval_id: UUID) -> str:
        return "approved"
