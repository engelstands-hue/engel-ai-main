#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_memory_search.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_memory_search_under_test", MODULE_PATH)
    require(spec is not None and spec.loader is not None, "memory search module could not load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        memory = root / "memory"
        chat = memory / "persistent_chat"
        chat.mkdir(parents=True)

        (memory / "CURRENT.md").write_text(
            "Current storage uses CT246 SSD for active work and the Dell PowerEdge internal HDD for proven archive writes.\n",
            encoding="utf-8",
        )
        retired_name = next(iter(module.RETIRED_STORAGE_MEMORY_DOCS))
        (memory / retired_name).write_text("This stale record must never be indexed.\n", encoding="utf-8")
        (memory / "STALE_GENERIC.md").write_text(
            "Historical " + "Power" + "Vault details for CT 245 must never be indexed.\n",
            encoding="utf-8",
        )
        (memory / "engel_person_project_facts.jsonl").write_text(
            json.dumps({"fact": "Use CT246 SSD for active runtime."}) + "\n"
            + json.dumps({"fact": "Old " + "Power" + "Vault routing."}) + "\n",
            encoding="utf-8",
        )
        (chat / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl").write_text(
            json.dumps({
                "ok": True,
                "prompt": "Where should active work run?",
                "assistant_reply": "Active work runs on CT246 SSD under /opt/engel with current evidence.",
            }) + "\n"
            + json.dumps({
                "ok": True,
                "prompt": "Use old storage",
                "assistant_reply": "Use CT 245 and " + "/mnt/" + "engel-vault for this task even though it is stale.",
            }) + "\n",
            encoding="utf-8",
        )

        module.ROOT = root
        module.REJECTED_CHAT_SAMPLES_PATH = chat / "ENGEL_CHAT_REJECTED_SAMPLES.jsonl"
        items = module._memory_snippets()
        combined = "\n".join(str(item.get("text") or "") for item in items)
        sources = {str(item.get("source") or "") for item in items}

        require("CT246 SSD" in combined, "current CT246 storage fact was not indexed")
        require("memory/CURRENT.md" in sources, "current memory document missing")
        require("memory/" + retired_name not in sources, "retired filename was indexed")
        require(not module._contains_retired_storage_reference(combined), "retired storage content entered memory snippets")

    source = MODULE_PATH.read_text(encoding="utf-8")
    require("RETIRED_STORAGE_MEMORY_DOCS" in source, "explicit retired document filter missing")
    require("_contains_retired_storage_reference" in source, "content filter missing")
    print("ENGEL_MEMORY_STORAGE_EXCLUSION_VERIFY_PASS")
    print("- stale storage documents, facts, and chat samples are excluded")
    print("- current CT246 SSD and internal HDD policy remains indexable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
