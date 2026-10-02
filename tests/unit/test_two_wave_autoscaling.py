"""Two-wave worker autoscaling helpers and ScaledObject spec."""

from __future__ import annotations

from nexus_ai_engine.services.worker_management_service import (
    SCALE_HORIZON_WAVES,
    build_scaled_object_spec,
    two_wave_lag_count,
    useful_max_replicas,
)


def test_two_wave_lag_count_is_horizon_times_threads() -> None:
    assert SCALE_HORIZON_WAVES == 2
    assert two_wave_lag_count(3) == 6
    assert two_wave_lag_count(1) == 2
    assert two_wave_lag_count(0) == 2


def test_useful_max_replicas_capped_by_global_slots() -> None:
    assert useful_max_replicas(10, 3, 50, 3) == 10
    assert useful_max_replicas(20, 3, 50, 16) == 3
    assert useful_max_replicas(20, 1, 50, 16) == 3


def test_scaled_object_uses_two_wave_lag_and_step_limits() -> None:
    spec = build_scaled_object_spec(
        deployment_name="ai-engine-local-job-worker",
        min_replicas=3,
        max_replicas=10,
        redis_address="redis-svc.nexus-local.svc.cluster.local:6379",
        threads=3,
        max_global_jobs=50,
    )
    assert spec["triggers"][0]["metadata"]["lagCount"] == "6"
    assert spec["maxReplicaCount"] == 10
    behavior = spec["advanced"]["horizontalPodAutoscalerConfig"]["behavior"]
    assert behavior["scaleUp"]["policies"][0]["value"] == 2
    assert behavior["scaleUp"]["policies"][0]["periodSeconds"] == 30
    assert behavior["scaleDown"]["policies"][0]["value"] == 1
    assert behavior["scaleDown"]["stabilizationWindowSeconds"] == 180
