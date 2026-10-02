"""Unit tests for Redis Cache operations overview and safe flush."""

from __future__ import annotations

from nexus_ai_engine.services.redis_cache_service import RedisCacheService, _host_from_url


def test_host_from_url_includes_port():
    assert _host_from_url("redis://redis-svc:6379/0") == "redis-svc:6379"


def test_overview_and_protected_flush(monkeypatch):
    deleted: list[str] = []

    class FakeClient:
        def ping(self):
            return True

        def info(self, section):
            return {"used_memory_human": "4.50M", "maxmemory_human": "256.00M"}

        def llen(self, key):
            return {"ai-engine:sla-snapshots": 3, "ai-engine:queue-snapshots": 2}.get(key, 0)

        def xlen(self, _key):
            return 5

        def scard(self, _key):
            return 0

        def scan_iter(self, match, count=200):
            if match == "sse:*:history":
                return iter(["sse:job:abc:history", "sse:execution:1:history"])
            return iter([])

        def delete(self, key):
            deleted.append(key)
            return 1

    monkeypatch.setattr("nexus_ai_engine.services.redis_cache_service._client", lambda: FakeClient())
    monkeypatch.setattr(
        "nexus_ai_engine.services.redis_cache_service.get_queue_snapshot",
        lambda: {"lag": 1, "active": 0, "pending": 0, "consumer_count": 2},
    )
    monkeypatch.setattr("nexus_ai_engine.services.redis_cache_service.is_queue_mode", lambda: True)

    svc = RedisCacheService()
    data = svc.get_overview()
    assert data["connected"] is True
    assert data["memory"]["used_memory_human"] == "4.50M"
    assert data["snapshots"]["key_total"] == 5
    assert data["queue"]["stream_length"] == 5
    assert data["queue"]["protected"] is True
    assert data["sse"]["key_total"] == 2

    flushed = svc.flush_snapshots()
    assert flushed["flushed"] is True
    assert set(deleted) == {
        "ai-engine:sla-snapshots",
        "ai-engine:queue-snapshots",
        "ai-engine:resource-snapshots",
    }
    assert "ai-engine:jobs" not in deleted

    deleted.clear()
    sse = svc.flush_sse_history()
    assert sse["keys_deleted"] == 2
    assert all(key.endswith(":history") for key in deleted)
    assert "ai-engine:jobs" not in deleted
