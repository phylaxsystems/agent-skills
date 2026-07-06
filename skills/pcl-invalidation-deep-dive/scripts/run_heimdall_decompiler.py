#!/usr/bin/env python3
"""Run Heimdall-rs decompilation for contract-context targets."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class HeimdallError(RuntimeError):
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
        raise HeimdallError(f"bytecode file is empty: {path}")
    if not re.fullmatch(r"(0x)?[0-9a-fA-F]*", bytecode):
        raise HeimdallError(f"bytecode file is not hex bytecode: {path}")
    return bytecode if bytecode.startswith("0x") else f"0x{bytecode}"


def resolve_heimdall(explicit: str | None) -> str:
    candidate = explicit or os.getenv("HEIMDALL_BIN") or "heimdall"
    if os.path.sep in candidate:
        path = Path(candidate).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
        raise HeimdallError(f"heimdall binary is not executable: {candidate}")
    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    raise HeimdallError("Missing Heimdall-rs. Install `heimdall` on PATH or set HEIMDALL_BIN.")


def list_relative_files(out_dir: Path) -> list[str]:
    if not out_dir.exists():
        return []
    files = [path.relative_to(out_dir).as_posix() for path in out_dir.rglob("*") if path.is_file()]
    return sorted(files)


def command_preview(argv: list[str], bytecode: str) -> list[str]:
    return ["<bytecode>" if item == bytecode else item for item in argv]


def run_target(
    target: dict[str, Any],
    chain_id: str,
    out_dir: Path,
    heimdall_bin: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    address = str(target.get("address") or "")
    result: dict[str, Any] = {
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
        result["error"] = "no runtime bytecode path; recover trace-created bytecode before Heimdall decompilation"
        return result

    address_out_dir = target_output_dir(out_dir, chain_id, address)
    result["output_dir"] = str(address_out_dir)

    try:
        bytecode_path = Path(str(bytecode_path_raw)).expanduser().resolve()
        bytecode = read_bytecode(bytecode_path)
        address_out_dir.mkdir(parents=True, exist_ok=True)
        write_json(address_out_dir / "target.json", target)
        write_text(address_out_dir / "bytecode.txt", bytecode)

        argv = [
            heimdall_bin,
            "decompile",
            bytecode,
            "--default",
            "--include-sol",
            "--output",
            "print",
        ]
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
            if re.search(r"\b(contract|library|interface|function)\b", completed.stdout):
                write_text(address_out_dir / "source.sol", completed.stdout)

        write_json(
            address_out_dir / "heimdall.json",
            {
                "heimdall_bin": heimdall_bin,
                "argv_preview": command_preview(argv, bytecode),
                "started_at_unix": started_at,
                "ended_at_unix": ended_at,
                "duration_seconds": round(ended_at - started_at, 6),
                "returncode": completed.returncode,
            },
        )

        result["returncode"] = completed.returncode
        result["status"] = "completed" if completed.returncode == 0 else "error"
        if completed.returncode != 0:
            result["error"] = f"heimdall decompile exited {completed.returncode}"
        result["artifacts"] = {path: path for path in list_relative_files(address_out_dir)}
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Heimdall-rs for contract_context decompiler targets.")
    parser.add_argument("manifest", help="contract_context_manifest.json")
    parser.add_argument("--out-dir", default=None, help="Output directory for decompiled artifacts.")
    parser.add_argument("--address", action="append", default=[], help="Only decompile this address. Repeatable.")
    parser.add_argument("--heimdall-bin", default=None, help="Path or command name for heimdall. Defaults to HEIMDALL_BIN or heimdall on PATH.")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="Exit non-zero when any bytecode-backed target did not decompile successfully.",
    )
    args = parser.parse_args()

    try:
        heimdall_bin = resolve_heimdall(args.heimdall_bin)
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    chain_id = str(manifest.get("chain_id") or "unknown")
    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir(manifest_path)
    targets = selected_targets(manifest, args.address)

    results = [
        run_target(target, chain_id, out_dir, heimdall_bin, args.timeout_seconds)
        for target in targets
    ]
    output = {
        "chain_id": chain_id,
        "decompiler": "heimdall-rs",
        "heimdall_bin": heimdall_bin,
        "target_count": len(targets),
        "completed_count": sum(1 for result in results if result["status"] == "completed"),
        "skipped_count": sum(1 for result in results if result["status"] == "skipped"),
        "error_count": sum(1 for result in results if result["status"] == "error"),
        "results": results,
    }
    write_json(out_dir / "heimdall_decompilation_manifest.json", output)
    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if args.require_success:
        bytecode_backed = [result for result in results if result.get("bytecode_path")]
        if any(result["status"] != "completed" for result in bytecode_backed):
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
