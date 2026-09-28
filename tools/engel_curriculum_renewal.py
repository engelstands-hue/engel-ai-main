#!/usr/bin/env python3
"""Substantive eight-hour renewal material for Engel's non-AEC curricula.

The historical prompt shapes are intentionally reused, but the lesson material is not.
Every engineering and communication card is bound to existing repository artifacts by
path, byte count, and SHA-256.  Every math card names ten distinct declared problems whose
ground truth lives in :mod:`engel_math_problems`; the prompt generator poses those exact
questions instead of letting the model invent the exercise it will later be graded on.

No timestamp, nonce, suffix, or capitalization change is used to manufacture novelty.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION = (
    "engel_capabilities_renewal_v6_20260925"
)
ENGEL_MATH_SCHOOL_RENEWAL_MATERIAL_VERSION = (
    "engel_math_school_declared_renewal_v6_20260925"
)
ENGEL_SELF_BUILD_RENEWAL_MATERIAL_VERSION = (
    "engel_self_build_renewal_v6_20260925"
)
ENGEL_CHAT_COMMUNICATION_RENEWAL_MATERIAL_VERSION = (
    "engel_chat_communication_renewal_v2_20260809"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _bind_cards(cards: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return copies whose grounding artifacts are resolved and byte-bound.

    Canonical renewal material is code-reviewed rather than operator-uploaded, but it
    should carry the same proof strength as an adopted weakness card.  Import therefore
    fails closed if an artifact leaves the repository, becomes a link, or is missing.
    """

    root = ROOT.resolve()
    bound: list[dict[str, Any]] = []
    for card_index, source in enumerate(cards, start=1):
        card = dict(source)
        raw_artifacts = card.get("artifacts")
        if not isinstance(raw_artifacts, list) or not raw_artifacts:
            raise ValueError(f"renewal card {card_index} names no grounding artifacts")
        records: list[dict[str, Any]] = []
        for raw in raw_artifacts:
            relative_text = str(raw or "").replace("\\", "/").strip()
            relative = Path(relative_text)
            if (
                not relative_text
                or relative.is_absolute()
                or relative.drive
                or ".." in relative.parts
            ):
                raise ValueError(
                    f"renewal card {card_index} has unsafe artifact {relative_text!r}"
                )
            candidate = ROOT / relative
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                raise ValueError(
                    f"renewal card {card_index} artifact is missing: {relative_text}"
                ) from exc
            if (
                resolved == root
                or root not in resolved.parents
                or candidate.is_symlink()
                or not resolved.is_file()
            ):
                raise ValueError(
                    f"renewal card {card_index} artifact is not a safe file: "
                    f"{relative_text}"
                )
            records.append(
                {
                    "path": relative.as_posix(),
                    "resolved_path": str(resolved),
                    "sha256": _sha256_file(resolved),
                    "bytes": resolved.stat().st_size,
                }
            )
        card["_grounding_artifact_records"] = records
        bound.append(card)
    return bound


# v4 (2026-08-16): eight NEW capability audits over subsystems the spent v3 set never
# taught - the GAIS confidence verdict, the consensus review lane, the peer-exchange
# turn budget, per-host capability probing, the two trainer retry seams, lane
# training-eligibility stamping, and the worker's belt receipts. Novelty comes from
# the different subject matter, never from rewording (module docstring rule).
# v5 (2026-09-14): eight NEW capability audits over REPS, Computer Mode, humanization,
# SLM roster gates, CT246 storage truth, Android worker independence, curriculum adoption,
# and Wiki One stamping. Novelty is new subject matter grounded in local artifacts.
_CAPABILITY_CARDS: list[dict[str, Any]] = [
    {
        "topic": "keeping each Engel Discord desk mention-only so it does not copy the research hourly board",
        "scenario": "Architect, Memory, Builder, Proof, and Training share the Engel AI Main room. The audit must show they speak when addressed, stay quiet on the hourly board, and do not inherit a shared proactive flag.",
        "constraint": "Do not turn a desk proactive to make it look busy, and do not let one drop-in force every desk to post on a timer.",
        "proof": "Ground the mention gate in tools/engel_discord_bridge.py and tools/engel_discord_desk_proactive.py.",
        "artifacts": ["tools/engel_discord_bridge.py", "tools/engel_discord_desk_proactive.py"],
    },
    {
        "topic": "serving phone health on a fast path so a worker heartbeat cannot stall the Devices page",
        "scenario": "Alpha, Beta, and Gamma keep polling while the Devices page asks whether the receiver is up. The audit must show health answers without waiting behind a heartbeat that probes itself.",
        "constraint": "Do not answer /health by opening another /health on the same process, and do not treat a listening socket that never replies as online.",
        "proof": "Use rust/engel-core-rs/src/lan_receiver.rs and rust/engel-core-rs/src/lan_link.rs as the receiver contract.",
        "artifacts": ["rust/engel-core-rs/src/lan_receiver.rs", "rust/engel-core-rs/src/lan_link.rs"],
    },
    {
        "topic": "joining one-to-eight-hour prompt slices into one current 1-through-80 curriculum chain",
        "scenario": "Joshua ran each lesson in a shorter window than eight hours. The audit must show a finished 10-per-hour slice can chain with later slices of the same curriculum, and an unfinished slice cannot.",
        "constraint": "Do not accept a pack that skips an index, changes the prompt hash, or claims a plan it did not finish.",
        "proof": "Bind the chain rule to tools/run_engel_real_training_cycle.py and tools/verify_engel_real_training.py.",
        "artifacts": ["tools/run_engel_real_training_cycle.py", "tools/verify_engel_real_training.py"],
    },
    {
        "topic": "keeping Discord desk identity locked to each mouth's charter and public bot id",
        "scenario": "A desk reply could be mistaken for Engel or for another seat. The audit must name the desk, its charter, and why Guardian is not a Discord mouth.",
        "constraint": "Do not let a desk speak as Engel, and do not invent a bot id that is not in the identity registry.",
        "proof": "Use tools/engel_discord_identity_lock.py and memory/ENGEL_DISCORD_IDENTITY_REGISTRY_V1.json.",
        "artifacts": ["tools/engel_discord_identity_lock.py", "memory/ENGEL_DISCORD_IDENTITY_REGISTRY_V1.json"],
    },
    {
        "topic": "keeping the BAD COMPANY rally bot off the Engel AI Main Discord fleet",
        "scenario": "The gaming room needs its own voice. The audit must show Rally belongs on that clan server, keeps its own persona file, and is not invited into Engel AI Main Chat.",
        "constraint": "Do not route Rally through the Engel chat service, and do not restart the Engel desk fleet to change Rally.",
        "proof": "Ground the split in tools/engel_clan_rally_bridge.py and memory/BC_RALLY_PERSONA_V1.json.",
        "artifacts": ["tools/engel_clan_rally_bridge.py", "memory/BC_RALLY_PERSONA_V1.json"],
    },
    {
        "topic": "refusing model training until every current curriculum has a complete pack chain",
        "scenario": "Prompt hours finished unevenly. The audit must name which curricula still lack a current 1-through-80 chain and why Train Selected Models stays failed until those chains exist.",
        "constraint": "Do not invent pack rows, and do not admit a math answer that contradicts the registered result.",
        "proof": "Use tools/run_engel_real_training_cycle.py and tools/run_engel_flutter_main_ui_prompt_training.py.",
        "artifacts": ["tools/run_engel_real_training_cycle.py", "tools/run_engel_flutter_main_ui_prompt_training.py"],
    },
    {
        "topic": "adopting the next generated lesson only with the digest-bound phrase the summary prints",
        "scenario": "Construction and chat material ran out. The audit must show a proposal, its digest, the exact approval phrase, and the adopted file, and why Prepare Files cannot invent hours.",
        "constraint": "Do not treat a proposal as live material, and treat an adopted file whose bytes disagree with its receipt as tampered.",
        "proof": "Trace the chain through tools/engel_curriculum_adoption.py and tools/verify_engel_curriculum_adoption.py.",
        "artifacts": ["tools/engel_curriculum_adoption.py", "tools/verify_engel_curriculum_adoption.py"],
    },
    {
        "topic": "reading Wiki One before a code landing and updating organs when a duty changes",
        "scenario": "A job changed what an organ talks to. The audit must show Wiki One was read first and organs.json moved with the duty.",
        "constraint": "Do not land code against a stale Wiki One, and do not stamp the journal when the job forbids that rewrite.",
        "proof": "Use wiki/ONE.md and tools/stamp_wiki_one_journal.py as the named second-brain contract.",
        "artifacts": ["wiki/ONE.md", "tools/stamp_wiki_one_journal.py"],
    },
]

