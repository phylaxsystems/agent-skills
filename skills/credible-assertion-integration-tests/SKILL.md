---
name: credible-assertion-integration-tests
description: Use when changing credible-sdk assertion-executor, credible-std, assertion-verification, or sidecar behavior that should be proven with a new assertion-driven test, especially for new precompiles, trigger semantics, assertion specs, or LocalInstance-based integration coverage.
---

# Credible Assertion Integration Tests

## Goal
Prove executor-facing features with real assertion bytecode, using the existing `credible-sdk` harnesses instead of ad hoc mocks.

## When to Use
- Changing `crates/assertion-executor`, `crates/sidecar`, `crates/assertion-verification`, or `testdata/mock-protocol/lib/credible-std`
- Adding a precompile or changing precompile semantics
- Changing trigger registration, assertion spec gating, transaction envelope access, or sidecar assertion validation
- Any feature that is only really proved once an assertion contract runs against the harness

## When Not to Use
- Pure Rust refactors with no observable assertion behavior change
- Generic unit tests that never execute assertion bytecode
- Repositories that do not contain the expected `credible-sdk` paths

## Inputs
- Changed behavior, feature, or bugfix affecting assertion execution or authoring
- Relevant `credible-sdk` module, crate, or Solidity fixture
- Existing nearby assertion examples and precompile implementations
- Repository-local verification commands and toolchain constraints

## Outputs
- The smallest assertion-based test proving the changed behavior
- Reuse of the closest existing harness and fixtures
- Brief notes on why the chosen layer proves the behavior
- Verification results with exact commands run and any remaining gap

## Required Skill Stacking
- Pair with `rust` for Rust changes.
- Pair with `implement-task-from-plan` or `bugfix` when the task is already scoped that way.

## Core Rules

1. **New executor-facing behavior needs an assertion test**
   - If a feature changes what assertion authors can do, add assertion-based coverage.
   - Helper-level tests alone are not enough when the behavior is exposed through deployed assertion bytecode.

2. **Reuse the existing harness before inventing a new one**
   - Start with `assertion_executor::test_utils`, `LocalInstance`, and the mock-protocol Foundry assertions profile.
   - Add new helpers only when two or more tests clearly need them.

3. **Keep assertions tiny and single-purpose**
   - One smallest proving scenario per feature.
   - Prefer a focused assertion contract over a broad kitchen-sink fixture.

4. **Treat assertion syntax as repo-local and time-sensitive**
   - Do not trust copied syntax from old notes or memory.
   - For Solidity assertion syntax and precompile usage, copy the nearest current example from the repo and check the corresponding executor precompile module.

5. **Choose the lowest layer that proves the behavior**
   - Executor/precompile tests for inspector semantics, selector gating, and gas accounting
   - Foundry assertion-project tests for public `credible-std` authoring behavior
   - `LocalInstance` integration for sidecar, transport, commit, or transaction-result behavior

6. **Register triggers and specs explicitly**
   - Implement `triggers()` and register the exact selector being exercised.
   - If the feature depends on gated precompiles, set the assertion spec explicitly.

7. **Ask for user judgment when the proving scenario is ambiguous**
   - If multiple plausible assertions would prove different behavior, ask the user which scenario matters most before locking in the test.
   - If the mapping is obvious, proceed and state the chosen scenario in a short update.

8. **Never assume — always ask**
   - When facing ambiguity, missing context, or multiple reasonable interpretations, ask the user rather than guessing.
   - It is always better to ask one clarifying question than to write a test based on a wrong assumption.
   - This applies to expected behavior, assertion scenarios, test scope, and edge cases. If you are not sure, ask.

## Standard Workflow
1. Restate the changed behavior and name the assertion scenario that should prove it.
2. Read `references/credible-sdk-assertion-testing.md` and the nearest current assertions/precompile modules.
3. Pick the test layer and the closest existing example to copy.
4. Add the smallest new assertion contract or reuse an existing fixture with minimal edits.
5. Wire the Rust or Foundry test through existing helpers.
6. Run the narrowest relevant test command first, then broaden if needed.
7. In closeout, name the assertion, the harness, and what behavior it proves.

## Test Layer Selection
- Use `crates/assertion-executor/src/inspectors/...` tests when the feature is a precompile, selector gate, gas accounting rule, or assertion-spec rule.
- Use `testdata/mock-protocol/assertions/src` plus `testdata/mock-protocol/assertions/test` when the feature is about authoring experience or public `credible-std` behavior.
- Use `crates/sidecar/src/.../tests.rs` with `LocalInstance` when the feature must be exercised through the full engine, transport, commit, or transaction-result path.

## Common Mistakes
- Adding Rust-only tests for behavior that should be proved with deployed assertion bytecode
- Creating a new helper before checking `LocalInstance` and `assertion_executor::test_utils`
- Reusing a broad fixture when a smaller assertion would make the behavior clearer
- Forgetting to set the assertion spec when the feature depends on gated precompiles
- Stopping at Foundry or executor tests when the change actually lives in sidecar integration

## Verification
- Run the narrowest relevant `cargo test` or `forge test` target that covers the new assertion path.
- If you changed sidecar behavior, prefer a `LocalInstance`-backed test instead of only lower-level coverage.
- If you changed precompile exposure or spec gating, verify both the allowed and forbidden paths when applicable.

## Verification Fallback
If full verification cannot complete for reasons unrelated to the change:
1. Run the narrowest commands that still cover the touched assertion path.
2. Prefer the test layer that directly proves the changed behavior instead of broad unrelated coverage.
3. State the blocker, fallback commands, achieved coverage, and remaining gap.
4. Do not describe the work as fully verified while a reachable check for the touched assertion path remains unrun.

## No Premature Closeout
- Do not claim the behavior is covered until the assertion-based test proving it has been run.
- Do not stop at lower-level coverage when the change requires sidecar or author-facing proof.
- Do not rely on memory for assertion syntax, spec names, or gating rules when the repo can be checked directly.

## Escalate When
- The repo does not contain the expected `credible-sdk` paths
- The right assertion scenario is ambiguous and different assertions would prove different behavior
- The feature spans both executor semantics and sidecar integration, and it is unclear whether one layer is enough

## Reference
- `references/credible-sdk-assertion-testing.md` - helper catalog, file locations, existing examples, and verification commands
