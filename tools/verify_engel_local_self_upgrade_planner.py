#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

FIXTURE_MARKER = "planner-before-marker"


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    import engel_local_self_upgrade_planner as planner

    failures: list[str] = []
    relative = "tools/verify_engel_local_self_upgrade_planner.py"
    inventory = {
        "surfaces": {
            "chat": {
                "files": [{"relative_path": relative}],
                "verifiers": [{"relative_path": relative}],
            }
        }
    }
    old_line = "FIXTURE_MARKER = " + json.dumps(FIXTURE_MARKER)
    new_line = "FIXTURE_MARKER = " + json.dumps("planner-after-marker")

    def valid_model(_: str) -> dict[str, object]:
        return {
            "text": json.dumps(
                {
                    "diagnosis": "the planner fixture marker needs a bounded replacement",
                    "patch_plan": "replace only the unique fixture marker",
                    "operations": [
                        {
                            "op": "replace_text",
                            "file": relative,
                            "old_text": old_line,
                            "new_text": new_line,
                        }
                    ],
                    "lesson": "Exact current source text must bind every local patch candidate.",
                    "extra_required_verifiers": [
                        "tools/verify_engel_local_self_upgrade_planner.py"
                    ],
                }
            ),
            "model": "fixture-local-coder",
            "model_result": {"model_cache_active_count": 1},
        }

    result = planner.plan_request(
        {
            "request_text": "Fix the chat planner fixture marker without changing anything else.",
            "affected_surface": "chat",
            "severity": "medium",
            "target_files": [relative],
        },
        model_generate_fn=valid_model,
        inventory=inventory,
    )
    cycle_request = result.get("cycle_request") or {}
    require(result.get("ok") is True, "valid local plan did not pass", failures)
    require(result.get("provider_called") is False, "provider was claimed", failures)
    require(
        result.get("source_mutation_performed") is False,
        "planner claimed source mutation",
        failures,
    )
    require(
        cycle_request.get("affected_surface") == "chat",
        "cycle surface was not preserved",
        failures,
    )
    require(
        cycle_request.get("files_to_change") == [relative],
        "changed files were not derived from validated operations",
        failures,
    )
    require(
        (cycle_request.get("operations") or [{}])[0].get("old_text")
        == old_line,
        "exact old_text was not preserved",
        failures,
    )
    receipt = ROOT / str(result.get("receipt_path") or "").replace("\\", "/")
    require(receipt.is_file(), "local plan receipt was not written", failures)

    inferred_targets = planner._mentioned_declared_files(
        inventory["surfaces"]["chat"],
        (
            "Review tools/verify_engel_local_self_upgrade_planner.py, but ignore "
            "tools/not_owned_by_this_surface.py."
        ),
    )
    require(
        inferred_targets == [relative],
        "exact inventory-owned file path was not recovered from operator text",
        failures,
    )
    inferred_result = planner.plan_request(
        {
            "request_text": (
                "Fix the chat planner fixture in "
                "tools/verify_engel_local_self_upgrade_planner.py."
            ),
            "affected_surface": "chat",
            "severity": "medium",
        },
        model_generate_fn=valid_model,
        inventory=inventory,
    )
    require(
        (inferred_result.get("cycle_request") or {}).get("files_to_change")
        == [relative],
        "operator-named inventory file was not approved without adapter target_files",
        failures,
    )

    exact_relative = "tools/engel_conical_self_upgrade_cycle.py"
    semantic_decoy = "tools/run_engel_ui_chat_meeting_room_llm.py"
    exact_old = 'GOAL_ID = "engel_conical_agentic_sentient_self_upgrading_system"'
    exact_new = (
        'GOAL_ID = "engel_conical_agentic_sentient_self_upgrading_system_candidate"'
    )
    exact_inventory = {
        "surfaces": {
            "meeting_room": {
                "files": [{"relative_path": semantic_decoy}],
                "verifiers": [{"relative_path": relative}],
                "failure_keywords": ["meeting room", "visible room"],
            },
            "self_upgrade": {
                "files": [{"relative_path": exact_relative}],
                "verifiers": [{"relative_path": relative}],
                "failure_keywords": ["self upgrade", "cycle"],
            },
        }
    }

    def exact_target_model(_: str) -> dict[str, object]:
        return {
            "text": json.dumps(
                {
                    "diagnosis": "the named cycle target needs a bounded candidate",
                    "patch_plan": "replace only the exact named cycle constant",
                    "operations": [
                        {
                            "op": "replace_text",
                            "file": exact_relative,
                            "old_text": exact_old,
                            "new_text": exact_new,
                        }
                    ],
                    "lesson": "Exact inventory paths outrank semantic surface keywords.",
                    "extra_required_verifiers": [relative],
                }
            ),
            "model": "fixture-local-coder",
        }

    exact_result = planner.plan_request(
        {
            "request_text": (
                "Improve Meeting Room completion in "
                "tools/engel_conical_self_upgrade_cycle.py without applying it."
            ),
            "severity": "medium",
        },
        model_generate_fn=exact_target_model,
        inventory=exact_inventory,
    )
    require(
        exact_result.get("inventory_surface") == "self_upgrade",
        "semantic keywords overrode exact inventory path ownership",
        failures,
    )
    require(
        exact_result.get("candidate_files_considered") == [exact_relative],
        "exact path did not exclusively bound local model source context",
        failures,
    )
    require(
        (exact_result.get("cycle_request") or {}).get("files_to_change")
        == [exact_relative],
        "exact path plan escaped to the semantic Meeting Room decoy",
        failures,
    )

    conflicting_surface_rejected = False
    try:
        planner.plan_request(
            {
                "request_text": (
                    "Improve Meeting Room completion in "
                    "tools/engel_conical_self_upgrade_cycle.py without applying it."
                ),
                "affected_surface": "meeting_room",
                "severity": "medium",
            },
            model_generate_fn=exact_target_model,
            inventory=exact_inventory,
        )
    except planner.LocalPlannerError:
        conflicting_surface_rejected = True
    require(
        conflicting_surface_rejected,
        "explicit conflicting surface was allowed to override exact target ownership",
        failures,
    )

    ambiguous_inventory = {
        "surfaces": {
            "chat": {
                "files": [{"relative_path": relative}],
                "verifiers": [{"relative_path": relative}],
            },
            "desktop_ui": {
                "files": [{"relative_path": relative}],
                "verifiers": [{"relative_path": relative}],
            },
        }
    }
    ambiguous_target_rejected = False
    try:
        planner._resolve_exact_inventory_targets(
            ambiguous_inventory,
            f"Review {relative}.",
            [],
        )
    except planner.LocalPlannerError:
        ambiguous_target_rejected = True
    require(
        ambiguous_target_rejected,
        "shared-file ownership ambiguity did not fail closed",
        failures,
    )

    def invalid_model(_: str) -> dict[str, object]:
        payload = valid_model("")["text"]
        data = json.loads(str(payload))
        data["operations"][0]["old_text"] = f"absent-source-{id(data)}"
        return {"text": json.dumps(data), "model": "fixture-local-coder"}

    rejected = False
    try:
        planner.plan_request(
            {
                "request_text": "Fix the chat planner fixture marker using invented source.",
                "affected_surface": "chat",
                "target_files": [relative],
            },
            model_generate_fn=invalid_model,
            inventory=inventory,
        )
    except planner.LocalPlannerError:
        rejected = True
    require(rejected, "invented old_text was accepted", failures)

    def nonexistent_verifier_model(_: str) -> dict[str, object]:
        payload = valid_model("")["text"]
        data = json.loads(str(payload))
        data["extra_required_verifiers"] = [
            "tools/verify_engel_planner_that_does_not_exist.py"
        ]
        return {"text": json.dumps(data), "model": "fixture-local-coder"}

    rejected_verifier = False
    try:
        planner.plan_request(
            {
                "request_text": "Fix the chat planner fixture with a made-up verifier.",
                "affected_surface": "chat",
                "target_files": [relative],
            },
            model_generate_fn=nonexistent_verifier_model,
            inventory=inventory,
        )
    except planner.LocalPlannerError:
        rejected_verifier = True
    require(
        rejected_verifier,
        "nonexistent or undeclared extra verifier was accepted",
        failures,
    )

    resolver_inventory = {
        "surfaces": {
            "desktop_ui": {
                "files": [
                    {"relative_path": "engel_flutter_main/lib/main.dart"},
                ],
                "verifiers": [],
                "failure_keywords": ["ui", "screen"],
            },
            "self_upgrade": {
                "files": [
                    {"relative_path": "engel_self_upgrade_system.py"},
                    {"relative_path": "tools/engel_local_self_upgrade_planner.py"},
                ],
                "verifiers": [
                    {
                        "relative_path":
                            "tools/verify_engel_local_self_upgrade_planner.py"
                    },
                ],
                "failure_keywords": ["self upgrade", "planner", "patch"],
            },
        },
    }
    request_text = (
        "Improve the local self-upgrade planner error message when no "
        "codebase surface can be resolved so the Engel UI gives a specific error."
    )
    inventory_surface, cycle_surface, surface_entry = planner._resolve_surface(
        request_text,
        "",
        resolver_inventory,
    )
    require(
        inventory_surface == "self_upgrade" and cycle_surface == "source_patch",
        "hyphenated self-upgrade request resolved to the UI surface",
        failures,
    )
    inferred_files = planner._candidate_files(surface_entry, request_text, [])
    require(
        inferred_files
        and inferred_files[0][0] == "tools/engel_local_self_upgrade_planner.py",
        "planner request did not select the planner source as its sole implicit target",
        failures,
    )

    no_match_rejected = False
    try:
        planner._candidate_files(
            {
                "files": [
                    {"relative_path": "engel_flutter_main/lib/main.dart"},
                ],
            },
            "quasar xenolith zephyrian",
            [],
        )
    except planner.LocalPlannerError:
        no_match_rejected = True
    require(
        no_match_rejected,
        "unmatched request silently selected an unrelated source file",
        failures,
    )

    planner_relative = "tools/engel_local_self_upgrade_planner.py"
    planner_path = ROOT / planner_relative
    mapping_old = (
        'SURFACE_MAP = {\n'
        '    "chat": "chat",\n'
        '    "discord": "discord",\n'
    )
    mapping_new = (
        'SURFACE_MAP = {\n'
        '    "chat": "chat",\n'
        '    "discord": "discord",\n'
        '    "source_patch": "source_patch",\n'
    )
    message_mismatch_rejected = False
    try:
        planner._validate_plan(
            {
                "diagnosis": "the error message needs to be clearer",
                "patch_plan": "change the mapping",
                "operations": [
                    {
                        "op": "replace_text",
                        "file": planner_relative,
                        "old_text": mapping_old,
                        "new_text": mapping_new,
                    },
                ],
                "lesson": "messages should be specific",
                "extra_required_verifiers": [
                    "tools/verify_engel_local_self_upgrade_planner.py"
                ],
            },
            request_text=(
                "Improve the planner error message so it tells me which "
                "specific failing surface to describe."
            ),
            cycle_surface="source_patch",
            allowed_files={planner_relative: planner_path},
            allowed_verifiers={
                "tools/verify_engel_local_self_upgrade_planner.py"
            },
            severity="medium",
        )
    except planner.LocalPlannerError:
        message_mismatch_rejected = True
    require(
        message_mismatch_rejected,
        "message request accepted an unrelated mapping-only patch",
        failures,
    )

    retry_calls = 0

    def retrying_model(_: str) -> dict[str, object]:
        nonlocal retry_calls
        retry_calls += 1
        if retry_calls == 1:
            return invalid_model("")
        return valid_model("")

    retried = planner.plan_request(
        {
            "request_text": "Fix the chat planner fixture after one local validation retry.",
            "affected_surface": "chat",
            "target_files": [relative],
        },
        model_generate_fn=retrying_model,
        inventory=inventory,
    )
    require(
        retry_calls == 2
        and retried.get("planner_attempt_count") == 2
        and len(retried.get("validation_rejections") or []) == 1,
        "bounded local validation retry did not correct the candidate",
        failures,
    )

    anchored = planner._canonical_old_text(
        planner_path.read_text(encoding="utf-8"),
        'SURFACE_MAP = {\n"chat": "chat",\n"discord": "discord",',
    )
    require(
        anchored.startswith('SURFACE_MAP = {\n    "chat": "chat",')
        and '"discord": "discord",' in anchored,
        "unique whitespace-only source anchoring did not preserve exact current text",
        failures,
    )
    ambiguous_rejected = False
    try:
        planner._canonical_old_text("x = 1\nx = 1\n", "x = 1")
    except planner.LocalPlannerError:
        ambiguous_rejected = True
    require(
        ambiguous_rejected,
        "ambiguous whitespace-only source anchor was accepted",
        failures,
    )

    planner_source = (
        ROOT / "tools" / "engel_local_self_upgrade_planner.py"
    ).read_text(encoding="utf-8")
    require(
        "ENGEL_MOE_REASON_GGUF_MODEL" in planner_source
        and "sparse_moe_self_upgrade_reasoning" in planner_source
        and planner_source.index('"structured_code_patch_planner"')
        < planner_source.index('"sparse_moe_self_upgrade_reasoning"')
        and '"single_resident_model": True' in planner_source,
        "self-upgrade planner does not prefer the code transformer before sparse-MoE review",
        failures,
    )

    structured_call: dict[str, object] = {}
    original_model_module = sys.modules.get("engel_local_model_service")
    original_selector = planner._select_planner_model
    fake_model_module = types.ModuleType("engel_local_model_service")

    def structured_model_stub(**kwargs: object) -> dict[str, object]:
        structured_call.update(kwargs)
        return {"ok": True, "text": '{"diagnosis":"bounded"}'}

    fake_model_module.run_llama_cpp_lora_text_with_model = structured_model_stub
    sys.modules["engel_local_model_service"] = fake_model_module
    planner._select_planner_model = lambda: (
        str(planner_path),
        "verifier_structured_output",
    )
    try:
        planner._default_model_generate("Return a candidate.")
    finally:
        planner._select_planner_model = original_selector
        if original_model_module is None:
            sys.modules.pop("engel_local_model_service", None)
        else:
            sys.modules["engel_local_model_service"] = original_model_module
    require(
        structured_call.get("response_format") == {"type": "json_object"}
        and str(structured_call.get("prompt") or "").startswith("/no_think\n"),
        "local planner did not request constrained JSON output with thinking disabled",
        failures,
    )

    multi_operation_rejected = False
    try:
        planner._validate_plan(
            {
                "diagnosis": "one bounded change is required",
                "patch_plan": "replace the fixture once",
                "operations": [
                    {
                        "op": "replace_text",
                        "file": relative,
                        "old_text": old_line,
                        "new_text": new_line,
                    },
                    {
                        "op": "replace_text",
                        "file": relative,
                        "old_text": "FIXTURE_MARKER",
                        "new_text": "FIXTURE_MARKER_SECOND",
                    },
                ],
                "lesson": "implicit one-file plans stay atomic",
            },
            request_text="Fix one bounded planner fixture behavior.",
            cycle_surface="chat",
            allowed_files={relative: ROOT / relative},
            allowed_verifiers={relative},
            severity="medium",
            max_operations=1,
        )
    except planner.LocalPlannerError:
        multi_operation_rejected = True
    require(
        multi_operation_rejected,
        "implicit one-file plan accepted multiple operations",
        failures,
    )

    nearby_branch_rejected = False
    try:
        planner._validate_plan(
            {
                "diagnosis": "automatic codebase resolution needs guidance",
                "patch_plan": "change a nearby surface error",
                "operations": [
                    {
                        "op": "replace_text",
                        "file": planner_relative,
                        "old_text":
                            'raise LocalPlannerError(f"unknown affected surface: {explicit}")',
                        "new_text":
                            'raise LocalPlannerError("describe one specific failing surface before retrying")',
                    },
                ],
                "lesson": "target the named failure branch",
                "extra_required_verifiers": [
                    "tools/verify_engel_local_self_upgrade_planner.py"
                ],
            },
            request_text=(
                "Improve the error when no codebase surface can be resolved "
                "so it tells me what failing surface to describe."
            ),
            cycle_surface="source_patch",
            allowed_files={planner_relative: planner_path},
            allowed_verifiers={
                "tools/verify_engel_local_self_upgrade_planner.py"
            },
            severity="medium",
            max_operations=1,
        )
    except planner.LocalPlannerError:
        nearby_branch_rejected = True
    require(
        nearby_branch_rejected,
        "codebase-resolution request accepted the nearby explicit-surface branch",
        failures,
    )

    resolution_excerpt = planner._source_excerpt(
        planner_path,
        (
            "Improve the error when no codebase surface can be resolved "
            "so it tells me what failing surface to describe."
        ),
    )
    require(
        "codebase inventory could not resolve" in resolution_excerpt
        and "unknown affected surface" not in resolution_excerpt,
        "resolution-failure excerpt still exposes the nearby explicit-surface branch",
        failures,
    )

    forbidden_inventory = {
        "surfaces": {
            "chat": {
                "files": [{"relative_path": "reports/forbidden.py"}],
                "verifiers": [],
            }
        }
    }
    rejected_forbidden = False
    try:
        planner.plan_request(
            {
                "request_text": "Fix the chat report file through the source planner.",
                "affected_surface": "chat",
            },
            model_generate_fn=valid_model,
            inventory=forbidden_inventory,
        )
    except planner.LocalPlannerError:
        rejected_forbidden = True
    require(rejected_forbidden, "forbidden report target was accepted", failures)

    payload = {
        "schema": "ENGEL_LOCAL_SELF_UPGRADE_PLANNER_VERIFICATION_V1",
        "ok": not failures,
        "failures": failures,
        "provider_called": False,
        "source_mutation_performed": False,
        "validated_receipt": str(receipt),
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
