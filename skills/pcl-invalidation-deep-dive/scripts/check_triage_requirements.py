#!/usr/bin/env python3
"""Preflight local requirements for PCL invalidation triage.

The goal is to fail early with an actionable capability report. Do not print
secret values; only report whether a requirement is configured and usable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.request
from typing import Any


ALCHEMY_HOSTS = {
    "1": "eth-mainnet.g.alchemy.com",
    "10": "opt-mainnet.g.alchemy.com",
    "137": "polygon-mainnet.g.alchemy.com",
    "42161": "arb-mainnet.g.alchemy.com",
    "8453": "base-mainnet.g.alchemy.com",
    "59144": "linea-mainnet.g.alchemy.com",
}

CHAIN_RPC_ENV = {
    "1": "ETH_RPC_URL",
    "10": "OPTIMISM_RPC_URL",
    "137": "POLYGON_RPC_URL",
    "324": "ZKSYNC_RPC_URL",
    "43114": "AVALANCHE_RPC_URL",
    "42161": "ARBITRUM_RPC_URL",
    "8453": "BASE_RPC_URL",
    "100": "GNOSIS_RPC_URL",
    "5000": "MANTLE_RPC_URL",
    "534352": "SCROLL_RPC_URL",
    "59144": "LINEA_RPC_URL",
    "81457": "BLAST_RPC_URL",
}

EXPLORER_ENV_VARS = [
    "ETHERSCAN_API_KEY",
    "EXPLORER_API_KEY",
    "BLOCKSCOUT_API_KEY",
    "LINEASCAN_API_KEY",
    "BASESCAN_API_KEY",
    "ARBISCAN_API_KEY",
    "OPTIMISTIC_ETHERSCAN_API_KEY",
    "POLYGONSCAN_API_KEY",
    "BSCSCAN_API_KEY",
    "SNOWTRACE_API_KEY",
    "GNOSISSCAN_API_KEY",
    "CELOSCAN_API_KEY",
    "SCROLLSCAN_API_KEY",
]

DECOMPILER_ENV_VARS = [
    "DEDAUB_API_KEY",
    "DEDAUB_API_URL",
    "DEDAUB_DECOMPILE_CMD",
    "EVM_DECOMPILER_API_URL",
    "EVM_DECOMPILER_CMD",
    "DECOMPILER_CMD",
]


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def chain_rpc_env_names(chain_id: str) -> list[str]:
    names = [
        CHAIN_RPC_ENV.get(chain_id),
        f"CHAIN_{chain_id}_RPC_URL",
        f"RPC_URL_{chain_id}",
        f"EVM_{chain_id}_RPC_URL",
    ]
    return unique([name for name in names if name])


def rpc_candidates(chain_id: str, explicit: str | None) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if explicit:
        candidates.append({"source": "--rpc-url", "url": explicit})

    for chain_env in chain_rpc_env_names(chain_id):
        if os.getenv(chain_env):
            candidates.append({"source": chain_env, "url": os.getenv(chain_env, "")})

    if os.getenv("RPC_URL"):
        candidates.append({"source": "RPC_URL", "url": os.getenv("RPC_URL", "")})

    alchemy_key = os.getenv("ALCHEMY_API_KEY")
    host = ALCHEMY_HOSTS.get(chain_id)
    if alchemy_key and host:
        candidates.append({"source": "ALCHEMY_API_KEY", "url": f"https://{host}/v2/{alchemy_key}"})
    return candidates


def rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def check_rpc(chain_id: str, explicit: str | None) -> dict[str, Any]:
    candidates = rpc_candidates(chain_id, explicit)
    requirement = {
        "name": "chain_rpc",
        "required_for": [
            "eth_getCode contract/EOA classification",
            "block-pinned balances, ownership, approvals, and protocol state",
            "receipt/log/transaction verification",
            "replay/debug trace when supported",
        ],
        "acceptable_configuration": [
            "--rpc-url <url>",
            *chain_rpc_env_names(chain_id),
            "RPC_URL",
            "ALCHEMY_API_KEY for supported chains",
        ],
        "configured": bool(candidates),
        "ok": False,
        "selected_source": None,
        "error": None,
    }
    if not candidates:
        requirement["error"] = "No RPC URL configured for this chain."
        return requirement

    try:
        expected_hex = hex(int(chain_id))
    except ValueError:
        requirement["error"] = f"chain_id must be a decimal EVM chain id; got {chain_id!r}."
        return requirement

    errors = []
    for candidate in candidates:
        try:
            actual = rpc_call(candidate["url"], "eth_chainId", [])
        except Exception as exc:
            errors.append(f"{candidate['source']}: {exc}")
            continue
        if str(actual).lower() != expected_hex:
            errors.append(f"{candidate['source']}: eth_chainId returned {actual}, expected {expected_hex}")
            continue
        requirement["ok"] = True
        requirement["selected_source"] = candidate["source"]
        return requirement

    requirement["error"] = "; ".join(errors) if errors else "No RPC candidate matched the chain id."
    return requirement


def tool_requirement(name: str, executable: str, required_for: list[str]) -> dict[str, Any]:
    path = shutil.which(executable)
    return {
        "name": name,
        "required_for": required_for,
        "acceptable_configuration": [f"{executable} on PATH"],
        "configured": bool(path),
        "ok": bool(path),
        "selected_source": path,
        "error": None if path else f"`{executable}` is not on PATH.",
    }


def env_requirement(
    name: str,
    env_vars: list[str],
    required_for: list[str],
    required: bool,
) -> dict[str, Any]:
    configured = [env for env in env_vars if os.getenv(env)]
    return {
        "name": name,
        "required_for": required_for,
        "acceptable_configuration": env_vars,
        "configured": bool(configured),
        "ok": bool(configured) or not required,
        "selected_source": configured[0] if configured else None,
        "error": None
        if configured or not required
        else f"Missing one of: {', '.join(env_vars)}.",
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "PCL invalidation triage requirements",
        f"chain_id: {report['chain_id']}",
        f"status: {'ok' if report['ok'] else 'missing_requirements'}",
        "",
    ]
    for item in report["requirements"]:
        status = "ok" if item["ok"] else "missing"
        lines.append(f"- {item['name']}: {status}")
        if item.get("selected_source"):
            lines.append(f"  selected: {item['selected_source']}")
        if item.get("error"):
            lines.append(f"  error: {item['error']}")
        lines.append(f"  required_for: {', '.join(item['required_for'])}")
        lines.append(f"  configure_with: {', '.join(item['acceptable_configuration'])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail fast when local triage requirements are missing.")
    parser.add_argument("--chain-id", required=True, help="EVM chain id, e.g. 59144")
    parser.add_argument("--rpc-url", default=None, help="Explicit RPC URL. Secrets are not printed.")
    parser.add_argument("--require-explorer", action="store_true", help="Fail if explorer/source API access is absent.")
    parser.add_argument("--require-decompiler", action="store_true", help="Fail if decompiler config is absent.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    requirements = [
        tool_requirement("pcl_cli", "pcl", ["platform auth", "incident detail", "trace retrieval"]),
        tool_requirement("foundry_cast", "cast", ["selector decoding", "calldata decoding", "RPC calls", "state reads", "replay checks"]),
        check_rpc(args.chain_id, args.rpc_url),
        env_requirement(
            "explorer_api",
            EXPLORER_ENV_VARS,
            ["verified source/ABI", "previous transaction lookup", "public explorer evidence"],
            args.require_explorer,
        ),
        env_requirement(
            "decompiler_api",
            DECOMPILER_ENV_VARS,
            ["unverified runtime bytecode", "transient contract bytecode review", "source-gap reduction"],
            args.require_decompiler,
        ),
    ]

    report = {
        "chain_id": args.chain_id,
        "ok": all(item["ok"] for item in requirements),
        "requirements": requirements,
    }

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
