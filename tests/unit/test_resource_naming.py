from nexus_ai_engine.resource_naming import glue_database_name, resolved_dlq_table, resolved_glue_database


def test_glue_database_name_uses_capability_env(monkeypatch):
    monkeypatch.setenv("CAPABILITY_NAME", "ai-engine")
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("GLUE_DATABASE_NAME", raising=False)
    monkeypatch.delenv("GLUE_DATABASE", raising=False)
    assert glue_database_name() == "ai_engine_local_db"
    assert resolved_glue_database() == "ai_engine_local_db"


def test_resolved_glue_database_honors_env(monkeypatch):
    monkeypatch.setenv("GLUE_DATABASE_NAME", "custom_db")
    assert resolved_glue_database() == "custom_db"


def test_resolved_dlq_table_uses_capability_env(monkeypatch):
    monkeypatch.setenv("CAPABILITY_NAME", "ai-engine")
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("DYNAMODB_DLQ_TABLE", raising=False)
    assert resolved_dlq_table() == "ai-engine-local-dlq"