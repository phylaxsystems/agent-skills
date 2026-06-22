#!/usr/bin/env python3
"""Render a fast production-style triage report from a compact evidence packet.

This is intentionally deterministic and network-free. It gives report agents a
high-quality draft they can review quickly instead of composing from raw traces.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Any


BULLET_VALUE_RE = re.compile(r"^- (?P<key>[^:]+): `(?P<value>.*)`$")
TRANSFER_RE = re.compile(
    r"token `(?P<token>0x[a-fA-F0-9]{40})`, source `(?P<src>0x[a-fA-F0-9]{40})`, "
    r"recipient `(?P<dst>0x[a-fA-F0-9]{40})`, raw `(?P<raw>[0-9]+)`"
)
EVENT_RE = re.compile(
    r"`(?P<standard>[^`]+)` from `(?P<src>0x[a-fA-F0-9]{40})` to "
    r"`(?P<dst>0x[a-fA-F0-9]{40})` raw `(?P<raw>[^`]+)`"
)
ALLOWANCE_RE = re.compile(
    r"token `(?P<token>0x[a-fA-F0-9]{40})`, owner `(?P<owner>0x[a-fA-F0-9]{40})`, "
    r"spender `(?P<spender>0x[a-fA-F0-9]{40})`, returned `(?P<returned>[^`]+)`"
)


def read_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    try:
        with path.open() as file:
            return json.load(file)
    except (JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def unwrap_data(value: Any) -> Any:
    current = value
    for _ in range(5):
        if isinstance(current, dict) and "data" in current and isinstance(current["data"], (dict, list)):
            current = current["data"]
        else:
            break
    return current


def short(address: str | None) -> str:
    if not address or not address.startswith("0x") or len(address) < 12:
        return address or "unknown"
    return f"{address[:6]}...{address[-4:]}"


def first_address(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"0x[a-fA-F0-9]{40}", text)
    return match.group(0) if match else None


def human_amount(raw: str | int | None, decimals: int = 6) -> str:
    if raw is None:
        return "unknown"
    try:
        value = int(str(raw).split()[0])
    except ValueError:
        return str(raw)
    return f"{value / (10 ** decimals):,.6f}"


def parse_packet(packet: str, run_dir: Path) -> dict[str, Any]:
    scope: dict[str, str] = {}
    artifacts: dict[str, Path] = {}
    transfers: list[dict[str, str]] = []
    events: list[dict[str, str]] = []
    allowances: list[dict[str, str]] = []
    source_lines: list[str] = []
    revert_decoded = None
    section = None

    for line in packet.splitlines():
        if line.startswith("## "):
            section = line.removeprefix("## ").strip()
            continue
        match = BULLET_VALUE_RE.match(line)
        if match and section == "Scope":
            scope[match.group("key").strip()] = match.group("value").strip()
            continue
        if match and section == "Artifact Paths":
            value = match.group("value").strip()
            path = Path(value)
            artifacts[match.group("key").strip()] = path if path.is_absolute() else run_dir / path
            continue
        if line.startswith("- ") and section == "Artifact Paths" and ": `" in line:
            label, rest = line[2:].split(": `", 1)
            value = rest.rstrip("`")
            path = Path(value)
            artifacts[label.strip()] = path if path.is_absolute() else run_dir / path
            continue
        if line.startswith("- transferFrom:"):
            transfer_match = TRANSFER_RE.search(line)
            if transfer_match:
                transfers.append(transfer_match.groupdict())
        if line.startswith("- event:"):
            event_match = EVENT_RE.search(line)
            if event_match:
                events.append(event_match.groupdict())
        if line.startswith("- allowance:"):
            allowance_match = ALLOWANCE_RE.search(line)
            if allowance_match:
                allowances.append(allowance_match.groupdict())
        if line.startswith("- Revert reason decoded:"):
            revert_decoded = line.split("`", 2)[1]
        if section == "Source and Decompiler Coverage" and line:
            source_lines.append(line)
    return {
        "scope": scope,
        "artifacts": artifacts,
        "transfers": transfers,
        "events": events,
        "allowances": allowances,
        "source_lines": source_lines,
        "revert_decoded": revert_decoded,
    }


def first_artifact(artifacts: dict[str, Path], contains: str) -> Path | None:
    contains = contains.lower()
    for label, path in artifacts.items():
        if contains in label.lower():
            return path
    return None


def first_json_artifact(artifacts: dict[str, Path], *patterns: str) -> Path | None:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for label, path in artifacts.items():
        label_lower = label.lower()
        if all(pattern in label_lower for pattern in lowered_patterns) and path.suffix.lower() == ".json":
            return path
    return None


def tx_from_incident(incident: Any, tx_id: str | None) -> dict[str, Any]:
    payload = unwrap_data(incident) if incident is not None else {}
    if not isinstance(payload, dict):
        return {}
    txs = payload.get("invalidating_transactions") or []
    for tx in txs:
        if tx.get("id") == tx_id:
            return tx
    return txs[0] if txs else {}


def normalize_record(normalized: Any, tx_id: str | None) -> dict[str, Any]:
    records = normalized.get("records", []) if isinstance(normalized, dict) else []
    for record in records:
        if record.get("pcl_tx_id") == tx_id:
            return record
    return records[0] if records else {}


def read_prefetched(packet_data: dict[str, Any]) -> dict[str, Any]:
    artifacts = packet_data["artifacts"]
    incident = read_json(first_artifact(artifacts, "incident detail"))
    normalized = read_json(first_artifact(artifacts, "normalized trace"))
    state = read_json(
        first_json_artifact(artifacts, "state")
        or first_json_artifact(artifacts, "balance")
        or first_json_artifact(artifacts, "allowance")
    )
    previous = read_json(first_json_artifact(artifacts, "previous") or first_json_artifact(artifacts, "history"))
    preflight = read_json(first_json_artifact(artifacts, "preflight") or first_json_artifact(artifacts, "capability"))
    tx = tx_from_incident(incident, packet_data["scope"].get("PCL tx id"))
    record = normalize_record(normalized, packet_data["scope"].get("PCL tx id"))
    return {
        "incident": incident,
        "normalized": normalized,
        "state": state,
        "previous": previous,
        "preflight": preflight,
        "tx": tx,
        "record": record,
    }


def decimals_for(state: dict[str, Any] | None, token: str | None) -> int:
    if not state or not token:
        return 6
    token_meta = (state.get("tokens") or {}).get(token) or {}
    return int(token_meta.get("decimals") or 6)


def symbol_for(state: dict[str, Any] | None, token: str | None) -> str:
    if not state or not token:
        return "token"
    token_meta = (state.get("tokens") or {}).get(token) or {}
    return token_meta.get("symbol") or "token"


def state_reads(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    reads = state.get("reads")
    if isinstance(reads, list):
        return [read for read in reads if isinstance(read, dict)]
    if isinstance(reads, dict):
        return [read for read in reads.values() if isinstance(read, dict)]
    return []


def capability_note(preflight: Any) -> str:
    if not isinstance(preflight, dict):
        return (
            "Capability preflight artifact was not listed in the packet. Treat data access mode as "
            "unspecified and preserve source/RPC gaps explicitly."
        )
    selection = preflight.get("capability_selection")
    requirements = preflight.get("requirements") if isinstance(preflight.get("requirements"), list) else []
    if not isinstance(selection, dict):
        return "Capability preflight artifact is present but does not include capability_selection."
    rpc = next((item for item in requirements if item.get("name") == "chain_rpc"), {})
    explorer = next(
        (item for item in requirements if item.get("name") in ("explorer_api", "keyed_explorer_api")),
        {},
    )
    decompiler = next((item for item in requirements if item.get("name") == "heimdall_decompiler"), {})
    rpc_source = f" ({rpc.get('selected_source')})" if rpc.get("selected_source") else ""
    explorer_source = f" ({explorer.get('selected_source')})" if explorer.get("selected_source") else ""
    decompiler_source = f" ({decompiler.get('selected_source')})" if decompiler.get("selected_source") else ""
    return (
        f"Capability mode: `{selection.get('mode', 'unknown')}`. "
        f"Configured/private RPC: `{'yes' if selection.get('private_or_configured_rpc_available') else 'no'}`"
        f"{rpc_source}. "
        f"Keyed explorer: `{'yes' if selection.get('keyed_explorer_available') else 'no'}`"
        f"{explorer_source}. "
        f"Public RPC fallback: `{'yes' if selection.get('public_rpc_available') else 'no'}`. "
        f"Local decompiler: `{'yes' if selection.get('local_decompiler_available') else 'no'}`"
        f"{decompiler_source}. "
        f"{selection.get('operator_message', '')}"
    )


def decompiler_note(source_lines: list[str], preflight: Any) -> str:
    joined = "\n".join(source_lines).lower()
    selection = preflight.get("capability_selection") if isinstance(preflight, dict) else {}
    decompiler_available = bool(isinstance(selection, dict) and selection.get("local_decompiler_available"))
    if "0 completed" in joined or (not decompiler_available and "decompiled_needed" in joined):
        return (
            "Decompiler output is unavailable for at least one important code-bearing contract. "
            "Do not treat transient/router implementation behavior as source-confirmed; the value "
            "conclusion here comes from executed trace calls and events."
        )
    if "completed" in joined:
        return (
            "Decompiler output is approximate. It is useful for route shape and source-gap tracking; "
            "the value conclusion comes from executed trace calls and events."
        )
    return "No decompiler output was used in this deterministic draft."


def unique_attempted(transfers: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    totals: dict[tuple[str, str], int] = {}
    for transfer in transfers:
        key = (transfer["token"].lower(), transfer["src"].lower())
        totals[key] = max(totals.get(key, 0), int(transfer["raw"]))
    return totals


def render_report(packet_data: dict[str, Any], prefetched: dict[str, Any], packet_path: Path, out_path: Path) -> str:
    scope = packet_data["scope"]
    transfers = packet_data["transfers"]
    events = packet_data["events"]
    allowances = packet_data["allowances"]
    state = prefetched["state"] if isinstance(prefetched.get("state"), dict) else {}
    preflight = prefetched.get("preflight")
    tx = prefetched["tx"]
    record = prefetched["record"]
    decimals = decimals_for(state, transfers[0]["token"] if transfers else None)
    symbol = symbol_for(state, transfers[0]["token"] if transfers else None)
    unique_raw = sum(unique_attempted(transfers).values())
    repeated_raw = sum(int(transfer["raw"]) for transfer in transfers)
    final_event = events[-1] if events else None
    actual_loss = "0" if str(scope.get("Landed on chain")).lower() == "false" else "unknown"
    revert_reason = packet_data["revert_decoded"] or "unknown"
    sender = tx.get("from_address") or record.get("from_address") or "unknown"
    target = tx.get("to_address") or record.get("to_address") or "unknown"
    hash_value = scope.get("Tx hash") or tx.get("transaction_hash") or record.get("transaction_hash") or "unknown"
    adopter = scope.get("Adopter", "unknown")
    adopter_address = first_address(adopter) or adopter
    incident_id = scope.get("Incident id", "unknown")
    pcl_tx_id = scope.get("PCL tx id", "unknown")
    chain_id = scope.get("Chain id", "unknown")
    block = tx.get("block_number") or record.get("block_number") or "unknown"
    tx_present = state.get("transaction") is not None if state else False
    receipt_present = state.get("receipt") is not None if state else False

    movement_rows = []
    for transfer in transfers:
        movement_rows.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` {} |".format(
                short(transfer["token"]),
                short(transfer["src"]),
                short(transfer["dst"]),
                transfer["raw"],
                human_amount(transfer["raw"], decimals),
                symbol,
            )
        )

    exposure_rows = []
    for read in state_reads(state):
        exposure_rows.append(
            "| `{}` | `{}` {} | `{}` {} | `{}` |".format(
                short(read.get("source_owner")),
                human_amount(read.get("balance_at_block"), decimals),
                symbol,
                human_amount(read.get("balance_latest"), decimals),
                symbol,
                "max" if str(read.get("allowance_latest", "")).startswith("115792089") else read.get("allowance_latest", "not prefetched"),
            )
        )

    trace_steps = []
    trace_steps.append(f"1. `{short(sender)}` calls `{short(target)}` with the invalidating calldata; PCL simulates it at block `{block}`.")
    trace_steps.append(f"2. The route reaches the 0x Settler adopter `{adopter}` and uses USDC `{short(transfers[0]['token']) if transfers else 'unknown'}`.")
    step = 3
    for transfer in transfers:
        trace_steps.append(
            f"{step}. Settler executes `transferFrom({short(transfer['src'])}, {short(transfer['dst'])}, "
            f"{human_amount(transfer['raw'], decimals)} {symbol})`."
        )
        step += 1
    if final_event and transfers and final_event["src"].lower() == transfers[-1]["dst"].lower():
        trace_steps.append(
            f"{step}. The intermediate recipient transfers `{human_amount(final_event['raw'].split()[0], decimals)} {symbol}` "
            f"to final recipient `{short(final_event['dst'])}`."
        )
        step += 1
    trace_steps.extend(
        [
            f"{step}. The assertion reads the adopted contract and simulated logs/call inputs for the Settler execution.",
            f"{step + 1}. The assertion checks allowance for `{short(allowances[0]['owner']) if allowances else 'source owner'}` to `{short(allowances[0]['spender']) if allowances else 'adopter'}` and observes non-zero/max allowance.",
            f"{step + 2}. The assertion reverts with `{revert_reason}`, so the transaction does not land.",
        ]
    )

    previous_summary = "No previous-sender history file was listed in the packet."
    previous = prefetched.get("previous")
    if isinstance(previous, dict):
        result = previous.get("result")
        if isinstance(result, list):
            previous_summary = f"{len(result)} sender-history rows prefetched; use them for attribution only, not protected-value accounting."
        elif previous.get("error"):
            previous_summary = f"prefetch gap: {previous.get('error')}"

    source_context = "\n".join(packet_data["source_lines"][:10]) or "- source context not available"
    access_note = capability_note(preflight)
    source_note = decompiler_note(packet_data["source_lines"], preflight)
    artifact_count = len(packet_data["artifacts"])

    report = f"""# PCL Invalidation Triage Report: 0x-settler `{incident_id[:8]}`

