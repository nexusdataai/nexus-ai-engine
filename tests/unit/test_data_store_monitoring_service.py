"""Unit tests for DynamoDB and Athena monitoring overviews."""

from __future__ import annotations

from types import SimpleNamespace

from nexus_ai_engine.services.data_store_monitoring_service import DataStoreMonitoringService


def test_dynamodb_overview_describes_engine_tables(monkeypatch):
    class FakeDdb:
        def list_tables(self, Limit=1):
            return {"TableNames": ["ai-engine-local-journeys"]}

        def describe_table(self, TableName):
            return {
                "Table": {
                    "TableStatus": "ACTIVE",
                    "ItemCount": 7,
                    "TableSizeBytes": 2048,
                    "GlobalSecondaryIndexes": [{}],
                    "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
                }
            }

        def scan(self, TableName, Limit=1, ReturnConsumedCapacity="TOTAL"):
            return {"Items": [{}], "ConsumedCapacity": {"CapacityUnits": 0.5}}

    monkeypatch.setattr(
        "nexus_ai_engine.services.data_store_monitoring_service._client",
        lambda service: FakeDdb() if service == "dynamodb" else None,
    )
    monkeypatch.setattr(
        "nexus_ai_engine.services.data_store_monitoring_service.get_config",
        lambda: SimpleNamespace(
            environment="local",
            aws_region="us-east-1",
            dynamodb_transformation_table="ai-engine-local-journeys",
            dynamodb_executions_table="ai-engine-local-executions",
            dynamodb_prompts_table="ai-engine-local-prompts",
        ),
    )
    data = DataStoreMonitoringService().get_dynamodb_overview()
    assert data["connected"] is True
    assert data["tables_active"] == 4
    assert data["tables"][0]["item_count"] == 7
    assert data["tables"][0]["gsi_count"] == 1
    assert [kpi["id"] for kpi in data["kpis"]] == ["read_rcu", "write_wcu", "read_latency", "write_latency"]
    assert data["kpis"][0]["value"] == 0.5
    assert data["kpis"][2]["value"] is not None
    assert data["points"]


def test_dynamodb_overview_uses_cloudwatch_capacity(monkeypatch):
    class FakeDdb:
        def list_tables(self, Limit=1):
            return {"TableNames": ["ai-engine-local-journeys"]}

        def describe_table(self, TableName):
            return {"Table": {"TableStatus": "ACTIVE", "ItemCount": 1, "TableSizeBytes": 10}}

        def scan(self, TableName, Limit=1, ReturnConsumedCapacity="TOTAL"):
            return {"Items": [], "ConsumedCapacity": {"CapacityUnits": 0.5}}

    class FakeCw:
        def get_metric_statistics(self, **kwargs):
            metric = kwargs["MetricName"]
            ts = __import__("datetime").datetime(2026, 9, 6, 12, 0, tzinfo=__import__("datetime").timezone.utc)
            if metric == "ConsumedReadCapacityUnits":
                return {"Datapoints": [{"Timestamp": ts, "Sum": 3.0}]}
            if metric == "ConsumedWriteCapacityUnits":
                return {"Datapoints": [{"Timestamp": ts, "Sum": 1.5}]}
            if metric == "SuccessfulRequestLatency":
                op = next((d["Value"] for d in kwargs.get("Dimensions") or [] if d["Name"] == "Operation"), "")
                value = 9.0 if op == "GetItem" else 14.0
                return {"Datapoints": [{"Timestamp": ts, "Average": value}]}
            return {"Datapoints": []}

    def fake_client(service):
        if service == "dynamodb":
            return FakeDdb()
        if service == "cloudwatch":
            return FakeCw()
        return None

    monkeypatch.setattr("nexus_ai_engine.services.data_store_monitoring_service._client", fake_client)
    monkeypatch.setattr(
        "nexus_ai_engine.services.data_store_monitoring_service.get_config",
        lambda: SimpleNamespace(
            environment="local",
            aws_region="us-east-1",
            dynamodb_transformation_table="ai-engine-local-journeys",
            dynamodb_executions_table="ai-engine-local-executions",
            dynamodb_prompts_table="ai-engine-local-prompts",
        ),
    )
    data = DataStoreMonitoringService().get_dynamodb_overview()
    assert data["metrics_source"] == "cloudwatch"
    assert data["kpis"][0]["value"] == 12.0
    assert data["kpis"][1]["value"] == 6.0
    assert data["points"][0]["read_rcu"] == 12.0
    assert data["tables"][0]["read_rcu"] == 3.0


def test_athena_overview_reads_glue_table(monkeypatch):
    class FakeGlue:
        def get_databases(self, MaxResults=1):
            return {"DatabaseList": [{"Name": "default"}]}

        def get_table(self, DatabaseName, Name):
            assert Name == "archived_jobs"
            return {
                "Table": {
                    "StorageDescriptor": {"Location": "s3://bucket/job-archive/"},
                    "PartitionKeys": [{"Name": "year"}],
                    "Parameters": {"recordCount": "12"},
                }
            }

        def get_partitions(self, DatabaseName, TableName, MaxResults=100):
            return {"Partitions": [{}, {}], "NextToken": None}

    class FakeAthena:
        def get_work_group(self, WorkGroup):
            return {"WorkGroup": {"Name": WorkGroup, "State": "ENABLED"}}

        def list_query_executions(self, WorkGroup, MaxResults=5):
            return {"QueryExecutionIds": ["qid-1", "qid-2"]}

        def get_query_execution(self, QueryExecutionId):
            if QueryExecutionId == "qid-2":
                return {
                    "QueryExecution": {
                        "Query": "INSERT INTO archived_jobs VALUES (1)",
                        "Status": {"State": "SUCCEEDED", "SubmissionDateTime": "2026-09-06T01:00:00Z"},
                        "Statistics": {"EngineExecutionTimeInMillis": 40, "DataScannedInBytes": 2048},
                    }
                }
            return {
                "QueryExecution": {
                    "Query": "SELECT * FROM archived_jobs LIMIT 1",
                    "Status": {"State": "SUCCEEDED", "SubmissionDateTime": "2026-09-06T00:00:00Z"},
                    "Statistics": {"EngineExecutionTimeInMillis": 80, "DataScannedInBytes": 4096},
                }
            }

    def fake_client(service):
        return FakeGlue() if service == "glue" else FakeAthena()

    monkeypatch.setattr("nexus_ai_engine.services.data_store_monitoring_service._client", fake_client)
    monkeypatch.setattr(
        "nexus_ai_engine.services.data_store_monitoring_service.get_config",
        lambda: SimpleNamespace(aws_region="us-east-1", s3_journey_reports_bucket="reports"),
    )
    monkeypatch.setattr(
        "nexus_ai_engine.services.data_store_monitoring_service.archive_bucket_name",
        lambda _cfg: "archive-bucket",
    )
    data = DataStoreMonitoringService().get_athena_overview()
    assert data["connected"] is True
    assert data["glue_reachable"] is True
    assert data["athena_reachable"] is True
    assert data["table"]["exists"] is True
    assert data["table"]["record_count"] == 12
    assert data["table"]["partition_count"] == 2
    assert data["recent_queries"][0]["id"] == "qid-1"
    assert data["recent_queries"][0]["kind"] == "read"
    assert data["kpis"][0]["id"] == "read_queries"
    assert data["kpis"][0]["value"] == 1
    assert data["kpis"][1]["value"] == 1
    assert data["points"]
