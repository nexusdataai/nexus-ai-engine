"""Shipped adapters: AWS (boto3 client manager + LocalStack), DynamoDB (manage_journey),
S3 (logs/reports sinks).

Adapters are selected via :func:`nexus_ai_engine.factory.build_engine` from
the ``EngineConfig`` (DynamoDB+S3 by default; the in-memory engine remains
the default fallback for the embedded UI).
"""