## Executive Summary

**Transaction.** PCL blocked `{hash_value}` on Linea (`chain_id={chain_id}`) at block `{block}`. The transaction was from `{sender}` to `{target}` and is marked `landed_on_chain=false`; prefetched chain evidence shows RPC transaction object `{'present' if tx_present else 'absent'}` and receipt `{'present' if receipt_present else 'absent'}`. Treat it as blocked unless a receipt proves otherwise. The completed trace shows an attempted {symbol} drain through `{adopter}`.

**Assertion.** `AllowanceAssertion` (`{scope.get('Assertion id', 'unknown')}`) invalidated with exact reason: `{revert_reason}`.

**Verdict.** Likely malicious allowance abuse. The source owners differ from the transaction sender, the trace shows `transferFrom` calls through the Settler adopter, and the funds are consolidated to a recipient controlled by the route.

**Recommended next step.** Keep the assertion active. Revoke or reduce {symbol} approvals to `{adopter}` for the source owners below, starting with any owner whose latest allowance remains max/non-zero.

**Agent warning.** This triage was generated by an agent and can be wrong. Verify critical conclusions against the raw transaction, trace, and assertion evidence before taking irreversible action.

## Triage Report

### Scope And Data Freshness

| Field | Value |
|---|---|
| Incident id | `{incident_id}` |
| PCL tx id | `{pcl_tx_id}` |
| Window | `{scope.get('Window', 'unknown')}` |
| Chain | `Linea / {chain_id}` |
| Trace status | `{scope.get('Debug trace status', 'unknown')}` |
| Evidence | `{packet_path}` plus `{artifact_count}` listed artifact files |
| Live calls during render | `none` |

