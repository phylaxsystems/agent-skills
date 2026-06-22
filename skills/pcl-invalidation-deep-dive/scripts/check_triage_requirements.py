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
import urllib.parse
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

PUBLIC_RPC_URLS = {
    "1": ["https://ethereum-rpc.publicnode.com"],
    "10": ["https://mainnet.optimism.io", "https://optimism-rpc.publicnode.com"],
    "137": ["https://polygon-rpc.com", "https://polygon-bor-rpc.publicnode.com"],
    "42161": ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"],
    "8453": ["https://mainnet.base.org", "https://base-rpc.publicnode.com"],
    "59144": ["https://rpc.linea.build", "https://linea-rpc.publicnode.com"],
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

DECOMPILER_ENV_VARS = ["HEIMDALL_BIN"]


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


def rpc_source_label(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc or url
    return f"public_rpc:{host}"


def public_rpc_options(chain_id: str) -> list[str]:
    return PUBLIC_RPC_URLS.get(chain_id, [])


def rpc_candidates(chain_id: str, explicit: str | None, no_api_keys: bool) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if explicit:
        candidates.append({"source": "--rpc-url", "url": explicit})

    for chain_env in chain_rpc_env_names(chain_id):
        if os.getenv(chain_env):
            candidates.append({"source": chain_env, "url": os.getenv(chain_env, "")})

    if os.getenv("RPC_URL"):
        candidates.append({"source": "RPC_URL", "url": os.getenv("RPC_URL", "")})

    if not no_api_keys:
        alchemy_key = os.getenv("ALCHEMY_API_KEY")
        host = ALCHEMY_HOSTS.get(chain_id)
        if alchemy_key and host:
            candidates.append({"source": "ALCHEMY_API_KEY", "url": f"https://{host}/v2/{alchemy_key}"})

    for public_url in public_rpc_options(chain_id):
        candidates.append({"source": rpc_source_label(public_url), "url": public_url})
    return candidates


def rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "pcl-invalidation-deep-dive/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def check_rpc(chain_id: str, explicit: str | None, no_api_keys: bool) -> dict[str, Any]:
    candidates = rpc_candidates(chain_id, explicit, no_api_keys)
    public_options = public_rpc_options(chain_id)
    requirement = {
        "name": "chain_rpc",
        "required_for": [
            "eth_getCode contract/EOA classification",
            "block-pinned balances, ownership, approvals, and protocol state",
            "receipt/log/transaction verification",
            "replay/debug trace when supported by the selected RPC",
        ],
        "acceptable_configuration": [
            "--rpc-url <url>",
            *chain_rpc_env_names(chain_id),
            "RPC_URL",
            *([] if no_api_keys else ["ALCHEMY_API_KEY for supported chains"]),
            *[f"public RPC fallback: {url}" for url in public_options],
        ],
        "configured": bool(candidates),
        "ok": False,
        "selected_source": None,
        "error": None,
        "notes": [],
    }
    if public_options:
        requirement["notes"].append(
            "Public RPC fallbacks are keyless but may be rate-limited and may not support archive/debug methods."
        )
    if no_api_keys:
        requirement["notes"].append("No-API-key mode: provider API-key-derived RPC URLs are ignored.")
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


def public_source_requirement(no_api_keys: bool) -> dict[str, Any]:
    return {
        "name": "keyless_source_lookup",
        "required_for": [
            "Sourcify verified source/ABI when available",
            "4byte selector/event signature lookup",
            "local Heimdall decompilation after bytecode capture",
        ],
        "acceptable_configuration": [
            "Sourcify /server/v2/contract/<chain-id>/<address>?fields=all",
            "4byte.directory public API or cast 4byte",
            "heimdall on PATH or HEIMDALL_BIN for unverified bytecode",
        ],
        "configured": True,
        "ok": True,
        "selected_source": "public no-key services",
        "error": None,
        "notes": ["Used as the default source path in no-API-key mode." if no_api_keys else "Available as fallback."],
    }


def skipped_keyed_explorer_requirement() -> dict[str, Any]:
    return {
        "name": "keyed_explorer_api",
        "required_for": ["optional verified source/ABI acceleration", "optional account-history lookup"],
        "acceptable_configuration": EXPLORER_ENV_VARS,
        "configured": False,
        "ok": True,
        "selected_source": None,
        "error": None,
        "notes": ["Skipped because --no-api-keys was requested; record account-history gaps if no keyless source exists."],
    }


def decompiler_requirement(required: bool) -> dict[str, Any]:
    required_for = [
        "unverified runtime bytecode",
        "transient contract bytecode review",
        "source-gap reduction",
    ]
    acceptable_configuration = [
        "heimdall on PATH",
        "HEIMDALL_BIN=/absolute/path/to/heimdall",
    ]

    configured_bin = os.getenv("HEIMDALL_BIN")
    if configured_bin:
        resolved = shutil.which(configured_bin) if os.path.sep not in configured_bin else configured_bin
        exists = bool(resolved and os.path.exists(resolved) and os.access(resolved, os.X_OK))
        return {
            "name": "heimdall_decompiler",
            "required_for": required_for,
            "acceptable_configuration": acceptable_configuration,
            "configured": bool(configured_bin),
            "ok": exists or not required,
            "selected_source": "HEIMDALL_BIN",
            "error": None if exists or not required else f"HEIMDALL_BIN is set but is not executable: {configured_bin}",
        }

    heimdall_path = shutil.which("heimdall")
    if heimdall_path:
        return {
            "name": "heimdall_decompiler",
            "required_for": required_for,
            "acceptable_configuration": acceptable_configuration,
            "configured": True,
            "ok": True,
            "selected_source": heimdall_path,
            "error": None,
        }

    return {
        "name": "heimdall_decompiler",
        "required_for": required_for,
        "acceptable_configuration": acceptable_configuration,
        "configured": False,
        "ok": not required,
        "selected_source": None,
        "error": None
        if not required
        else "Missing Heimdall-rs. Install `heimdall` on PATH or set HEIMDALL_BIN to an executable heimdall binary.",
    }


def find_requirement(requirements: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((item for item in requirements if item.get("name") == name), None)


def build_capability_selection(
    requirements: list[dict[str, Any]],
    no_api_keys: bool,
) -> dict[str, Any]:
    rpc = find_requirement(requirements, "chain_rpc") or {}
    explorer = find_requirement(requirements, "explorer_api") or find_requirement(
        requirements, "keyed_explorer_api"
    ) or {}
    decompiler = find_requirement(requirements, "heimdall_decompiler") or {}

    rpc_source = rpc.get("selected_source")
    rpc_ok = bool(rpc.get("ok"))
    public_rpc = bool(isinstance(rpc_source, str) and rpc_source.startswith("public_rpc:"))
    configured_or_private_rpc = rpc_ok and bool(rpc_source) and not public_rpc
    keyed_explorer_available = bool(explorer.get("configured") and explorer.get("ok"))
    decompiler_available = bool(decompiler.get("configured") and decompiler.get("ok"))

    if configured_or_private_rpc or keyed_explorer_available:
        mode = "private-or-mixed"
        decision = (
            "Use configured/private endpoints for higher-confidence reads, then fall back to "
            "Sourcify, 4byte/cast, Heimdall, and public RPC for missing surfaces."
        )
    elif rpc_ok:
        mode = "keyless-public"
        decision = (
            "Proceed keyless with public RPC, Sourcify, 4byte/cast, and local Heimdall when "
            "available; report archive/debug and account-history gaps."
        )
    else:
        mode = "blocked"
        decision = (
            "No working RPC was found. Stop before source/context collection unless the user "
            "accepts a degraded packet without bytecode/state verification."
        )

    return {
        "mode": mode,
        "private_or_configured_rpc_available": configured_or_private_rpc,
        "public_rpc_available": rpc_ok and public_rpc,
        "keyed_explorer_available": keyed_explorer_available,
        "local_decompiler_available": decompiler_available,
        "no_api_keys_requested": no_api_keys,
        "operator_message": decision,
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "PCL invalidation triage requirements",
        f"chain_id: {report['chain_id']}",
        f"status: {'ok' if report['ok'] else 'missing_requirements'}",
        "",
        "Capability selection",
        f"recommended_mode: {report['capability_selection']['mode']}",
        (
            "private_or_configured_rpc_available: "
            f"{'yes' if report['capability_selection']['private_or_configured_rpc_available'] else 'no'}"
        ),
        (
            "keyed_explorer_available: "
            f"{'yes' if report['capability_selection']['keyed_explorer_available'] else 'no'}"
        ),
        (
            "public_rpc_available: "
            f"{'yes' if report['capability_selection']['public_rpc_available'] else 'no'}"
        ),
        f"decision: {report['capability_selection']['operator_message']}",
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
        for note in item.get("notes", []):
            lines.append(f"  note: {note}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail fast when local triage requirements are missing.")
    parser.add_argument("--chain-id", required=True, help="EVM chain id, e.g. 59144")
    parser.add_argument("--rpc-url", default=None, help="Explicit RPC URL. Secrets are not printed.")
    parser.add_argument("--require-explorer", action="store_true", help="Fail if explorer/source API access is absent.")
    parser.add_argument("--require-decompiler", action="store_true", help="Fail if decompiler config is absent.")
    parser.add_argument(
        "--no-api-keys",
        action="store_true",
        help="Use only explicit/env RPC URLs, public RPC fallbacks, Sourcify/4byte, and local tools. Ignore provider/explorer API keys.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    requirements = [
        tool_requirement("pcl_cli", "pcl", ["platform auth", "incident detail", "trace retrieval"]),
        tool_requirement("foundry_cast", "cast", ["selector decoding", "calldata decoding", "RPC calls", "state reads", "replay checks"]),
        check_rpc(args.chain_id, args.rpc_url, args.no_api_keys),
        public_source_requirement(args.no_api_keys),
        skipped_keyed_explorer_requirement()
        if args.no_api_keys
        else env_requirement(
            "explorer_api",
            EXPLORER_ENV_VARS,
            ["verified source/ABI", "previous transaction lookup", "public explorer evidence"],
            args.require_explorer,
        ),
        decompiler_requirement(args.require_decompiler),
    ]

    report = {
        "chain_id": args.chain_id,
        "ok": all(item["ok"] for item in requirements),
        "requirements": requirements,
    }
    report["capability_selection"] = build_capability_selection(requirements, args.no_api_keys)

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
