# Invariant Mapping Workflow

## Step 1: Protocol Map
- **Assets**: tokens, vault balances, reserves, accounting units.
- **Roles**: owner/admin/timelock, guardians, rebalancer EOAs, oracles.
- **Entrypoints**: external functions that move value or modify critical state.
- **Critical state**: totals, exchange rates, health factors, caps, expirations.

## Step 2: Invariant Inventory (by category)
- **Access control**: only authorized upgrades, minting, role changes.
- **Accounting**: balance deltas match events and internal counters.
- **Pricing**: oracle liveness, deviation bounds, cross‑feed sanity.
- **Solvency**: reserves/borrowed/collateral relationships.
- **Limits**: caps, rate limits, timelock delays, emissions bounds.
- **Modes**: pause/upgrade/deposit modes are mutually exclusive.
- **Cross‑contract**: routing or controller invariants across modules.

## Step 3: Exceptions
Examples:
- Bad‑debt socialization can allow share‑price decreases.
- Emergency mode allows withdrawals but blocks deposits.
- Initial epochs can permit calibration outside bounds.

## Step 4: Observation Plan
Decide how to observe each invariant:
- **State**: pre/post values, storage slots, mapping entries.
- **Logs**: Transfer/Withdraw/Borrow/Deposit events for accounting.
- **Call inputs**: decode parameters and verify outcomes.
- **Call frames**: per‑call checks with `forkPreCall`/`forkPostCall`.

## Step 5: Trigger Plan
- **Call triggers**: for specific operations (withdraw, liquidate, upgrade).
- **Storage triggers**: for slots that can change via multiple paths.
- **Balance triggers**: for ETH outflows.

## Step 6: Coverage Matrix
For each invariant:
- **Where it runs** (selector/slot/balance).
- **What it reads** (state/logs/inputs).
- **Exceptions** (explicit checks).
- **Priority** (P0/P1/P2).
