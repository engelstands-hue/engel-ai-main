#!/usr/bin/env python3
"""Verify the Engel AI Sub-Engel standalone package and GUI source."""

from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "dist" / "EngelAI-SubEngel-Standalone-20260607.zip"
STANDALONE = ROOT / "workflows" / "sub_engel_nodes" / "standalone"
GUI = STANDALONE / "engel_sub_engel_gui.py"

REQUIRED_ZIP_FILES = {
    "Start-EngelAISubEngel.cmd",
    "Start-EngelAISubEngel.ps1",
    "Run-EngelAISubEngelSelfTest.cmd",
    "Run-EngelAISubEngelSelfTest.ps1",
    "Run-EngelAISubEngelLifecycleDemo.cmd",
    "Run-EngelAISubEngelLifecycleDemo.ps1",
    "README_STANDALONE.md",
    "package_manifest.json",
    "BUILD_RECEIPT.json",
    "app/engel_sub_engel_gui.py",
    "app/engel_sub_engel_self_test.py",
    "app/engel_sub_engel_lifecycle_demo.py",
    "agent/engel_windows_sub_node_agent.py",
    "workflows/install_windows_sub_engel_node.ps1",
    "config/windows_sub_engel_file_structure.json",
    "models/sub_engel_local_helper_model.json",
    "models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf",
    "bin/README_PYTHON.txt",
}

REQUIRED_GUI_MARKERS = [
    "ENGEL AI SUB-ENGEL",
    "Main Work Orders",
    "Incoming Work",
    "Local Done Work",
    "Shared Sent Work",
    "Shared Root Files",
    "Start Agent",
    "Pair Code",
    "Self Test",
    "sub_engel_standalone_self_test",
    "standalone-self-test",
    "APPROVE_ENGEL_WINDOWS_SUB_NODE",
    "sub_engel_transport",
    "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
    "ENGEL_SHARED_ROOM_ROOT",
    "Import Selected Main Work Order",
    "main_work_order_imported",
    "Import Selected Shared Root File",
    "shared_root_file_imported",
    "Mark Selected Incoming Done",
    "sub_engel_work_completed",
    "Send Selected Done File To Shared Room",
    "shared_room_file_exported",
    "SUB_ENGEL_WORK_ORDERS",
    "SUB_ENGEL_SENT_WORK",
    "local_helper_model_file_check",
    "sha256_file",
    "workspace\" / \"jobs\" / \"incoming",
    "workspace\" / \"jobs\" / \"done",
    "models\" / \"sub_engel_local_helper_model.json",
]

