"""Unit tests for K3s resource monitoring snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from nexus_ai_engine.services import resource_monitoring_service as rms
from nexus_ai_engine.services.resource_monitoring_service import (
    ResourceMonitoringService,
    network_bytes,
    parse_k8s_bytes,
    parse_k8s_cpu,
    parse_kubelet_summary,
)


def test_parse_k8s_cpu_units():
    assert parse_k8s_cpu("250m") == 0.25
    assert parse_k8s_cpu("1000000000n") == 1.0
    assert parse_k8s_cpu("2") == 2.0
    assert parse_k8s_cpu("") is None
    assert parse_k8s_cpu(None) is None


def test_parse_k8s_bytes_units():
    assert parse_k8s_bytes("1024Ki") == 1024 * 1024
    assert parse_k8s_bytes("1Gi") == 1024**3
    assert parse_k8s_bytes("1000") == 1000.0
    assert parse_k8s_bytes(None) is None


def test_parse_kubelet_summary_python_repr():
    raw = str(
        {
            "node": {
                "fs": {"usedBytes": 10, "capacityBytes": 100},
                "network": {"name": "eth0", "interfaces": [{"name": "eth0", "rxBytes": 8, "txBytes": 2}]},
            }
        }
    )
    data = parse_kubelet_summary(raw)
    assert data["node"]["fs"]["usedBytes"] == 10
    rx, tx = network_bytes(data["node"]["network"])
    assert (rx, tx) == (8, 2)


def test_summary_kpis_and_points_from_mocked_probes(monkeypatch):
    rms._memory.clear()

    class FakeCustom:
        def list_cluster_custom_object(self, **_kwargs):
            return {
                "items": [
                    {
                        "metadata": {"name": "k3s-node"},
                        "usage": {"cpu": "200m", "memory": "512Mi"},
                    }
                ]
            }

    class FakeCore:
        def list_node(self):
            return SimpleNamespace(
                items=[
                    SimpleNamespace(
                        metadata=SimpleNamespace(name="k3s-node"),
                        status=SimpleNamespace(capacity={"cpu": "2", "memory": "2Gi"}),
                    )
                ]
            )

        def connect_get_node_proxy_with_path(self, name, path):
            assert name == "k3s-node"
            assert path == "stats/summary"
            return str(
                {
                    "node": {
                        "fs": {"usedBytes": 25 * 1024**3, "capacityBytes": 100 * 1024**3},
                        "network": {
                            "name": "eth0",
                            "interfaces": [{"name": "eth0", "rxBytes": 2_000_000, "txBytes": 1_000_000}],
                        },
                    }
                }
            )

    monkeypatch.setattr(
        "nexus_ai_engine.services.job_queue_service.redis_available",
        lambda: False,
    )
    svc = ResourceMonitoringService()
    monkeypatch.setattr(svc, "_k8s_clients", lambda: (FakeCore(), FakeCustom()))
    monkeypatch.setattr(svc, "_jobs_running", lambda: 4)

    first = svc.collect_snapshot()
    assert first["cpu_pct"] == 10.0
    assert first["memory_pct"] == 25.0
    assert first["storage_pct"] == 25.0
    assert first["jobs_running"] == 4
    assert first["node"] == "k3s-node"

    older = datetime.now(timezone.utc) - timedelta(seconds=10)
    with rms._lock:
        rms._memory[-1]["timestamp"] = older.isoformat()

    data = svc.get_summary("1h")
    ids = {k["id"]: k for k in data["kpis"]}
    assert ids["cpu"]["value"] == 10.0
    assert ids["memory"]["value"] == 25.0
    assert ids["storage"]["value"] == 25.0
    assert ids["jobs"]["value"] == 4
    assert ids["network"]["value"] is not None
    assert data["points"]
    assert data["node"] == "k3s-node"
