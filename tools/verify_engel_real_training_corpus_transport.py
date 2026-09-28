#!/usr/bin/env python3
"""Offline behavioral gate for run-scoped construction-corpus transport.

No SSH, model, service, or training command is executed.  Remote helpers are replaced
with deterministic fakes while the real cycle planning, validation, receipt, and
failure branches run.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import inspect
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (ROOT, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_engel_real_training_cycle as cycle  # noqa: E402


checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str) -> None:
    checks.append((name, bool(condition), detail))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


temp_parent = ROOT / "runtime" / "temp"
temp_parent.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix="engel_corpus_transport_", dir=str(temp_parent)))
complete_root = work / "complete"
empty_root = work / "empty"
partial_root = work / "partial"
for directory in (complete_root / "extracted", empty_root, partial_root):
    directory.mkdir(parents=True, exist_ok=True)

(complete_root / "CONSTRUCTION_CORPUS_MANIFEST.json").write_text(
    json.dumps({"schema": "fixture_manifest_v2"}), encoding="utf-8"
)
(complete_root / "CONSTRUCTION_SECTION_INDEX.json").write_text(
    json.dumps({"schema": "fixture_index_v2", "sections": {"1.1": []}}),
    encoding="utf-8",
)
(complete_root / "extracted" / "fixture.jsonl").write_text(
    json.dumps({"doc": "fixture.pdf", "page": 1, "text": "SECTION 1.1 fixture"}) + "\n",
    encoding="utf-8",
)
(partial_root / "CONSTRUCTION_CORPUS_MANIFEST.json").write_text(
    json.dumps({"schema": "fixture_manifest_v2"}), encoding="utf-8"
)

original_verify = getattr(cycle.construction_corpus, "verify_corpus_bundle", None)


def fixture_verifier(root: Path | str | None = None) -> dict[str, Any]:
    corpus_root = Path(root or complete_root)
    if corpus_root == partial_root:
        return {
            "ok": False,
            "files": [],
            "bundle_sha256": "",
            "blockers": ["index and extracted set are missing"],
        }
    records = []
    for path in sorted(item for item in corpus_root.rglob("*") if item.is_file()):
        records.append(
            {
                "relative_path": path.relative_to(corpus_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    material = "\n".join(
        f"{item['relative_path']}:{item['bytes']}:{item['sha256']}" for item in records
    ).encode("utf-8")
    return {
        "ok": True,
        "files": records,
        "bundle_sha256": hashlib.sha256(material).hexdigest(),
        "blockers": [],
    }


try:
    cycle.construction_corpus.verify_corpus_bundle = fixture_verifier
    complete = cycle.inspect_construction_corpus_bundle(
        complete_root, "realtrain_fixture_complete"
    )
    check(
        "complete_bundle_is_exactly_planned",
        complete.get("ok") is True
        and complete.get("mode") == "complete"
        and len(complete.get("files") or []) == 3
        and all(item.get("sha256") for item in complete.get("files") or []),
        f"mode={complete.get('mode')} files={len(complete.get('files') or [])}",
    )
    complete_contract = {
        "construction_corpus": cycle.construction_corpus_receipt(complete)
    }
    binding_ok, _binding_detail = cycle.corpus_binding_verdict(
        complete_contract,
        {
            "construction_corpus_root": complete["ct_root"],
            "construction_corpus_verified": True,
            "construction_corpus_bundle_sha256": complete["bundle_sha256"],
        },
    )
    wrong_binding, wrong_detail = cycle.corpus_binding_verdict(
        complete_contract,
        {
            "construction_corpus_root": "/opt/engel/memory/training/construction_env",
            "construction_corpus_verified": True,
            "construction_corpus_bundle_sha256": complete["bundle_sha256"],
        },
    )
    check(
        "builder_receipt_must_echo_the_exact_run_scoped_binding",
        binding_ok and not wrong_binding and "assigned" in wrong_detail,
        f"good={binding_ok} wrong={wrong_detail}",
    )

    partial = cycle.inspect_construction_corpus_bundle(
        partial_root, "realtrain_fixture_partial"
    )
    check(
        "partial_bundle_fails_before_remote_work",
        partial.get("ok") is False
        and partial.get("mode") == "invalid"
        and bool(partial.get("blockers")),
        repr(partial.get("blockers")),
    )

    def verifier_must_not_run(_root: Any = None) -> dict[str, Any]:
        raise AssertionError("empty root must not be mistaken for a partial bundle")

    cycle.construction_corpus.verify_corpus_bundle = verifier_must_not_run
    empty = cycle.inspect_construction_corpus_bundle(empty_root, "realtrain_fixture_empty")
    check(
        "absent_corpus_gets_explicit_empty_mode",
        empty.get("ok") is True
        and empty.get("mode") == "empty"
        and empty.get("files") == []
        and empty.get("ct_root", "").endswith("/realtrain_fixture_empty/construction_corpus"),
        repr(empty),
    )
    empty_binding, empty_binding_detail = cycle.corpus_binding_verdict(
        {"construction_corpus": cycle.construction_corpus_receipt(empty)},
        {
            "construction_corpus_root": empty["ct_root"],
            "construction_corpus_verified": False,
            "construction_corpus_bundle_sha256": "",
        },
    )
    check(
        "builder_receipt_can_prove_the_explicit_empty_contract",
        empty_binding,
        empty_binding_detail,
    )

    cycle.construction_corpus.verify_corpus_bundle = fixture_verifier
    originals = {
        name: getattr(cycle, name)
        for name in ("ssh_run", "run_local", "remote_sha256", "remote_file_set")
    }
    scp_calls: list[list[str]] = []
    try:
        cycle.ssh_run = lambda _cfg, _command, _timeout, **_kwargs: {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }

        def fake_copy(argv: list[str], _timeout: float) -> dict[str, Any]:
            scp_calls.append(list(argv))
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

        cycle.run_local = fake_copy
        cycle.remote_sha256 = lambda _cfg, paths: {
            "ok": True,
            "hashes": {
                str(item["remote_path"]): str(item["sha256"])
                for item in complete.get("files") or []
                if str(item["remote_path"]) in set(paths)
            },
            "stderr": "",
        }
        cycle.remote_file_set = lambda _cfg, _root: {
            "ok": True,
            "paths": sorted(item["remote_path"] for item in complete.get("files") or []),
            "stderr": "",
        }
        receipt = {"steps": [], "blockers": []}
        with contextlib.redirect_stdout(io.StringIO()):
            pushed = cycle.push_construction_corpus(
                receipt, {"target": "root@fixture", "key": "", "port": ""}, complete
            )
        evidence = receipt.get("construction_corpus") or {}
        check(
            "complete_transfer_persists_hash_evidence",
            pushed
            and evidence.get("remote_verified") is True
            and evidence.get("bundle_sha256") == complete.get("bundle_sha256")
            and len(evidence.get("files") or []) == 3
            and all(
                item.get("remote_sha256") == item.get("sha256")
                for item in evidence.get("files") or []
            )
            and len(scp_calls) == 3,
            f"pushed={pushed} scp={len(scp_calls)} evidence={evidence.get('remote_verified')}",
        )

        set_plan = cycle.inspect_construction_corpus_bundle(
            complete_root, "realtrain_fixture_set_mismatch"
        )
        cycle.remote_sha256 = lambda _cfg, paths: {
            "ok": True,
            "hashes": {
                str(item["remote_path"]): str(item["sha256"])
                for item in set_plan.get("files") or []
                if str(item["remote_path"]) in set(paths)
            },
            "stderr": "",
        }
        cycle.remote_file_set = lambda _cfg, root: {
            "ok": True,
            "paths": sorted(
                [item["remote_path"] for item in set_plan.get("files") or []]
                + [f"{root}/unexpected-stale.jsonl"]
            ),
            "stderr": "",
        }
        set_receipt = {"steps": [], "blockers": []}
        with contextlib.redirect_stdout(io.StringIO()):
            set_ok = cycle.push_construction_corpus(
                set_receipt,
                {"target": "root@fixture", "key": "", "port": ""},
                set_plan,
            )
        check(
            "unexpected_remote_file_fails_the_exact_set_gate",
            not set_ok
            and (set_receipt.get("construction_corpus") or {}).get("remote_verified") is False
            and any(
                "file set mismatch" in blocker
                for blocker in (set_receipt.get("construction_corpus") or {}).get("blockers", [])
            ),
            repr((set_receipt.get("construction_corpus") or {}).get("blockers")),
        )

        empty_for_push = copy.deepcopy(empty)
        cycle.remote_sha256 = lambda _cfg, paths: {
            "ok": not paths,
            "hashes": {},
            "stderr": "",
        }
        cycle.remote_file_set = lambda _cfg, _root: {
            "ok": True,
            "paths": [],
            "stderr": "",
        }
        empty_receipt = {"steps": [], "blockers": []}
        with contextlib.redirect_stdout(io.StringIO()):
            empty_pushed = cycle.push_construction_corpus(
                empty_receipt,
                {"target": "root@fixture", "key": "", "port": ""},
                empty_for_push,
            )
        check(
            "empty_mode_reserves_and_proves_an_empty_run_root",
            empty_pushed
            and (empty_receipt.get("construction_corpus") or {}).get("remote_verified") is True
            and (empty_receipt.get("construction_corpus") or {}).get("files") == [],
            repr(empty_receipt.get("construction_corpus")),
        )

        failed_plan = cycle.inspect_construction_corpus_bundle(
            complete_root, "realtrain_fixture_failed_copy"
        )
        cycle.run_local = lambda _argv, _timeout: {
            "ok": False,
            "returncode": 1,
            "stdout": "",
            "stderr": "simulated short copy",
        }
        cycle.remote_sha256 = lambda _cfg, _paths: {
            "ok": False,
            "hashes": {},
            "stderr": "missing remote bytes",
        }
        cycle.remote_file_set = lambda _cfg, _root: {
            "ok": True,
            "paths": [],
            "stderr": "",
        }
        failed_receipt = {"steps": [], "blockers": []}
        with contextlib.redirect_stdout(io.StringIO()):
            failed = cycle.push_construction_corpus(
                failed_receipt,
                {"target": "root@fixture", "key": "", "port": ""},
                failed_plan,
            )
        check(
            "failed_transfer_is_fail_closed_and_run_isolated",
            not failed
            and bool(failed_receipt.get("blockers"))
            and failed_plan["ct_root"]
            != cycle.ct_construction_corpus_dir("realtrain_fixture_next_cycle")
            and "/realtrain_fixture_failed_copy/" in failed_plan["ct_root"],
            f"failed={failed} root={failed_plan.get('ct_root')}",
        )

        existing_plan = copy.deepcopy(empty)
        cycle.ssh_run = lambda _cfg, _command, _timeout, **_kwargs: {
            "ok": False,
            "returncode": 73,
            "stdout": "",
            "stderr": "refusing existing cycle corpus root",
        }
        existing_receipt = {"steps": [], "blockers": []}
        with contextlib.redirect_stdout(io.StringIO()):
            existing_ok = cycle.push_construction_corpus(
                existing_receipt,
                {"target": "root@fixture", "key": "", "port": ""},
                existing_plan,
            )
        check(
            "preexisting_run_root_is_never_reused",
            not existing_ok and "fresh run-scoped" in existing_receipt["steps"][-1]["detail"],
            existing_receipt["steps"][-1]["detail"],
        )
    finally:
        for name, value in originals.items():
            setattr(cycle, name, value)

    plan_receipt: dict[str, Any] = {
        "run_id": "realtrain_fixture_plan",
        "steps": [],
        "blockers": [],
        "packs": {
            "ct_stage_dir": f"{cycle.CT_CYCLE_RUN_DIR}/realtrain_fixture_plan/packs"
        },
        "construction_corpus": cycle.construction_corpus_receipt(
            cycle.inspect_construction_corpus_bundle(
                complete_root, "realtrain_fixture_plan"
            )
        ),
    }
    args = argparse.Namespace(
        no_push_tools=False,
        targets=cycle.normalize_training_targets("slm,llm"),
        slm_tasks=cycle.DEFAULT_SLM_TASKS,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        cycle.plan_remote_steps(
            plan_receipt,
            {"target": "root@fixture"},
            args,
            {"files": 2},
        )
    planned = {item["step"]: str(item.get("command") or "") for item in plan_receipt["steps"]}
    planned_root = plan_receipt["construction_corpus"]["ct_root"]
    check(
        "dry_run_shows_corpus_transport_and_explicit_builder_roots",
        "push_construction_corpus" in planned
        and planned_root in planned["push_construction_corpus"]
        and f"--corpus-root {planned_root}" in planned["build_dataset"]
        and f"--training-target llm" in planned["build_dataset"]
        and f"--corpus-root {planned_root}" in planned["slm_datasets"]
        and f"--training-target slm" in planned["slm_datasets"],
        repr(planned),
    )
    check(
        "canary_gate_is_in_the_ct_tool_roster",
        "run_engel_ct246_lora_canary_gate.py" in cycle.CT_TOOL_FILES,
        repr(cycle.CT_TOOL_FILES),
    )
    pretty_payload = {
        "construction_corpus_root": planned_root,
        "construction_corpus_verified": True,
        "nested": {"value": 1},
    }
    check(
        "pretty_printed_builder_receipt_is_parseable",
        cycle.last_json_object("builder log\n" + json.dumps(pretty_payload, indent=2))
        == pretty_payload,
        "SLM builder emits its manifest as indented JSON",
    )

    # A zero exit code is not proof that the staged session material reached the SFT
    # dataset. Exercise the real build step with deterministic SSH replies and require
    # the admitted>0 / consumed=0 branch to become a hard false result.
    original_ssh_run = cycle.ssh_run
    try:
        expected_root = (
            "/opt/engel/run/real_training/fixture_missing_rows/construction_corpus"
        )
        expected_digest = "a" * 64

        def fake_dataset_ssh(
            _cfg: dict[str, Any],
            command: str,
            _timeout: float,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            if command.startswith("cat "):
                return {
                    "ok": False,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "fixture has no separate receipt",
                }
            return {
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "raw_counts": {"prompt_training": 0},
                        "train": 100,
                        "val": 10,
                        "dataset": "/opt/engel/memory/training/datasets/latest",
                        "training_target": "llm",
                        "prompt_training_target_filter": {
                            "training_target": "llm",
                            "rows_explicitly_targeting": 3,
                        },
                        "construction_corpus_root": expected_root,
                        "construction_corpus_verified": True,
                        "construction_corpus_bundle_sha256": expected_digest,
                    }
                ),
                "stderr": "",
            }

        cycle.ssh_run = fake_dataset_ssh
        missing_rows_receipt: dict[str, Any] = {
            "steps": [],
            "blockers": [],
            "construction_corpus": {
                "mode": "complete",
                "ct_root": expected_root,
                "bundle_sha256": expected_digest,
            },
        }
        with contextlib.redirect_stdout(io.StringIO()):
            missing_rows_ok = cycle.step_build_dataset(
                missing_rows_receipt,
                {"target": "root@fixture"},
                "python3",
                3,
                "/opt/engel/run/real_training/fixture_missing_rows/packs",
                expected_rows_seen=3,
                expected_explicit_rows=3,
            )
        check(
            "zero_consumed_admitted_rows_is_a_hard_build_failure",
            not missing_rows_ok
            and (missing_rows_receipt.get("dataset") or {}).get(
                "prompt_training_consumed"
            )
            is False
            and missing_rows_receipt.get("steps", [])[-1].get("ok") is False
            and any(
                "did not consume the exact validated pack roster" in item
                for item in missing_rows_receipt.get("blockers", [])
            ),
            repr(missing_rows_receipt.get("blockers")),
        )
        run_cycle_source = inspect.getsource(cycle.run_cycle)
        dataset_build = run_cycle_source.index("dataset_ok = step_build_dataset")
        slm_training_branch = run_cycle_source.index(
            '\n    if "slm" in targets:', dataset_build
        )
        check(
            "llm_dataset_failure_does_not_cross_contaminate_slm_lane",
            "return finish" not in run_cycle_source[dataset_build:slm_training_branch]
            and 'packs["admitted_by_target"]["llm"]'
            in run_cycle_source[dataset_build:slm_training_branch],
            "an LLM-filtered SFT refusal must not abort the independent SLM builder",
        )
    finally:
        cycle.ssh_run = original_ssh_run
finally:
    if original_verify is None:
        try:
            delattr(cycle.construction_corpus, "verify_corpus_bundle")
        except AttributeError:
            pass
    else:
        cycle.construction_corpus.verify_corpus_bundle = original_verify
    shutil.rmtree(work, ignore_errors=True)


passed = sum(1 for _name, ok, _detail in checks if ok)
for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'} {name} :: {detail}")
print(f"\n{passed}/{len(checks)} checks passed")
print("verify_engel_real_training_corpus_transport: " + ("GREEN" if passed == len(checks) else "RED"))
raise SystemExit(0 if passed == len(checks) else 1)