_CAPABILITY_CARDS_V3_RETIRED: list[dict[str, Any]] = [
    {
        "topic": "walking one Conductor goal loop from plan through bounded run to its observed ledger entry",
        "scenario": "A goal entered the Conductor and the operator needs the plan, each bounded action, the observation that followed, and the ledger closeout kept distinct, instead of one confident sentence claiming the goal simply succeeded.",
        "constraint": "Do not report a Conductor goal as done from its plan or from a started action; only the observe step and the ledger entry close it, and action grants default to off.",
        "proof": "Trace the loop through engel_conductor.py and use tools/verify_engel_conductor.py as the named deterministic check; a step absent from that evidence stays open.",
        "artifacts": ["engel_conductor.py", "tools/verify_engel_conductor.py"],
    },
    {
        "topic": "separating Orchestra's parallel read-only lanes from the single draft that may hold the lock",
        "scenario": "Several Conductor lanes ran side by side and produced findings while one draft advanced. A correct account says which lanes were read-only, which single draft held the one-in-flight lock, and how the merged receipt binds them.",
        "constraint": "Do not describe a parallel lane as having changed anything; Orchestra lanes are read-only by design and no lane may claim the draft lock it never held.",
        "proof": "Ground the review in engel_orchestra.py and tools/verify_engel_orchestra.py, naming the lane cap, the draft lock, and the merged receipt those artifacts define.",
        "artifacts": ["engel_orchestra.py", "tools/verify_engel_orchestra.py"],
    },
    {
        "topic": "reading an EngelScript plan as validated structure rather than as prose that resembles commands",
        "scenario": "A drafted EngelScript names routes and steps. Before anything is said about running it, the review must distinguish a parsed and validated script, a dry docs lookup, and an actual run receipt.",
        "constraint": "Do not treat script text that failed validation as a plan, and do not present a validate result as evidence any step executed.",
        "proof": "Use engel_script.py and tools/verify_engel_script.py to separate docs, validate, and run, binding each claim to the stage that actually produced it.",
        "artifacts": ["engel_script.py", "tools/verify_engel_script.py"],
    },
    {
        "topic": "resolving an operator intent to a registered route through the capability index instead of memory",
        "scenario": "A request could be served by one of Engel's hundreds of registered routes. The answer must show the index lookup that ranked the candidates and the registry entry that proves the selected route exists.",
        "constraint": "Do not name a route from recall or plausibility; a capability claim binds to an index hit whose route id resolves in the registry, and zero hits is the honest answer.",
        "proof": "Base the resolution on engel_capability_index.py with tools/verify_engel_capability_index.py, reporting the ranked candidates those artifacts return.",
        "artifacts": ["engel_capability_index.py", "tools/verify_engel_capability_index.py"],
    },
    {
        "topic": "explaining which roster model advised a chat turn and why its output stayed advisory",
        "scenario": "A small roster model served in the chat hot path and its signal influenced a reply. The operator needs the model, its gate status, and the advisory boundary stated without implying the roster model authored the reply.",
        "constraint": "Do not present an advisory roster signal as the reply's author, and do not count a gated-off head as having served at all.",
        "proof": "Use tools/engel_slm_runtime.py and tools/verify_engel_slm_runtime.py to name the serving head, its enforced gates, and the advisory-only contract.",
        "artifacts": ["tools/engel_slm_runtime.py", "tools/verify_engel_slm_runtime.py"],
    },
    {
        "topic": "answering where a model's weights actually are through the ModelExpress control plane",
        "scenario": "A lane asks for a model and the broker must say which store holds the weights and by which transport they could move, while the fast paths that need absent hardware remain honestly gated off.",
        "constraint": "Do not claim an accelerated transfer path that the hardware gate reports unavailable; a broker answer without a weight location is not a route.",
        "proof": "Ground the answer in tools/engel_model_express.py and tools/verify_engel_model_express.py, keeping control-plane truth separate from data-plane capability.",
        "artifacts": ["tools/engel_model_express.py", "tools/verify_engel_model_express.py"],
    },
    {
        "topic": "reviewing an authored agent direction as versioned text whose action grants stay operator-owned",
        "scenario": "Engel drafted a new agent direction. The review must show the version lineage, what the direction permits, and the fact that allow_actions defaults off and cannot be granted by the author itself.",
        "constraint": "Do not describe an authored agent as active or empowered from its draft; Engel cannot self-grant action rights and an unapproved version directs nothing.",
        "proof": "Use tools/engel_agent_author.py and tools/verify_engel_agent_author.py to bind version, permitted scope, and the default-off grant boundary.",
        "artifacts": ["tools/engel_agent_author.py", "tools/verify_engel_agent_author.py"],
    },
    {
        "topic": "identifying a LAN device from fused signals while keeping honest-unknown as a first-class verdict",
        "scenario": "A MAC shows up with partial fingerprint signals from several probes. The identification must weigh the fused evidence per device and report unknown when the signals cannot separate the candidates.",
        "constraint": "Do not promote a single weak signal to an identity, and never replace honest-unknown with the most familiar device name.",
        "proof": "Base every identity claim on tools/engel_lan_fingerprint.py and tools/verify_engel_lan_fingerprint.py, citing the fused signals that carried the verdict.",
        "artifacts": ["tools/engel_lan_fingerprint.py", "tools/verify_engel_lan_fingerprint.py"],
    },
]

