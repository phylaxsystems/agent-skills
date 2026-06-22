#!/usr/bin/env python3
"""Run a configured EVM decompiler backend for contract-context targets.

The runner is intentionally vendor-neutral. It can call a local/headless
command such as Heimdall or JEB, or POST bytecode to a JSON API owned by the
operator. The output is normalized into one directory per contract so the
triage report can cite decompiled artifacts without depending on a single
provider.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


COMMAND_ENV_VARS = [
    "HEIMDALL_DECOMPILE_CMD",
    "JEB_DECOMPILE_CMD",
    "EVM_DECOMPILER_CMD",
    "DECOMPILER_CMD",
    "DEDAUB_DECOMPILE_CMD",
]

API_URL_ENV_VARS = [
    "EVM_DECOMPILER_API_URL",
    "DECOMPILER_API_URL",
]

API_KEY_ENV_VARS = [
    "EVM_DECOMPILER_API_KEY",
    "DECOMPILER_API_KEY",
]


class DecompilerError(RuntimeError):
    pass


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, data: str | None) -> None:
    if data is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if data.endswith("\n") else data + "\n")


def default_out_dir(manifest_path: Path) -> Path:
    if manifest_path.parent.name == "contract_context":
        return manifest_path.parent.parent / "decompiled"
    return manifest_path.parent / "decompiled"


def target_output_dir(base_out_dir: Path, chain_id: str, address: str) -> Path:
    return base_out_dir / str(chain_id) / address.lower()


def selected_targets(manifest: dict[str, Any], addresses: list[str]) -> list[dict[str, Any]]:
    targets = [target for target in manifest.get("decompiler_targets", []) if isinstance(target, dict)]
    if not addresses:
        return targets
    allowed = {address.lower() for address in addresses}
    return [target for target in targets if str(target.get("address", "")).lower() in allowed]


def read_bytecode(path: Path) -> str:
    bytecode = path.read_text().strip()
    if not bytecode or bytecode == "0x":
        raise DecompilerError(f"bytecode file is empty: {path}")
    if not re.fullmatch(r"(0x)?[0-9a-fA-F]*", bytecode):
        raise DecompilerError(f"bytecode file is not hex bytecode: {path}")
    return bytecode if bytecode.startswith("0x") else f"0x{bytecode}"


def first_env(names: list[str]) -> tuple[str | None, str | None]:
    for name in names:
        value = os.getenv(name)
        if value:
            return name, value
    return None, None


def default_heimdall_command() -> str | None:
    if not shutil.which("heimdall"):
        return None
    return "heimdall decompile {bytecode} --default --include-sol --include-yul --output print"


def resolve_command(explicit: str | None) -> tuple[str | None, str | None]:
    if explicit:
        return "--cmd", explicit
    env_name, env_value = first_env(COMMAND_ENV_VARS)
    if env_value:
        return env_name, env_value
    heimdall_command = default_heimdall_command()
    if heimdall_command:
        return "heimdall on PATH", heimdall_command
    return None, None


def resolve_api_url(explicit: str | None) -> tuple[str | None, str | None]:
    if explicit:
        return "--api-url", explicit
    return first_env(API_URL_ENV_VARS)


def resolve_api_key(explicit: str | None) -> tuple[str | None, str | None]:
    if explicit:
        return "--api-key", explicit
    return first_env(API_KEY_ENV_VARS)


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def argv_preview(argv: list[str], bytecode: str) -> list[str]:
    preview = []
    for item in argv:
        if item == bytecode:
            preview.append("<bytecode>")
        elif len(item) > 240 and re.fullmatch(r"(0x)?[0-9a-fA-F]+", item):
            preview.append("<long-hex>")
        else:
            preview.append(item)
    return preview


def list_relative_files(out_dir: Path) -> list[str]:
    if not out_dir.exists():
        return []
    files = [path.relative_to(out_dir).as_posix() for path in out_dir.rglob("*") if path.is_file()]
    return sorted(files)


def write_common_target_files(out_dir: Path, target: dict[str, Any], bytecode: str) -> None:
    write_json(out_dir / "target.json", target)
    write_text(out_dir / "bytecode.txt", bytecode)


def run_command_backend(
    target: dict[str, Any],
    chain_id: str,
    out_dir: Path,
    command_template: str,
    command_source: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    address = str(target.get("address") or "")
    result: dict[str, Any] = {
        "backend": "command",
        "backend_source": command_source,
        "address": address,
        "bytecode_path": target.get("bytecode_path"),
        "reason": target.get("reason"),
        "status": "skipped",
        "output_dir": None,
        "artifacts": {},
        "returncode": None,
        "error": None,
    }

    bytecode_path_raw = target.get("bytecode_path")
    if not bytecode_path_raw:
        result["error"] = "no runtime bytecode path; recover trace-created bytecode before decompilation"
        return result

    address_out_dir = target_output_dir(out_dir, chain_id, address)
    result["output_dir"] = str(address_out_dir)

    try:
        bytecode_path = Path(str(bytecode_path_raw)).expanduser().resolve()
        bytecode = read_bytecode(bytecode_path)
        address_out_dir.mkdir(parents=True, exist_ok=True)
        write_common_target_files(address_out_dir, target, bytecode)

        values = {
            "address": address,
            "address_lower": address.lower(),
            "chain_id": str(chain_id),
            "bytecode": bytecode,
            "bytecode_no_0x": bytecode[2:] if bytecode.startswith("0x") else bytecode,
            "bytecode_path": str(bytecode_path),
            "out_dir": str(address_out_dir),
        }
        command = render_template(command_template, values)
        argv = shlex.split(command)
        if not argv:
            raise DecompilerError("decompiler command template rendered to an empty command")

        started_at = time.time()
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        ended_at = time.time()

        write_text(address_out_dir / "stdout.txt", completed.stdout)
        write_text(address_out_dir / "stderr.txt", completed.stderr)
        if completed.stdout.strip():
            write_text(address_out_dir / "output.txt", completed.stdout)
            if (
                re.search(r"\b(contract|library|interface|function)\b", completed.stdout)
                and not (address_out_dir / "source.sol").exists()
            ):
                write_text(address_out_dir / "source.sol", completed.stdout)

        metadata = {
            "backend": "command",
            "backend_source": command_source,
            "command_template": command_template,
            "argv_preview": argv_preview(argv, bytecode),
            "started_at_unix": started_at,
            "ended_at_unix": ended_at,
            "duration_seconds": round(ended_at - started_at, 6),
            "returncode": completed.returncode,
        }
        write_json(address_out_dir / "command.json", metadata)

        result["returncode"] = completed.returncode
        result["status"] = "completed" if completed.returncode == 0 else "error"
        if completed.returncode != 0:
            result["error"] = f"decompiler command exited {completed.returncode}"
        result["artifacts"] = {path: path for path in list_relative_files(address_out_dir)}
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result


def request_api_json(
    url: str,
    payload: dict[str, Any],
    api_key: str | None,
    api_key_header: str,
    api_key_prefix: str,
    timeout_seconds: float,
) -> Any:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "phylax-pcl-invalidation-deep-dive/0.1",
    }
    if api_key:
        headers[api_key_header] = f"{api_key_prefix}{api_key}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise DecompilerError(f"POST {url} returned HTTP {exc.code}: {body[:1000]}") from exc
    except Exception as exc:
        raise DecompilerError(f"POST {url} failed: {exc}") from exc

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def write_api_artifacts(address_out_dir: Path, response: Any) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    if isinstance(response, dict):
        write_json(address_out_dir / "api_response.json", response)
        artifacts["api_response"] = "api_response.json"

        source = (
            response.get("source")
            or response.get("solidity")
            or response.get("decompiled")
            or response.get("code")
            or response.get("contract")
        )
        if isinstance(source, str):
            write_text(address_out_dir / "source.sol", source)
            artifacts["source"] = "source.sol"

        yul = response.get("yul")
        if isinstance(yul, str):
            write_text(address_out_dir / "yul.yul", yul)
            artifacts["yul"] = "yul.yul"

        disassembly = response.get("disassembly") or response.get("disassembled") or response.get("assembly")
        if isinstance(disassembly, str):
            write_text(address_out_dir / "disassembled.txt", disassembly)
            artifacts["disassembled"] = "disassembled.txt"

        abi = response.get("abi")
        if abi is not None:
            write_json(address_out_dir / "abi.json", abi)
            artifacts["abi"] = "abi.json"
    elif isinstance(response, str):
        write_text(address_out_dir / "api_response.txt", response)
        artifacts["api_response"] = "api_response.txt"
        if re.search(r"\b(contract|library|interface|function)\b", response):
            write_text(address_out_dir / "source.sol", response)
            artifacts["source"] = "source.sol"
    else:
        write_json(address_out_dir / "api_response.json", response)
        artifacts["api_response"] = "api_response.json"
    return artifacts


def run_api_backend(
    target: dict[str, Any],
    chain_id: str,
    out_dir: Path,
    api_url: str,
    api_url_source: str,
    api_key: str | None,
    api_key_header: str,
    api_key_prefix: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    address = str(target.get("address") or "")
    result: dict[str, Any] = {
        "backend": "api",
        "backend_source": api_url_source,
        "address": address,
        "bytecode_path": target.get("bytecode_path"),
        "reason": target.get("reason"),
        "status": "skipped",
        "output_dir": None,
        "artifacts": {},
        "error": None,
    }

    bytecode_path_raw = target.get("bytecode_path")
    if not bytecode_path_raw:
        result["error"] = "no runtime bytecode path; recover trace-created bytecode before decompilation"
        return result

    address_out_dir = target_output_dir(out_dir, chain_id, address)
    result["output_dir"] = str(address_out_dir)

    try:
        bytecode_path = Path(str(bytecode_path_raw)).expanduser().resolve()
        bytecode = read_bytecode(bytecode_path)
        address_out_dir.mkdir(parents=True, exist_ok=True)
        write_common_target_files(address_out_dir, target, bytecode)
        payload = {
            "bytecode": bytecode,
            "address": address,
            "chain_id": str(chain_id),
            "target": target,
        }
        started_at = time.time()
        response = request_api_json(
            api_url,
            payload,
            api_key=api_key,
            api_key_header=api_key_header,
            api_key_prefix=api_key_prefix,
            timeout_seconds=timeout_seconds,
        )
        ended_at = time.time()
        artifacts = write_api_artifacts(address_out_dir, response)
        write_json(
            address_out_dir / "api_request.json",
            {
                "backend": "api",
                "api_url": api_url,
                "api_key_header": api_key_header if api_key else None,
                "has_api_key": bool(api_key),
                "started_at_unix": started_at,
                "ended_at_unix": ended_at,
                "duration_seconds": round(ended_at - started_at, 6),
                "payload": {key: value for key, value in payload.items() if key != "bytecode"},
            },
        )
        artifacts["api_request"] = "api_request.json"
        result["status"] = "completed"
        result["artifacts"] = artifacts
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result


def choose_backend(backend: str, command_template: str | None, api_url: str | None) -> str:
    if backend != "auto":
        return backend
    if command_template:
        return "command"
    if api_url:
        return "api"
    raise DecompilerError(
        "No decompiler backend configured. Set HEIMDALL_DECOMPILE_CMD, JEB_DECOMPILE_CMD, "
        "EVM_DECOMPILER_CMD, DECOMPILER_CMD, EVM_DECOMPILER_API_URL, DECOMPILER_API_URL, "
        "or install heimdall on PATH."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run configured decompiler backend for contract_context decompiler targets."
    )
    parser.add_argument("manifest", help="contract_context_manifest.json")
    parser.add_argument("--out-dir", default=None, help="Output directory for decompiled artifacts.")
    parser.add_argument("--address", action="append", default=[], help="Only decompile this address. Repeatable.")
    parser.add_argument("--backend", choices=("auto", "command", "api"), default="auto")
    parser.add_argument(
        "--cmd",
        default=None,
        help=(
            "Command template. Tokens: {bytecode_path}, {bytecode}, {bytecode_no_0x}, "
            "{address}, {address_lower}, {chain_id}, {out_dir}."
        ),
    )
    parser.add_argument("--api-url", default=None, help="Generic JSON decompiler API URL.")
    parser.add_argument("--api-key", default=None, help="Generic decompiler API key. Secrets are not printed.")
    parser.add_argument("--api-key-header", default="Authorization")
    parser.add_argument("--api-key-prefix", default="Bearer ")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="Exit non-zero when any bytecode-backed target did not decompile successfully.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    chain_id = str(manifest.get("chain_id") or "unknown")
    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir(manifest_path)
    targets = selected_targets(manifest, args.address)

    command_source, command_template = resolve_command(args.cmd)
    api_url_source, api_url = resolve_api_url(args.api_url)
    api_key_source, api_key = resolve_api_key(args.api_key)

    try:
        backend = choose_backend(args.backend, command_template, api_url)
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    results = []
    for target in targets:
        if backend == "command":
            if not command_template or not command_source:
                sys.stderr.write(
                    "Command backend selected but no command is configured. Set --cmd, "
                    "HEIMDALL_DECOMPILE_CMD, JEB_DECOMPILE_CMD, EVM_DECOMPILER_CMD, "
                    "or DECOMPILER_CMD.\n"
                )
                return 2
            results.append(
                run_command_backend(
                    target,
                    chain_id,
                    out_dir,
                    command_template,
                    command_source,
                    args.timeout_seconds,
                )
            )
            continue

        if backend == "api":
            if not api_url or not api_url_source:
                sys.stderr.write(
                    "API backend selected but no API URL is configured. Set --api-url, "
                    "EVM_DECOMPILER_API_URL, or DECOMPILER_API_URL.\n"
                )
                return 2
            results.append(
                run_api_backend(
                    target,
                    chain_id,
                    out_dir,
                    api_url,
                    api_url_source,
                    api_key,
                    args.api_key_header,
                    args.api_key_prefix,
                    args.timeout_seconds,
                )
            )

    output = {
        "chain_id": chain_id,
        "backend": backend,
        "backend_source": command_source if backend == "command" else api_url_source,
        "api_key_source": api_key_source if backend == "api" and api_key else None,
        "target_count": len(targets),
        "completed_count": sum(1 for result in results if result["status"] == "completed"),
        "skipped_count": sum(1 for result in results if result["status"] == "skipped"),
        "error_count": sum(1 for result in results if result["status"] == "error"),
        "results": results,
    }
    write_json(out_dir / "decompiler_manifest.json", output)
    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if args.require_success:
        bytecode_backed = [result for result in results if result.get("bytecode_path")]
        if any(result["status"] != "completed" for result in bytecode_backed):
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
