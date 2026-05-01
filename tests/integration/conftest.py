"""Integration-tier fixtures backed by moto mocks of AWS services.

Activates the shipped AWS adapters against moto 5's unified ``@mock_aws``
context, so tests exercise the real DynamoDB/S3 client code without touching
a real AWS account.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest


@pytest.fixture
def aws_credentials_env() -> Iterator[None]:
    """Set dummy AWS credentials so boto3 does not read ~/.aws/credentials."""
    keys = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }
    previous = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture
def mock_aws_ctx(aws_credentials_env):
    """Enter moto's unified AWS mock context for the duration of a test."""
    try:
        from moto import mock_aws
    except ImportError:  # pragma: no cover - moto required for this tier
        pytest.skip("moto is not installed; run `pip install nexus-ai-engine[test]`")
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_resource(mock_aws_ctx):
    import boto3

    return boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture
def s3_client(mock_aws_ctx):
    import boto3

    return boto3.client("s3", region_name="us-east-1")


@pytest.fixture
def transformation_table(dynamodb_resource):
    table = dynamodb_resource.create_table(
        TableName="test-transformation",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def logs_bucket(s3_client):
    s3_client.create_bucket(Bucket="test-logs")
    return "test-logs"


@pytest.fixture
def reports_bucket(s3_client):
    s3_client.create_bucket(Bucket="test-reports")
    return "test-reports"
