# Protection Assertion Guide

Use this guide after `SKILL.md` triggers and before writing assertions.

For concrete lessons from current assertion bundles, read `existing-assertion-lessons.md`. For E2E testing steps and `pcl test` commands, read `e2e-testing-with-pcl.md`.

## Classification Checklist

Classify by protocol mechanics, not branding.

- `vault`: ERC-4626-like shares, deposit/mint/withdraw/redeem flows, asset/share accounting, preview consistency, share price, TVL outflow controls.
- `lending`: borrow/supply/collateral markets, debt accounting, health checks, liquidation, interest indices, reserve accounting.
- `swaps`: AMMs, pools, stableswap/cryptoswap curves, LP tokens, virtual price, oracle/price accumulators, pool custody versus balances.
- `perpetual`: margin, positions, funding, mark/index price, liquidation, account equity, open interest, risk-increasing trades.
- `access_control`: privileged roles, protected slots, admin mutation boundaries, paused/guardian flows, asset custody controlled by admin functions.

Create a new folder only when none of these categories describe the dominant risk model. If a protocol spans categories, put each assertion where its target surface belongs, and keep shared helpers close to the most specific common category.

## Existing Suite Surfaces To Reuse

Prefer these before custom assertion logic:

- ERC-4626 vaults: `ERC4626BaseAssertion`, `ERC4626SharePriceAssertion`, `ERC4626PreviewAssertion`, `ERC4626AssetFlowAssertion`, `ERC4626CumulativeOutflowAssertion`.
- Lending: `LendingBaseAssertion`, operation-safety patterns, solvency/health checks, selector-group registration helpers.
- Perpetuals: `PerpetualBaseAssertion`, operation-safety and post-mutation risk patterns.
- Access control: `AccessControlBaseAssertion`, `SlotProtectionAssertion`, `BalanceConservationAssertion`, generic share-price/balance conservation wrappers.
- Cross-cutting precompiles: `assetsMatchSharePrice`, `conserveBalance`, `watchCumulativeOutflow`, `watchCumulativeInflow`, `oracleSanity`, fork reads, call context, ERC20 deltas, and math helpers.

If a reusable primitive is missing, add it to the relevant base assertion or protection precompile wrapper when it would improve at least two examples or the whole category's ergonomics.

## V2 Syntax Source

Use the bundled `v2-precompiles-and-triggers.md` digest as the portable source for V2 syntax, trigger selection, fork reads, and protection-suite precompiles. If the target repo vendors Credible interfaces, verify exact function signatures there before writing code.

Do not use Notion as a required dependency. Reference `https://docs.phylax.systems/` when current public Credible Layer behavior, product concepts, or CLI/test workflow details are relevant. Otherwise, fetch external docs only when the user explicitly asks for the latest upstream behavior or the target repo appears newer than the bundled digest.

Do not use a stateful-assertion document or persistent assertion storage as a design input for V2 Reshiram assertions. V2 examples should be stateless over fork/call snapshots unless they use built-in cumulative inflow/outflow circuit breakers.

## Invariant Selection

Choose a small invariant set that protects protocol value and explains well.

Strong candidates:

- Custody covers accounting: contract-held external assets are at least protocol liabilities, claimable balances, reserves, or shares.
- Share price, virtual price, or exchange rate obeys expected monotonicity or bounded movement across user operations.
- Preview/quote functions match actual cross-contract mutations within tolerances.
- Debt, collateral, and health factors remain safe after risk-increasing operations, using post-state rather than only input bounds.
- Liquidation improves or bounds account risk according to protocol rules.
- Oracle values are initialized, bounded, and consistent across relevant forks and dependent contracts.
- Fee/admin/accounting variables stay inside explicit protocol bounds after privileged changes.
- Privileged operations do not mutate protected slots or drain protected balances except through documented paths.
- Circuit breakers watch cumulative outflows/inflows for protocol treasuries, vault assets, AMM reserves, bridges, or escrow accounts.
- Rolling-window flow limits use built-in circuit breakers rather than custom assertion storage.

Weak candidates:

- Checks that duplicate a single `require` condition or custom error branch.
- Checks that validate only calldata constraints the protocol already enforces before mutation.
- Custom persistent/stateful assertion storage for V2 Reshiram examples.
- Assertions that only confirm a function was called.
- Properties requiring complete global enumeration when the protocol has no iterable index.
- Exact equality over calculations with known rounding, interest accrual, or oracle latency unless the protocol guarantees it.
- Implementation details that are likely to change without changing user safety.

Before selecting final assertions, scan the relevant protocol functions for `require`, `revert`, custom errors, modifiers, and downstream library checks. Pick invariants that observe external post-state, fork-to-fork deltas, custody, oracle answers, or dependent contract effects that those guards do not fully express.

## File Organization

Use this shape unless the local category already uses a more specific pattern:

```solidity
/// @title ProtocolAssertion
/// @notice Protects the protocol's most important accounting and risk invariants.
/// - Reuses the existing suite surface for standard category checks.
/// - Adds protocol-specific assertions only where the base suite cannot express the property.
/// - Keeps helper-heavy state retrieval outside the main assertion contract.
contract ProtocolAssertion is ExistingBaseAssertion, ProtocolHelpers {
    constructor(/* addresses, thresholds */) ExistingBaseAssertion(/* ... */) {}

    function triggers() external view override {
        _registerExistingSuiteTriggers();
        _registerProtocolSpecificTriggers();
    }

    /// @notice Checks the core protocol property after the relevant trigger.
    /// - Compares the protocol's user-facing accounting to held assets or risk state.
    /// - Fails when the triggering transaction leaves value undercollateralized or unsafe.
    /// - Keeps protocol reads in helpers so the property remains readable.
    function assertCriticalProperty() external {
        // short, direct property check
    }
}
```

Put non-trivial state retrieval in helpers:

- Protocol address getters and immutable wiring.
- Struct assembly from several calls.
- Fork-aware reads and decoded call-context helpers.
- Selector registration groups.
- Unit/decimal normalization.
- Protocol interfaces and selector constants when direct imports are unavailable or noisy.

Keep assertion functions readable enough to present in documentation or a PR review. A reader should understand the property without tracing through many private helpers.

## Base-Suite Extension Rules

Modify the base suite when all are true:

- The helper or invariant is category-level, not protocol-branded.
- The abstraction reduces duplicate code or exposes a protection-suite primitive more cleanly.
- Existing examples can adopt it without contorting their logic.
- Tests or examples show the new surface in use.

Keep logic protocol-local when any are true:

- It depends on named protocol contracts, unusual selector overloads, or bespoke accounting.
- It encodes a threshold that only makes sense for one deployment.
- It needs one-off storage layout details.
- It would make the base suite harder to explain.

## Presentation Rules

- Use clear contract and function names: `assertPoolCustodyCoversBalances`, `assertPostOperationSolvency`, `assertVirtualPriceNonDecreasing`.
- Prefer one assertion per property. Split when failure messages or triggers differ materially.
- Use constants and named thresholds instead of magic numbers.
- Add NatSpec for invariant intent, trigger rationale, and tolerated rounding/deviation.
- Every assertion contract must include a few lines or bullets summarizing what it protects, what suite surface it reuses, and what protocol-specific risk remains.
- Every assertion function must include a few lines or bullets summarizing the checked property, the trigger context, and what a failure means.
- Do not include the words "executive summary" in these comments.
- Use explicit revert messages that describe the broken protocol property.
- Keep imports sorted by source locality and avoid wildcard-style helper dumps.
