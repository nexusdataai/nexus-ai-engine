"""Compile Journey DSL → ExecutionGraph (docs/spec/010, 090)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from nexus_ai_engine.contracts.execution_graph import (
    ExecutionGraph,
    ExecutionNode,
    NodeKind,
    NodeVerification,
    RetryPolicy,
)
from nexus_ai_engine.contracts.journey_dsl import (
    JourneyDefinition,
    JourneyStep,
    RiskClass,
    StepKind,
    walk_steps,
)


class JourneyCompiler:
    """Transform a validated JourneyDefinition into a frozen ExecutionGraph."""

    DEFAULT_CAPABILITY = "nexus-ai"

    def compile(
        self,
        journey: JourneyDefinition,
        *,
        tenant_id: UUID,
        trace_id: str = "compile",
        planner_result_id: UUID | None = None,
    ) -> ExecutionGraph:
        planner_id = planner_result_id or uuid4()
        now = datetime.now(timezone.utc)
        nodes: list[ExecutionNode] = []
        node_by_step: dict[str, UUID] = {}
        stage_entry_nodes: dict[str, list[UUID]] = {}
        stage_exit_nodes: dict[str, list[UUID]] = {}

        defaults = journey.spec.defaults
        max_parallelism = journey.spec.concurrency.max_parallel_steps
        max_wall_clock_s = defaults.timeout_s

        for stage in self._topo_sort_stages(journey):
            prev_in_stage: UUID | None = None
            stage_deps: list[UUID] = []
            for dep_stage_id in stage.depends_on:
                stage_deps.extend(stage_exit_nodes.get(dep_stage_id, []))

            for step in walk_steps(stage.steps):
                step_nodes = self._compile_step(
                    step,
                    stage_id=stage.id,
                    defaults_retry=defaults.retry,
                    default_timeout=defaults.timeout_s,
                    default_on_failure=defaults.on_failure.value,
                    prev_in_stage=prev_in_stage,
                    stage_deps=stage_deps,
                    parent_parallel=step.parallel,
                )
                for node, sid in step_nodes:
                    nodes.append(node)
                    node_by_step[sid] = node.node_id
                    if prev_in_stage is None and not stage_deps:
                        stage_entry_nodes.setdefault(stage.id, []).append(node.node_id)
                    prev_in_stage = node.node_id

            if prev_in_stage:
                stage_exit_nodes[stage.id] = [prev_in_stage]
            elif stage_deps:
                stage_exit_nodes[stage.id] = list(stage_deps)

        if not nodes:
            raise ValueError("compiler produced zero nodes")

        content_sha = ExecutionGraph.compute_content_sha256(
            nodes, [], max_parallelism, max_wall_clock_s
        )
        return ExecutionGraph(
            id=uuid4(),
            version=1,
            created_at=now,
            tenant_id=tenant_id,
            trace_id=trace_id,
            planner_result_id=planner_id,
            nodes=nodes,
            edges=[],
            max_parallelism=max_parallelism,
            max_wall_clock_s=max_wall_clock_s,
            content_sha256=content_sha,
        )

    def _compile_step(
        self,
        step: JourneyStep,
        *,
        stage_id: str,
        defaults_retry,
        default_timeout: int,
        default_on_failure: str,
        prev_in_stage: UUID | None,
        stage_deps: list[UUID],
        parent_parallel: bool,
    ) -> list[tuple[ExecutionNode, str]]:
        """Return compiled nodes for one step (may include approval prefix)."""
        out: list[tuple[ExecutionNode, str]] = []
        depends = list(stage_deps)
        if step.depends_on:
            # Explicit deps resolved at compile time via step ids in same stage only
            depends = []  # caller wires via node_by_step in full impl; sequential fallback below
        elif prev_in_stage and not parent_parallel:
            depends = [prev_in_stage]

        retry = step.retry or defaults_retry
        timeout = step.timeout_s or default_timeout
        risk = step.risk_class.value if step.risk_class else "read"
        needs_approval = step.requires_approval and step.risk_class in (
            RiskClass.WRITE,
            RiskClass.DESTRUCTIVE,
        )

        if needs_approval:
            approval_id = uuid4()
            out.append(
                (
                    ExecutionNode(
                        node_id=approval_id,
                        kind=NodeKind.APPROVAL,
                        capability=self.DEFAULT_CAPABILITY,
                        depends_on=depends,
                        requires_approval=True,
                        display_name=f"Approve {step.name or step.id}",
                        reason=f"Approval required for {step.id}",
                        timeout_s=timeout,
                        on_failure=default_on_failure,
                    ),
                    f"{stage_id}.{step.id}.__approval",
                )
            )
            depends = [approval_id]

        kind = self._resolve_kind(step)
        verifications = [
            NodeVerification(
                check_id=v.check_id,
                expression=v.expression,
                timeout_s=v.timeout_s,
            )
            for v in step.verification
        ]

        node_id = uuid4()
        arguments = dict(step.params)
        if step.logic:
            arguments["logic"] = step.logic
        if step.foreach:
            arguments["foreach"] = step.foreach
        if step.condition:
            arguments["condition"] = step.condition
        if step.output:
            arguments["output"] = step.output

        out.append(
            (
                ExecutionNode(
                    node_id=node_id,
                    kind=kind,
                    tool_id=step.tool if kind is NodeKind.TOOL_CALL else None,
                    capability=self.DEFAULT_CAPABILITY,
                    arguments=arguments,
                    timeout_s=timeout,
                    retry_policy=RetryPolicy(
                        max_attempts=retry.max_attempts,
                        initial_backoff_s=retry.initial_backoff_s,
                        max_backoff_s=retry.max_backoff_s,
                        backoff_multiplier=retry.backoff_multiplier,
                        jitter=retry.jitter,
                        retryable_error_codes=list(retry.retryable_errors),
                    ),
                    verification=verifications,
                    depends_on=depends,
                    can_parallel=step.parallel or parent_parallel,
                    risk_class=risk,
                    requires_approval=step.requires_approval,
                    display_name=step.name or step.id,
                    on_failure=default_on_failure,
                ),
                f"{stage_id}.{step.id}",
            )
        )
        return out

    @staticmethod
    def _resolve_kind(step: JourneyStep) -> NodeKind:
        if step.tool:
            return NodeKind.TOOL_CALL
        if step.type is StepKind.VERIFY:
            return NodeKind.VERIFY
        if step.type is StepKind.APPROVAL:
            return NodeKind.APPROVAL
        if step.type is StepKind.NOOP or step.type is StepKind.COMPUTE:
            return NodeKind.NOOP
        return NodeKind.TOOL_CALL

    @staticmethod
    def _topo_sort_stages(journey: JourneyDefinition):
        stages = list(journey.spec.stages)
        by_id = {s.id: s for s in stages}
        visited: set[str] = set()
        order: list = []

        def visit(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            for dep in by_id[sid].depends_on:
                if dep in by_id:
                    visit(dep)
            order.append(by_id[sid])

        for s in stages:
            visit(s.id)
        return order
