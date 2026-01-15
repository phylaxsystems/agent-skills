# Event Parsing

## Basics
- `topics[0]` is the event signature hash.
- Indexed fields are in topics; non-indexed fields are in `data`.

## Pattern
1. `PhEvm.Log[] memory logs = ph.getLogs();`
2. Filter by `log.emitter` and `log.topics[0]`.
3. Decode `log.data` with `abi.decode` in the event field order.

## Aggregation
- Sum all matching events in the transaction to avoid missing multi-call cases.
- Be explicit about which events count toward an accounting invariant.

## Common Pitfalls
- Mixed event overloads with same name but different types.
- Ignoring emitted events from nested contracts (e.g., underlying vaults).
- Logs show emitted events, not intermediate state; backstop with pre/post reads when needed.
