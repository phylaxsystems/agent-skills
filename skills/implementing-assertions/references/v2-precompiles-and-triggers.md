# V2 Precompiles And Triggers Digest

Use this portable digest when writing Credible Layer V2 assertions. It intentionally captures the pieces most useful for high-signal protocol invariants; verify exact signatures against a vendored `credible-std` when a target repo has one.

## Core Model

- Assertions inherit `Assertion`, which exposes `ph` for `PhEvm` reads and internal trigger registration helpers.
- `triggers()` registers when assertion functions execute. Prefer V2 triggers for new assertions.
- Fork IDs describe read snapshots: PreTx, PostTx, PreCall, and PostCall. Use fork-aware reads instead of legacy fork switching.
- `ph.context()` is available only inside assertions fired by `registerFnCallTrigger`.
- V2 Reshiram assertion examples should be stateless over fork/call snapshots. Do not use custom persistent assertion storage as a design pattern.
- Circuit breakers are the exception: rolling-window inflow/outflow state is handled by the built-in trigger/precompile machinery, not by assertion-authored storage.

Common fork helpers in current `Assertion` implementations:

```solidity
PhEvm.ForkId memory pre = _preTx();
PhEvm.ForkId memory post = _postTx();
PhEvm.ForkId memory preCall = _preCall(ctx.callStart);
PhEvm.ForkId memory postCall = _postCall(ctx.callEnd);
```

## Trigger Selection

Use `registerTxEndTrigger(assertFn)` when the invariant is about the whole transaction:

- custody covers liabilities after all side effects
- protected balances/slots are unchanged across PreTx to PostTx
- oracle values or exchange rates did not drift beyond tolerance
- aggregate solvency, debt, reserves, or fee bounds hold at transaction end

Use `registerFnCallTrigger(assertFn, selector)` when the invariant must be checked per matching call:

- share price, health factor, or quote consistency around a specific operation
- input/output decoding is needed with `ph.callinputAt(ctx.callStart)` or `ph.callOutputAt(ctx.callStart)`
- each deposit, withdraw, borrow, repay, swap, liquidate, or admin call needs its own pre/post-call boundary

Use `registerErc20ChangeTrigger(assertFn, token)` when any balance movement of a token should cause a check:

- custody, escrow, reserve, or treasury balances must still cover accounting
- token movements can happen through multiple protocol entry points
- call selectors are incomplete or too easy to bypass

Use `watchCumulativeOutflow(token, thresholdBps, windowDuration, assertFn)` for circuit breakers:

- vault assets, treasuries, escrows, bridges, AMM reserves, or lending reserves should not leave too quickly
- the invariant is a rolling-window risk limit rather than a single-call property
- use this instead of writing custom stateful tracking for cumulative exits
- read `ph.outflowContext()` only inside the triggered assertion if selector-aware smart breaker logic is needed

Use `watchCumulativeInflow(token, thresholdBps, windowDuration, assertFn)` for suspicious inflows:

- manipulated donations, reserve stuffing, oracle/price manipulation via token inflows, or accounting skew
- use this instead of writing custom stateful tracking for cumulative entries
- read `ph.inflowContext()` only inside the triggered assertion if the assertion needs window details

Use storage triggers sparingly:

- `registerStorageChangeTrigger(assertFn, slot)` for protected implementation/admin/config slots
- `registerStorageChangeTrigger(assertFn)` only when broad storage writes are the direct risk and gas/noise are acceptable

## Fork Reads And Call Inspection

Use `ph.staticcallAt(target, data, gasLimit, fork)` to read protocol state at a snapshot:

- total assets, total supply, reserves, debt, collateral, health factor, price, utilization, config
- prefer typed helper functions that decode return data and revert clearly when the read fails

Use `ph.loadStateAt(target, slot, fork)` when a public getter is unavailable or slot protection is the property:

- proxy implementation/admin slots
- packed configuration values
- storage-layout-specific assertions after verifying layout from source

Use `ph.callinputAt(callId)` and `ph.callOutputAt(callId)` inside call-triggered assertions:

- decode arguments and outputs for preview/actual consistency
- `ph.callinputAt` returns raw calldata including the selector; strip the first 4 bytes before ABI-decoding arguments
- compare a swap quote to actual output
- check that user/share/account deltas match the operation result

Use `ph.matchingCalls(target, selector, filter, limit)` when an assertion must detect downstream calls:

- confirm whether a triggered operation called a known oracle, vault, pool, or escrow
- bound side effects on dependent contracts
- avoid using it only to assert that a function was called unless that call is part of a larger safety property

