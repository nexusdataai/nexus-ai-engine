Feature: Journey lifecycle
  Users create a journey, run a job on it, and observe logs + step results.
  Exercises the deterministic step-tool dispatch path end-to-end.

  Scenario: Run a noop pipeline end-to-end
    Given the reference server is running in-process
    And a journey with 3 noop steps named "noop-pipeline"
    When I start a job on the journey
    And I wait for the job to reach a terminal state
    Then the job ends with status "completed"
    And step "s1" has status "completed"
    And step "s2" has status "completed"
    And step "s3" has status "completed"
    And the job has at least 6 logs

  Scenario: Generate multiple reports in one job
    Given the reference server is running in-process
    And a journey that emits 3 reports named "report-gen"
    When I start a job on the journey
    And I wait for the job to reach a terminal state
    Then the job ends with status "completed"
    And the job has 3 reports