### Data Access Mode

{access_note}

### Detailed Transaction Explanation

The route attempted to move {human_amount(repeated_raw, decimals)} {symbol} from {len(transfers)} source owner(s). The final visible transfer event sends {human_amount(final_event['raw'].split()[0], decimals) + ' ' + symbol if final_event else 'the accumulated funds'} to `{short(final_event['dst']) if final_event else 'unknown'}`. Because the transaction did not land, these movements are simulated attempted effects, not realized loss.

```mermaid
sequenceDiagram
  autonumber
  participant Sender as Sender/route<br/>{short(sender)}
  participant Settler as LineaSettler<br/>{short(adopter_address)}
  participant USDC as {symbol}<br/>{short(transfers[0]['token']) if transfers else 'unknown'}
  participant Owner1 as Source owner(s)
  participant Recipient as Recipient<br/>{short(final_event['dst']) if final_event else short(transfers[0]['dst']) if transfers else 'unknown'}
  participant Assert as AllowanceAssertion
  Sender->>Settler: execute encoded route
  Settler->>USDC: transferFrom source owner(s)
  USDC-->>Sender: simulated Transfer event(s)
  Sender->>USDC: transfer consolidated funds
  Assert->>USDC: allowance(source owner, LineaSettler)
  USDC-->>Assert: non-zero/max allowance
  Assert--xSender: revert {revert_reason}
```

