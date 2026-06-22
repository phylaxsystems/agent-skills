#!/usr/bin/env python3
"""Normalize PCL incident trace JSON/text into compact triage rows.

This is intentionally lightweight: it extracts the rows agents most often need
before reasoning, while leaving full EVM decoding to PCL/RPC/explorer tools.
It focuses on deterministic evidence from the trace: token calls, emitted
token/vault events, allowance reads, and raw balance-change deltas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
TRANSFER_FROM_RE = re.compile(
    r"(?P<token>0x[a-fA-F0-9]{40})::transferFrom\("
    r"(?P<src>0x[a-fA-F0-9]{40}),\s*"
    r"(?P<dst>0x[a-fA-F0-9]{40}),\s*"
    r"(?P<amount>[0-9]+)"
)
TRANSFER_RE = re.compile(
    r"(?P<token>0x[a-fA-F0-9]{40})::transfer\("
    r"(?P<dst>0x[a-fA-F0-9]{40}),\s*"
    r"(?P<amount>[0-9]+)"
)
APPROVE_RE = re.compile(
    r"(?P<token>0x[a-fA-F0-9]{40})::approve\("
    r"(?P<spender>0x[a-fA-F0-9]{40}),\s*"
    r"(?P<amount>[0-9]+)"
)
ALLOWANCE_RE = re.compile(
    r"(?P<token>0x[a-fA-F0-9]{40})::allowance\("
    r"(?P<owner>0x[a-fA-F0-9]{40}),\s*"
    r"(?P<spender>0x[a-fA-F0-9]{40})\)"
)
CALL_RE = re.compile(
    r"(?P<contract>0x[a-fA-F0-9]{40})::(?P<function>[A-Za-z_][A-Za-z0-9_]*)\("
)
EVENT_RE = re.compile(r"emit\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\((?P<params>.*)\)")
RETURN_RE = re.compile(r"\[Return\]\s+(?P<value>0x[a-fA-F0-9]+|[0-9]+)")
UUID_RE = re.compile(
    r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"
)
TRACE_CONTENT_KEYS = ("transaction_trace_content", "assertion_trace_content", "trace_content")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def first_nested(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = first_nested(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = first_nested(value, key)
            if found is not None:
                return found
    return None


def all_nested(obj: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(obj, dict):
        if key in obj:
            found.append(obj[key])
        for value in obj.values():
            found.extend(all_nested(value, key))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(all_nested(value, key))
    return found


def trace_parts(debug_trace: dict[str, Any]) -> list[str]:
    parts = []
    for key in TRACE_CONTENT_KEYS:
        value = debug_trace.get(key)
        if value:
            parts.append(str(value))
    return parts


def debug_trace_candidates(obj: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for value in all_nested(obj, "debug_trace"):
        if isinstance(value, dict):
            candidates.append(value)

    for value in all_nested(obj, "debug_traces"):
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            candidates.append(value)

    if isinstance(obj, dict) and any(obj.get(key) for key in TRACE_CONTENT_KEYS):
        candidates.append(obj)

    traces: list[dict[str, Any]] = []
    seen: set[int] = set()
    for candidate in candidates:
        candidate_id = id(candidate)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        traces.append(candidate)
    return traces


def debug_trace_summary(index: int, debug_trace: dict[str, Any], has_content: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "index": index,
        "status": debug_trace.get("status"),
        "trace_present": has_content,
    }
    for key in ("id", "type", "request_id", "error", "error_message"):
        if debug_trace.get(key) is not None:
            summary[key] = debug_trace.get(key)
    return summary


def status_summary(statuses: list[Any]) -> tuple[Any, dict[str, int]]:
    counts: dict[str, int] = {}
    for status in statuses:
        key = str(status) if status is not None else "unknown"
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None, counts
    if len(counts) == 1:
        return next(iter(counts)), counts
    return "mixed", counts


def trace_text_from_json(obj: Any) -> tuple[str, dict[str, Any]]:
    tx = first_nested(obj, "invalidating_transaction") or {}
    debug_traces = debug_trace_candidates(obj)
    parts = []
    debug_trace_results = []
    for index, debug_trace in enumerate(debug_traces):
        current_parts = trace_parts(debug_trace)
        parts.extend(current_parts)
        debug_trace_results.append(debug_trace_summary(index, debug_trace, bool(current_parts)))

    debug_trace_statuses = [result.get("status") for result in debug_trace_results]
    debug_trace_status, debug_trace_status_counts = status_summary(debug_trace_statuses)

    meta = {
        "incident_id": first_nested(obj, "incident_id"),
        "pcl_tx_id": tx.get("id") if isinstance(tx, dict) else None,
        "transaction_hash": tx.get("transaction_hash") if isinstance(tx, dict) else None,
        "from_address": tx.get("from_address") if isinstance(tx, dict) else None,
        "to_address": tx.get("to_address") if isinstance(tx, dict) else None,
        "block_number": tx.get("block_number") if isinstance(tx, dict) else None,
        "landed_on_chain": tx.get("landed_on_chain") if isinstance(tx, dict) else None,
        "revert_reason": tx.get("revert_reason") if isinstance(tx, dict) else None,
        "debug_trace_status": debug_trace_status,
        "debug_trace_statuses": debug_trace_statuses,
        "debug_trace_status_counts": debug_trace_status_counts,
        "debug_trace_results": debug_trace_results,
        "debug_trace_count": len(debug_trace_results),
        "debug_trace_present_count": sum(1 for result in debug_trace_results if result["trace_present"]),
        "trace_present": bool(parts),
    }
    return "\n".join(parts), meta


def parse_event_params(params_text: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for idx, chunk in enumerate(params_text.split(",")):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            key, value = chunk.split(":", 1)
            params[key.strip()] = value.strip()
        else:
            params[f"param{idx}"] = chunk
    return params


def raw_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    return None


def balance_delta(address: str, raw_amount: str, sign: int, source: str) -> dict[str, Any]:
    amount = raw_int(raw_amount)
    return {
        "address": address,
        "raw_delta": str(sign * amount) if amount is not None else None,
        "raw_amount": raw_amount,
        "direction": "increase" if sign > 0 else "decrease",
        "source": source,
    }


def classify_event(
    name: str,
    params: dict[str, str],
    emitting_contract: str | None,
    line: str,
    delegate_context: bool,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event": name,
        "emitting_contract": emitting_contract,
        "params": params,
        "delegate_context": delegate_context,
        "line": line.strip(),
    }

    if name == "Transfer":
        from_address = params.get("from") or params.get("src") or params.get("param0")
        to_address = params.get("to") or params.get("dst") or params.get("param1")
        amount = params.get("value") or params.get("wad") or params.get("amount") or params.get("param2")
        event.update(
            {
                "standard": "ERC20",
                "from": from_address,
                "to": to_address,
                "raw_amount": amount,
                "balance_changes": (
                    [
                        balance_delta(from_address, amount, -1, "ERC20.Transfer"),
                        balance_delta(to_address, amount, 1, "ERC20.Transfer"),
                    ]
                    if from_address and to_address and amount
                    else []
                ),
            }
        )
    elif name == "Approval":
        event.update(
            {
                "standard": "ERC20",
                "owner": params.get("owner") or params.get("param0"),
                "spender": params.get("spender") or params.get("param1"),
                "raw_amount": params.get("value") or params.get("amount") or params.get("param2"),
            }
        )
    elif name == "Deposit":
        # WETH Deposit(dst, wad) has 2 params; ERC4626 Deposit(sender, owner, assets, shares) has 4.
        if "param3" in params or "shares" in params:
            event.update(
                {
                    "standard": "ERC4626",
                    "sender": params.get("sender") or params.get("param0"),
                    "owner": params.get("owner") or params.get("param1"),
                    "raw_assets": params.get("assets") or params.get("param2"),
                    "raw_shares": params.get("shares") or params.get("param3"),
                }
            )
        else:
            dst = params.get("dst") or params.get("param0")
            amount = params.get("wad") or params.get("amount") or params.get("param1")
            event.update(
                {
                    "standard": "WETH",
                    "to": dst,
                    "raw_amount": amount,
                    "balance_changes": (
                        [balance_delta(dst, amount, 1, "WETH.Deposit")] if dst and amount else []
                    ),
                }
            )
    elif name in ("Withdrawal", "Withdraw"):
        # WETH Withdrawal(src, wad) has 2 params; ERC4626 Withdraw has 5.
        if name == "Withdraw" or "param4" in params or "shares" in params:
            event.update(
                {
                    "standard": "ERC4626",
                    "sender": params.get("sender") or params.get("param0"),
                    "receiver": params.get("receiver") or params.get("param1"),
                    "owner": params.get("owner") or params.get("param2"),
                    "raw_assets": params.get("assets") or params.get("param3"),
                    "raw_shares": params.get("shares") or params.get("param4"),
                }
            )
        else:
            src = params.get("src") or params.get("param0")
            amount = params.get("wad") or params.get("amount") or params.get("param1")
            event.update(
                {
                    "standard": "WETH",
                    "from": src,
                    "raw_amount": amount,
                    "balance_changes": (
                        [balance_delta(src, amount, -1, "WETH.Withdrawal")] if src and amount else []
                    ),
                }
            )
    return event


def parse_trace(text: str) -> dict[str, Any]:
    clean = strip_ansi(text)
    lines = clean.splitlines()
    transfer_from_calls: list[dict[str, Any]] = []
    transfer_calls: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    allowance_checks: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    last_call_contract: str | None = None
    last_call_delegate = False

    for i, line in enumerate(lines):
        call = CALL_RE.search(line)
        if call:
            last_call_contract = call.group("contract")
            last_call_delegate = "[delegatecall]" in line

        transfer = TRANSFER_FROM_RE.search(line)
        if transfer and "[delegatecall]" not in line:
            transfer_from_calls.append(
                {
                    "token": transfer.group("token"),
                    "source_owner": transfer.group("src"),
                    "recipient": transfer.group("dst"),
                    "raw_amount": transfer.group("amount"),
                    "line": line.strip(),
                }
            )

        direct_transfer = TRANSFER_RE.search(line)
        if direct_transfer and "[delegatecall]" not in line and "transferFrom(" not in line:
            transfer_calls.append(
                {
                    "token": direct_transfer.group("token"),
                    "recipient": direct_transfer.group("dst"),
                    "raw_amount": direct_transfer.group("amount"),
                    "line": line.strip(),
                }
            )

        approve = APPROVE_RE.search(line)
        if approve and "[delegatecall]" not in line:
            approvals.append(
                {
                    "token": approve.group("token"),
                    "spender": approve.group("spender"),
                    "raw_amount": approve.group("amount"),
                    "line": line.strip(),
                }
            )

        allowance = ALLOWANCE_RE.search(line)
        if allowance and "[delegatecall]" not in line:
            value = None
            for lookahead in lines[i + 1 : i + 5]:
                returned = RETURN_RE.search(lookahead)
                if returned:
                    value = returned.group("value")
                    break
            allowance_checks.append(
                {
                    "token": allowance.group("token"),
                    "owner": allowance.group("owner"),
                    "spender": allowance.group("spender"),
                    "returned": value,
                    "line": line.strip(),
                }
            )

        emitted = EVENT_RE.search(line)
        if emitted:
            events.append(
                classify_event(
                    emitted.group("name"),
                    parse_event_params(emitted.group("params")),
                    last_call_contract,
                    line,
                    last_call_delegate,
                )
            )

    event_balance_changes = [
        {**change, "token": event.get("emitting_contract"), "event": event.get("event")}
        for event in events
        for change in event.get("balance_changes", [])
    ]

    return {
        "transfers": transfer_from_calls,
        "transfer_from_calls": transfer_from_calls,
        "transfer_calls": transfer_calls,
        "approvals": approvals,
        "events": events,
        "event_balance_changes": event_balance_changes,
        "allowance_checks": allowance_checks,
        "transfer_count": len(transfer_from_calls),
        "transfer_from_call_count": len(transfer_from_calls),
        "transfer_call_count": len(transfer_calls),
        "approval_call_count": len(approvals),
        "event_count": len(events),
        "event_balance_change_count": len(event_balance_changes),
        "allowance_check_count": len(allowance_checks),
    }


def parse_file(path: Path) -> dict[str, Any]:
    raw = path.read_text(errors="replace")
    meta: dict[str, Any] = {
        "source_file": str(path),
        "incident_id": None,
        "pcl_tx_id": None,
        "transaction_hash": None,
        "debug_trace_status": None,
        "debug_trace_statuses": [],
        "debug_trace_status_counts": {},
        "debug_trace_results": [],
        "debug_trace_count": 0,
        "debug_trace_present_count": 0,
        "trace_present": bool(raw.strip()),
    }

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        trace_text = raw
    else:
        trace_text, meta = trace_text_from_json(obj)
        meta["source_file"] = str(path)

    parsed = parse_trace(trace_text)
    uuids = UUID_RE.findall(path.name)
    if meta.get("incident_id") is None and uuids:
        meta["incident_id"] = uuids[0]
    if meta.get("pcl_tx_id") is None and len(uuids) > 1:
        meta["pcl_tx_id"] = uuids[1]
    return {**meta, **parsed}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract token calls, events, balance deltas, and allowance rows from PCL trace JSON/text."
    )
    parser.add_argument("files", nargs="+", help="PCL trace JSON/text files")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    records = [parse_file(Path(file_name)) for file_name in args.files]
    output = {"records": records}
    json.dump(output, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
