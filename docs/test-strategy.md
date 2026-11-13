# Ghostfolio QualityLab — Risk-Based Test Strategy

## 1. Mission

Provide an independent, extensible quality engineering framework for
Ghostfolio 3.99.0, demonstrating financial correctness, API reliability,
data isolation, contract validation and developer-owned test automation.

The framework must distinguish verified behavior from planned coverage.
A green result must never depend on silently skipped critical tests.

## 2. System under test

- SUT: Ghostfolio 3.99.0
- Backend: Ghostfolio API
- Dependencies: PostgreSQL and Redis
- Financial oracle: independent Python Decimal implementation
- API automation: Python, pytest, httpx
- Planned browser automation: Playwright with TypeScript

This is an independent quality project, not an official Ghostfolio test suite.

## 3. Risk assessment model

Severity (S): 1 = negligible, 5 = critical financial/security impact.
Likelihood (L): 1 = rare, 5 = frequent.
Risk score = S x L.

Initial scores are engineering hypotheses, not production incident statistics.

| Risk | Failure mode | S | L | Score | Priority |
|------|--------------|---|---|-------|----------|
| R01 | Incorrect portfolio position or exposure | 5 | 4 | 20 | P0 |
| R02 | Incorrect money, fees or precision | 5 | 4 | 20 | P0 |
| R03 | API contract or validation defects | 4 | 3 | 12 | P1 |
| R04 | Unauthorized access or cross-user exposure | 5 | 3 | 15 | P0 |
| R05 | Data corruption or test isolation failure | 5 | 3 | 15 | P0 |
| R06 | UI and backend state inconsistency | 3 | 3 | 9 | P1 |
| R07 | Reliability or performance degradation | 4 | 3 | 12 | P1 |
| R08 | Service or dependency health failure | 4 | 3 | 12 | P1 |

P0: score >= 15.
P1: score 8-14.
P2: score <= 7.

Priority determines implementation order, not automatic test inclusion
in a particular CI gate.

## 4. Test architecture

### Unit / Financial Core

- Runs without Ghostfolio, network access or credentials.
- Validates deterministic financial reference calculations.
- Must run on every pull request.

### API Integration

- Uses a real local Ghostfolio instance.
- Validates persisted activities and portfolio results.
- Requires authenticated API access for write scenarios.
- Uses isolated symbols and verified teardown.
- The strict integration gate rejects missing credentials and skipped tests.

### API Contracts and Security

- Tests success and rejection paths.
- Negative requests must not create unintended data.
- Cross-user authorization tests require two dedicated test identities.
- Expected error responses must be confirmed against Ghostfolio behavior.

### UI End-to-End

- Planned: Playwright / TypeScript.
- Browser workflows must be verified against API state.
- Tests should not depend on execution order or shared mutable data.

### Reliability

- Uses measured baselines, explicit timeouts and actionable diagnostics.
- Destructive fault injection requires a disposable environment.
- Failed checks must not be automatically retried into a green result.

## 5. Coverage inventory

The canonical inventory is docs/test-catalog.csv.

Each case defines:
- Stable test ID
- Functional area
- Primary risk ID
- Priority
- Test layer
- Implementation status
- Scenario
- Exact pytest node ID where implemented
- Prerequisite where applicable

Status definitions:
- implemented: automated test exists and is mapped to a collected test
- planned: accepted candidate, not implemented
- blocked: requires an explicit prerequisite or design decision

A manual experiment does not count as an implemented automated test.

## 6. Execution and quality gates

Current commands:

    uv run pytest -m unit -v
    uv run pytest -m integration --require-integration -v

Current GitHub Actions workflow runs the Financial Core gate.

The integration suite is not yet executed in GitHub Actions.
Its successful local execution must not be presented as CI coverage.

Future gates:
1. Pull request: static checks and deterministic Financial Core.
2. Integration: disposable Ghostfolio environment with required credentials.
3. Extended regression: UI, security and reliability checks.

No integration gate may report success if required tests are skipped.

## 7. Financial correctness boundaries

The existing independent oracle validates:
- Position quantity
- Trade notional
- Buy/sell cash flow
- Fees
- Decimal arithmetic

Current API integration verifies activity records and portfolio quantity.
The test suite reconstructs net cash flow from activity records; it does
not verify a Ghostfolio-reported cash balance.

Not yet verified:
- Cost basis
- Realized and unrealized P&L
- Valuation and market prices
- FX conversion
- Corporate actions and dividends

These require additional domain rules and independent expected results.

## 8. Test data and environment safety

- Write tests target only local HTTP Ghostfolio instances.
- Each financial scenario creates a unique manual asset.
- Created activities are tracked and deleted in reverse order.
- Deletion is verified using subsequent GET requests returning 404.
- Failures during cleanup are test errors, not harmless warnings.
- Test credentials must never be logged or committed.
- Do not point destructive tests at real investment accounts.

Known limitation:
An HTTP write can succeed while its response is lost, leaving an
untracked activity. Recovery and orphan detection remain future work.

## 9. Developer contribution rules

A new automated test must:
1. Reference a catalog ID and a documented risk.
2. Have one clearly stated business or technical objective.
3. Use the lowest sufficient testing layer.
4. Be independent of test execution order.
5. Own its data and define cleanup.
6. Provide deterministic assertions and useful failure diagnostics.
7. Declare environment prerequisites.
8. Be classified with the appropriate pytest marker.
9. Update the catalog when implemented.
10. Pass the appropriate quality gate.

Prefer small test helpers over a large abstraction framework.

## 10. Definition of done

A scenario is complete only when:
- Its assertion verifies the intended risk.
- It has run successfully in its required environment.
- Its cleanup and negative paths are considered.
- It is discoverable and maintainable by another developer.
- Its catalog entry reflects its actual implementation status.

Passing test count is a progress metric, not proof of financial safety.
