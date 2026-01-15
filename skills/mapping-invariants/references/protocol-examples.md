# Protocol Example Patterns

Use these as inspiration when mapping invariants.

## Ethereum Vault Connector (EVC)
- Share price monotonicity with bad‑debt exception.
- Exchange‑rate spike bounds (±5%).
- Vault balance ≥ internal cash accounting.
- Asset transfers accounted by Withdraw/Borrow/Deposit events.
- Account health must not degrade after EVC calls (batch/call/controlCollateral).
- Note: decode nested batch/call payloads to extract real targets and accounts.

## Lagoon v0
- Sync vs async deposit mode exclusivity.
- NAV validity lifecycle: expiration, lifespan, manual expire.
- Epoch isolation: syncDeposit does not affect epoch counters.
- Uses unstructured storage offsets for packed NAV metadata.

## Myx v2
- Order fill bounds: filledSize ≤ size.
- Pool reserve solvency: reserved ≤ total.
- Transaction‑level collateral accounting (net deltas).
- Debt‑collateral coupling: debt implies collateral.

## Malda Lending
- Outflow limiter: cumulative USD outflows within a window.
- Oracle config bounds: staleness, max deltas, per‑symbol limits.
- Rebalancer allowlists + transfer size limits + rate limits.
- Oracle price sanity and cross‑feed deviation on borrow.
- Uses downstream call verification for bridge sends.

## Etherex
- Timelock min delay.
- Emissions multiplier bounds by epoch.
- Authorized minting only by Minter.
- Proxy admin ownership and upgrade authorization.
