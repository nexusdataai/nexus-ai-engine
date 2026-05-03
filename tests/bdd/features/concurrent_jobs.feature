Feature: Concurrent jobs on a single journey
  The engine's stated purpose is many concurrent jobs with isolated
  logs + state. This feature asserts that core promise.

  Scenario: Five jobs run in parallel and each completes independently
    Given the reference server is running in-process
    And a journey with 2 noop steps named "parallel"
    When I start 5 jobs on the journey
    And I wait for all jobs to reach a terminal state
    Then all jobs end with status "completed"
    And the journey has 5 jobs
