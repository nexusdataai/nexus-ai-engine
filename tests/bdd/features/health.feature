Feature: Reference server liveness
  The library's reference server exposes health, readiness, and version endpoints
  so deployments can be probed by Kubernetes and operators.

  Scenario: health endpoint returns ok
    Given the reference server is running in-process
    When I GET "/health"
    Then the response status is 200
    And the response body has key "status" with value "ok"

  Scenario: version endpoint reports the package name
    Given the reference server is running in-process
    When I GET "/version"
    Then the response status is 200
    And the response body has key "name" with value "nexus-ai-engine"