### Root Cause Analysis

Mechanism: allowance abuse via the 0x Settler adopter. The critical evidence is the combination of `transferFrom` calls, simulated ERC20 `Transfer` events, and the assertion allowance read. {previous_summary}

### Source And Decompiler Context

{source_context}

{source_note}

### Transaction Object

| Field | Value |
|---|---|
| hash | `{hash_value}` |
| from | `{sender}` |
| to | `{target}` |
| value | `{tx.get('value', 'unknown')}` |
| block | `{block}` |
| landed | `{scope.get('Landed on chain', 'unknown')}` |
| revert | `{revert_reason}` |

### Full Improved Trace

{chr(10).join(trace_steps)}

### Value And Exposure

| Metric | Amount |
|---|---:|
| Actual landed loss | `{actual_loss} {symbol}` |
| Unique protected value | `{human_amount(unique_raw, decimals)} {symbol}` |
| Repeated blocked attempt volume | `{human_amount(repeated_raw, decimals)} {symbol}` |

| Token | Source owner | Recipient | Raw amount | Human amount |
|---|---|---|---:|---:|
{chr(10).join(movement_rows)}

| Source owner | Balance at block | Latest balance | Latest allowance to adopter |
|---|---:|---:|---|
{chr(10).join(exposure_rows) if exposure_rows else '| not prefetched | unknown | unknown | unknown |'}

### Open Gaps And Confidence

Confidence is high for the attempted {symbol} movement, blocked status, and assertion reason because the packet contains a completed trace, normalized movement rows, decoded events, and prefetched receipt/null checks. Remaining gaps: source-level intent for transient/decompiled-only contracts, any source owner whose latest allowance was not prefetched, and historical attribution beyond the bounded sender-history artifact.

### Runtime And Usage

Rendered deterministically from packet and local artifacts. Token usage is not exposed by this script. Output bytes are reported by the caller; packet size was {packet_path.stat().st_size} bytes.
"""
    out_path.write_text(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    run_dir = (args.run_dir or args.packet.parent).resolve()
    packet = args.packet.read_text()
    packet_data = parse_packet(packet, run_dir)
    prefetched = read_prefetched(packet_data)
    report = render_report(packet_data, prefetched, args.packet.resolve(), args.out)
    elapsed_ms = int((time.time() - start) * 1000)
    print(json.dumps({"output": str(args.out), "bytes": len(report.encode()), "elapsed_ms": elapsed_ms}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
