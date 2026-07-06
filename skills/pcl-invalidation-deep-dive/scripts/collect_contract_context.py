#!/usr/bin/env python3
"""Collect contract bytecode/source context for addresses in PCL traces.

Fetches verified source from Etherscan V2 and Sourcify when available, fetches
runtime bytecode through JSON-RPC when configured, and emits a decompiler target
manifest for contracts without verified source.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rpc_resolver import resolve_rpc_url, rpc_call, rpc_requirement_message  # noqa: E402


ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
ADDRESS_RE = re.compile(r"(?<![a-fA-F0-9])0x[a-fA-F0-9]{40}(?![a-fA-F0-9])")
CREATED_RE = re.compile(r"\bnew\b[^@\n]*@(?P<address>0x[a-fA-F0-9]{40})")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def extract_address_context(files: list[Path]) -> tuple[list[str], set[str]]:
    seen: dict[str, str] = {}
    created: set[str] = set()
    for path in files:
        raw = path.read_text(errors="replace")
        clean = strip_ansi(raw)
        for created_match in CREATED_RE.finditer(clean):
            created_address = created_match.group("address")
            created.add(created_address.lower())
            seen.setdefault(created_address.lower(), created_address)
        for address in ADDRESS_RE.findall(clean):
            key = address.lower()
            if key not in (
                "0x0000000000000000000000000000000000000000",
                "0xffffffffffffffffffffffffffffffffffffffff",
            ):
                seen.setdefault(key, address)
    return [seen[key] for key in sorted(seen)], created


def fetch_json(url: str, headers: dict[str, str] | None = None) -> tuple[int | None, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}
    except Exception as exc:  # network/env failures belong in manifest, not stderr noise
        return None, {"error": str(exc)}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)


def etherscan_source(chain_id: str, address: str, api_key: str) -> tuple[int | None, Any]:
    query = urllib.parse.urlencode(
        {
            "chainid": chain_id,
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": api_key,
        }
    )
    return fetch_json(f"https://api.etherscan.io/v2/api?{query}")


def sourcify_source(chain_id: str, address: str) -> tuple[int | None, Any]:
    return fetch_json(f"https://sourcify.dev/server/v2/contract/{chain_id}/{address}?fields=all")


def etherscan_verified(data: Any) -> bool:
    if not isinstance(data, dict) or data.get("status") != "1":
        return False
    result = data.get("result")
    if not isinstance(result, list) or not result:
        return False
    source = result[0].get("SourceCode")
    abi = result[0].get("ABI")
    return bool(source) or (bool(abi) and abi != "Contract source code not verified")


def sourcify_verified(status: int | None, data: Any) -> bool:
    if status != 200 or not isinstance(data, dict):
        return False
    return any(key in data for key in ("stdJsonInput", "metadata", "sources", "abi"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch bytecode/source context for contracts referenced in PCL trace files."
    )
    parser.add_argument("files", nargs="+", help="Trace JSON/text files to scan for addresses")
    parser.add_argument("--chain-id", required=True, help="EVM chain id, e.g. 59144")
    parser.add_argument("--out-dir", required=True, help="Output directory for source artifacts")
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument(
        "--etherscan-api-key",
        "--explorer-api-key",
        dest="etherscan_api_key",
        default=None,
        help="Etherscan V2-compatible source API key. Secrets are not printed.",
    )
    parser.add_argument(
        "--no-api-keys",
        action="store_true",
        help="Ignore provider/explorer API keys; use explicit/env/public RPC, Sourcify, and local tools only.",
    )
    parser.add_argument("--skip-sourcify", action="store_true")
    parser.add_argument(
        "--allow-missing-rpc",
        action="store_true",
        help="Continue without eth_getCode bytecode collection. Reports must list this as a degraded-mode gap.",
    )
    args = parser.parse_args()
    rpc_url, rpc_source, rpc_errors = resolve_rpc_url(args.chain_id, args.rpc_url, args.no_api_keys)
    if not rpc_url and not args.allow_missing_rpc:
        sys.stderr.write(rpc_requirement_message(args.chain_id) + "\n")
        if rpc_errors:
            sys.stderr.write("configured_rpc_errors:\n")
            for error in rpc_errors:
                sys.stderr.write(f"- {error}\n")
        return 2
    etherscan_api_key = None
    if not args.no_api_keys:
        etherscan_api_key = (
            args.etherscan_api_key
            or os.getenv("ETHERSCAN_API_KEY")
            or os.getenv("EXPLORER_API_KEY")
        )

    files = [Path(file_name) for file_name in args.files]
    out_dir = Path(args.out_dir)
    addresses, created_addresses = extract_address_context(files)
    manifest: dict[str, Any] = {
        "chain_id": args.chain_id,
        "rpc_required": True,
        "rpc_configured": bool(rpc_url),
        "rpc_source": rpc_source,
        "no_api_keys": args.no_api_keys,
        "keyed_explorer_configured": bool(etherscan_api_key),
        "rpc_requirement": None if rpc_url else rpc_requirement_message(args.chain_id),
        "address_count": len(addresses),
        "created_address_count": len(created_addresses),
        "created_addresses": sorted(created_addresses),
        "addresses": [],
        "decompiler_targets": [],
    }

    for address in addresses:
        address_dir = out_dir / args.chain_id / address.lower()
        item: dict[str, Any] = {
            "address": address,
            "bytecode": None,
            "code_type": "unknown",
            "etherscan_source": None,
            "sourcify_source": None,
            "verified_source_available": False,
            "created_in_trace": address.lower() in created_addresses,
            "decompiler_needed": False,
        }

        if rpc_url:
            try:
                bytecode = rpc_call(rpc_url, "eth_getCode", [address, "latest"])
                item["bytecode"] = "bytecode.txt"
                write_text(address_dir / "bytecode.txt", (bytecode or "") + "\n")
                item["code_type"] = "no_code" if bytecode in (None, "", "0x") else "contract"
            except Exception as exc:
                item["bytecode_error"] = str(exc)

        if item["code_type"] == "no_code":
            if item["created_in_trace"]:
                item["code_type"] = "trace_created_no_onchain_code"
                item["decompiler_needed"] = True
                item["decompiler_unavailable_reason"] = (
                    "address appears in a trace creation line but eth_getCode(latest) returned no code"
                )
                manifest["decompiler_targets"].append(
                    {
                        "address": address,
                        "bytecode_path": None,
                        "reason": (
                            "contract appears created in the PCL trace but no deployed runtime "
                            "bytecode exists at latest; extract init/runtime bytecode from the "
                            "trace, calldata, or replay before relying on this route in RCA"
                        ),
                    }
                )
            manifest["addresses"].append(item)
            continue

        if etherscan_api_key:
            status, data = etherscan_source(args.chain_id, address, etherscan_api_key)
            item["etherscan_source"] = {"status": status, "path": "etherscan_source.json"}
            write_json(address_dir / "etherscan_source.json", data)
            item["verified_source_available"] = item["verified_source_available"] or etherscan_verified(data)

        if not args.skip_sourcify:
            status, data = sourcify_source(args.chain_id, address)
            item["sourcify_source"] = {"status": status, "path": "sourcify_contract.json"}
            write_json(address_dir / "sourcify_contract.json", data)
            item["verified_source_available"] = item["verified_source_available"] or sourcify_verified(status, data)

        bytecode_present = False
        bytecode_path = address_dir / "bytecode.txt"
        if bytecode_path.exists():
            bytecode_value = bytecode_path.read_text().strip()
            bytecode_present = bytecode_value not in ("", "0x")

        item["decompiler_needed"] = (
            bytecode_present and not item["verified_source_available"]
        ) or (
            bool(item["created_in_trace"])
            and not item["verified_source_available"]
            and not bytecode_present
        )
        if item["decompiler_needed"] and bytecode_present:
            manifest["decompiler_targets"].append(
                {
                    "address": address,
                    "bytecode_path": str(bytecode_path),
                    "reason": "runtime bytecode found but no verified source from configured sources",
                }
            )
        elif item["decompiler_needed"] and item["created_in_trace"]:
            manifest["decompiler_targets"].append(
                {
                    "address": address,
                    "bytecode_path": None,
                    "reason": (
                        "contract appears created in the PCL trace but no deployed or captured "
                        "runtime bytecode is available; fetch trace/replay bytecode before relying "
                        "on this route in RCA"
                    ),
                }
            )
        manifest["addresses"].append(item)

    write_json(out_dir / "contract_context_manifest.json", manifest)
    json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