_CAPABILITY_CARDS_V2_RETIRED: list[dict[str, Any]] = [
    {
        "topic": "reconstructing why Engel admitted or refused an action from its Governor decision path",
        "scenario": "A request moved from ordinary chat toward an executable action, and the operator needs a fast explanation of the interpreted intent, authority, risk, and final admission without trusting a confident narrative after the fact.",
        "constraint": "Do not claim an action was authorized unless the decision record binds the same request, actor, authority evidence, and selected route.",
        "proof": "Trace the decision through tools/engel_governor.py and use tools/verify_engel_governor.py as the named deterministic check; anything not present in that evidence stays open.",
        "artifacts": ["tools/engel_governor.py", "tools/verify_engel_governor.py"],
    },
    {
        "topic": "following one agent-kernel goal from decomposition through bounded dispatch and returned evidence",
        "scenario": "A broad operator goal can create several agent steps, but a useful answer must distinguish a planned step, an allowed dispatch, a returned artifact, and a completed goal instead of treating all four as the same state.",
        "constraint": "Do not mark a goal complete from a plan or dispatch receipt; completion requires the kernel's returned evidence and closing status.",
        "proof": "Ground the review in engel_agent_kernel.py and tools/verify_engel_agent_kernel.py, naming the exact state transition each artifact actually proves.",
        "artifacts": ["engel_agent_kernel.py", "tools/verify_engel_agent_kernel.py"],
    },
    {
        "topic": "auditing a Code Forge candidate from isolated workspace to verified proposal without implying deployment",
        "scenario": "Engel produced a candidate patch that looks plausible. The operator needs to know what was generated, which checks ran, what remains review-only, and why a verified candidate still is not a production deployment.",
        "constraint": "Never collapse generated, verified, approved, applied, and deployed into one word; each transition needs its own evidence.",
        "proof": "Use engel_code_forge.py and tools/verify_engel_code_forge.py to identify the candidate-workspace, verification, and approval boundaries without inventing a promotion receipt.",
        "artifacts": ["engel_code_forge.py", "tools/verify_engel_code_forge.py"],
    },
    {
        "topic": "explaining a device-broker route using authenticated capability evidence instead of a remembered device label",
        "scenario": "A job could be sent to more than one phone or node. A friendly name is not enough to prove identity, reachability, or capability, so Engel must show why the selected worker was eligible and how its return is correlated.",
        "constraint": "Do not dispatch from display name alone and do not count a silent or mismatched return as the selected device's work.",
        "proof": "Base every route claim on tools/engel_device_broker.py and tools/verify_engel_device_broker.py; unobserved liveness or capability remains explicitly unknown.",
        "artifacts": ["tools/engel_device_broker.py", "tools/verify_engel_device_broker.py"],
    },
    {
        "topic": "replaying a Meeting Room handoff as a correlated event stream rather than a collection of filenames",
        "scenario": "An order entered the room, one or more workers observed it, and a result later appeared. The operator needs a single causal read that separates order creation, claim, return, and authoritative closeout.",
        "constraint": "Do not join room events by timing or similar text when their order, worker, or correlation identifiers disagree.",
        "proof": "Use tools/engel_meeting_room_event_stream.py with tools/verify_engel_agent_meeting_room.py and report only transitions those artifacts support.",
        "artifacts": [
            "tools/engel_meeting_room_event_stream.py",
            "tools/verify_engel_agent_meeting_room.py",
        ],
    },
    {
        "topic": "round-tripping lifted intent between the human-facing language and Engel's MIPL work representation",
        "scenario": "A human request is lifted into machine-oriented work and later rendered back for review. The critical capability is preserving the objective, constraints, and open questions across both directions, not merely producing another syntax.",
        "constraint": "Do not report a successful round trip when the rendered intent drops a constraint, changes the requested outcome, or hides an undecided branch.",
        "proof": "Ground the mapping in engel_mipl_agent_work.py and tools/verify_engel_lifted_intent.py, with every retained and open field tied to the real representation.",
        "artifacts": ["engel_mipl_agent_work.py", "tools/verify_engel_lifted_intent.py"],
    },
    {
        "topic": "checking Engel's live self-model before using a capability claim to answer or route work",
        "scenario": "A stored description says a component exists, but paths, services, and seats can drift. Before Engel relies on that description, it must distinguish a live observation from remembered inventory and an unsupported assumption.",
        "constraint": "Do not promote a remembered self-fact to current truth without the runtime observation and freshness evidence its contract requires.",
        "proof": "Use tools/engel_self_model_runtime.py and tools/verify_engel_self_model_runtime.py to show which self-claims are live, stale, or absent.",
        "artifacts": [
            "tools/engel_self_model_runtime.py",
            "tools/verify_engel_self_model_runtime.py",
        ],
    },
    {
        "topic": "proving that admitted prompt-training rows reach the selected model lanes with the same corpus contract",
        "scenario": "Prompt training captured reviewed answers and a later cycle prepares SLM and local-LLM work. The operator needs proof that admitted rows were actually consumed, the construction corpus binding survived transport, and an empty handoff stops every selected lane.",
        "constraint": "Do not call captured answers trained merely because a dataset command exited zero; the row counts and corpus binding must close across the cycle receipt.",
        "proof": "Review tools/run_engel_real_training_cycle.py with tools/verify_engel_real_training_corpus_transport.py and leave model promotion separate from training completion.",
        "artifacts": [
            "tools/run_engel_real_training_cycle.py",
            "tools/verify_engel_real_training_corpus_transport.py",
        ],
    },
]