FORBIDDEN_GUI_MARKERS = [
    "shell=True",
    "os.system",
    "diskpart",
    "Format-Volume",
    "New-Service",
    "Register-ScheduledTask",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    if not ZIP_PATH.exists():
        fail(f"missing zip: {ZIP_PATH}")
    if not GUI.exists():
        fail(f"missing GUI source: {GUI}")

    gui_text = GUI.read_text(encoding="utf-8")
    ast.parse(gui_text)
    for marker in REQUIRED_GUI_MARKERS:
        if marker not in gui_text:
            fail(f"GUI missing marker: {marker}")
    for marker in FORBIDDEN_GUI_MARKERS:
        if marker in gui_text:
            fail(f"GUI contains forbidden marker: {marker}")

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        names = set(zf.namelist())
        missing = sorted(REQUIRED_ZIP_FILES - names)
        if missing:
            fail(f"zip missing files: {missing}")
        manifest = json.loads(zf.read("package_manifest.json").decode("utf-8"))
        model_manifest = json.loads(zf.read("models/sub_engel_local_helper_model.json").decode("utf-8"))
        readme = zf.read("README_STANDALONE.md").decode("utf-8")
        model_info = zf.getinfo("models/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf")

    if manifest.get("branding") != "Engel AI":
        fail("package manifest is not Engel AI branded")
    if manifest.get("shows_received_and_sent_work") is not True:
        fail("package manifest does not declare received/sent work GUI")
    self_test = manifest.get("self_test") or {}
    for key in [
        "enabled",
        "writes_receipt",
        "cli_entrypoint",
        "checks_node_root",
        "checks_shared_room",
        "checks_pair_token_command",
        "checks_local_helper_model",
    ]:
        if self_test.get(key) is not True:
            fail(f"package manifest self-test flag must be true: {key}")
    lifecycle = manifest.get("lifecycle_demo") or {}
    for key in [
        "enabled",
        "cli_entrypoint",
        "imports_work_order",
        "marks_done",
        "exports_done_work",
        "writes_receipt",
    ]:
        if lifecycle.get(key) is not True:
            fail(f"package manifest lifecycle flag must be true: {key}")
    source_manifest = json.loads((STANDALONE / "package_manifest.json").read_text(encoding="utf-8"))
    shared_room = (
        source_manifest.get("local_sub_engel_transport")
        or source_manifest.get("google_drive_shared_room")
        or {}
    )
    if shared_room.get("enabled") is not True:
        fail("package manifest does not declare local Sub-Engel transport")
    if shared_room.get("room_name") not in {"sub_engel_transport", "ENGEL_SHARED_NODE_ROOM"}:
        fail("package manifest shared room name mismatch")
    if shared_room.get("shows_shared_room_files") is not True:
        fail("package manifest does not declare shared-room file GUI")
    if shared_room.get("work_order_folder") != "SUB_ENGEL_WORK_ORDERS":
        fail("package manifest shared-room work-order folder mismatch")
    if shared_room.get("separate_main_work_order_lane") is not True:
        fail("package manifest does not declare separate Main work-order lane")
    if shared_room.get("shows_main_work_order_files") is not True:
        fail("package manifest does not declare Main work-order visibility")
    if shared_room.get("imports_selected_file_to_incoming_work") is not True:
        fail("package manifest does not declare shared-room import")
    if shared_room.get("imports_selected_main_work_order_to_incoming_work") is not True:
        fail("package manifest does not declare Main work-order import")
    if shared_room.get("writes_import_receipt") is not True:
        fail("package manifest does not declare shared-room import receipts")
    if shared_room.get("marks_selected_incoming_done") is not True:
        fail("package manifest does not declare incoming completion")
    if shared_room.get("writes_completion_receipt") is not True:
        fail("package manifest does not declare completion receipts")
    if shared_room.get("exports_selected_done_file_to_shared_room") is not True:
        fail("package manifest does not declare shared-room export")
    if shared_room.get("shared_room_sent_work_folder") != "SUB_ENGEL_SENT_WORK":
        fail("package manifest shared-room sent folder mismatch")
    if shared_room.get("separate_shared_sent_work_lane") is not True:
        fail("package manifest does not declare separate shared sent-work lane")
    if shared_room.get("shows_shared_sent_work_files") is not True:
        fail("package manifest does not declare shared sent-work visibility")
    if shared_room.get("writes_export_receipt") is not True:
        fail("package manifest does not declare shared-room export receipts")
    if model_manifest.get("branding") != "Engel AI Sub-Engel":
        fail("local helper model manifest is not Sub-Engel branded")
    if model_manifest.get("status") != "included_gguf_model_file":
        fail("local helper model manifest does not declare included GGUF")
    included = model_manifest.get("included_model") or {}
    if included.get("sha256") != "041474553FCABFC2A2D67903F9D2C2E50BD92528E670DA4F33B5D0CE6E59FD55":
        fail("included model SHA256 is not recorded")
    if model_info.file_size != 522186592:
        fail(f"included model size mismatch: {model_info.file_size}")
    safety = model_manifest.get("safety") or {}
    for key in [
        "model_output_trusted",
        "command_execution_from_model",
        "trusted_memory_write_from_model",
        "auto_download",
        "provider_fallback",
        "network_download",
        "autonomy_from_model",
    ]:
        if safety.get(key) is not False:
            fail(f"model safety flag must be false: {key}")
    source_readme = (STANDALONE / "README_STANDALONE.md").read_text(encoding="utf-8")
    if "This is the branded standalone Sub-Engel node package" not in readme and "This is the branded standalone Sub-Engel node package" not in source_readme:
        fail("README does not describe standalone Engel-branded package")
    if (
        "Google Drive shared room files" not in readme
        and "Local Sub-Engel transport" not in source_readme
        and "local Sub-Engel transport" not in source_readme
    ):
        fail("README does not describe local Sub-Engel transport")
    if "Import Selected Main Work Order" not in readme:
        fail("README does not describe Main work-order import")
    if "Import Selected Shared Root File" not in readme:
        fail("README does not describe shared-root import")
    if "Mark Selected Incoming Done" not in readme:
        fail("README does not describe incoming completion")
    if "SUB_ENGEL_WORK_ORDERS" not in readme:
        fail("README does not describe Main work-order folder")
    if "SUB_ENGEL_SENT_WORK" not in readme:
        fail("README does not describe sent-work folder")
    if "Send Selected Done File To Shared Room" not in readme:
        fail("README does not describe shared-room export")
    if "Local Helper tab verifies" not in readme:
        fail("README does not describe local helper model verification")
    if "Self Test" not in readme:
        fail("README does not describe self-test")
    if "Run-EngelAISubEngelSelfTest.cmd" not in readme:
        fail("README does not describe CLI self-test")
    if "Run-EngelAISubEngelLifecycleDemo.cmd" not in readme:
        fail("README does not describe CLI lifecycle demo")

    print(json.dumps({"ok": True, "zip_path": str(ZIP_PATH), "files_checked": len(REQUIRED_ZIP_FILES)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
