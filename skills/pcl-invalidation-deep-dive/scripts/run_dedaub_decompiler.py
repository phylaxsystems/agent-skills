#!/usr/bin/env python3
"""Run Dedaub on-demand decompilation for contract-context targets.

The Dedaub API accepts raw EVM bytecode via POST /api/on_demand, returns the
bytecode MD5 job id, exposes job status via GET /api/on_demand/{md5}/status,
and returns decompiled representations via GET /api/on_demand/decompilation/{md5}.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.dedaub.com"
MD5_RE = re.compile(r"^(0x)?[0-9A-Fa-f]{32}$")
COMPLETED_STATUS = "COMPLETED"
PENDING_STATUSES = {
    "SCHEDULED",
    "DECOMPILATION_STARTED",
    "ANALYSIS_STARTED",
    "ANALYSIS_ENDED",
    "UNKNOWN",
}


class DedaubError(RuntimeError):
    pass


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, data: str | None) -> None:
    if data is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if data.endswith("\n") else data + "\n")


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def urllib_request_json(
    method: str,
    url: str,
    api_key: str,
    payload: Any | None = None,
    timeout: float = 30,
) -> Any:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "phylax-pcl-invalidation-deep-dive/0.1",
        "x-api-key": api_key,
    }
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise DedaubError(f"{method} {url} returned HTTP {exc.code}: {body[:1000]}") from exc
    except Exception as exc:
        raise DedaubError(f"{method} {url} failed: {exc}") from exc

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise DedaubError(f"{method} {url} returned non-JSON response: {body[:1000]}") from exc


def curl_request_json(
    method: str,
    url: str,
    api_key: str,
    payload: Any | None = None,
    timeout: float = 30,
) -> Any:
    body_path = None
    config_path = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False) as config_file:
            config_path = config_file.name
            os.chmod(config_path, 0o600)
            config_file.write(f'url = "{url}"\n')
            config_file.write(f'request = "{method}"\n')
            config_file.write("silent\n")
            config_file.write("show-error\n")
            config_file.write("location\n")
            config_file.write('header = "Accept: application/json"\n')
            config_file.write(f'header = "x-api-key: {api_key}"\n')
            if payload is not None:
                with tempfile.NamedTemporaryFile("w", delete=False) as body_file:
                    body_path = body_file.name
                    body_file.write(json.dumps(payload))
                config_file.write('header = "Content-Type: application/json"\n')
                config_file.write(f'data-binary = "@{body_path}"\n')

        completed = subprocess.run(
            ["curl", "--config", config_path, "--write-out", "\n%{http_code}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = completed.stdout
        if "\n" not in stdout:
            raise DedaubError(
                f"curl {method} {url} failed with exit {completed.returncode}: {completed.stderr[:1000]}"
            )
        body, status_text = stdout.rsplit("\n", 1)
        try:
            status = int(status_text)
        except ValueError as exc:
            raise DedaubError(f"curl {method} {url} returned invalid status marker: {status_text!r}") from exc
        if completed.returncode != 0 and not body:
            raise DedaubError(
                f"curl {method} {url} failed with exit {completed.returncode}: {completed.stderr[:1000]}"
            )
        if status >= 400:
            raise DedaubError(f"{method} {url} returned HTTP {status}: {body[:1000]}")
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise DedaubError(f"{method} {url} returned non-JSON response: {body[:1000]}") from exc
    finally:
        for path in (config_path, body_path):
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass


def request_json(
    method: str,
    url: str,
    api_key: str,
    payload: Any | None = None,
    timeout: float = 30,
    transport: str = "auto",
) -> Any:
    selected = "curl" if transport == "auto" and shutil.which("curl") else transport
    if selected == "curl":
        return curl_request_json(method, url, api_key, payload=payload, timeout=timeout)
    if selected == "urllib":
        return urllib_request_json(method, url, api_key, payload=payload, timeout=timeout)
    raise DedaubError(f"unknown Dedaub transport {transport!r}; use auto, curl, or urllib")


def md5_from_response(response: Any) -> str:
    if isinstance(response, str):
        md5 = response
    elif isinstance(response, dict):
        md5 = (
            response.get("md5")
            or response.get("md5_bytecode")
            or response.get("md5Bytecode")
            or response.get("hash")
            or response.get("id")
        )
    else:
        md5 = None
    if not isinstance(md5, str) or not MD5_RE.fullmatch(md5):
        raise DedaubError(f"Dedaub submit response did not contain an md5 job id: {response!r}")
    return md5 if md5.startswith("0x") else f"0x{md5}"


def status_from_response(response: Any) -> str:
    if isinstance(response, str):
        status = response
    elif isinstance(response, dict):
        status = response.get("status") or response.get("stage") or response.get("state")
    else:
        status = None
    if not isinstance(status, str):
        raise DedaubError(f"Dedaub status response did not contain a status string: {response!r}")
    return status


def read_bytecode(path: Path) -> str:
    bytecode = path.read_text().strip()
    if not bytecode or bytecode == "0x":
        raise DedaubError(f"bytecode file is empty: {path}")
    if not re.fullmatch(r"(0x)?[0-9a-fA-F]*", bytecode):
        raise DedaubError(f"bytecode file is not hex bytecode: {path}")
    return bytecode if bytecode.startswith("0x") else f"0x{bytecode}"


def target_output_dir(base_out_dir: Path, chain_id: str, address: str) -> Path:
    return base_out_dir / str(chain_id) / address.lower()


def submit_and_poll(
    bytecode: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    request_timeout_seconds: float,
    once: bool,
    transport: str,
) -> tuple[str, str, list[dict[str, Any]], Any | None]:
    md5_response = request_json(
        "POST",
        f"{base_url}/api/on_demand",
        api_key,
        payload=bytecode,
        timeout=request_timeout_seconds,
        transport=transport,
    )
    md5 = md5_from_response(md5_response)
    history: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout_seconds
    status = "UNKNOWN"

    while True:
        status_response = request_json(
            "GET",
            f"{base_url}/api/on_demand/{md5}/status",
            api_key,
            timeout=request_timeout_seconds,
            transport=transport,
        )
        status = status_from_response(status_response)
        history.append({"status": status, "response": status_response, "checked_at_unix": time.time()})
        if status == COMPLETED_STATUS:
            decompilation = request_json(
                "GET",
                f"{base_url}/api/on_demand/decompilation/{md5}",
                api_key,
                timeout=request_timeout_seconds,
                transport=transport,
            )
            return md5, status, history, decompilation
        if once or status not in PENDING_STATUSES or time.monotonic() >= deadline:
            return md5, status, history, None
        time.sleep(poll_interval_seconds)


def decompile_target(
    target: dict[str, Any],
    chain_id: str,
    out_dir: Path,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    request_timeout_seconds: float,
    once: bool,
    transport: str,
) -> dict[str, Any]:
    address = str(target.get("address") or "")
    result: dict[str, Any] = {
        "address": address,
        "bytecode_path": target.get("bytecode_path"),
        "reason": target.get("reason"),
        "status": "skipped",
        "md5": None,
        "output_dir": None,
        "artifacts": {},
        "status_history": [],
        "error": None,
    }
    bytecode_path_raw = target.get("bytecode_path")
    if not bytecode_path_raw:
        result["error"] = "no runtime bytecode path; recover trace-created bytecode before Dedaub submission"
        return result

    bytecode_path = Path(str(bytecode_path_raw))
    try:
        bytecode = read_bytecode(bytecode_path)
        md5, status, history, decompilation = submit_and_poll(
            bytecode,
            base_url,
            api_key,
            timeout_seconds,
            poll_interval_seconds,
            request_timeout_seconds,
            once,
            transport,
        )
        result["md5"] = md5
        result["status"] = status
        result["status_history"] = history
        address_out_dir = target_output_dir(out_dir, chain_id, address)
        result["output_dir"] = str(address_out_dir)
        write_json(address_out_dir / "status_history.json", history)

        if decompilation is not None:
            artifacts = {
                "decompilation_json": "decompilation.json",
                "source": "source.sol",
                "yul": "yul.yul",
                "tac": "tac.txt",
                "disassembled": "disassembled.txt",
            }
            write_json(address_out_dir / "decompilation.json", decompilation)
            if isinstance(decompilation, dict):
                write_text(address_out_dir / "source.sol", decompilation.get("source"))
                write_text(address_out_dir / "yul.yul", decompilation.get("yul"))
                write_text(address_out_dir / "tac.txt", decompilation.get("tac"))
                write_text(address_out_dir / "disassembled.txt", decompilation.get("disassembled"))
            result["artifacts"] = artifacts
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result


def default_out_dir(manifest_path: Path) -> Path:
    if manifest_path.parent.name == "contract_context":
        return manifest_path.parent.parent / "decompiled"
    return manifest_path.parent / "decompiled"


def selected_targets(manifest: dict[str, Any], addresses: list[str]) -> list[dict[str, Any]]:
    targets = [target for target in manifest.get("decompiler_targets", []) if isinstance(target, dict)]
    if not addresses:
        return targets
    allowed = {address.lower() for address in addresses}
    return [target for target in targets if str(target.get("address", "")).lower() in allowed]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit contract_context decompiler targets to Dedaub on-demand API."
    )
    parser.add_argument("manifest", help="contract_context_manifest.json")
    parser.add_argument("--out-dir", default=None, help="Output directory for decompiled artifacts.")
    parser.add_argument("--address", action="append", default=[], help="Only decompile this address. Repeatable.")
    parser.add_argument("--api-key", default=os.getenv("DEDAUB_API_KEY"), help="Dedaub API key. Secrets are not printed.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("DEDAUB_API_URL") or DEFAULT_BASE_URL,
        help="Dedaub-compatible API base URL.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--poll-interval-seconds", type=float, default=2)
    parser.add_argument("--request-timeout-seconds", type=float, default=30)
    parser.add_argument(
        "--transport",
        choices=("auto", "curl", "urllib"),
        default="auto",
        help="HTTP transport. auto prefers curl because Dedaub/Cloudflare may reject urllib's default signature.",
    )
    parser.add_argument("--once", action="store_true", help="Submit and check status once without polling.")
    parser.add_argument(
        "--require-completed",
        action="store_true",
        help="Exit non-zero when any bytecode-backed target is not COMPLETED.",
    )
    args = parser.parse_args()

    if not args.api_key:
        sys.stderr.write(
            "Missing Dedaub API key. Set DEDAUB_API_KEY or pass --api-key. "
            "DEDAUB_API_URL alone is only a base URL override and is not auth.\n"
        )
        return 2

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    chain_id = str(manifest.get("chain_id") or "unknown")
    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir(manifest_path)
    base_url = normalize_base_url(args.base_url)
    targets = selected_targets(manifest, args.address)
    results = [
        decompile_target(
            target,
            chain_id,
            out_dir,
            base_url,
            args.api_key,
            args.timeout_seconds,
            args.poll_interval_seconds,
            args.request_timeout_seconds,
            args.once,
            args.transport,
        )
        for target in targets
    ]
    output = {
        "chain_id": chain_id,
        "base_url": base_url,
        "target_count": len(targets),
        "completed_count": sum(1 for result in results if result["status"] == COMPLETED_STATUS),
        "skipped_count": sum(1 for result in results if result["status"] == "skipped"),
        "error_count": sum(1 for result in results if result["status"] == "error"),
        "results": results,
    }
    write_json(out_dir / "dedaub_decompilation_manifest.json", output)
    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if args.require_completed:
        bytecode_backed = [result for result in results if result.get("bytecode_path")]
        if any(result["status"] != COMPLETED_STATUS for result in bytecode_backed):
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
