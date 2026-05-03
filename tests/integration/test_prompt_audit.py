"""Prompt-catalog update/reset semantics with audit trail."""

from __future__ import annotations

from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.models import PromptUpdate


async def test_update_bumps_version_and_sets_is_default_false(
    seeded_engine: InMemoryEngine,
) -> None:
    prompts = await seeded_engine.list_prompts()
    assert prompts, "seeded engine should ship default prompts"
    target = prompts[0]

    updated = await seeded_engine.update_prompt(
        target.id, PromptUpdate(content="new content v1", note="test change")
    )
    assert updated is not None
    assert updated.content == "new content v1"
    assert updated.version == target.version + 1
    assert updated.is_default is False


async def test_audit_log_captures_update_and_reset(
    seeded_engine: InMemoryEngine,
) -> None:
    prompts = await seeded_engine.list_prompts()
    target = prompts[0]
    original_content = target.content

    await seeded_engine.update_prompt(
        target.id, PromptUpdate(content="edited", note="first change")
    )
    await seeded_engine.update_prompt(
        target.id, PromptUpdate(content="edited twice", note="second change")
    )

    audit = await seeded_engine.prompt_audit_log()
    assert len(audit) >= 2
    # Most recent entry is first.
    assert audit[0].action == "updated"
    assert audit[0].note == "second change"
    assert audit[0].previous_content == "edited"
    assert audit[1].previous_content == original_content


async def test_reset_restores_defaults_and_is_audited(
    seeded_engine: InMemoryEngine,
) -> None:
    prompts = await seeded_engine.list_prompts()
    target = prompts[0]
    original_content = target.content

    await seeded_engine.update_prompt(
        target.id, PromptUpdate(content="changed", note="about to reset")
    )

    restored = await seeded_engine.reset_prompts()
    assert restored, "reset should return the default prompts"
    by_id = {p.id: p for p in restored}
    assert by_id[target.id].content == original_content
    assert by_id[target.id].is_default is True

    audit = await seeded_engine.prompt_audit_log()
    assert audit[0].action == "reset"


async def test_update_unknown_prompt_returns_none(seeded_engine: InMemoryEngine) -> None:
    assert await seeded_engine.update_prompt(
        "prompt-not-found", PromptUpdate(content="x")
    ) is None


async def test_list_prompt_types_is_sorted_unique(seeded_engine: InMemoryEngine) -> None:
    types = await seeded_engine.list_prompt_types()
    assert types == sorted(set(types))
