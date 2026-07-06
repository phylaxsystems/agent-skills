"""Shared JSON-RPC discovery helpers for PCL invalidation triage scripts."""

from __future__ import annotations

import json
import os
import re
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


def sanitize_rpc_error(message: str) -> str:
    # Avoid echoing URLs that may contain provider keys in path/query strings.
    return re.sub(r"https?://\S+", "<rpc-url>", message)


def rpc_call(rpc_url: str, method: str, params: list[Any], timeout: int = 20) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "pcl-invalidation-deep-dive/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def validate_rpc_url(chain_id: str, rpc_url: str) -> str | None:
    try:
        expected = hex(int(chain_id))
    except ValueError:
        return f"chain_id must be a decimal EVM chain id; got {chain_id!r}"
    try:
        actual = rpc_call(rpc_url, "eth_chainId", [])
    except Exception as exc:
        return f"configured RPC did not answer eth_chainId: {sanitize_rpc_error(str(exc))}"
    if str(actual).lower() != expected:
        return f"configured RPC returned eth_chainId {actual}, expected {expected}"
    return None


def rpc_requirement_message(chain_id: str) -> str:
    alchemy_note = (
        "ALCHEMY_API_KEY can derive an RPC URL for this chain"
        if chain_id in ALCHEMY_HOSTS
        else "ALCHEMY_API_KEY cannot derive an RPC URL for this unsupported chain id"
    )
    configure_options = [
        "--rpc-url <url>",
        *chain_rpc_env_names(chain_id),
        "RPC_URL",
        alchemy_note,
        *[f"public RPC fallback: {url}" for url in public_rpc_options(chain_id)],
    ]
    return "\n".join(
        [
            "Missing required JSON-RPC access for PCL invalidation triage.",
            f"chain_id: {chain_id}",
            "required_for:",
            "- eth_getCode contract/EOA classification",
            "- runtime bytecode capture for decompiler targets",
            "- source/decompiler coverage checks before RCA",
            "configure one of:",
            *[f"- {option}" for option in configure_options],
            (
                "Run python3 {baseDir}/scripts/check_triage_requirements.py --chain-id "
                f"{chain_id} to see the full local requirements report."
            ),
            (
                "Use --allow-missing-rpc only when explicitly accepting a degraded "
                "source-only packet and list the missing RPC as a report gap."
            ),
            (
                "Use --no-api-keys to ignore provider/explorer API keys and rely on "
                "public RPC fallbacks when this chain has one configured."
            ),
        ]
    )


def resolve_rpc_url(
    chain_id: str,
    explicit: str | None,
    no_api_keys: bool,
) -> tuple[str | None, str | None, list[str]]:
    errors: list[str] = []
    for candidate in rpc_candidates(chain_id, explicit, no_api_keys):
        rpc_error = validate_rpc_url(chain_id, candidate["url"])
        if rpc_error:
            errors.append(f"{candidate['source']}: {rpc_error}")
            continue
        return candidate["url"], candidate["source"], errors
    return None, None, errors
