Feature: Deterministic failures short-circuit the pipeline
  When a step fails, downstream steps must not run. Logs capture the
  failure reason.

  Scenario: Failure in step 2 prevents step 3 from running
    Given the reference server is running in-process
    And a journey with a deterministic failing step named "short-circuit"
    When I start a job on the journey
    And I wait for the job to reach a terminal state
    Then the job ends with status "failed"
    And step "ok" has status "completed"
    And step "boom" has status "failed"
    And step "never" has status "queued"
