# Invariant Patterns

Use these as starting points. Pick the smallest invariant that blocks the exploit path.

## Monotonicity / Ratio Bounds
- Example: share price must not decrease unless a specific event occurs.
- Observation: pre/post `totalAssets`, `totalSupply` or reserves.
- Triggers: call triggers on vault operations or controller entrypoints.

## Accounting Conservation
- Example: `totalAssets` moves exactly by settled amounts; transfers out are accounted by events.
- Observation: parse events with `getLogs` and compare to post-state.
- Triggers: settlement functions or storage slot changes.

## Rate Limits and Time Windows
- Example: cumulative outflow within a window must not exceed a limit.
- Observation: pre/post cumulative counters + timestamp reset logic.
- Triggers: outflow entrypoints (borrow, redeem, rebalancer).

## Upgradeability and Initialization
- Example: implementation slot changes only by admin; initializers called once.
- Observation: pre/post `ph.load` on EIP-1967 slots; call input checks for upgrade selectors.
- Triggers: storage change on implementation/admin slots or call triggers on upgrade functions.

## Authorization on Sensitive Changes
- Example: implementation slot changes only via ProxyAdmin; mint only by Minter.
- Observation: pre/post `ph.load` on EIP-1967 slots + `getCallInputs` for upgrade or mint selectors.
- Triggers: storage change on the slot or call trigger on upgrade/mint.

## Solvency / Reserve Coverage
- Example: reserved <= total in pools; vault balance >= cash; gauge rewards balance >= liabilities.
- Observation: post-state view functions; sometimes need loops over reward tokens.
- Triggers: reserve updates, position execution, or storage change on reserve slots.

## Coupling Invariants
- Example: if `totalDebt > 0`, then `baseCollateral > 0`.
- Observation: post-state struct read.
- Triggers: functions that mutate either side of the coupling.

## Cross-Contract Health
- Example: account health must remain healthy across controller vaults.
- Observation: extract affected accounts from call inputs, then check each controller.
- Triggers: call triggers on protocol entrypoints that touch accounts.

## Oracle Sanity and Cross-Feed Deviation
- Example: prices must be non-zero, fresh, and within per-symbol deltas.
- Observation: read price + staleness; compare two feeds with a bounded delta.
- Triggers: risk-critical entrypoints (borrow, liquidate, execute).

## Token Integration Safety
- Example: fee-on-transfer, rebasing, missing return values, or low/high decimals.
- Observation: prefer balance deltas over return values; validate decimal assumptions.
- Triggers: transfer/mint/burn entrypoints and accounting updates.

## Mode Exclusivity
- Example: sync deposit allowed only when NAV valid; async otherwise.
- Observation: post-state `isTotalAssetsValid()` or expiration slot.
- Triggers: call triggers on both sync and async entrypoints.

## Supply/Cap Bounds
- Example: totalSupply <= cap; emissions multiplier within range.
- Observation: post-state reads and optional pre/post comparison.
- Triggers: storage change or call triggers on mint/update functions.

## Exception-Gated Invariants
- Example: share price cannot decrease unless a specific event (bad debt) occurs.
- Observation: pre/post ratio + event scan in the same transaction.
- Triggers: call triggers on protocol entrypoints, with event-based exceptions.

## Timelocks and Cooling Periods
- Example: upgrade or admin actions only after min delay; no rapid multisig threshold changes.
- Observation: pre/post timelock fields + timestamps; call inputs for execute/upgrade.
- Triggers: call triggers on execute/upgrade or storage triggers on delay/threshold slots.

## Emergency Pause Modes
- Example: when paused, only withdrawals allowed; balances cannot increase.
- Observation: pre/post pause flag + balance deltas; call inputs for deposit/mint.
- Triggers: call triggers on entrypoints or storage trigger on pause slot.

## AMM Math and Fee Invariants
- Example: constant product maintained; tick stays within bounds; fee only from whitelist.
- Observation: reserve product, tick state, fee slot changes.
- Triggers: storage change on reserve/tick/fee slots; call triggers on swap/mint/burn.

## ERC4626 Accounting
- Example: assets/shares consistency; preview* matches actual; share value monotonic.
- Observation: pre/post assets + supply + preview outputs; call inputs for deposit/withdraw.
- Triggers: call triggers on ERC4626 entrypoints, optional storage trigger on totalSupply.

## Price Liveness and Deviation
- Example: oracle updates within time window; price deviation within bps; intra-tx deviations.
- Observation: post-state timestamp + per-call price checks via forkPostCall.
- Triggers: call triggers on price update or risk-critical functions (borrow/liquidate).

## Drain and Outflow Limits
- Example: per-tx outflow capped; large transfers only to whitelisted recipients.
- Observation: pre/post balance delta; optional recipient allowlist via call inputs.
- Triggers: balance trigger for ETH; call triggers on transfer/withdraw.

## Rounding and Proportionality
- Example: withdrawals reduce balances proportional to shares burned.
- Observation: per-call pre/post balances with dynamic tolerance (bps + min 1 wei).
- Triggers: call triggers on withdraw/redeem; use forkPreCall/forkPostCall.

## First-Depositor and Exchange-Rate Floors
- Example: minimum supply after market open; deposit must mint >0 shares.
- Observation: pre/post totalSupply, exchange rate, and deposit amount.
- Triggers: call triggers on deposit/mint or storage trigger on totalSupply slot.
- Use protocol-specific conversion formulas (e.g., virtual deposits) to avoid false positives.

## Phantom Collateral and Value Bounds
- Example: reported collateral/AUM cannot exceed actual extractable value.
- Observation: compare view-reported value vs real token balances + oracle rate.
- Triggers: call triggers on valuation-sensitive entrypoints.

## Configuration and Parameter Bounds
- Example: oracle staleness, price delta, emission multipliers, or timelock delays stay within safe ranges.
- Observation: decode config setter inputs and validate post-state matches.
- Triggers: call triggers on config setters; avoid global storage triggers when possible.
