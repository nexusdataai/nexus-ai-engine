"""Retry policy helpers (docs/spec/020)."""

from __future__ import annotations

from nexus_ai_engine.contracts.execution_graph import RetryPolicy

NON_RETRYABLE = frozenset({"POLICY_VIOLATION", "VALIDATION_ERROR", "APPROVAL_REJECTED"})


def should_retry(policy: RetryPolicy, attempt: int, error_code: str | None) -> bool:
    if error_code and error_code in NON_RETRYABLE:
        return False
    if error_code and policy.retryable_error_codes and error_code not in policy.retryable_error_codes:
        return False
    return attempt < policy.max_attempts


def backoff_seconds(policy: RetryPolicy, attempt: int) -> float:
    delay = policy.initial_backoff_s * (policy.backoff_multiplier ** max(0, attempt - 1))
    return min(delay, policy.max_backoff_s)
