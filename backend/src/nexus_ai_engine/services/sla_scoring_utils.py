"""Threshold-based scoring helpers for infra SLA monitoring."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def status_from_score(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= 95:
        return "healthy"
    if score >= 80:
        return "warning"
    return "critical"


def score_lower_is_better(
    value: Optional[float],
    *,
    target: float,
    warning: float,
    critical: float,
) -> Optional[float]:
    """Lower raw values score higher (latency, error rate, CPU%)."""
    if value is None:
        return None
    if value <= target:
        return 100.0
    if value <= warning:
        span = warning - target
        if span <= 0:
            return 70.0
        ratio = (value - target) / span
        return max(70.0, 100.0 - ratio * 30.0)
    if value <= critical:
        span = critical - warning
        if span <= 0:
            return 30.0
        ratio = (value - warning) / span
        return max(30.0, 70.0 - ratio * 40.0)
    return max(0.0, 30.0 - min(30.0, (value - critical) / max(critical, 1) * 30.0))


def score_higher_is_better(
    value: Optional[float],
    *,
    target: float,
    warning: float,
    critical: float,
) -> Optional[float]:
    """Higher raw values score higher (uptime %, success rate)."""
    if value is None:
        return None
    if value >= target:
        return 100.0
    if value >= warning:
        span = target - warning
        if span <= 0:
            return 70.0
        ratio = (target - value) / span
        return max(70.0, 100.0 - ratio * 30.0)
    if value >= critical:
        span = warning - critical
        if span <= 0:
            return 30.0
        ratio = (warning - value) / span
        return max(30.0, 70.0 - ratio * 40.0)
    return max(0.0, 30.0 - min(30.0, (critical - value) / max(critical, 1) * 30.0))


def weighted_score(components: List[Dict[str, Any]]) -> Optional[float]:
    """Weighted average; renormalizes when some components are unknown."""
    total_weight = 0.0
    acc = 0.0
    for comp in components:
        score = comp.get("score")
        weight = float(comp.get("weight") or 0)
        if score is None or weight <= 0:
            continue
        acc += float(score) * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return round(acc / total_weight, 1)


def build_layer(
    components: List[Dict[str, Any]],
) -> Dict[str, Any]:
    score = weighted_score(components)
    return {
        "score": score,
        "status": status_from_score(score),
        "components": components,
    }


def build_pillar(
    *,
    app_components: List[Dict[str, Any]],
    data_components: List[Dict[str, Any]],
    app_weight: float,
    data_weight: float,
    summary_metrics: List[Dict[str, str]],
) -> Dict[str, Any]:
    app_layer = build_layer(app_components)
    data_layer = build_layer(data_components)
    app_score = app_layer.get("score")
    data_score = data_layer.get("score")

    if app_score is not None and data_score is not None:
        pillar_score = round(app_weight * app_score + data_weight * data_score, 1)
    elif app_score is not None:
        pillar_score = app_score
    elif data_score is not None:
        pillar_score = data_score
    else:
        pillar_score = None

    headline = "All checks nominal"
    lowest = None
    for comp in app_components + data_components:
        s = comp.get("score")
        if s is None:
            continue
        if lowest is None or s < lowest.get("score", 101):
            lowest = comp
    if lowest and lowest.get("score", 100) < 95:
        headline = f"{lowest.get('label', 'Metric')} needs attention"

    for comp in app_components + data_components:
        comp["status"] = status_from_score(comp.get("score"))

    return {
        "score": pillar_score,
        "status": status_from_score(pillar_score),
        "headline": headline,
        "app_layer": {
            "score": app_layer.get("score"),
            "status": app_layer.get("status"),
            "components": app_components,
        },
        "data_layer": {
            "score": data_layer.get("score"),
            "status": data_layer.get("status"),
            "components": data_components,
        },
        "summary_metrics": summary_metrics,
    }