# v4 (2026-08-16): eight NEW self-build reviews over loops the spent v3 set never
# taught - the pack writer's provenance guard, void-tolerant segment chains,
# history-aware curriculum drafting, the novel-hours computation, the five-plan
# readiness gate, the tail-resume playbook, service lifecycle repair, and
# calibration honesty as self-knowledge.
# v5 (2026-09-14): eight NEW self-build reviews over Clean/Regular mode, measured
# communication renewal, construction regeneration, weakness adoption, ren6 minting,
# humanization skip rules, partial five-curriculum readiness, and REPS authority.
_SELF_BUILD_CARDS: list[dict[str, Any]] = [
    {
        "topic": "rebuilding the LAN receiver after a self-probe filled its own worker pool",
        "scenario": "Phones were paired and the port was listening, but Devices still said offline. The review must show the health request no longer waits behind the heartbeat that asked for health.",
        "constraint": "Do not leave the old binary running after the source fix, and do not bind the receiver over the loopback port the phones reverse into.",
        "proof": "Ground the rebuild in rust/engel-core-rs/src/lan_receiver.rs and rust/engel-core-rs/src/lan_link.rs.",
        "artifacts": ["rust/engel-core-rs/src/lan_receiver.rs", "rust/engel-core-rs/src/lan_link.rs"],
    },
    {
        "topic": "finishing a scheduled prompt plan after the wall clock instead of dropping the tail",
        "scenario": "A two-hour plan of twenty prompts stopped at eighteen because each turn ran longer than its slot. The review must show later prompts in that same plan still get a send window.",
        "constraint": "Do not stretch the idle wait past the chosen hours, and do not mark a partial pack as a finished hour.",
        "proof": "Use tools/run_engel_flutter_main_ui_prompt_training.py and tools/run_engel_real_training_cycle.py.",
        "artifacts": ["tools/run_engel_flutter_main_ui_prompt_training.py", "tools/run_engel_real_training_cycle.py"],
    },
    {
        "topic": "registering a ren6 math lesson only after the grader accepts every minted answer",
        "scenario": "Math School exhausted ren5. The review must show eighty new questions, no reused wording, and a second oracle the runtime grader accepts.",
        "constraint": "Do not hand-write an answer the production grader rejects, and do not reuse a question already in the registry.",
        "proof": "Ground the mint in tools/mint_engel_math_ren6_curriculum.py and tools/engel_math_problems.py.",
        "artifacts": ["tools/mint_engel_math_ren6_curriculum.py", "tools/engel_math_problems.py"],
    },
    {
        "topic": "drawing the next unread construction sections after the previous corpus hours were consumed",
        "scenario": "Construction reached the end of its adopted sections. The review must show the generator skipping history-consumed anchors and keeping only sections with a real local excerpt.",
        "constraint": "Do not replay a section whose prompts are already in the novelty ledger, and never invent an excerpt the corpus cannot resolve.",
        "proof": "Base the path on tools/engel_construction_corpus_card_generator.py and tools/engel_prompt_novelty.py.",
        "artifacts": ["tools/engel_construction_corpus_card_generator.py", "tools/engel_prompt_novelty.py"],
    },
    {
        "topic": "drafting the next chat-voice lesson from measured misses instead of replaying spent cards",
        "scenario": "Chat Communication hours were exhausted. The review must show rejected-reply classes becoming a proposal, then a digest-bound adopt, with nonce rewording forbidden.",
        "constraint": "Do not renew a spent voice curriculum by capitalization tricks, and do not adopt without the printed approval phrase.",
        "proof": "Use tools/engel_communication_renewal_generator.py and tools/engel_prompt_novelty.py.",
        "artifacts": ["tools/engel_communication_renewal_generator.py", "tools/engel_prompt_novelty.py"],
    },
    {
        "topic": "reporting each curriculum's novelty on its own after a renewal instead of one all-ready flag",
        "scenario": "Some lanes received fresh material and others did not. The review must leave an exhausted lane visible and a partial lane partial.",
        "constraint": "Do not claim every curriculum is ready while any canonical lane is exhausted.",
        "proof": "Use tools/sync_engel_training_assets.py and tools/verify_engel_all_five_training_readiness.py.",
        "artifacts": ["tools/sync_engel_training_assets.py", "tools/verify_engel_all_five_training_readiness.py"],
    },
    {
        "topic": "keeping the voice rewrite off labelled math Result lines and engineering proof lines",
        "scenario": "A math Result/Check answer and a Confirmed/Proof construction answer entered the humanizer. The review must show those forms skip the spoken rewrite.",
        "constraint": "Do not humanize a form-graded training answer; chat-voice samples stay spoken.",
        "proof": "Use tools/engel_chat_humanization_slm.py and tools/verify_engel_chat_humanization_slm.py.",
        "artifacts": ["tools/engel_chat_humanization_slm.py", "tools/verify_engel_chat_humanization_slm.py"],
    },
    {
        "topic": "holding Josh then Guardian then Engel when a training fix also changes a verifier",
        "scenario": "A useful training change also edits the check that admits packs. The review must show the verifier moved with the rule and nothing auto-applied past the operator ask.",
        "constraint": "Do not weaken an admit rule to make a failed run look successful, and do not deploy a trained adapter from the cycle itself.",
        "proof": "Ground the cut in memory/ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md and tools/verify_engel_real_training.py.",
        "artifacts": ["memory/ENGEL_UNIVERSAL_REPS_TEMPLATE_V1.md", "tools/verify_engel_real_training.py"],
    },
]

