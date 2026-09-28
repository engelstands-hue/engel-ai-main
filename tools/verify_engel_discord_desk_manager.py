#!/usr/bin/env python3
"""Verify the Discord desk manager scores initiative without posting."""

from __future__ import annotations

from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "engel_discord_desk_manager.py"
BRIDGE = ROOT / "tools" / "engel_discord_bridge.py"
PROACTIVE = ROOT / "tools" / "engel_discord_desk_proactive.py"


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    from engel_discord_desk_manager import (  # noqa: E402
        allow_unsummoned_reply,
        evaluate_initiative,
        initiative_open,
        note_room_line,
        note_spoke,
    )

    failures: list[str] = []

    def require(ok: bool, message: str) -> None:
        print("[PASS]" if ok else "[FAIL]", message)
        if not ok:
            failures.append(message)

    require(MODULE.is_file(), "manager module present")
    bridge = BRIDGE.read_text(encoding="utf-8")
    proactive = PROACTIVE.read_text(encoding="utf-8")
    require("_desk_manager_allows_unsummoned" in bridge, "bridge asks the manager before staying silent")
    require("initiative_open" in proactive, "standing loop asks the manager before speaking")
    require(
        'phase in {"OwnerSilence", "Cooldown"}' in proactive,
        "a quiet-room Hold still allows the scheduled check-in",
    )
    require("def desk_duty_report" in proactive, "standing watch can run a real desk check")
    require(
        'os.environ.get("ENGEL_ROOT")' in proactive,
        "desk duty checks read that desk sandbox, not Main's tree",
    )
    require("def ensure_desk_second_brain" in bridge, "each desk can keep its own second brain")
    require("Second brain:" in bridge, "desk replies include that desk's second brain")
    require("def ensure_desk_sandbox" in proactive, "each desk has a working sandbox")
    require("def read_desk_sandbox_brief" in proactive, "turns read the desk sandbox before speaking")
    require("def note_desk_sandbox_turn" in proactive, "turns write back into the desk sandbox")
    require("Sandbox files, use them and do not recite them" in bridge, "replies are grounded in sandbox files")
    require("Do not paste the duty check verbatim" in bridge, "standing watch does not recite the duty script")
    require("source = \"sandbox_thought\"" in proactive, "a fresh model line beats the canned duty script")
    require(
        "Download/EngelRemoteWorker/desks" in proactive,
        "the working sandbox path is on the phone",
    )
    phone_dart = ROOT / "mobile" / "engel_remote_worker" / "lib" / "desk_phone_sandbox.dart"
    require(phone_dart.is_file(), "phone worker can keep a desk sandbox")
    phone_src = phone_dart.read_text(encoding="utf-8")
    require("Download/EngelRemoteWorker/desks" in phone_src, "phone sandbox uses the Download worker folder")
    require("discord_on_phone" in phone_src, "Discord stays off the phone")
    require("No run was started" in proactive, "training duty does not start a run")
    require("I did not apply a patch" in proactive, "builder duty does not apply a patch")
    require("I did not approve" in proactive, "architect duty does not pass the founder gate")
    from engel_discord_desk_proactive import desk_duty_report

    training = desk_duty_report("training")
    require("No run was started" in training, "training report stays read-only")
    architect = desk_duty_report("architect")
    require("I did not approve" in architect, "architect report does not approve a plan")
    from engel_discord_desk_proactive import (
        ensure_desk_sandbox,
        file_desk_ask,
        note_desk_sandbox_turn,
        read_desk_sandbox_brief,
        sandbox_repeats_last,
    )

    with tempfile.TemporaryDirectory() as sandbox_tmp:
        desk_root = Path(sandbox_tmp) / "desks" / "product"
        desk_root.mkdir(parents=True)
        room = ensure_desk_sandbox(
            "product",
            root=desk_root,
            charter={"addressed_as": "Engel Product", "duty": "ship the next slice"},
        )
        require(room is not None and (desk_root / "sandbox" / "work" / "OPEN.md").is_file(), "sandbox work room is created")
        require(Path("/opt/engel/wiki/ONE.md") != (desk_root / "wiki" / "ONE.md"), "desk sandbox is not Wiki One")
        filed = file_desk_ask("product", "what should product ship next", root=desk_root)
        require(filed is not None and "ship next" in filed.read_text(encoding="utf-8"), "an ask is filed in the desk inbox")
        noted = note_desk_sandbox_turn("product", "reply", "Ship the chat slice first.", root=desk_root)
        require(noted is not None, "the reply is journaled in the sandbox")
        brief = read_desk_sandbox_brief("product", root=desk_root)
        require("ship next" in brief and "Ship the chat slice first." in brief, "the next turn can read the sandbox")
        require(sandbox_repeats_last("Ship the chat slice first.", "product", root=desk_root), "an identical line is treated as a repeat")
        require(ensure_desk_sandbox("product", root=Path("/opt/engel")) is None, "Main /opt/engel is not a desk sandbox")
    require("huggingface" not in MODULE.read_text(encoding="utf-8"), "manager does not fetch weights")

    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        quiet = evaluate_initiative("product", run, "", now=1_000_000.0)
        require(quiet.get("speak") is False, "empty room does not speak")
        require(quiet.get("evaluation_state") == "Hold", "empty room holds")
        note_room_line(
            run,
            author="Engel Research",
            text="The roadmap feature priority for the flutter app cosmic swarm MVP needs a product call.",
            author_kind="peer",
        )
        note_room_line(run, author="Josh", text="what should product ship next?", author_kind="human")
        understood = allow_unsummoned_reply("product", run, "roadmap feature priority flutter app")
        require(understood is True, "product understands a roadmap line without a summon")
        hot = evaluate_initiative(
            "product",
            run,
            "roadmap feature priority flutter app cosmic swarm MVP",
            now=1_000_000.0 + 2000.0,
        )
        require(float(hot.get("topic_relevance") or 0) > 0, "topic relevance moves when markers hit")
        require(hot.get("activation_margin") is not None, "activation margin is scored")
        note_spoke(run, reason="test")
        cooling = evaluate_initiative("product", run, "roadmap feature mvp", now=1_000_000.0 + 2000.0)
        require(cooling.get("evaluation_state") == "Cooldown", "a fresh speak enters cooldown")
        require(cooling.get("speak") is False, "cooldown blocks initiative")
        require(float(cooling.get("activation_margin") or 0) < 0, "cooldown negates the margin")
        open_now, _decision = initiative_open("sales", run)
        require(open_now is False, "a desk with no charter hit stays quiet")

    if failures:
        print("ENGEL_DISCORD_DESK_MANAGER_VERIFIER_FAILED")
        return 1
    print("ENGEL_DISCORD_DESK_MANAGER_VERIFIER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