Use `ph.getLogsForCall(query, callId)` or `ph.getLogsQuery(query, fork)` when logs are the safest observable:

- ERC events not exposed through state
- per-call emitted amounts where state deltas are expensive or ambiguous
- do not treat logs as stronger than state when state can be read directly

Use ERC20 transfer helpers when asset flow is the invariant:

- `ph.getErc20Transfers(token, fork)`
- `ph.getErc20TransfersForTokens(tokens, fork)`
- `ph.changedErc20BalanceDeltas(token, fork)`
- `ph.reduceErc20BalanceDeltas(token, fork)`

## Protection-Suite Precompiles

Use `ph.assetsMatchSharePrice(vault, toleranceBps)` for transaction-wide ERC-4626-style share price consistency:

- vault share price should not drift beyond tolerance across transaction fork points
- pair with an explicit PreTx/PostTx ratio comparison when readability matters
- best for vaults, wrapped assets, receipt-token systems, and share-based staking

Use `ph.assetsMatchSharePriceAt(vault, toleranceBps, fork0, fork1)` for per-call share price checks:

- deposit/mint/withdraw/redeem or strategy operations should not dilute holders around one call
- read call context with `ph.context()`

Use `ph.conserveBalance(fork0, fork1, token, account)` for protected external balances:

- treasury, escrow, reserve, bridge, fee receiver, or custody account balance must not change on a path
- especially useful for external state requirements not encoded by protocol `require`s
- use selector-aware custom logic when some authorized functions may move the balance

Use `ph.oracleSanity(target, data, bpsDeviation)` for transaction-wide oracle consistency:

- oracle answer must stay initialized and within deviation across fork points
- applies to price feeds, TWAP reads, exchange-rate oracles, and dependent oracle adapters

Use `ph.oracleSanityAt(target, data, bpsDeviation, fork0, fork1)` for a specific pre/post boundary:

- risk-increasing calls should not rely on a materially different price before and after one call
- pair with protocol-level solvency checks for lending/perpetuals

Use math precompiles for readable ratio and unit checks:

- `ph.mulDivDown(x, y, denominator)` and `ph.mulDivUp(x, y, denominator)` for precise proportional math
- `ph.normalizeDecimals(amount, fromDecimals, toDecimals)` for cross-token accounting
- `ph.ratioGe(num1, den1, num2, den2, toleranceBps)` for monotonic ratio checks without ad hoc division

## External-State Invariant Patterns

Prefer invariants that observe something outside a single function's local guards:

- token balance of vault/pool/escrow/treasury covers user-facing liabilities after mutation
- shares, debt, collateral, reserves, and external ERC20 balances move consistently
- oracle answers used for risk are initialized, bounded, and stable across the relevant fork boundary
- protected admin/config slots and external balances do not change during unrelated user operations
- cumulative flows stay below thresholds even when many individually-valid calls are combined
- liquidation, deleveraging, or settlement improves account risk in post-state

Avoid invariants that only re-check:

- input bounds already guarded by `require`
- sender/role checks already enforced by modifiers
- zero address checks or paused-state branches already present on the exact path
- arithmetic equality that is brittle under rounding, interest accrual, or asynchronous oracle updates
- custom stateful counters, baselines, or rolling windows maintained by the assertion contract itself

## Minimal V2 Assertion Shape

```solidity
contract ProtocolAssertion is Assertion {
    address immutable protocol;
    address immutable token;

    constructor(address protocol_, address token_) {
        protocol = protocol_;
        token = token_;
    }

    function triggers() external view override {
        registerTxEndTrigger(this.assertCustodyCoversAccounting.selector);
        registerFnCallTrigger(this.assertPerCallRisk.selector, IProtocol.borrow.selector);
    }

    /// @notice Checks external custody against protocol accounting after the transaction.
    /// - Reads accounting and token custody at PreTx/PostTx snapshots.
    /// - Fails when valid protocol calls leave external assets below liabilities.
    function assertCustodyCoversAccounting() external {
        // Use staticcallAt/conserveBalance/helper reads, then require the protocol property.
    }

    /// @notice Checks a risk-increasing call leaves the account safe in post-state.
    /// - Uses the V2 call context for per-call fork boundaries.
    /// - Fails when the operation passes local requires but leaves external risk unsafe.
    function assertPerCallRisk() external {
        PhEvm.TriggerContext memory ctx = ph.context();
        // Decode input or compare _preCall(ctx.callStart) to _postCall(ctx.callEnd).
    }
}
```
