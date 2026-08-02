"""Journey DSL schema + semantic validation (docs/spec/010-journey-dsl.md)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition, walk_steps

# Known registry tools — warn when absent; strict mode elevates to error.
_KNOWN_TOOLS = frozenset(
    {
        "echo",
        "query_virtual_entity",
        "soql_query",
        "o2c_match_order_delivery_invoice",
        "s3_write_exceptions",
    }
)


class ValidationIssue(BaseModel):
    path: str
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue]) -> ValidationResult:
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        return cls(valid=not errors, errors=errors, warnings=warnings)


class JourneyValidator:
    """Validate Journey DSL documents at submit time."""

    def __init__(self, *, known_tools: frozenset[str] | None = None) -> None:
        self._known_tools = known_tools if known_tools is not None else _KNOWN_TOOLS

    def validate(
        self,
        data: dict[str, Any] | JourneyDefinition,
        *,
        strict_tools: bool = False,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        if isinstance(data, JourneyDefinition):
            journey = data
        else:
            try:
                journey = JourneyDefinition.model_validate(data)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = ".".join(str(p) for p in err.get("loc", ()))
                    issues.append(
                        ValidationIssue(
                            path=loc or "$",
                            code=err.get("type", "schema"),
                            message=err.get("msg", "validation error"),
                        )
                    )
                return ValidationResult.from_issues(issues)

        issues.extend(self._semantic_issues(journey, strict_tools=strict_tools))
        return ValidationResult.from_issues(issues)

    def _semantic_issues(
        self, journey: JourneyDefinition, *, strict_tools: bool
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        stage_ids = {s.id for s in journey.spec.stages}

        # Stage DAG
        issues.extend(self._dag_issues(journey.spec.stages, stage_ids, kind="stage"))

        all_step_ids: set[str] = set()
        for stage in journey.spec.stages:
            for dep in stage.depends_on:
                if dep not in stage_ids:
                    issues.append(
                        ValidationIssue(
                            path=f"spec.stages.{stage.id}.depends_on",
                            code="unresolved_reference",
                            message=f"stage depends_on references unknown stage '{dep}'",
                        )
                    )

            step_ids = {s.id for s in walk_steps(stage.steps)}
            all_step_ids.update(step_ids)

            for step in walk_steps(stage.steps):
                for dep in step.depends_on:
                    if dep not in step_ids:
                        issues.append(
                            ValidationIssue(
                                path=f"spec.stages.{stage.id}.steps.{step.id}.depends_on",
                                code="unresolved_reference",
                                message=f"step depends_on references unknown step '{dep}'",
                            )
                        )

                if step.tool:
                    if step.tool not in self._known_tools:
                        severity: Literal["error", "warning"] = (
                            "error" if strict_tools else "warning"
                        )
                        issues.append(
                            ValidationIssue(
                                path=f"spec.stages.{stage.id}.steps.{step.id}.tool",
                                code="unknown_tool",
                                message=f"tool '{step.tool}' not in registry catalog",
                                severity=severity,
                            )
                        )
                elif step.type is None:
                    issues.append(
                        ValidationIssue(
                            path=f"spec.stages.{stage.id}.steps.{step.id}",
                            code="missing_step_kind",
                            message="step must specify tool or type",
                        )
                    )

        return issues

    @staticmethod
    def _dag_issues(stages, ids: set[str], *, kind: str) -> list[ValidationIssue]:
        """Detect cycles in stage depends_on DAG."""
        issues: list[ValidationIssue] = []
        graph = {s.id: list(s.depends_on) for s in stages}

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in graph.get(node, []):
                if dep in ids and visit(dep):
                    issues.append(
                        ValidationIssue(
                            path=f"spec.stages.{node}.depends_on",
                            code="cycle",
                            message=f"{kind} dependency graph contains a cycle",
                        )
                    )
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        for sid in ids:
            visit(sid)
        return issues
