"""Unit tests for Operations runbooks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from nexus_ai_engine.services.runbooks_service import RunbooksService
from nexus_ai_engine.services.stale_job_manager import StaleJobRecord, StaleJobScanResult


def test_list_stale_jobs(monkeypatch):
    class FakeManager:
        def scan(self):
            return StaleJobScanResult(
                jobs=[
                    StaleJobRecord(
                        job_id="job-1",
                        journey_id="j1",
                        stage_id="s1",
                        current_step="step",
                        age_min=12.5,
                        confidence="STALE",
                        pk="PK",
                        sk="SK",
                    )
                ]
            )

    monkeypatch.setattr("nexus_ai_engine.services.runbooks_service._get_transformation_table", lambda: object())
    monkeypatch.setattr("nexus_ai_engine.services.runbooks_service.StaleJobManager", lambda *_a, **_k: FakeManager())
    data = RunbooksService().list_stale_jobs()
    assert data["summary"]["total_stale"] == 1
    assert data["jobs"][0]["job_id"] == "job-1"


def test_crash_analyzer_filters_restarts(monkeypatch):
    kubernetes = pytest.importorskip("kubernetes")

    class Term:
        reason = "OOMKilled"
        exit_code = 137
        finished_at = None
        message = "killed"

    class LastState:
        terminated = Term()

    class Status:
        name = "api"
        restart_count = 3
        last_state = LastState()

    class Pod:
        metadata = SimpleNamespace(name="ai-engine-local-backend-abc")
        status = SimpleNamespace(phase="Running", start_time=None, container_statuses=[Status()])
        spec = SimpleNamespace(node_name="node-1")

    class FakeCore:
        def list_namespaced_pod(self, namespace):
            return SimpleNamespace(items=[Pod()])

        def read_namespaced_pod_log(self, **_kwargs):
            return "boom"

        def list_namespaced_event(self, namespace, field_selector):
            return SimpleNamespace(items=[])

    monkeypatch.setattr(kubernetes.config, "load_incluster_config", lambda: None)
    monkeypatch.setattr(kubernetes.client, "CoreV1Api", FakeCore)
    monkeypatch.setattr("nexus_ai_engine.services.runbooks_service._namespace", lambda: "ai-engine-local")
    data = RunbooksService().list_crashed_pods()
    assert data["available"] is True
    assert data["count"] == 1
    assert data["pods"][0]["restarts"] == 3
