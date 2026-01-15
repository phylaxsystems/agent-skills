# Tolerance and Rounding

## When to Use Tolerances
- Value conversions that involve prices or exchange rates.
- Aggregation over multiple events with rounding/decimals.
- Cross-feed comparisons with oracle rounding differences.

## Guidelines
- Keep tolerances minimal and justified (e.g., 0.1% for USD conversions).
- Derive tolerance from input magnitude (basis points).
- Avoid fixed absolute tolerances unless token decimals are fixed.

## Example Pattern
```solidity
uint256 tolerance = expected / 1000; // 0.1%
require(actual >= expected - tolerance && actual <= expected + tolerance, "Value mismatch");
```

## Dynamic Minimums
For tiny amounts, add a 1 wei floor to avoid false positives from rounding:
```solidity
uint256 tolerance = expected / 100 + 1; // 1% + 1 wei minimum
```

## Anti-Patterns
- Unbounded tolerances that hide real violations.
- Using tolerance to compensate for logic errors.
