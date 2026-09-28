#!/usr/bin/env python3
"""Build the shareable Engel AI Main CLI client package.

The artifact is intentionally a thin client.  This builder records that fact
in a manifest, emits per-file checksums, and writes a checksum sidecar for the
ZIP itself.  No credentials or provider/network calls are involved.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workflows" / "engel_ai_main_cli_api_share"
DIST = ROOT / "dist"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d")
ZIP_NAME = f"EngelAI-Main-CLI-API-{STAMP}.zip"
PACKAGE_PREFIX = "EngelAI-Main-CLI-API"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_zip_member(zf: zipfile.ZipFile, path: Path, arcname: str) -> None:
    """Write a reproducible member and preserve the shell launch bit."""
    info = zipfile.ZipInfo(arcname)
    info.date_time = (2020, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = 0o755 if path.name.endswith(".sh") else 0o644
    info.external_attr = (mode & 0xFFFF) << 16
    zf.writestr(info, path.read_bytes())


def main() -> int:
    SRC.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "engel_ai_main_api_client.py", SRC / "engel_ai_main_api_client.py")
    DIST.mkdir(parents=True, exist_ok=True)
    zip_path = DIST / ZIP_NAME
    payload_names = [
        "README.md",
        "config.example.json",
        "engel_ai_main_api_client.py",
        "Engel-AI-Main-API.cmd",
        "Engel-AI-Main-API.sh",
    ]
    missing = [name for name in payload_names if not (SRC / name).is_file()]
    if missing:
        raise SystemExit("Missing package inputs: " + ", ".join(missing))

    payload_hashes = {name: _sha256(SRC / name) for name in payload_names}
    manifest = {
        "schema": "engel_ai_main_cli_api_package_manifest_v2",
        "package_kind": "client_only",
        "transport": ["ssh_stdio", "local_stdio"],
        "http": False,
        "secrets": False,
        "payload_files": payload_names,
        "payload_sha256": payload_hashes,
        "requires": [
            "Python 3.10 or newer",
            "OpenSSH client for ssh_stdio",
            "an approved key-based SSH account for the selected Engel host",
        ],
        "local_stdio_requires": [
            "the complete Engel App source tree and its local runtime",
            "ENGEL_ROOT or ENGEL_APP_ROOT when that tree is not beside the client",
        ],
        "host_api": "engel_ai_main_api.py must already be installed on the SSH host",
    }
    manifest_path = SRC / "PACKAGE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum_names = payload_names + ["PACKAGE_MANIFEST.json"]
    checksum_path = SRC / "SHA256SUMS.txt"
    checksum_path.write_text(
        "".join(f"{_sha256(SRC / name)}  {name}\n" for name in checksum_names),
        encoding="utf-8",
    )
    names = checksum_names + ["SHA256SUMS.txt"]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            path = SRC / name
            _write_zip_member(zf, path, PACKAGE_PREFIX + "/" + name)

    zip_sha256 = _sha256(zip_path)
    sidecar = zip_path.with_suffix(zip_path.suffix + ".sha256")
    sidecar.write_text(f"{zip_sha256}  {zip_path.name}\n", encoding="ascii")
    receipt = {
        "schema": "engel_ai_main_cli_api_package_receipt_v2",
        "ok": True,
        "zip": str(zip_path),
        "zip_sha256": zip_sha256,
        "checksum_sidecar": str(sidecar),
        "manifest": str(manifest_path),
        "files": names,
        "package_kind": "client_only",
        "http": False,
        "secrets": False,
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    (SRC / "PACKAGE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