_SELF_BUILD_CARDS_V2_RETIRED: list[dict[str, Any]] = [
    {
        "topic": "detecting architecture-map drift before choosing the next self-build target",
        "scenario": "Engel has many routes and tools, and an upgrade selected from an old inventory can repair the wrong layer. The first job is to rebuild the registry and identify a concrete gap whose source still exists.",
        "constraint": "Do not prioritize an upgrade from a stale diagram or a component name that cannot be resolved in the current workspace.",
        "proof": "Use tools/build_engel_workspace_system_registry.py and tools/verify_engel_codebase_inventory.py to bind the proposed target to current files and inventory evidence.",
        "artifacts": [
            "tools/build_engel_workspace_system_registry.py",
            "tools/verify_engel_codebase_inventory.py",
        ],
    },
    {
        "topic": "turning a reproduced failure into one deduplicated issue with an owner and close condition",
        "scenario": "Logs contain repeated symptoms from old and current runs. A self-improving system must reproduce the live failure, avoid opening duplicates, and state the evidence that will close the issue.",
        "constraint": "Do not create or reopen an issue from a stale signature that no longer reproduces, and do not close it from a code edit alone.",
        "proof": "Ground the lifecycle in tools/engel_conical_failure_to_issue.py and tools/verify_engel_conical_failure_to_issue.py.",
        "artifacts": [
            "tools/engel_conical_failure_to_issue.py",
            "tools/verify_engel_conical_failure_to_issue.py",
        ],
    },
    {
        "topic": "reviewing a conical self-upgrade as a reversible proposal with authoritative Meeting Room closeout",
        "scenario": "An upgrade cycle can discover a weakness, draft a change, and collect evidence, but those events do not authorize silent application. The operator needs the proposal, checks, rollback, and room outcome kept distinct.",
        "constraint": "Do not treat a generated or reviewed upgrade as applied, and do not close the visible Meeting Room order with a non-authoritative intermediate result.",
        "proof": "Use tools/engel_conical_self_upgrade_cycle.py and tools/verify_engel_conical_self_upgrade_cycle.py to trace proposal, review, application gate, and closeout.",
        "artifacts": [
            "tools/engel_conical_self_upgrade_cycle.py",
            "tools/verify_engel_conical_self_upgrade_cycle.py",
        ],
    },
    {
        "topic": "measuring a capability change against a fixed baseline and held-out task set",
        "scenario": "A new route feels better in a few examples. Engel must preserve the prior baseline, run the same scored tasks, expose regressions, and avoid selecting a metric only after seeing the result.",
        "constraint": "Do not call a capability improved from activity volume, training loss alone, or a task set changed after the candidate was observed.",
        "proof": "Use tools/engel_capability_eval.py and tools/verify_engel_capability_eval.py to name the baseline, task set, score, and regression evidence.",
        "artifacts": ["tools/engel_capability_eval.py", "tools/verify_engel_capability_eval.py"],
    },
    {
        "topic": "holding a newly trained model at the promotion boundary until its lineage and canary evidence agree",
        "scenario": "Training produced a candidate artifact, but serving it changes Engel's behavior for real users. The review must bind dataset lineage, evaluation, canary result, operator approval, and rollback without assuming one implies another.",
        "constraint": "Do not promote from a training-success receipt, and never overwrite the incumbent or rollback target before the candidate clears the promotion gate.",
        "proof": "Use tools/engel_model_promotion_gate.py and tools/verify_engel_model_promotion_gate.py as the named promotion contract.",
        "artifacts": [
            "tools/engel_model_promotion_gate.py",
            "tools/verify_engel_model_promotion_gate.py",
        ],
    },
    {
        "topic": "repairing memory retrieval without teaching Engel to quote its own training wrappers back into chat",
        "scenario": "Useful operator history and training turns share storage surfaces. Self-improvement must keep normal context available while quarantining prompt contracts, echoes, and ineligible rows from future conversational grounding.",
        "constraint": "Do not solve contamination by disabling memory, and do not reload a record stamped ineligible or echo merely because its text is relevant.",
        "proof": "Review tools/engel_memory_search.py with tools/verify_engel_memory_hygiene.py and separate persistence from context eligibility.",
        "artifacts": ["tools/engel_memory_search.py", "tools/verify_engel_memory_hygiene.py"],
    },
    {
        "topic": "checking route-registry continuity before changing which component owns an operator intent",
        "scenario": "A route change can leave docs, status, and execution pointing at different modules. Engel must inspect the registry, implementation, and verifier together before claiming the new owner is wired end to end.",
        "constraint": "Do not count a route name or UI card as capability proof when the executable target or verification path is missing.",
        "proof": "Use engel_ai_update_routes.py and tools/verify_engel_ai_update_routes.py to bind route identity, target module, status, and execution.",
        "artifacts": ["engel_ai_update_routes.py", "tools/verify_engel_ai_update_routes.py"],
    },
    {
        "topic": "converting measured rejected rows into an adopted weakness curriculum without auto-teaching the draft",
        "scenario": "Rejected training samples reveal recurring gaps, but a generated lesson can be wrong, ungrounded, or duplicate old material. The self-build loop must draft from evidence, require explicit adoption, bind real artifacts, and recheck prompt novelty.",
        "constraint": "Do not treat a generated weakness card as approved material and do not renew it with a nonce or cosmetic paraphrase.",
        "proof": "Use tools/engel_weakness_curriculum.py and tools/verify_engel_weakness_curriculum.py to distinguish draft, adoption, artifact grounding, and training readiness.",
        "artifacts": [
            "tools/engel_weakness_curriculum.py",
            "tools/verify_engel_weakness_curriculum.py",
        ],
    },
]


