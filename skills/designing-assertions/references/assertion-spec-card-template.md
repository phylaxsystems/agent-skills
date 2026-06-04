# Assertion Spec Card Template

Create one card per selected invariant before writing Solidity. Keep it concise enough for the coordinator, reviewer, and report writer to scan.

```md
# <Invariant Name>

## Protocol Surface

- Category: <vault | lending | swaps | perpetual | access_control | other>
- Contracts:
- Protected functions/selectors:
- Trigger type: <tx-end | function-call | ERC20-change | cumulative-inflow | cumulative-outflow | storage-change>

## Property

- Invariant:
- Protected value:
- Why this matters:
- Why this is stronger than existing protocol `require`/custom-error checks:

## State And Data Reads

- Pre-state reads:
- Post-state reads:
- Call input/output decoding:
- External contracts or tokens:
- Tolerances:

## Expected Exceptions

- Legitimate cases that should not trip:
- Empty/uninitialized cases:
- Rounding, accrual, oracle latency, or async effects:

## Implementation Plan

- Assertion contract:
- Helper/interface files:
- Reused suite surface or precompile:
- New protocol-local logic:
- Revert reason:

## Test Plan

- Honest path:
- Failing path:
- Mocks or knobs needed:
- `pcl test` selector/path:

## Liveness And Report Relevance

- Related liveness surface:
- Metrics or evidence that would make the report stronger:
- Open gaps:
```
