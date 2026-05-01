"""Common behave step definitions for health, status, and JSON assertions."""

from __future__ import annotations

from behave import given, then, when


@given('the reference server is running in-process')
def step_server_running(context) -> None:
    assert context.app is not None, "Harness app must be initialized in before_all"
    assert context.client is not None, "Harness client must be initialized in before_all"


@when('I GET "{path}"')
def step_get(context, path: str) -> None:
    context.response = context.loop.run_until_complete(context.client.get(path))


@then('the response status is {expected:d}')
def step_status(context, expected: int) -> None:
    assert context.response.status_code == expected, (
        f"Expected status {expected}, got {context.response.status_code}: {context.response.text}"
    )


@then('the response body has key "{key}" with value "{value}"')
def step_body_has_key_value(context, key: str, value: str) -> None:
    body = context.response.json()
    assert key in body, f"Expected key {key!r} in response body {body!r}"
    assert str(body[key]) == value, f"Expected {key}={value!r}, got {body[key]!r}"
