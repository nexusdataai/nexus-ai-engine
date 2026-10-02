"""Unit tests for SLA scoring helpers."""

from nexus_ai_engine.services.sla_scoring_utils import (
    build_pillar,
    score_higher_is_better,
    score_lower_is_better,
    status_from_score,
    weighted_score,
)


class TestScoreLowerIsBetter:
    def test_at_target_is_perfect(self):
        assert score_lower_is_better(100, target=500, warning=2000, critical=5000) == 100.0

    def test_at_critical_is_low(self):
        s = score_lower_is_better(5000, target=500, warning=2000, critical=5000)
        assert s is not None and s <= 35

    def test_none_is_unknown(self):
        assert score_lower_is_better(None, target=1, warning=2, critical=3) is None


class TestScoreHigherIsBetter:
    def test_uptime_target(self):
        assert score_higher_is_better(99.95, target=99.9, warning=99.0, critical=95.0) == 100.0

    def test_uptime_critical(self):
        s = score_higher_is_better(90.0, target=99.9, warning=99.0, critical=95.0)
        assert s is not None and s < 40


class TestStatusFromScore:
    def test_bands(self):
        assert status_from_score(96) == "healthy"
        assert status_from_score(85) == "warning"
        assert status_from_score(50) == "critical"
        assert status_from_score(None) == "unknown"


class TestBuildPillar:
    def test_weighted_composite(self):
        result = build_pillar(
            app_components=[
                {"label": "A", "score": 100.0, "weight": 0.5},
                {"label": "B", "score": 80.0, "weight": 0.5},
            ],
            data_components=[
                {"label": "C", "score": 90.0, "weight": 1.0},
            ],
            app_weight=0.5,
            data_weight=0.5,
            summary_metrics=[],
        )
        assert result["score"] == 90.0
        assert result["app_layer"]["score"] == 90.0
        assert result["data_layer"]["score"] == 90.0


class TestWeightedScoreRenormalize:
    def test_skips_unknown_components(self):
        score = weighted_score([
            {"score": 100.0, "weight": 0.5},
            {"score": None, "weight": 0.5},
        ])
        assert score == 100.0
