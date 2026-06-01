# Existing Assertion Lessons

Use these lessons from current Credible assertion bundles when designing new examples. They are portable patterns, not requirements to copy any one protocol.

## Structure

- Keep the public assertion contract small: constructor, `triggers()`, assertion functions.
- Keep each assertion function focused on one coherent property. Split checks when triggers, failure meanings, or remediation paths differ.
- Move fork-aware reads, calldata decoding, selector constants, unit normalization, and protocol structs into helper/protocol files.
- Keep minimal interfaces in separate files when direct imports are unavailable, unstable, or too noisy.
- Use inherited mixins/base assertions for reusable category logic; keep protocol-specific thresholds, selectors, and unusual accounting local to the example.
- Pass important addresses into the assertion constructor. Assertion deployment may happen in an isolated runtime, so constructor logic should not depend on reading mutable target state unless the target runtime guarantees it.
- Avoid deploying child helper contracts from assertion constructors. Prefer inherited helpers/mixins or explicitly supplied deployed addresses. If a suite-as-separate-contract pattern cannot run through the E2E harness, add a flat test fixture that exercises the same invariant path.

## Trigger Patterns

- Use call-scoped triggers for properties tied to one operation: swap price movement, ERC-4626 preview/actual consistency, virtual price non-decrease, post-borrow solvency, withdrawal debit/custody outflow, or fee-claim preservation.
- Use tx-end triggers for envelope properties: custody covers accounting, admin balances covered, fee bounds, oracle initialization, mapping-storage consistency, protected balance/slot conservation, or aggregate solvency.
- Use explicit selector-group helper functions when one assertion covers many overloads or protocol variants. This makes selector coverage reviewable.
- Register non-standard overloads manually when their calldata layout still fits inherited assertion logic.
- Use cumulative inflow/outflow breakers for rolling-window flow risk. Tiered breakers are useful: warning tier allows only an emergency/withdrawal/liquidation path, critical tier hard-reverts.

## Invariant Patterns

- Prefer custody-versus-accounting checks over local input checks: pool reserves versus ERC20 balances, protocol fees versus token custody, vault liquidity/outstanding accounting, treasury/escrow balances versus liabilities.
- Compare fork-to-fork external state around the triggering call: pre-call to post-call share price, virtual price, health factor, account equity, reserve state, oracle state, or token custody.
- Use call input and output decoding when the invariant depends on the exact operation result. ERC-4626 preview checks are stronger when comparing pre-call preview to the actual return value.
- Model protocol-specific exceptions explicitly. For example, allow a share-price drop only when same-call debt socialization explains it, or allow large outflow only when a liquidation/withdrawal path is present.
- Bound rounding and asynchronous effects with named tolerances. Avoid exact equality when interest accrual, oracle latency, virtual offsets, or decimal normalization can create legitimate dust.
- Skip impossible or uninitialized cases deliberately: empty pools/vaults, native-token legs that cannot be checked as ERC20 custody, metapools without a base pool, or virtual price reads before initialization.
- Do not turn implementation trivia into assertions. A good property should remain meaningful if the protocol refactors internals while preserving user safety.

## Testability Lessons

- Keep tests small and focused. Each behavior test should arm one assertion, execute one monitored call, and prove one expected pass or failure.
- Design mocks with one knob per failure mode so each test trips exactly one invariant and revert reason.
- Seed non-trivial pre-state. Share-price, reserve, liquidity, and health-factor assertions often need nonzero supply, reserves, collateral, or observations.
- Keep smoke tests separate from behavior tests. Plain deployment tests catch constructor and inheritance issues; `cl.assertion` behavior tests must arm an assertion immediately before the monitored external call.
- If the runtime cannot fully simulate a production helper pattern, still test the invariant through a flat assertion fixture and keep a deployment/selector smoke test for the production bundle.
- Use precise revert reasons. They double as the user-facing explanation when an assertion trips.