# v4 (2026-08-16): eight NEW hours over the freshly minted ren4-* problem families
# (80 sympy-computed decidable problems appended to engel_math_problems.py, each
# double-entered in the renewal verifier's independent v4 oracle and self-proved
# through the production grader before adoption).
# v5 (2026-09-14): eight NEW hours over the freshly minted ren6-* problem families
_MATH_CARDS: list[dict[str, Any]] = [
    {
        "topic": "resolving ten newly minted equations and reductions whose declared roots invite substitution checks",
        "scenario": "Every prompt carries one specific ren6 equation or rational reduction from the ground-truth registry; the declared parameters are new, so a memorized older exercise cannot stand in for the work.",
        "constraint": "Do not soften or swap the declared equation; prove each root by substituting it back and each reduced form by expanding it again before the Result line.",
        "proof": "The exact question must resolve to its ren6-alg problem ID in tools/engel_math_problems.py and the Result must agree with the registered symbolic answer.",
        "problem_ids": [f"ren6-alg-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "differentiating and integrating ten newly minted expressions with the inverse operation as witness",
        "scenario": "The ren6 calculus set pairs polynomial and trigonometric derivatives with antiderivatives, factored limits, a second derivative, and one definite integral, all with registered symbolic truth.",
        "constraint": "Do not state a calculus result the inverse operation has not witnessed; differentiate every antiderivative back and substitute every limit's factored form.",
        "proof": "Each delivered question resolves to a decidable ren6-cal ID and its Result is compared symbolically with the registered answer.",
        "problem_ids": [f"ren6-cal-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "evaluating ten newly minted matrix computations spanning determinants, trace, rank, and eigenvalues",
        "scenario": "The ren6 linear set widens past determinants to a trace, a dot product, a matrix-vector component, a rank, eigenvalues, an inverse entry, and a squared norm, each independently registered.",
        "constraint": "Do not answer from a remembered matrix; recompute the declared entries by a second route such as cofactor expansion, elimination, or direct substitution.",
        "proof": "The exact matrix question resolves to ren6-lin ground truth and the stated quantity must match it.",
        "problem_ids": [f"ren6-lin-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "producing exact probabilities for ten newly minted draws, flips, rolls, and joint events",
        "scenario": "Fresh ren6 sample spaces cover die thresholds, coin patterns, marble draws with and without replacement, dice sums, independence, and mutually exclusive unions, all exactly fractional.",
        "constraint": "Do not answer with a decimal or a simulated estimate; enumerate or normalize the declared sample space and keep the fraction exact.",
        "proof": "Each question resolves to a decidable ren6-prb ID and its fraction is compared symbolically to declared ground truth.",
        "problem_ids": [f"ren6-prb-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "confirming ten newly minted divisor, totient, factorization, and residue computations arithmetically",
        "scenario": "The ren6 number set spans gcd, lcm, a prime factorization, a modular power, divisor counts and sums, a totient, a remainder, a next prime, and a smallest prime factor.",
        "constraint": "Do not assert a divisibility or residue claim without recomposing it on the same numbers, multiplying factors back or reducing the residue chain again.",
        "proof": "The exact question resolves to its ren6-num ID and the bounded CAS compares the Result to the registered answer.",
        "problem_ids": [f"ren6-num-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "counting ten newly minted selections, codes, committees, and word arrangements two ways",
        "scenario": "The ren6 counting set fixes small exact answers for binomial choices, shelf orders, no-repeat codes, handshakes, binary strings, a constrained committee, a repeated-letter word, polygon diagonals, and prize assignments.",
        "constraint": "Do not drift the counting convention; honor replacement, order, and distinguishability exactly as each declared question states them, and recount by a second route.",
        "proof": "Every prompt resolves to a ren6-cnt ID and the exact integer is compared to declared ground truth.",
        "problem_ids": [f"ren6-cnt-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "recomputing ten newly minted sequence terms, partial sums, and one convergent series exactly",
        "scenario": "Fresh ren6 sequences give arithmetic and geometric terms, integer sums, a finite geometric series, a Fibonacci value, a recurrence, an infinite geometric sum, a triangular number, and a sum of squares.",
        "constraint": "Do not assume an indexing convention the declared question does not state, and recompute every term chain explicitly before summing.",
        "proof": "Each exact question resolves to a ren6-seq ID and the Result is checked against its registered value.",
        "problem_ids": [f"ren6-seq-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "executing ten newly minted bounded numeric procedures whose exact rational outputs are registered",
        "scenario": "The ren6 numeric set walks a recurrence, one trapezoid application, one Babylonian step, binary and base-7 conversions, a Hamming distance, a checksum, a weighted average, a continued fraction, and one integer power.",
        "constraint": "Do not report more precision than the declared procedure produces; keep every rational output as an exact fraction and rerun the procedure as its own check.",
        "proof": "Every question resolves to a decidable ren6-numc ID and the exact Result is compared symbolically with the registry.",
        "problem_ids": [f"ren6-numc-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
]

_MATH_CARDS_V3_RETIRED: list[dict[str, Any]] = [
    {
        "topic": "solving ten fresh linear and quadratic renewal equations whose roots and reduced forms are declared",
        "scenario": "Each prompt poses one new linear equation, quadratic with integer roots, or rational simplification from Engel's ren3 ground-truth registry, so swapping in an easier exercise is detectable.",
        "constraint": "Do not change the declared question; verify roots by substitution and simplified expressions by symbolic recomposition before stating the Result.",
        "proof": "The exact question must resolve to its ren3-alg problem ID in tools/engel_math_problems.py and the Result line must match the independent symbolic answer.",
        "problem_ids": [f"ren3-alg-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "working ten fresh derivative, antiderivative, limit, and definite-integral problems with reverse checks",
        "scenario": "The ren3 problems cover polynomial and trigonometric derivatives, antiderivatives, factored limits, and one definite integral with declared symbolic ground truth.",
        "constraint": "Do not accept a recalled calculus pattern without differentiating back, substituting, or evaluating the declared expression independently.",
        "proof": "Every delivered question resolves to a decidable ren3-cal ID and its Result is compared symbolically with the registered answer.",
        "problem_ids": [f"ren3-cal-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "expanding ten new two-by-two and three-by-three integer determinants registered for exact comparison",
        "scenario": "Each prompt supplies one concrete integer matrix whose determinant is independently registered in the ren3 ground-truth set.",
        "constraint": "Do not substitute a different matrix and do not report a determinant without a second cofactor expansion or elimination recomputation.",
        "proof": "The exact matrix question resolves to ren3-lin ground truth and the stated determinant must match it.",
        "problem_ids": [f"ren3-lin-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "deriving exact fractions for ten fresh coin, dice, card, and token probability questions",
        "scenario": "Coins flipped up to eight times, paired dice, single card draws, and small token bags give bounded sample spaces with exact fractional answers.",
        "constraint": "Do not use a simulation or a decimal as the answer; derive the exact fraction and check it by enumeration or normalization.",
        "proof": "Each question resolves to a decidable ren3-prb ID and its fraction is compared symbolically to declared ground truth.",
        "problem_ids": [f"ren3-prb-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "verifying ten new gcd, lcm, modular power, totient, and congruence computations by residue checks",
        "scenario": "The ren3 set covers gcd, lcm, modular powers, a division remainder, a modular inverse, a totient, a factorization, and one congruence pair.",
        "constraint": "Do not assert a modular or divisibility result without a finite Euclidean, residue, or recomposition check on the same numbers.",
        "proof": "The exact question resolves to its ren3-num ID and the bounded CAS compares Result to the registered answer.",
        "problem_ids": [f"ren3-num-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "counting ten fresh selection, arrangement, path, and derangement problems by two finite routes",
        "scenario": "Choices, permutations, ordered selections, binary strings, ball placements, grid paths, committees, derangements, and circular seatings all have fixed small answers.",
        "constraint": "Do not change the counting convention; treat replacement, order, rotation, and distinguishability exactly as the declared question states them.",
        "proof": "Every prompt resolves to a ren3-cnt ID and the exact integer is compared to declared ground truth.",
        "problem_ids": [f"ren3-cnt-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "computing ten fresh sequence terms and finite partial sums by explicit term-by-term recomputation",
        "scenario": "Arithmetic and geometric terms, Fibonacci values, a polynomial sequence, and bounded partial sums provide exact values with quick recomputation.",
        "constraint": "Do not infer an unstated indexing convention; use the first-term and index definitions exactly as the declared question gives them.",
        "proof": "Each exact question resolves to a ren3-seq ID and the Result is checked against its registered value.",
        "problem_ids": [f"ren3-seq-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "carrying out ten fresh bounded numeric and discrete computations that stay exactly rational",
        "scenario": "Polynomial evaluation, a midpoint, an approximation error, a recurrence, one trapezoid step, one Babylonian step, binary conversion, Hamming distance, a checksum, and a weighted average all remain exactly decidable.",
        "constraint": "Do not report more precision than the declared operation provides; keep exact fractions whenever the answer is rational.",
        "proof": "Every question resolves to a decidable ren3-numc ID and the exact Result is compared symbolically with the registry.",
        "problem_ids": [f"ren3-numc-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
]

_MATH_CARDS_V2_RETIRED: list[dict[str, Any]] = [
    {
        "topic": "solving a fixed set of renewal algebra equations and simplifications against declared answers",
        "scenario": "Each prompt poses a specific new equation or expression from Engel's ground-truth registry, so replacing it with an easier example is detectable.",
        "constraint": "Do not change the declared question; solve it and verify roots by substitution or expressions by symbolic recomposition.",
        "proof": "The exact question must resolve to its ren-alg problem ID in tools/engel_math_problems.py and the Result line must match the independent symbolic answer.",
        "problem_ids": [f"ren-alg-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "working a fixed calculus renewal set with reverse differentiation and exact limit checks",
        "scenario": "The problems cover derivatives, antiderivatives, limits, and one definite integral with declared symbolic ground truth.",
        "constraint": "Do not accept a recalled calculus pattern without differentiating, substituting, or evaluating the declared expression independently.",
        "proof": "Every delivered question resolves to a decidable ren-cal ID and its Result is compared symbolically with the registered answer.",
        "problem_ids": [f"ren-cal-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "recomputing ten declared matrix determinants without relying on a memorized example",
        "scenario": "Each prompt supplies one concrete two-by-two or three-by-three matrix whose determinant is independently registered.",
        "constraint": "Do not substitute a different matrix and do not report a determinant without a second expansion, elimination, or direct recomputation.",
        "proof": "The exact matrix question resolves to ren-lin ground truth and the stated determinant must match it.",
        "problem_ids": [f"ren-lin-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "computing ten exact finite probability questions from declared sample spaces",
        "scenario": "Coins, dice, cards, and small token bags provide bounded sample spaces with exact fractional answers.",
        "constraint": "Do not use a simulation as the answer; derive the exact fraction and use enumeration or normalization as the independent check.",
        "proof": "Each question resolves to a decidable ren-prb ID and its fraction is compared symbolically to declared ground truth.",
        "problem_ids": [f"ren-prb-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "checking ten finite number-theory computations against declared modular ground truth",
        "scenario": "The renewal set covers gcd, lcm, modular powers, a remainder, an inverse, factorization, and a small congruence pair.",
        "constraint": "Do not assert a modular or divisibility result without a finite Euclidean, residue, or recomposition check on the same numbers.",
        "proof": "The exact question resolves to its ren-num ID and the bounded CAS compares Result to the registered answer.",
        "problem_ids": [f"ren-num-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "deriving ten declared combinatorics counts and confirming them by a second finite route",
        "scenario": "Selections, permutations, binary strings, paths, committees, boxes, derangements, and circular arrangements all have fixed small answers.",
        "constraint": "Do not change the counting convention or count rotations, replacement, and distinguishability differently from the declared question.",
        "proof": "Every prompt resolves to a ren-cnt ID and the exact integer is compared to declared ground truth.",
        "problem_ids": [f"ren-cnt-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "evaluating ten declared sequence and finite-series questions with direct term checks",
        "scenario": "Arithmetic, geometric, Fibonacci, polynomial, and finite sums provide exact values with bounded recomputation.",
        "constraint": "Do not infer an unstated indexing convention; use the index and first-term definitions in the declared question.",
        "proof": "Each exact question resolves to a ren-seq ID and the Result is checked against its registered value.",
        "problem_ids": [f"ren-seq-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
    {
        "topic": "performing ten bounded numerical and discrete computations with exact rational checks",
        "scenario": "Polynomial evaluation, one recurrence, one trapezoid step, one Babylonian step, binary conversion, Hamming distance, checksum, and a weighted average all remain exactly decidable.",
        "constraint": "Do not report more precision than the declared operation provides; retain exact fractions whenever the answer is rational.",
        "proof": "Every question resolves to a decidable ren-numc ID and the exact Result is compared symbolically with the registry.",
        "problem_ids": [f"ren-numc-{index:02d}" for index in range(1, 11)],
        "artifacts": ["tools/engel_math_problems.py", "tools/engel_math_answer_verifier.py"],
    },
]


_COMMUNICATION_CARDS: list[dict[str, Any]] = [
    {
        "topic": "leading with the answer while keeping evidence close enough to be useful",
        "scenario": "Joshua asks whether a fix is ready. The only honest evidence is a reviewed patch and a verifier result; a long architecture preface would hide the answer he needs.",
        "constraint": "Answer the readiness question first, use precise state words, and never upgrade reviewed or verified into deployed.",
        "proof": "memory/personality/ENGEL_STYLE_CARD.md requires answer-first plain language and tools/run_engel_standalone_chat_llm.py applies the visible reply contract.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/run_engel_standalone_chat_llm.py",
        ],
    },
    {
        "topic": "saying exactly what has not been checked before proposing the next useful inspection",
        "scenario": "Joshua asks why a live route is failing, but the current turn has no fresh service receipt. Engel can still be useful by naming the missing observation and the first safe check without inventing a cause.",
        "constraint": "Do not replace lack of proof with probably, apparently, or should be; put the evidence gap in the first line.",
        "proof": "The uncertainty rule comes from memory/personality/ENGEL_STYLE_CARD.md and the real-context boundary is exercised by tools/verify_engel_chat_grounding.py.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/verify_engel_chat_grounding.py",
        ],
    },
    {
        "topic": "keeping Engel and Joshua's identities straight when the source model swaps speakers",
        "scenario": "A raw model reply says 'Joshua here' or names its vendor as if that were the assistant. The visible answer must preserve Joshua as the operator and Engel as the speaker without awkwardly narrating the repair.",
        "constraint": "Never claim Joshua's identity as Engel's own and never introduce a provider identity unless Joshua asked which lane handled the turn.",
        "proof": "memory/personality/ENGEL_STYLE_CARD.md sets the identity voice and tools/verify_engel_chat_identity_guard.py exercises inversion, vendor disclosure, and duplicate repair.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/verify_engel_chat_identity_guard.py",
        ],
    },
    {
        "topic": "using settled context without pasting stored chat or training scaffolding back to Joshua",
        "scenario": "A previous decision matters to the next answer. Engel should carry it forward in one clause, while quarantined training wrappers and timestamped memory lines must not become conversational prose.",
        "constraint": "Do not make Joshua repeat a settled decision, but do not replay raw history, labels, or prompt contracts to prove memory exists.",
        "proof": "memory/personality/ENGEL_STYLE_CARD.md defines continuity in voice and tools/verify_engel_memory_hygiene.py proves context eligibility and training-turn quarantine.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/verify_engel_memory_hygiene.py",
        ],
    },
    {
        "topic": "matching the size of the reply to the size of Joshua's question",
        "scenario": "Joshua asks for one next step during a busy build. A technically complete essay would still be a poor answer because it delays the one action he requested.",
        "constraint": "Give the requested step in a couple of sentences and add detail only when it changes safety or the decision.",
        "proof": "The length rule is explicit in memory/personality/ENGEL_STYLE_CARD.md and tools/run_engel_standalone_chat_llm.py contains the reply-length enforcement path.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/run_engel_standalone_chat_llm.py",
        ],
    },
    {
        "topic": "owning a failed run without cushioning the bad news or promising an unverified fix",
        "scenario": "Joshua finds that an overnight run failed before Engel reported it. The useful reply acknowledges that plainly, separates the observed failure from any diagnosis, and gives the immediate evidence-gathering step.",
        "constraint": "No apology paragraph, motivational filler, blame shift, or claim that the issue is fixed before a passing rerun exists.",
        "proof": "memory/personality/ENGEL_STYLE_CARD.md defines the frustrated-user response and tools/verify_engel_chat_memory_quality_gate.py exercises unsafe, approximate, and drifted reply rejection.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/verify_engel_chat_memory_quality_gate.py",
        ],
    },
    {
        "topic": "asking one branch-changing clarification instead of guessing or opening an interview",
        "scenario": "Joshua's short request could mean reviewing an existing artifact or changing it. Those paths have different side effects, so Engel should ask the single question that selects the path and state what each answer changes.",
        "constraint": "Do not guess the intended mutation and do not return a stack of questions whose answers would not change the next action.",
        "proof": "memory/personality/ENGEL_STYLE_CARD.md supplies the direct workbench voice and tools/engel_main_local_model_worker.py owns the local intent and response path being clarified.",
        "artifacts": [
            "memory/personality/ENGEL_STYLE_CARD.md",
            "tools/engel_main_local_model_worker.py",
        ],
    },
    {
        "topic": "keeping the same grounded voice and identity across desktop and Discord surfaces",
        "scenario": "The same operator question reaches two chat surfaces. Routing metadata can differ, but Engel's identity, local-first proof, repaired reply, and training eligibility must not contradict each other.",
        "constraint": "Do not let a surface-specific wrapper reintroduce a provider persona, an ungrounded completion claim, or a row the shared guard rejected elsewhere.",
        "proof": "Use tools/engel_discord_desktop_route_parity.py and tools/verify_engel_discord_desktop_route_parity.py to ground the shared finalization contract.",
        "artifacts": [
            "tools/engel_discord_desktop_route_parity.py",
            "tools/verify_engel_discord_desktop_route_parity.py",
        ],
    },
]


ENGEL_CAPABILITIES_RENEWAL_CARDS_V2 = _bind_cards(_CAPABILITY_CARDS)
ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2 = _bind_cards(_MATH_CARDS)
ENGEL_SELF_BUILD_RENEWAL_CARDS_V2 = _bind_cards(_SELF_BUILD_CARDS)
ENGEL_CHAT_COMMUNICATION_RENEWAL_CARDS_V2 = _bind_cards(_COMMUNICATION_CARDS)


def validate_renewal_curricula() -> list[str]:
    """Pure structural and ground-truth validation used by sync and verifiers."""

    problems: list[str] = []
    groups = {
        "capabilities": ENGEL_CAPABILITIES_RENEWAL_CARDS_V2,
        "math_school": ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2,
        "self_build": ENGEL_SELF_BUILD_RENEWAL_CARDS_V2,
        "chat_communication": ENGEL_CHAT_COMMUNICATION_RENEWAL_CARDS_V2,
    }
    all_topics: set[str] = set()
    for name, cards in groups.items():
        if len(cards) != 8:
            problems.append(f"{name} renewal must contain exactly eight cards")
        for index, card in enumerate(cards, start=1):
            for key in ("topic", "scenario", "constraint", "proof"):
                if not str(card.get(key) or "").strip():
                    problems.append(f"{name} card {index} has no {key}")
            topic = str(card.get("topic") or "").strip().casefold()
            if topic in all_topics:
                problems.append(f"{name} card {index} duplicates a renewal topic")
            all_topics.add(topic)
            artifacts = card.get("artifacts")
            records = card.get("_grounding_artifact_records")
            if not isinstance(artifacts, list) or not artifacts:
                problems.append(f"{name} card {index} has no artifacts")
            if not isinstance(records, list) or len(records) != len(artifacts or []):
                problems.append(f"{name} card {index} artifact binding is incomplete")

    try:
        from engel_math_problems import BY_ID
    except Exception as exc:  # pragma: no cover - surfaced as a validation problem
        problems.append(f"declared math registry could not be imported: {exc}")
        return problems
    seen_math_ids: set[str] = set()
    seen_questions: set[str] = set()
    for card_index, card in enumerate(ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2, start=1):
        problem_ids = card.get("problem_ids")
        if not isinstance(problem_ids, list) or len(problem_ids) != 10:
            problems.append(f"math_school card {card_index} needs ten problem_ids")
            continue
        for problem_id in problem_ids:
            declared = BY_ID.get(str(problem_id))
            if declared is None:
                problems.append(f"math_school card {card_index} has unknown {problem_id}")
                continue
            if not declared.decidable:
                problems.append(f"math_school problem {problem_id} is not decidable")
            question = " ".join(declared.question.split()).casefold()
            if str(problem_id) in seen_math_ids:
                problems.append(f"math_school problem {problem_id} is reused")
            if question in seen_questions:
                problems.append(f"math_school question for {problem_id} is duplicated")
            seen_math_ids.add(str(problem_id))
            seen_questions.add(question)
    if len(seen_math_ids) != 80:
        problems.append(
            f"math_school renewal must bind 80 distinct problems, found {len(seen_math_ids)}"
        )
    return problems


__all__ = [
    "ENGEL_CAPABILITIES_RENEWAL_CARDS_V2",
    "ENGEL_CAPABILITIES_RENEWAL_MATERIAL_VERSION",
    "ENGEL_MATH_SCHOOL_RENEWAL_CARDS_V2",
    "ENGEL_MATH_SCHOOL_RENEWAL_MATERIAL_VERSION",
    "ENGEL_SELF_BUILD_RENEWAL_CARDS_V2",
    "ENGEL_SELF_BUILD_RENEWAL_MATERIAL_VERSION",
    "ENGEL_CHAT_COMMUNICATION_RENEWAL_CARDS_V2",
    "ENGEL_CHAT_COMMUNICATION_RENEWAL_MATERIAL_VERSION",
    "validate_renewal_curricula",
]
