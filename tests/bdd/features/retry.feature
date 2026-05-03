Feature: Retry after a failed job
  The retry action spawns a fresh job against the same stage. Retries
  from the "flaky" tool succeed unconditionally (model: the transient
  failure has cleared).

  Scenario: Retry a flaky job until it passes
    Given the reference server is running in-process
    And a journey with a flaky step named "needs-retry"
    When I start a job on the journey
    And I wait for the job to reach a terminal state
    Then the job ends with status "failed"
    When I retry the job
    And I wait for the job to reach a terminal state
    Then the job ends with status "completed"
