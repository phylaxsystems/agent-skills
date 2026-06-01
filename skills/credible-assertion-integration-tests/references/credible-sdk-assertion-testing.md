# Credible SDK Assertion Testing Reference

## Repository Assumptions
- This skill is for the `credible-sdk` repository shape.
- Expected paths:
  - `crates/assertion-executor`
  - `crates/sidecar`
  - `crates/assertion-verification`
  - `testdata/mock-protocol`
  - `testdata/mock-protocol/lib/credible-std`
- The mock-protocol Foundry assertions profile lives in `testdata/mock-protocol/foundry.toml` and maps:
  - `src = "assertions/src"`
  - `test = "assertions/test"`
  - `out = "out"`

If those paths are missing, stop and ask the user whether the repo layout changed.

## Reuse-First Helper Catalog

### Rust helpers for executor-facing tests
- `crates/assertion-executor/src/test_utils.rs`
- Reuse these before writing bespoke setup code:
  - `bytecode("File.sol:Contract")`: reads constructor bytecode from `testdata/mock-protocol/out`
  - `deployed_bytecode("File.sol:Contract")`: reads runtime bytecode
  - `run_precompile_test("TestGetLogs")`: loads `testdata/mock-protocol/src/precompiles/TestGetLogs.sol:TestGetLogs`, deploys `Target.sol`, executes `TriggeringTx`, and returns `TxValidationResult`
  - `run_precompile_test_with_spec("TestSpecForbidTxObject", AssertionSpec::Reshiram)`: same flow with an explicit assertion spec
  - `counter_call()`, `COUNTER_ADDRESS`, and `SIMPLE_ASSERTION_COUNTER`: stock counter fixture used across executor and sidecar tests

### Sidecar integration helpers
- `crates/sidecar/src/utils/instance.rs`
- Reuse these before adding new LocalInstance APIs:
  - `insert_custom_assertion(address, "MyAssertion.sol:MyAssertion")`
  - `insert_assertion(address, AssertionState::new_test(&bytecode(...)))`
  - `create_test_transaction(...)`
  - `send_call_tx_dry(...)`
  - `send_successful_create_tx_dry(...)`
  - `wait_for_transaction_processed(...)`
  - `is_transaction_successful(...)`
  - `is_transaction_invalid(...)`
  - `send_assertion_passing_failing_pair()`
- `crates/sidecar/src/utils/test_drivers.rs::setup_assertion_store()` preloads the counter assertion into the in-memory store. Reuse that pattern when you need a preloaded assertion store.

### Assertion syntax reference policy
- Assertion-specific Solidity syntax changes over time.
- Do not treat this skill as the source of truth for exact syntax.
- Instead, copy the current pattern from:
  - nearby fixtures in `testdata/mock-protocol/src/precompiles`
  - nearby author-facing assertions in `testdata/mock-protocol/assertions/src`
  - `testdata/mock-protocol/lib/credible-std/src/Assertion.sol`
  - `testdata/mock-protocol/lib/credible-std/src/PhEvm.sol`
  - the matching executor implementation under `crates/assertion-executor/src/inspectors/precompiles`
  - `crates/assertion-executor/src/inspectors/phevm.rs` when adding routing or gating behavior

If syntax in examples conflicts, treat the newest relevant implementation and tests as the source of truth.

## Current Assertion Spec Model
- `crates/assertion-executor/src/inspectors/spec_recorder.rs`
- Treat the current names and gating rules below as orientation, not a stable API contract.
- Before relying on them, verify the current model in `spec_recorder.rs` and the nearest relevant tests.
- Current spec tiers are:
  - `Legacy`
  - `Reshiram`
  - `Experimental`
- Current gating pattern:
  - `Legacy` forbids Reshiram-only selectors such as `getTxObject`
  - `Reshiram` allows legacy and Reshiram selectors
  - `Experimental` is the unrestricted superset

If a feature depends on precompile availability, test both the allowed and forbidden paths where possible.

## Existing Patterns To Copy

### 1. Precompile and spec-gating tests
- Rust:
  - `crates/assertion-executor/src/inspectors/phevm.rs`
- Solidity fixtures:
  - `testdata/mock-protocol/src/precompiles/TestSpecLegacy.sol`
  - `testdata/mock-protocol/src/precompiles/TestSpecForbidTxObject.sol`
  - `testdata/mock-protocol/src/precompiles/TestSpecReshiramWithLegacy.sol`
- This pattern is the best starting point for new precompiles, selector gating, and spec-tier behavior.

### 2. User-facing assertion authoring tests
- Solidity assertions:
  - `testdata/mock-protocol/assertions/src/SpecAssertions.a.sol`
- Foundry tests:
  - `testdata/mock-protocol/assertions/test/SpecAssertions.t.sol`
- Pattern:
  - Use `CredibleTest`
  - Register the assertion with `cl.assertion({ adopter, createData, fnSelector })`
  - Call the adopter and assert pass or revert behavior

### 3. Sidecar integration coverage
- `crates/sidecar/src/engine/tests.rs`
- `crates/sidecar/src/utils/instance.rs`
- Use this layer when the behavior is only meaningful through the full engine and transport stack.
- Existing examples:
  - `test_execute_assertion_passing_failing_pair`
  - EIP system-call tests that inspect logs from executed transactions

## Choosing The Right Layer
- New `PhEvm` selector, gas accounting rule, or selector restriction:
  - Add a fixture under `testdata/mock-protocol/src/precompiles`
  - Drive it with `run_precompile_test(...)` or `run_precompile_test_with_spec(...)`
  - Assert on `TxValidationResult`
- New public assertion-authoring pattern in `credible-std`:
  - Add `.a.sol` under `testdata/mock-protocol/assertions/src`
  - Add a Foundry test under `testdata/mock-protocol/assertions/test`
- New sidecar behavior around commit, reorg, transaction results, or transport:
  - Add or extend a `LocalInstance`-based test in `crates/sidecar/src/.../tests.rs`

## Authoring Conventions
- Executor fixtures live under `testdata/mock-protocol/src/precompiles/*.sol`.
- Foundry assertion examples usually live under `testdata/mock-protocol/assertions/src/*.a.sol`.
- Keep one public assertion function per behavior under test when practical.
- Always implement `triggers()` and register the exact selector being exercised.
- When the feature depends on a specific assertion spec:
  - Set it in Solidity with `registerAssertionSpec(...)`, or
  - Set it in Rust with `.with_spec(...)` when constructing `AssertionState`
- Prefer assertions against contract-level behavior:
  - `result.is_valid()`
  - revert or error strings that express the real restriction
  - emitted logs or returned transaction data
- Avoid asserting on incidental implementation details unless they are the behavior being shipped.

## Build And Verification Notes
- The Rust bytecode helpers read from `testdata/mock-protocol/out`.
- If a new Solidity fixture is missing from `out`, rebuild artifacts from `testdata/mock-protocol` before rerunning Rust tests.
- Common narrow verification commands:
  - `cargo test -p assertion-executor <test-name>`
  - `cargo test -p sidecar <test-name>`
  - `cd testdata/mock-protocol && forge test --profile assertions --match-contract <ContractName>`

## Minimal Decision Checklist
1. What executor-visible behavior changed?
2. What is the smallest assertion contract that proves it?
3. Which existing example is closest?
4. If the feature depends on a spec tier, do I need both allowed and forbidden paths (see Current Assertion Spec Model)?
5. Does the feature require a specific assertion spec?
6. Is executor, Foundry, or sidecar coverage the right proof layer?
