Feature: Cooperative cancellation
  A running job can be cancelled mid-step. Subsequent steps must not run.

  Scenario: Cancel a long step, downstream step stays queued
    Given the reference server is running in-process
    And a journey with a long-running cancelable step named "cancel-me"
    When I start a job on the journey
    And I cancel the job
    And I wait for the job to reach a terminal state
    Then the job ends with status "cancelled"
    And step "never" has status "queued"
