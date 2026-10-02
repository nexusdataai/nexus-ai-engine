"""Unit tests for ai-engine infrastructure diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

from nexus_ai_engine.services.infra_diagnostics_service import CheckStatus, InfraDiagnosticsService


def test_backend_uptime_passes():
    result = InfraDiagnosticsService().check_backend_uptime()
    assert result.status == CheckStatus.PASS
    assert "uptime" in result.message


def test_dynamodb_read_write(monkeypatch):
    class FakeTable:
        table_status = "ACTIVE"
        key_schema = [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}]

        def load(self):
            return None

        def scan(self, **_kwargs):
            return {"Count": 1}

        def put_item(self, Item):
            assert Item["PK"] == "DIAG#test"
            assert Item["_diag"] is True

        def delete_item(self, Key):
            assert Key["PK"] == "DIAG#test"

    class FakeDdb:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr("nexus_ai_engine.services.infra_diagnostics_service._resource", lambda _svc: FakeDdb())
    monkeypatch.setattr(
        "nexus_ai_engine.services.infra_diagnostics_service.get_config",
        lambda: SimpleNamespace(
            environment="local",
            dynamodb_transformation_table="ai-engine-local-journeys",
            dynamodb_executions_table="ai-engine-local-executions",
            dynamodb_prompts_table="ai-engine-local-prompts",
        ),
    )
    result = InfraDiagnosticsService().check_dynamodb_tables()
    assert result.status == CheckStatus.PASS
    assert result.details["tables"]["journeys"]["writable"] is True


def test_frontend_config_html_fallback_is_pass(monkeypatch):
    class FakeResp:
        headers = {"Content-Type": "text/html"}

        def read(self):
            return b"<!doctype html><html><title>Journey Studio</title></html>"

    monkeypatch.setattr(
        "nexus_ai_engine.services.infra_diagnostics_service.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResp(),
    )
    result = InfraDiagnosticsService().check_frontend_config()
    assert result.status == CheckStatus.PASS
    assert result.details["served"] is False
    assert "not used" in result.message


def test_frontend_config_invalid_json_fails(monkeypatch):
    class FakeResp:
        headers = {"Content-Type": "application/json"}

        def read(self):
            return b"{not-json"

    monkeypatch.setattr(
        "nexus_ai_engine.services.infra_diagnostics_service.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResp(),
    )
    result = InfraDiagnosticsService().check_frontend_config()
    assert result.status == CheckStatus.FAIL
    assert "not valid JSON" in result.message


def test_athena_workgroup_does_not_start_query(monkeypatch):
    class FakeAthena:
        def get_work_group(self, WorkGroup):
            return {"WorkGroup": {"Name": WorkGroup, "State": "ENABLED"}}

        def start_query_execution(self, **_kwargs):
            raise AssertionError("diagnostics must not start Athena queries")

    monkeypatch.setattr("nexus_ai_engine.services.infra_diagnostics_service._client", lambda service: FakeAthena())
    result = InfraDiagnosticsService().check_athena_workgroup()
    assert result.status == CheckStatus.PASS
    assert result.details["workgroup"] == "primary"
