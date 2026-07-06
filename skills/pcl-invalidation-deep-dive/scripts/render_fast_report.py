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
CHAIN_NAMES = {
    "1": "Ethereum mainnet",
    "10": "Optimism",
    "137": "Polygon",
    "42161": "Arbitrum One",
    "8453": "Base",
    "59144": "Linea mainnet",
}


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


def parse_raw_int(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    parts = str(raw).split()
    if not parts:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def human_amount(raw: str | int | None, decimals: int = 6) -> str:
    if raw is None:
        return "unknown"
    value = parse_raw_int(raw)
    if value is None:
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


def token_meta_for(state: dict[str, Any] | None, token: str | None) -> dict[str, Any]:
    if not state or not token:
        return {}
    tokens = state.get("tokens")
    if not isinstance(tokens, dict):
        return {}
    direct = tokens.get(token)
    if isinstance(direct, dict):
        return direct
    token_lower = token.lower()
    for key, value in tokens.items():
        if isinstance(key, str) and key.lower() == token_lower and isinstance(value, dict):
            return value
    return {}


def decimals_for(state: dict[str, Any] | None, token: str | None) -> int:
    token_meta = token_meta_for(state, token)
    decimals = token_meta.get("decimals", 6)
    try:
        return int(decimals)
    except (TypeError, ValueError):
        return 6


def symbol_for(state: dict[str, Any] | None, token: str | None) -> str:
    if not token:
        return "asset"
    token_meta = token_meta_for(state, token)
    return token_meta.get("symbol") or "token"


def amount_label(raw: str | int | None, state: dict[str, Any] | None, token: str | None) -> str:
    return f"{human_amount(raw, decimals_for(state, token))} {symbol_for(state, token)}"


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
    completed_match = re.search(r"\b(\d+)\s+completed\b", joined)
    completed_count = int(completed_match.group(1)) if completed_match else 0
    needed_match = re.search(r"-\s*decompiled_needed:\s*`(\d+)`", joined)
    needed_count = int(needed_match.group(1)) if needed_match else 0
    if needed_count > completed_count:
        return (
            "Decompiler output is unavailable for at least one important code-bearing contract. "
            "Do not treat transient/router implementation behavior as source-confirmed; the value "
            "conclusion here comes from executed trace calls and events."
        )
    if completed_count > 0:
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


def token_totals(transfers: list[dict[str, str]], unique: bool) -> dict[str, int]:
    if unique:
        by_owner = unique_attempted(transfers)
        totals: dict[str, int] = {}
        for (token, _owner), raw in by_owner.items():
            totals[token] = totals.get(token, 0) + raw
        return totals
    totals = {}
    for transfer in transfers:
        token = transfer["token"].lower()
        raw = parse_raw_int(transfer.get("raw")) or 0
        totals[token] = totals.get(token, 0) + raw
    return totals


def render_token_totals(totals: dict[str, int], state: dict[str, Any] | None) -> str:
    if not totals:
        return "unknown"
    return "; ".join(amount_label(raw, state, token) for token, raw in sorted(totals.items()))


def chain_label(chain_id: str) -> str:
    name = CHAIN_NAMES.get(str(chain_id))
    return f"{name} / {chain_id}" if name else f"chain_id={chain_id}"


def split_adopter(adopter: str) -> tuple[str, str]:
    address = first_address(adopter) or "unknown"
    name = adopter
    if " at `" in adopter:
        name = adopter.split(" at `", 1)[0].strip() or "adopter"
    elif address != "unknown":
        name = adopter.replace(address, "").replace("`", "").strip(" at") or "adopter"
    return name or "adopter", address


def mechanism_label(transfers: list[dict[str, str]], allowances: list[dict[str, str]]) -> str:
    if transfers and allowances:
        return "allowance-sensitive transferFrom route"
    if transfers:
        return "transferFrom-based value movement"
    if allowances:
        return "allowance-sensitive assertion path"
    return "assertion-defined invariant violation"


def recommended_action(
    transfers: list[dict[str, str]],
    allowances: list[dict[str, str]],
    assertion_name: str,
    adopter_name: str,
) -> str:
    if allowances:
        return (
            f"Review and revoke or reduce any non-zero approvals to `{adopter_name}` for the affected "
            "owners/tokens below, then retry the route only if the approval is intentional."
        )
    if transfers:
        return "Inspect the affected owners/tokens below and confirm whether the simulated value movement was expected."
    return f"Inspect the `{assertion_name}` inputs and source-specific state before taking irreversible action."


def token_for_read(read: dict[str, Any], transfers: list[dict[str, str]]) -> str | None:
    explicit = read.get("token") or read.get("asset")
    if explicit:
        return str(explicit)
    owner = str(read.get("source_owner", "")).lower()
    for transfer in transfers:
        if transfer.get("src", "").lower() == owner:
            return transfer.get("token")
    return transfers[0].get("token") if len(transfers) == 1 else None


def render_report(packet_data: dict[str, Any], prefetched: dict[str, Any], packet_path: Path, out_path: Path) -> str:
    scope = packet_data["scope"]
    transfers = packet_data["transfers"]
    events = packet_data["events"]
    allowances = packet_data["allowances"]
    state = prefetched["state"] if isinstance(prefetched.get("state"), dict) else {}
    preflight = prefetched.get("preflight")
    tx = prefetched["tx"]
    record = prefetched["record"]
    unique_totals = token_totals(transfers, unique=True)
    repeated_totals = token_totals(transfers, unique=False)
    final_event = events[-1] if events else None
    landed = str(scope.get("Landed on chain")).lower()
    actual_loss = "0 (blocked/not landed)" if landed == "false" else "unknown; verify receipt/logs"
    revert_reason = packet_data["revert_decoded"] or "unknown"
    sender = tx.get("from_address") or record.get("from_address") or "unknown"
    target = tx.get("to_address") or record.get("to_address") or "unknown"
    hash_value = scope.get("Tx hash") or tx.get("transaction_hash") or record.get("transaction_hash") or "unknown"
    adopter = scope.get("Adopter", "unknown adopter")
    adopter_name, adopter_address = split_adopter(adopter)
    assertion_name = scope.get("Assertion", "unknown assertion")
    project_name = scope.get("Project", "unknown project")
    incident_id = scope.get("Incident id", "unknown")
    pcl_tx_id = scope.get("PCL tx id", "unknown")
    chain_id = scope.get("Chain id", "unknown")
    block = tx.get("block_number") or record.get("block_number") or "unknown"
    tx_present = state.get("transaction") is not None if state else False
    receipt_present = state.get("receipt") is not None if state else False
    mechanism = mechanism_label(transfers, allowances)
    action = recommended_action(transfers, allowances, assertion_name, adopter_name)
    source_owner_count = len({transfer["src"].lower() for transfer in transfers})
    token_count = len({transfer["token"].lower() for transfer in transfers})

    movement_rows = []
    for transfer in transfers:
        movement_rows.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` {} |".format(
                short(transfer["token"]),
                short(transfer["src"]),
                short(transfer["dst"]),
                transfer["raw"],
                human_amount(transfer["raw"], decimals_for(state, transfer["token"])),
                symbol_for(state, transfer["token"]),
            )
        )
    if not movement_rows:
        movement_rows.append("| not decoded | unknown | unknown | unknown | unknown |")

    exposure_rows = []
    for read in state_reads(state):
        token = token_for_read(read, transfers)
        latest_allowance = read.get("allowance_latest", "not prefetched")
        allowance_label = (
            "max"
            if str(latest_allowance).startswith("115792089")
            else amount_label(latest_allowance, state, token)
            if parse_raw_int(latest_allowance) is not None
            else str(latest_allowance)
        )
        exposure_rows.append(
            "| `{}` | `{}` {} | `{}` {} | `{}` |".format(
                short(read.get("source_owner")),
                human_amount(read.get("balance_at_block"), decimals_for(state, token)),
                symbol_for(state, token),
                human_amount(read.get("balance_latest"), decimals_for(state, token)),
                symbol_for(state, token),
                allowance_label,
            )
        )

    trace_steps = []
    trace_steps.append(f"1. `{short(sender)}` calls `{short(target)}` with the invalidating calldata; PCL simulates it at block `{block}`.")
    trace_steps.append(f"2. The route reaches adopter `{adopter}` and touches `{token_count or 'unknown'}` asset contract(s).")
    step = 3
    for transfer in transfers:
        trace_steps.append(
            f"{step}. The route executes `transferFrom({short(transfer['src'])}, {short(transfer['dst'])}, "
            f"{amount_label(transfer['raw'], state, transfer['token'])})` on `{short(transfer['token'])}`."
        )
        step += 1
    if final_event and transfers and final_event["src"].lower() == transfers[-1]["dst"].lower():
        event_amount = (
            amount_label(final_event.get("raw"), state, transfers[0]["token"])
            if token_count == 1
            else f"raw `{final_event.get('raw')}`"
        )
        trace_steps.append(
            f"{step}. The intermediate recipient transfers `{event_amount}` "
            f"to final recipient `{short(final_event['dst'])}`."
        )
        step += 1
    trace_steps.extend(
        [
            f"{step}. The assertion reads the adopted contract and simulated logs/call inputs.",
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

    repeated_text = render_token_totals(repeated_totals, state)
    unique_text = render_token_totals(unique_totals, state)
    verdict = (
        f"Suspicious `{mechanism}`. The source owner(s) differ from the transaction sender, "
        "and the trace shows attempted value movement through the adopter."
        if transfers
        else f"Inconclusive `{mechanism}`. No transferFrom movement was decoded from the packet, so preserve the assertion-specific gaps."
    )

    report = f"""# PCL Invalidation Triage Report: {project_name} `{incident_id[:8]}`

## Executive Summary

**Transaction.** PCL blocked `{hash_value}` on {chain_label(chain_id)} at block `{block}`. The transaction was from `{sender}` to `{target}` and is marked `landed_on_chain={scope.get('Landed on chain', 'unknown')}`; prefetched chain evidence shows RPC transaction object `{'present' if tx_present else 'absent'}` and receipt `{'present' if receipt_present else 'absent'}`. Treat it as blocked unless a receipt proves otherwise. The completed trace shows attempted movement of `{repeated_text}` through `{adopter}`.

**Assertion.** `{assertion_name}` (`{scope.get('Assertion id', 'unknown')}`) invalidated with exact reason: `{revert_reason}`.

**Verdict.** {verdict}

**Recommended next step.** Keep the assertion active. {action}

**Agent warning.** This triage was generated by an agent and can be wrong. Verify critical conclusions against the raw transaction, trace, and assertion evidence before taking irreversible action.

## Triage Report

### Scope And Data Freshness

| Field | Value |
|---|---|
| Incident id | `{incident_id}` |
| PCL tx id | `{pcl_tx_id}` |
| Window | `{scope.get('Window', 'unknown')}` |
| Chain | `{chain_label(chain_id)}` |
| Trace status | `{scope.get('Debug trace status', 'unknown')}` |
| Evidence | `{packet_path}` plus `{artifact_count}` listed artifact files |
| Live calls during render | `none` |

### Data Access Mode

{access_note}

### Detailed Transaction Explanation

The route attempted to move `{repeated_text}` from {source_owner_count or 'unknown'} source owner(s). The final visible event target is `{short(final_event['dst']) if final_event else 'unknown'}`. Because the transaction did not land, these movements are simulated attempted effects, not realized loss.

```mermaid
sequenceDiagram
  autonumber
  participant Sender as Sender/route<br/>{short(sender)}
  participant Adopter as {adopter_name}<br/>{short(adopter_address)}
  participant Asset as Asset(s)<br/>{token_count or 'unknown'}
  participant Owner1 as Source owner(s)
  participant Recipient as Recipient<br/>{short(final_event['dst']) if final_event else short(transfers[0]['dst']) if transfers else 'unknown'}
  participant Assert as {assertion_name}
  Sender->>Adopter: execute invalidating route
  Adopter->>Asset: transferFrom source owner(s)
  Asset-->>Sender: simulated movement event(s)
  Assert->>Adopter: inspect adopted-contract calls/logs
  Assert->>Asset: allowance/source-state checks
  Asset-->>Assert: decoded state/check result
  Assert--xSender: revert {revert_reason}
```

### Root Cause Analysis

Mechanism: {mechanism}. The critical evidence is the combination of decoded movement rows, simulated asset events, and the assertion's state/call inspection. {previous_summary}

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
| Actual landed loss | `{actual_loss}` |
| Unique protected value | `{unique_text}` |
| Repeated blocked attempt volume | `{repeated_text}` |

| Token | Source owner | Recipient | Raw amount | Human amount |
|---|---|---|---:|---:|
{chr(10).join(movement_rows)}

| Source owner | Balance at block | Latest balance | Latest allowance to adopter |
|---|---:|---:|---|
{chr(10).join(exposure_rows) if exposure_rows else '| not prefetched | unknown | unknown | unknown |'}

### Open Gaps And Confidence

Confidence is highest for decoded movement rows, blocked status, and assertion reason when the packet contains a completed trace, normalized movements/events, and prefetched receipt/null checks. Remaining gaps: source-level intent for transient/decompiled-only contracts, any source owner whose latest allowance was not prefetched, and historical attribution beyond the bounded sender-history artifact.

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
