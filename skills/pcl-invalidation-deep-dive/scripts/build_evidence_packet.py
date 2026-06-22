#!/usr/bin/env python3
"""Build a compact evidence packet from prefetched PCL triage artifacts.

The packet is meant for a report-only agent: it points at raw files, but keeps
the high-signal incident, trace, source, and decompiler facts in one small file.
It does not perform network or PCL calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> Any:
    if not path:
        return None
    with path.open() as file:
        return json.load(file)


def unwrap_data(value: Any) -> Any:
    current = value
    for _ in range(5):
        if isinstance(current, dict) and "data" in current and isinstance(
            current["data"], (dict, list)
        ):
            current = current["data"]
            continue
        break
    return current


def rel(path: Path | None, run_dir: Path) -> str | None:
    if not path:
        return None
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except ValueError:
        return str(path)


def first(values: list[Any]) -> Any:
    return values[0] if values else None


def find_tx(incident: dict[str, Any], tx_id: str | None) -> dict[str, Any] | None:
    txs = incident.get("invalidating_transactions") or incident.get("transactions") or []
    if not txs:
        return None
    if tx_id:
        for tx in txs:
            if tx.get("id") == tx_id or tx.get("transaction_id") == tx_id:
                return tx
    return txs[0]


def normalized_record(normalized: dict[str, Any] | None, tx_id: str | None) -> dict[str, Any] | None:
    if not normalized:
        return None
    records = normalized.get("records") if isinstance(normalized, dict) else None
    if not records:
        return None
    if tx_id:
        for record in records:
            if record.get("pcl_tx_id") == tx_id:
                return record
    return records[0]


def token_amount(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        return f"{int(raw) / 1_000_000:,.6f}"
    except ValueError:
        return None


def decode_error_string(payload: str | None) -> str | None:
    if not payload or not payload.startswith("0x08c379a0"):
        return None
    try:
        data = bytes.fromhex(payload[10:])
        if len(data) < 64:
            return None
        length = int.from_bytes(data[32:64], "big")
        raw = data[64 : 64 + length]
        return raw.decode("utf-8", errors="replace")
    except ValueError:
        return None


def source_summary(context: dict[str, Any] | None) -> dict[str, list[str]]:
    summary = {
        "verified_source": [],
        "decompiled_needed": [],
        "created_contracts": [],
        "no_code": [],
        "unresolved_code": [],
    }
    if not context:
        return summary
    for item in context.get("addresses", []):
        address = item.get("address")
        if not address:
            continue
        code_type = item.get("code_type")
        if item.get("verified_source_available"):
            summary["verified_source"].append(address)
        elif item.get("decompiler_needed"):
            summary["decompiled_needed"].append(address)
        elif item.get("created_in_trace"):
            summary["created_contracts"].append(address)
        elif code_type == "no_code":
            summary["no_code"].append(address)
        elif code_type == "contract":
            summary["unresolved_code"].append(address)
    return summary


def decompiler_summary(decompilation: dict[str, Any] | None) -> list[str]:
    if not decompilation:
        return []
    lines = [
        (
            f"{decompilation.get('decompiler', 'decompiler')}: "
            f"{decompilation.get('completed_count', 0)} completed, "
            f"{decompilation.get('skipped_count', 0)} skipped, "
            f"{decompilation.get('error_count', 0)} errored"
        )
    ]
    for result in decompilation.get("results", []):
        address = result.get("address")
        status = result.get("status")
        output_dir = result.get("output_dir")
        reason = result.get("reason")
        lines.append(f"- {address}: {status}; {reason}; output={output_dir}")
    return lines


def artifact_line(label: str, path: Path | None, run_dir: Path) -> str | None:
    if not path:
        return None
    return f"- {label}: `{rel(path, run_dir)}`"


def parse_aux_file(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--aux-file must be LABEL=PATH")
    label, path = value.split("=", 1)
    label = label.strip()
    path = path.strip()
    if not label or not path:
        raise argparse.ArgumentTypeError("--aux-file must include a non-empty label and path")
    return label, Path(path)


def build_packet(args: argparse.Namespace) -> str:
    run_dir = args.run_dir.resolve()
    incident_raw = load_json(args.incident_json)
    trace_raw = load_json(args.trace_json)
    normalized_raw = load_json(args.normalized_json)
    context_raw = load_json(args.contract_context)
    decompilation_raw = load_json(args.decompilation_manifest)

    incident = unwrap_data(incident_raw) if incident_raw is not None else {}
    trace = unwrap_data(trace_raw) if trace_raw is not None else {}
    tx_id = args.pcl_tx_id
    tx = find_tx(incident, tx_id) or trace.get("invalidating_transaction") or {}
    if not tx_id:
        tx_id = tx.get("id") or tx.get("transaction_id")
    record = normalized_record(normalized_raw, tx_id)

    record = record or {}
    incident_id = args.incident_id or incident.get("incident_id") or record.get("incident_id")
    chain_id = args.chain_id or incident.get("chain_id") or tx.get("chain_id") or (record or {}).get("chain_id")
    assertion = incident.get("assertion") if isinstance(incident, dict) else {}
    adopter = incident.get("assertion_adopter") if isinstance(incident, dict) else {}

    transfers = record.get("transfer_from_calls", [])
    allowance_checks = record.get("allowance_checks", [])
    events = record.get("events", [])
    src_summary = source_summary(context_raw)

    lines = [
        "# PCL Invalidation Evidence Packet",
        "",
        "Use this compact packet first. Open raw artifacts only to verify a claim, resolve a gap, or quote exact trace lines.",
        "",
        "## Scope",
        "",
        f"- Project: `{args.project or 'unknown'}`",
        f"- Project id: `{args.project_id or 'unknown'}`",
        f"- Chain id: `{chain_id or 'unknown'}`",
        f"- Environment: `{incident.get('environment', 'unknown') if isinstance(incident, dict) else 'unknown'}`",
        f"- Incident id: `{incident_id or 'unknown'}`",
        f"- PCL tx id: `{tx_id or 'unknown'}`",
        f"- Tx hash: `{tx.get('transaction_hash') or tx.get('hash') or record.get('transaction_hash') or 'unknown'}`",
        f"- Window: `{incident.get('window_start', 'unknown') if isinstance(incident, dict) else 'unknown'}`",
        f"- Incident timestamp: `{tx.get('incident_timestamp', 'unknown')}`",
        f"- Assertion: `{assertion.get('title') or args.assertion or 'unknown'}`",
        f"- Assertion id: `{incident.get('assertion_id') or assertion.get('assertion_id') or 'unknown'}`",
        f"- Adopter: `{adopter.get('name') or 'unknown'}` at `{adopter.get('address') or 'unknown'}`",
        f"- Landed on chain: `{tx.get('landed_on_chain', record.get('landed_on_chain', 'unknown'))}`",
        f"- Debug trace status: `{record.get('debug_trace_status', 'unknown')}`",
        "",
        "## Artifact Paths",
        "",
    ]

    for item in [
        artifact_line("incident detail", args.incident_json, run_dir),
        artifact_line("trace detail", args.trace_json, run_dir),
        artifact_line("normalized trace", args.normalized_json, run_dir),
        artifact_line("contract context", args.contract_context, run_dir),
        artifact_line("decompiler manifest", args.decompilation_manifest, run_dir),
    ]:
        if item:
            lines.append(item)
    for label, path in args.aux_file:
        lines.append(f"- {label}: `{rel(path, run_dir)}`")

    lines.extend(
        [
            "",
            "## Critical Trace Evidence",
            "",
            f"- Trace records in packet: `{len((normalized_raw or {}).get('records', [])) if isinstance(normalized_raw, dict) else 0}`",
            f"- TransferFrom calls: `{len(transfers)}`",
        ]
    )
    for transfer in transfers:
        amount = token_amount(transfer.get("raw_amount"))
        amount_text = f"{amount} token units assuming 6 decimals" if amount else transfer.get("raw_amount")
        lines.append(
            "- transferFrom: "
            f"token `{transfer.get('token')}`, "
            f"source `{transfer.get('source_owner')}`, "
            f"recipient `{transfer.get('recipient')}`, "
            f"raw `{transfer.get('raw_amount')}`"
            + (f", normalized `{amount_text}`" if amount_text else "")
        )
    lines.append(f"- Decoded event count: `{len(events)}`")
    for event in events[:8]:
        lines.append(
            "- event: "
            f"`{event.get('standard', 'unknown')}.{event.get('event')}` "
            f"from `{event.get('from')}` to `{event.get('to')}` "
            f"raw `{event.get('raw_amount') or event.get('token_id')}`"
        )
    lines.append(f"- Allowance checks: `{len(allowance_checks)}`")
    for check in allowance_checks:
        lines.append(
            "- allowance: "
            f"token `{check.get('token')}`, owner `{check.get('owner')}`, "
            f"spender `{check.get('spender')}`, returned `{check.get('returned')}`"
        )
    revert_reason = tx.get("revert_reason") or record.get("revert_reason")
    if revert_reason:
        lines.append(f"- Revert reason payload: `{revert_reason}`")
        decoded = decode_error_string(revert_reason)
        if decoded:
            lines.append(f"- Revert reason decoded: `{decoded}`")

    lines.extend(["", "## Source and Decompiler Coverage", ""])
    for key, values in src_summary.items():
        lines.append(f"- {key}: `{len(values)}`" + (f" ({', '.join(values[:6])})" if values else ""))
    for line in decompiler_summary(decompilation_raw):
        lines.append(line)

    tx_count = len(incident.get("invalidating_transactions", [])) if isinstance(incident, dict) else 0
    lines.extend(
        [
            "",
            "## Report-Agent Instructions",
            "",
            "- Produce one production-style triage report from this packet.",
            "- Fast packet-only mode is the default: target under 90 seconds for one completed trace and keep the main report around 1,200-1,800 words.",
            "- Prefer `scripts/render_fast_report.py --packet <this file> --run-dir <run-dir> --out <final_report.md>` for the first draft, then review briefly.",
            "- Do not refetch PCL list/detail/trace data unless a listed artifact is missing or inconsistent.",
            "- Read listed auxiliary state, receipt, price, and previous-transaction files before doing live RPC or explorer calls.",
            "- Do not do local Homebrew/formula/version checks, selector lookups, RPC calls, explorer calls, or raw-trace reads unless the packet is insufficient for a required claim.",
            "- Open the raw trace only for exact call ordering, selector details, or disputed evidence.",
            "- Use one `Full Improved Trace` section that combines transaction execution and assertion evaluation in order.",
            "- If this packet covers only one PCL tx but the incident has more txs, say the report is selected-tx scoped and list uncovered txs as gaps.",
            "- If a non-critical check is missing, list it as a gap instead of spending minutes fetching it.",
            "- Report wall-clock time and token usage if exposed. If token usage is unavailable, report packet size, key artifact size, and output size.",
            "",
            "## Coverage Gaps to Check",
            "",
            f"- Incident invalidating tx count from detail: `{tx_count}`.",
            "- Confirm whether current/latest balance and allowance reads are already present in an auxiliary state file.",
            "- Confirm whether sender previous transaction/account history is already present in an auxiliary file.",
            "- Confirm whether tx object and receipt null checks are already present in an auxiliary file.",
        ]
    )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--incident-json", type=Path)
    parser.add_argument("--trace-json", type=Path)
    parser.add_argument("--normalized-json", type=Path)
    parser.add_argument("--contract-context", type=Path)
    parser.add_argument("--decompilation-manifest", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project")
    parser.add_argument("--project-id")
    parser.add_argument("--chain-id")
    parser.add_argument("--incident-id")
    parser.add_argument("--pcl-tx-id")
    parser.add_argument("--assertion")
    parser.add_argument(
        "--aux-file",
        action="append",
        default=[],
        type=parse_aux_file,
        metavar="LABEL=PATH",
        help="Additional prefetched evidence file to list in the packet, such as state reads or previous tx history.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(packet)
    print(json.dumps({"output": str(args.out), "bytes": len(packet.encode())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
