"""Deployed version resolution for About /health /version."""

from __future__ import annotations

from nexus_ai_engine.runtime_version import deployed_git_sha, deployed_version


def test_deployed_version_prefers_app_version_tag(monkeypatch) -> None:
    monkeypatch.setenv("APP_VERSION", "0.3.54-de0cc9a")
    monkeypatch.setenv("GIT_SHA", "de0cc9a")
    assert deployed_version() == "0.3.54"
    assert deployed_git_sha() == "de0cc9a"


def test_deployed_version_strips_sha_from_tag_when_git_env_missing(monkeypatch) -> None:
    monkeypatch.setenv("APP_VERSION", "0.3.54-de0cc9a")
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILD_GIT_SHA", raising=False)
    monkeypatch.delenv("BUILD_SHA", raising=False)
    monkeypatch.delenv("SOURCE_VERSION", raising=False)
    assert deployed_version() == "0.3.54"
    assert deployed_git_sha() == "de0cc9a"
