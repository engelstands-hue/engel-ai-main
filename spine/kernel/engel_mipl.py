"""Engel Machine-Intent Packet Language (MIPL) v2.

MIPL is a tiny deterministic transport and verification language for Engel's
lifted intent.  It compiles without a model, provider, network connection, or
third-party package.  MIPL describes a request to Engel's existing engines; it
never authorizes or executes that request.

The wire form is bounded, hash-protected, optionally DEFLATE-compressed, and
uses numeric opcodes so low-resource workers do not need to load Engel's large
route catalog merely to validate a handoff.
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
import zlib
from enum import IntEnum
from typing import Any, Iterable, Mapping, Sequence


IR_SCHEMA = "engel_mipl_ir_v2"
STREAM_SCHEMA = "engel_mipl_packet_stream_v1"
LANGUAGE = "Engel MIPL"
VERSION = 2
PROFILE = "mipl2-low-resource"
MAGIC = b"MIPL"

MAX_PACKETS = 32
MAX_WIRE_BYTES = 32_768
MAX_PAYLOAD_BYTES = 24_576
MAX_RESULT_CHARS = 800
MAX_FIELD_CHARS = 2_000
MAX_TARGETS = 12
MAX_CRITERIA = 12
MAX_PROOF_PATHS = 12
MAX_SKILLS_PER_TASK = 8
MAX_SKILL_TOOLS = 8
MAX_TASK_CHARS = 2_000
MAX_COMPLETION_CRITERIA = 8

FLAG_DEFLATE = 0x01
_HEADER = struct.Struct(">4sBBBBII32s")


class Opcode(IntEnum):
    """Stable MIPL v2 opcodes.  Values are part of the wire contract."""

    BEGIN = 0x01
    INTENT = 0x02
    BUDGET = 0x03
    RESOLVE = 0x04
    GATE = 0x05
    DISPATCH = 0x06
    VERIFY = 0x07
    RETURN = 0x08
    RESULT = 0x09
    PROOF = 0x0A
    ERROR = 0x0B
    # Agent-work extension.  These values deliberately live outside the
    # original request/outcome range so old MIPL/2 readers fail closed rather
    # than mistaking an assignment for a normal request.
    AGENT = 0x10
    SKILL = 0x11
    TASK = 0x12
    ASSIGN = 0x13
    END = 0xFF


# Packet arguments are positional on the wire and named only when displayed.
_FIELDS: dict[Opcode, tuple[str, ...]] = {
    Opcode.BEGIN: ("kind", "failure", "request_hash"),
    Opcode.INTENT: ("expression_hash", "lifted_intent_hash", "effect"),
    Opcode.BUDGET: ("max_packets", "max_wire_bytes", "max_result_chars"),
    Opcode.RESOLVE: ("targets",),
    Opcode.GATE: ("policy", "failure"),
    Opcode.DISPATCH: ("engine", "authorization"),
    Opcode.VERIFY: ("criteria",),
    Opcode.RETURN: ("channel", "include_failures"),
    Opcode.RESULT: ("ok", "status", "result_hash"),
    Opcode.PROOF: ("paths",),
    Opcode.ERROR: ("code", "message"),
    Opcode.AGENT: ("agent_id", "name", "purpose", "lifecycle"),
    Opcode.SKILL: ("skill_id", "name", "tools", "requires_action_grant"),
    Opcode.TASK: ("task_id", "objective", "max_turns", "completion"),
    Opcode.ASSIGN: ("agent_id", "task_id", "skills"),
    Opcode.END: (),
}

_REQUEST_ORDER = (
    Opcode.BEGIN,
    Opcode.INTENT,
    Opcode.BUDGET,
    Opcode.RESOLVE,
    Opcode.GATE,
    Opcode.DISPATCH,
    Opcode.VERIFY,
    Opcode.RETURN,
    Opcode.END,
)
_AGENT_TASK_PREFIX = (
    Opcode.BEGIN,
    Opcode.INTENT,
    Opcode.BUDGET,
    Opcode.RESOLVE,
    Opcode.AGENT,
)
_AGENT_TASK_SUFFIX = (
    Opcode.TASK,
    Opcode.ASSIGN,
    Opcode.GATE,
    Opcode.DISPATCH,
    Opcode.VERIFY,
    Opcode.RETURN,
    Opcode.END,
)
_SIDE_EFFECTS = frozenset(
    ("create", "mutate", "dispatch", "train", "remember", "install", "execute")
)


class MiplError(ValueError):
    """Raised when MIPL source, IR, or wire data violates the v2 contract."""


def _bounded(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    return " ".join(str(value or "").split())[:limit]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


def _packet(seq: int, opcode: Opcode, values: Mapping[str, Any]) -> list[Any]:
    fields = _FIELDS[opcode]
    unknown = set(values) - set(fields)
    if unknown:
        raise MiplError(f"{opcode.name} has unknown fields: {sorted(unknown)}")
    args = [values.get(field) for field in fields]
    while args and args[-1] in (None, ""):
        args.pop()
    return [seq, int(opcode), args]


def _args(opcode: Opcode, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, list):
        raise MiplError(f"{opcode.name} arguments must be a list")
    fields = _FIELDS[opcode]
    if len(raw) > len(fields):
        raise MiplError(f"{opcode.name} has too many arguments")
    return {field: raw[index] if index < len(raw) else None for index, field in enumerate(fields)}


def _encode_stream(kind: str, packets: Sequence[list[Any]]) -> dict[str, Any]:
    if kind not in {"request", "outcome", "agent_task"}:
        raise MiplError(f"unsupported stream kind: {kind}")
    if not 1 <= len(packets) <= MAX_PACKETS:
        raise MiplError(f"packet count must be 1-{MAX_PACKETS}")
    envelope = {"s": STREAM_SCHEMA, "v": VERSION, "k": kind, "p": list(packets)}
    raw = _canonical(envelope)
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise MiplError(f"MIPL payload exceeds {MAX_PAYLOAD_BYTES} bytes")
    compressed = zlib.compress(raw, level=9)
    if len(compressed) < len(raw):
        flags = FLAG_DEFLATE
        body = compressed
        codec = "mipl2-json-deflate"
    else:
        flags = 0
        body = raw
        codec = "mipl2-json"
    digest = _digest(raw)
    header = _HEADER.pack(
        MAGIC,
        VERSION,
        flags,
        len(packets),
        0,
        len(raw),
        len(body),
        digest,
    )
    container = header + body
    if len(container) > MAX_WIRE_BYTES:
        raise MiplError(f"MIPL wire exceeds {MAX_WIRE_BYTES} bytes")
    return {
        "codec": codec,
        "packet_count": len(packets),
        "encoded_bytes": len(container),
        "payload_bytes": len(raw),
        "sha256": digest.hex(),
        "body": base64.b64encode(container).decode("ascii"),
    }


def decode_wire(wire: Mapping[str, Any] | str | bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode and integrity-check a bounded MIPL packet stream."""
    metadata: Mapping[str, Any] = wire if isinstance(wire, Mapping) else {}
    encoded: str | bytes = metadata.get("body", "") if metadata else wire
    if isinstance(encoded, str):
        try:
            container = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise MiplError(f"invalid MIPL base64: {exc}") from exc
    elif isinstance(encoded, bytes):
        container = encoded
    else:
        raise MiplError("MIPL wire body must be base64 text or bytes")
    if len(container) < _HEADER.size or len(container) > MAX_WIRE_BYTES:
        raise MiplError("MIPL wire size is outside the allowed bounds")
    try:
        magic, version, flags, count, reserved, raw_len, body_len, digest = _HEADER.unpack(
            container[: _HEADER.size]
        )
    except struct.error as exc:
        raise MiplError(f"invalid MIPL header: {exc}") from exc
    body = container[_HEADER.size :]
    if magic != MAGIC or version != VERSION or reserved != 0:
        raise MiplError("MIPL header magic, version, or reserved field is invalid")
    if flags not in (0, FLAG_DEFLATE):
        raise MiplError("MIPL wire uses unsupported flags")
    if not 1 <= count <= MAX_PACKETS or body_len != len(body):
        raise MiplError("MIPL packet count or body length is invalid")
    if not 1 <= raw_len <= MAX_PAYLOAD_BYTES:
        raise MiplError("MIPL payload length is outside the allowed bounds")
    if flags == FLAG_DEFLATE:
        inflater = zlib.decompressobj()
        try:
            raw = inflater.decompress(body, MAX_PAYLOAD_BYTES + 1)
        except zlib.error as exc:
            raise MiplError(f"invalid MIPL compressed body: {exc}") from exc
        if (
            not inflater.eof
            or inflater.unconsumed_tail
            or inflater.unused_data
            or len(raw) > MAX_PAYLOAD_BYTES
        ):
            raise MiplError("MIPL compressed body is truncated or exceeds its bound")
    else:
        raw = body
    if len(raw) != raw_len or _digest(raw) != digest:
        raise MiplError("MIPL payload length or SHA-256 integrity check failed")
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise MiplError(f"invalid MIPL JSON payload: {exc}") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("p"), list):
        raise MiplError("MIPL packet envelope is malformed")
    if (
        envelope.get("s") != STREAM_SCHEMA
        or envelope.get("v") != VERSION
        or len(envelope["p"]) != count
    ):
        raise MiplError("MIPL envelope schema, version, or count does not match")
    decoded = {
        "codec": "mipl2-json-deflate" if flags else "mipl2-json",
        "packet_count": count,
        "encoded_bytes": len(container),
        "payload_bytes": len(raw),
        "sha256": digest.hex(),
    }
    for key in ("packet_count", "encoded_bytes", "payload_bytes", "sha256"):
        if metadata and key in metadata and metadata.get(key) != decoded[key]:
            raise MiplError(f"MIPL wire metadata mismatch: {key}")
    return envelope, decoded


def _ir(kind: str, packets: Sequence[list[Any]]) -> dict[str, Any]:
    wire = _encode_stream(kind, packets)
    return {
        "schema": IR_SCHEMA,
        "language": LANGUAGE,
        "version": VERSION,
        "profile": PROFILE,
        "kind": kind,
        "execution_authorized": False,
        "limits": {
            "max_packets": MAX_PACKETS,
            "max_wire_bytes": MAX_WIRE_BYTES,
            "max_payload_bytes": MAX_PAYLOAD_BYTES,
            "max_result_chars": MAX_RESULT_CHARS,
        },
        "wire": wire,
    }


def compile_intent_ir(
    *,
    expression_hash: str,
    lifted_intent_hash: str,
    effect: str,
    targets: Iterable[Any],
    criteria: Iterable[Any],
    approval_required: bool,
) -> dict[str, Any]:
    """Compile a lifted intent to a deterministic, non-authorizing request."""
    effect_text = _bounded(effect, 40).casefold() or "converse"
    target_values = [_bounded(value, 500) for value in list(targets)[:MAX_TARGETS]]
    target_values = [value for value in target_values if value] or ["unspecified"]
    criteria_values = [_bounded(value, 800) for value in list(criteria)[:MAX_CRITERIA]]
    criteria_values = [value for value in criteria_values if value]
    gate_required = bool(approval_required or effect_text in _SIDE_EFFECTS)
    failure = "closed" if gate_required else "safe_default"
    policy = "approval_and_governor" if gate_required else "governor_route"
    specs = (
        (Opcode.BEGIN, {"kind": "request", "failure": failure}),
        (
            Opcode.INTENT,
            {
                "expression_hash": _bounded(expression_hash, 64),
                "lifted_intent_hash": _bounded(lifted_intent_hash, 64),
                "effect": effect_text,
            },
        ),
        (
            Opcode.BUDGET,
            {
                "max_packets": MAX_PACKETS,
                "max_wire_bytes": MAX_WIRE_BYTES,
                "max_result_chars": MAX_RESULT_CHARS,
            },
        ),
        (Opcode.RESOLVE, {"targets": target_values}),
        (Opcode.GATE, {"policy": policy, "failure": failure}),
        (
            Opcode.DISPATCH,
            {
                "engine": "existing_engel_engine",
                "authorization": "external_gate_required",
            },
        ),
        (Opcode.VERIFY, {"criteria": criteria_values}),
        (
            Opcode.RETURN,
            {"channel": "hipl_comprehension", "include_failures": True},
        ),
        (Opcode.END, {}),
    )
    ir = _ir("request", [_packet(seq, op, values) for seq, (op, values) in enumerate(specs)])
    validation = validate_ir(ir)
    if not validation["ok"]:
        raise MiplError("compiled request failed validation: " + "; ".join(validation["errors"]))
    return ir


def compile_agent_task_ir(
    *,
    expression_hash: str,
    lifted_intent_hash: str,
    agent_id: Any,
    agent_name: Any,
    agent_purpose: Any,
    task_id: Any,
    task_objective: Any,
    skills: Iterable[Mapping[str, Any]],
    criteria: Iterable[Any] = (),
    completion: Iterable[Any] = (),
    max_turns: int = 6,
    lifecycle: str = "draft",
) -> dict[str, Any]:
    """Compile one bounded agent, task, and skill assignment.

    The packet is a plan and an audit reference.  It never creates, activates,
    grants, or runs the agent; those state transitions remain external gates.
    """
    agent_ref = _bounded(agent_id, 120)
    task_ref = _bounded(task_id, 120)
    skill_specs: list[dict[str, Any]] = []
    for raw in list(skills)[:MAX_SKILLS_PER_TASK]:
        if not isinstance(raw, Mapping):
            raise MiplError("each agent-task skill must be a mapping")
        tool_values = [_bounded(value, 80) for value in list(raw.get("tools") or ())]
        tool_values = [value for value in tool_values if value][:MAX_SKILL_TOOLS]
        skill_specs.append(
            {
                "skill_id": _bounded(raw.get("skill_id"), 80),
                "name": _bounded(raw.get("name"), 160),
                "tools": tool_values,
                "requires_action_grant": bool(raw.get("requires_action_grant")),
            }
        )
    if not skill_specs:
        raise MiplError("an agent-task packet needs at least one skill")

    criteria_values = [_bounded(value, 800) for value in list(criteria)[:MAX_CRITERIA]]
    criteria_values = [value for value in criteria_values if value]
    completion_values = [
        _bounded(value, 500) for value in list(completion)[:MAX_COMPLETION_CRITERIA]
    ]
    completion_values = [value for value in completion_values if value]
    specs: list[tuple[Opcode, dict[str, Any]]] = [
        (Opcode.BEGIN, {"kind": "agent_task", "failure": "closed"}),
        (
            Opcode.INTENT,
            {
                "expression_hash": _bounded(expression_hash, 64),
                "lifted_intent_hash": _bounded(lifted_intent_hash, 64),
                "effect": "dispatch",
            },
        ),
        (
            Opcode.BUDGET,
            {
                "max_packets": MAX_PACKETS,
                "max_wire_bytes": MAX_WIRE_BYTES,
                "max_result_chars": MAX_RESULT_CHARS,
            },
        ),
        (Opcode.RESOLVE, {"targets": [f"agent:{agent_ref}", f"task:{task_ref}"]}),
        (
            Opcode.AGENT,
            {
                "agent_id": agent_ref,
                "name": _bounded(agent_name, 60),
                "purpose": _bounded(agent_purpose, 500),
                "lifecycle": _bounded(lifecycle, 20).casefold() or "draft",
            },
        ),
    ]
    specs.extend((Opcode.SKILL, spec) for spec in skill_specs)
    specs.extend(
        [
            (
                Opcode.TASK,
                {
                    "task_id": task_ref,
                    "objective": _bounded(task_objective, MAX_TASK_CHARS),
                    "max_turns": max_turns,
                    "completion": completion_values,
                },
            ),
            (
                Opcode.ASSIGN,
                {
                    "agent_id": agent_ref,
                    "task_id": task_ref,
                    "skills": [spec["skill_id"] for spec in skill_specs],
                },
            ),
            (Opcode.GATE, {"policy": "approval_and_governor", "failure": "closed"}),
            (
                Opcode.DISPATCH,
                {
                    "engine": "engel_authored_agent_runner",
                    "authorization": "external_gate_required",
                },
            ),
            (Opcode.VERIFY, {"criteria": criteria_values}),
            (Opcode.RETURN, {"channel": "hipl_comprehension", "include_failures": True}),
            (Opcode.END, {}),
        ]
    )
    ir = _ir(
        "agent_task",
        [_packet(seq, op, values) for seq, (op, values) in enumerate(specs)],
    )
    validation = validate_ir(ir)
    if not validation["ok"]:
        raise MiplError(
            "compiled agent-task request failed validation: "
            + "; ".join(validation["errors"])
        )
    return ir


def compile_outcome_ir(
    *,
    request_hash: str,
    ok: bool,
    status: Any,
    result_hash: str,
    proof_paths: Iterable[Any] = (),
    error: Any = "",
) -> dict[str, Any]:
    """Compile the bounded machine result that returns toward HIPL."""
    proof = [_bounded(value, 500) for value in list(proof_paths)[:MAX_PROOF_PATHS]]
    proof = [value for value in proof if value]
    specs: list[tuple[Opcode, dict[str, Any]]] = [
        (
            Opcode.BEGIN,
            {"kind": "outcome", "failure": "closed", "request_hash": _bounded(request_hash, 64)},
        ),
        (
            Opcode.RESULT,
            {
                "ok": bool(ok),
                "status": _bounded(status, 240) or "unknown",
                "result_hash": _bounded(result_hash, 64),
            },
        ),
    ]
    if proof:
        specs.append((Opcode.PROOF, {"paths": proof}))
    if not ok:
        specs.append(
            (
                Opcode.ERROR,
                {
                    "code": "machine_result_failed",
                    "message": _bounded(error or status, MAX_RESULT_CHARS),
                },
            )
        )
    specs.extend(
        (
            (Opcode.RETURN, {"channel": "hipl_comprehension", "include_failures": True}),
            (Opcode.END, {}),
        )
    )
    ir = _ir("outcome", [_packet(seq, op, values) for seq, (op, values) in enumerate(specs)])
    validation = validate_ir(ir)
    if not validation["ok"]:
        raise MiplError("compiled outcome failed validation: " + "; ".join(validation["errors"]))
    return ir


def packet_records(ir: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand a wire stream for display/debugging without changing the IR."""
    envelope, _ = decode_wire(ir.get("wire", {}))
    records: list[dict[str, Any]] = []
    for raw in envelope["p"]:
        if not isinstance(raw, list) or len(raw) != 3:
            raise MiplError("MIPL packet must be [sequence, opcode, arguments]")
        seq, code, values = raw
        try:
            opcode = Opcode(code)
        except (ValueError, TypeError) as exc:
            raise MiplError(f"unknown MIPL opcode: {code}") from exc
        records.append(
            {"seq": seq, "opcode": opcode.name, "code": int(opcode), "args": _args(opcode, values)}
        )
    return records


def validate_ir(ir: Mapping[str, Any]) -> dict[str, Any]:
    """Validate wire integrity, packet grammar, budgets, and authority boundary."""
    checks: dict[str, bool] = {}
    errors: list[str] = []

    def check(condition: bool, name: str, message: str) -> None:
        checks[name] = bool(condition)
        if not condition:
            errors.append(message)

    check(ir.get("schema") == IR_SCHEMA, "schema", "unsupported MIPL IR schema")
    check(ir.get("version") == VERSION, "version", "unsupported MIPL version")
    check(ir.get("profile") == PROFILE, "profile", "unknown MIPL resource profile")
    check(
        ir.get("execution_authorized") is False,
        "non_authorizing",
        "MIPL must never carry execution authority",
    )
    try:
        envelope, decoded = decode_wire(ir.get("wire", {}))
        checks["wire_integrity"] = True
    except (MiplError, TypeError, AttributeError) as exc:
        checks["wire_integrity"] = False
        errors.append(str(exc))
        return {"ok": False, "checks": checks, "errors": errors}

    kind = envelope.get("k")
    packets = envelope.get("p", [])
    check(
        kind in {"request", "outcome", "agent_task"},
        "kind",
        "invalid MIPL stream kind",
    )
    check(len(packets) <= MAX_PACKETS, "packet_budget", "MIPL packet budget exceeded")
    check(
        decoded["encoded_bytes"] <= MAX_WIRE_BYTES,
        "wire_budget",
        "MIPL wire budget exceeded",
    )
    codes: list[Opcode] = []
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(packets):
        if not isinstance(raw, list) or len(raw) != 3:
            errors.append(f"packet {index} is not [sequence, opcode, arguments]")
            continue
        seq, code, values = raw
        if seq != index:
            errors.append(f"packet {index} has a non-contiguous sequence")
        try:
            opcode = Opcode(code)
            args = _args(opcode, values)
        except (MiplError, ValueError, TypeError) as exc:
            errors.append(f"packet {index}: {exc}")
            continue
        codes.append(opcode)
        records.append({"opcode": opcode, "args": args})
    checks["packet_shape"] = len(records) == len(packets) and not any(
        "packet " in error for error in errors
    )
    if kind == "request":
        check(tuple(codes) == _REQUEST_ORDER, "request_grammar", "request packet order is invalid")
    elif kind == "agent_task":
        skill_codes = codes[len(_AGENT_TASK_PREFIX) : -len(_AGENT_TASK_SUFFIX)]
        check(
            tuple(codes[: len(_AGENT_TASK_PREFIX)]) == _AGENT_TASK_PREFIX
            and tuple(codes[-len(_AGENT_TASK_SUFFIX) :]) == _AGENT_TASK_SUFFIX
            and 1 <= len(skill_codes) <= MAX_SKILLS_PER_TASK
            and all(code == Opcode.SKILL for code in skill_codes),
            "agent_task_grammar",
            "agent-task packet order or skill count is invalid",
        )
    elif kind == "outcome":
        expected_outcome = [Opcode.BEGIN, Opcode.RESULT]
        if Opcode.PROOF in codes:
            expected_outcome.append(Opcode.PROOF)
        if Opcode.ERROR in codes:
            expected_outcome.append(Opcode.ERROR)
        expected_outcome.extend((Opcode.RETURN, Opcode.END))
        check(
            codes == expected_outcome,
            "outcome_grammar",
            "outcome packet order is invalid",
        )
    if records:
        begin = records[0]["args"]
        check(begin.get("kind") == kind, "begin_kind", "BEGIN kind does not match envelope")
    dispatch = next((record["args"] for record in records if record["opcode"] == Opcode.DISPATCH), None)
    if kind == "request":
        gate = next((record["args"] for record in records if record["opcode"] == Opcode.GATE), {})
        intent = next((record["args"] for record in records if record["opcode"] == Opcode.INTENT), {})
        budget = next((record["args"] for record in records if record["opcode"] == Opcode.BUDGET), {})
        resolve = next((record["args"] for record in records if record["opcode"] == Opcode.RESOLVE), {})
        verify = next((record["args"] for record in records if record["opcode"] == Opcode.VERIFY), {})
        effect = str(intent.get("effect") or "")
        gate_required = effect in _SIDE_EFFECTS
        hashes_valid = all(
            isinstance(intent.get(key), str)
            and len(intent[key]) == 64
            and all(char in "0123456789abcdef" for char in intent[key].casefold())
            for key in ("expression_hash", "lifted_intent_hash")
        )
        check(hashes_valid and bool(effect), "intent_reference", "INTENT hashes or effect are invalid")
        check(
            isinstance(budget.get("max_packets"), int)
            and 1 <= budget["max_packets"] <= MAX_PACKETS
            and isinstance(budget.get("max_wire_bytes"), int)
            and 1 <= budget["max_wire_bytes"] <= MAX_WIRE_BYTES
            and isinstance(budget.get("max_result_chars"), int)
            and 1 <= budget["max_result_chars"] <= MAX_RESULT_CHARS,
            "declared_budget",
            "BUDGET exceeds the MIPL low-resource profile",
        )
        targets = resolve.get("targets")
        criteria = verify.get("criteria")
        check(
            isinstance(targets, list)
            and 1 <= len(targets) <= MAX_TARGETS
            and all(isinstance(value, str) and 0 < len(value) <= 500 for value in targets),
            "target_bounds",
            "RESOLVE targets are missing or unbounded",
        )
        check(
            isinstance(criteria, list)
            and len(criteria) <= MAX_CRITERIA
            and all(isinstance(value, str) and 0 < len(value) <= 800 for value in criteria),
            "criteria_bounds",
            "VERIFY criteria are malformed or unbounded",
        )
        check(
            not gate_required or gate.get("failure") == "closed",
            "action_fail_closed",
            "side-effecting intent must fail closed",
        )
        check(
            dispatch is not None
            and dispatch.get("engine") == "existing_engel_engine"
            and dispatch.get("authorization") == "external_gate_required",
            "external_dispatch_gate",
            "DISPATCH must defer to an existing Engel engine and external gate",
        )
    elif kind == "agent_task":
        gate = next((record["args"] for record in records if record["opcode"] == Opcode.GATE), {})
        intent = next(
            (record["args"] for record in records if record["opcode"] == Opcode.INTENT), {}
        )
        budget = next(
            (record["args"] for record in records if record["opcode"] == Opcode.BUDGET), {}
        )
        resolve = next(
            (record["args"] for record in records if record["opcode"] == Opcode.RESOLVE), {}
        )
        agent = next(
            (record["args"] for record in records if record["opcode"] == Opcode.AGENT), {}
        )
        task = next(
            (record["args"] for record in records if record["opcode"] == Opcode.TASK), {}
        )
        assignment = next(
            (record["args"] for record in records if record["opcode"] == Opcode.ASSIGN), {}
        )
        verify = next(
            (record["args"] for record in records if record["opcode"] == Opcode.VERIFY), {}
        )
        skill_rows = [
            record["args"] for record in records if record["opcode"] == Opcode.SKILL
        ]

        hashes_valid = all(
            isinstance(intent.get(key), str)
            and len(intent[key]) == 64
            and all(char in "0123456789abcdef" for char in intent[key].casefold())
            for key in ("expression_hash", "lifted_intent_hash")
        )
        check(
            hashes_valid and intent.get("effect") == "dispatch",
            "agent_task_intent",
            "agent-task INTENT hashes or effect are invalid",
        )
        check(
            isinstance(budget.get("max_packets"), int)
            and 1 <= budget["max_packets"] <= MAX_PACKETS
            and isinstance(budget.get("max_wire_bytes"), int)
            and 1 <= budget["max_wire_bytes"] <= MAX_WIRE_BYTES
            and isinstance(budget.get("max_result_chars"), int)
            and 1 <= budget["max_result_chars"] <= MAX_RESULT_CHARS,
            "agent_task_budget",
            "agent-task BUDGET exceeds the low-resource profile",
        )
        agent_id = agent.get("agent_id")
        task_id = task.get("task_id")
        check(
            isinstance(agent_id, str)
            and 1 <= len(agent_id) <= 120
            and isinstance(agent.get("name"), str)
            and 1 <= len(agent["name"]) <= 60
            and isinstance(agent.get("purpose"), str)
            and 10 <= len(agent["purpose"]) <= 500
            and agent.get("lifecycle") in {"draft", "active"},
            "agent_bounds",
            "AGENT identity, purpose, or lifecycle is invalid",
        )
        completion = task.get("completion")
        check(
            isinstance(task_id, str)
            and 1 <= len(task_id) <= 120
            and isinstance(task.get("objective"), str)
            and 1 <= len(task["objective"]) <= MAX_TASK_CHARS
            and isinstance(task.get("max_turns"), int)
            and 1 <= task["max_turns"] <= 25
            and isinstance(completion, list)
            and len(completion) <= MAX_COMPLETION_CRITERIA
            and all(
                isinstance(value, str) and 0 < len(value) <= 500 for value in completion
            ),
            "task_bounds",
            "TASK identity, objective, budget, or completion criteria are invalid",
        )
        skill_ids: list[str] = []
        skills_valid = 1 <= len(skill_rows) <= MAX_SKILLS_PER_TASK
        for row in skill_rows:
            skill_id = row.get("skill_id")
            tools = row.get("tools")
            skills_valid = bool(
                skills_valid
                and isinstance(skill_id, str)
                and 1 <= len(skill_id) <= 80
                and isinstance(row.get("name"), str)
                and 1 <= len(row["name"]) <= 160
                and isinstance(tools, list)
                and len(tools) <= MAX_SKILL_TOOLS
                and all(isinstance(value, str) and 0 < len(value) <= 80 for value in tools)
                and isinstance(row.get("requires_action_grant"), bool)
            )
            if isinstance(skill_id, str):
                skill_ids.append(skill_id)
        check(
            skills_valid and len(skill_ids) == len(set(skill_ids)),
            "skill_bounds",
            "SKILL ids, tool lists, or grant markers are invalid",
        )
        targets = resolve.get("targets")
        assigned_skills = assignment.get("skills")
        check(
            assignment.get("agent_id") == agent_id
            and assignment.get("task_id") == task_id
            and isinstance(assigned_skills, list)
            and assigned_skills == skill_ids
            and isinstance(targets, list)
            and targets == [f"agent:{agent_id}", f"task:{task_id}"],
            "assignment_references",
            "ASSIGN or RESOLVE references do not match the declared agent, task, and skills",
        )
        criteria = verify.get("criteria")
        check(
            isinstance(criteria, list)
            and len(criteria) <= MAX_CRITERIA
            and all(isinstance(value, str) and 0 < len(value) <= 800 for value in criteria),
            "agent_task_criteria",
            "agent-task VERIFY criteria are malformed or unbounded",
        )
        check(
            gate.get("policy") == "approval_and_governor"
            and gate.get("failure") == "closed",
            "agent_task_gate",
            "agent-task work must require approval and fail closed",
        )
        check(
            dispatch is not None
            and dispatch.get("engine") == "engel_authored_agent_runner"
            and dispatch.get("authorization") == "external_gate_required",
            "agent_task_dispatch",
            "agent-task DISPATCH must defer to the authored-agent runner and external gate",
        )
    elif kind == "outcome":
        begin = next((record["args"] for record in records if record["opcode"] == Opcode.BEGIN), {})
        result = next((record["args"] for record in records if record["opcode"] == Opcode.RESULT), {})
        proof = next((record["args"] for record in records if record["opcode"] == Opcode.PROOF), None)
        request_hash = begin.get("request_hash")
        result_hash = result.get("result_hash")
        check(
            all(
                isinstance(value, str)
                and len(value) == 64
                and all(char in "0123456789abcdef" for char in value.casefold())
                for value in (request_hash, result_hash)
            ),
            "outcome_references",
            "outcome request or result hash is invalid",
        )
        check(
            isinstance(result.get("ok"), bool)
            and isinstance(result.get("status"), str)
            and 0 < len(result["status"]) <= 240,
            "result_bounds",
            "RESULT status is missing or unbounded",
        )
        check(
            (result.get("ok") is True and Opcode.ERROR not in codes)
            or (result.get("ok") is False and Opcode.ERROR in codes),
            "error_consistency",
            "ERROR packet does not match RESULT status",
        )
        if proof is not None:
            paths = proof.get("paths")
            check(
                isinstance(paths, list)
                and 1 <= len(paths) <= MAX_PROOF_PATHS
                and all(isinstance(value, str) and 0 < len(value) <= 500 for value in paths),
                "proof_bounds",
                "PROOF paths are missing or unbounded",
            )
    include_failures = next(
        (record["args"].get("include_failures") for record in records if record["opcode"] == Opcode.RETURN),
        None,
    )
    check(include_failures is True, "failure_return", "RETURN must preserve failures")
    return_args = next(
        (record["args"] for record in records if record["opcode"] == Opcode.RETURN), {}
    )
    check(
        return_args.get("channel") == "hipl_comprehension",
        "return_channel",
        "RETURN must target HIPL comprehension",
    )
    checks["known_opcodes"] = len(codes) == len(packets)
    checks["bounded_fields"] = len(_canonical(envelope)) <= MAX_PAYLOAD_BYTES
    if not checks["bounded_fields"]:
        errors.append("MIPL field payload exceeds its bound")
    return {"ok": not errors and all(checks.values()), "checks": checks, "errors": errors}


def disassemble(ir: Mapping[str, Any]) -> str:
    """Render editable MIPL/2 source.  This display is not execution authority."""
    validation = validate_ir(ir)
    if not validation["ok"]:
        raise MiplError("cannot disassemble invalid MIPL: " + "; ".join(validation["errors"]))
    source_kind = str(ir.get("kind") or "request").upper()
    lines = [f"MIPL/2 {source_kind}"]
    for record in packet_records(ir):
        args = {key: value for key, value in record["args"].items() if value is not None}
        lines.append(
            record["opcode"]
            + (" " + json.dumps(args, ensure_ascii=False, separators=(",", ":")) if args else "")
        )
    return "\n".join(lines)


def assemble(source: str) -> dict[str, Any]:
    """Assemble the bounded textual MIPL/2 format into validated wire IR."""
    lines = [line.strip() for line in str(source or "").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines or not lines[0].upper().startswith("MIPL/2 "):
        raise MiplError(
            "MIPL source must begin with 'MIPL/2 REQUEST', "
            "'MIPL/2 AGENT_TASK', or 'MIPL/2 OUTCOME'"
        )
    kind = lines[0].split(None, 1)[1].strip().casefold()
    packets: list[list[Any]] = []
    for seq, line in enumerate(lines[1:]):
        name, separator, raw_args = line.partition(" ")
        try:
            opcode = Opcode[name.upper()]
        except KeyError as exc:
            raise MiplError(f"unknown MIPL instruction: {name}") from exc
        try:
            values = json.loads(raw_args) if separator else {}
        except ValueError as exc:
            raise MiplError(f"{name} arguments must be one JSON object: {exc}") from exc
        if not isinstance(values, dict):
            raise MiplError(f"{name} arguments must be a JSON object")
        packets.append(_packet(seq, opcode, values))
    ir = _ir(kind, packets)
    validation = validate_ir(ir)
    if not validation["ok"]:
        raise MiplError("assembled MIPL failed validation: " + "; ".join(validation["errors"]))
    return ir


def runtime_profile(ir: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return honest low-resource limits and optional compiled stream size."""
    result: dict[str, Any] = {
        "profile": PROFILE,
        "compiler": "deterministic-standard-library",
        "model_required": False,
        "provider_required": False,
        "network_required": False,
        "third_party_packages_required": False,
        "executor_included": False,
        "max_packets": MAX_PACKETS,
        "max_wire_bytes": MAX_WIRE_BYTES,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "max_result_chars": MAX_RESULT_CHARS,
        "max_skills_per_task": MAX_SKILLS_PER_TASK,
        "max_task_chars": MAX_TASK_CHARS,
    }
    if ir is not None:
        wire = ir.get("wire", {}) if isinstance(ir, Mapping) else {}
        result.update(
            {
                "kind": ir.get("kind", ""),
                "packet_count": wire.get("packet_count", 0),
                "encoded_bytes": wire.get("encoded_bytes", 0),
                "payload_bytes": wire.get("payload_bytes", 0),
                "valid": validate_ir(ir).get("ok") is True,
            }
        )
    return result


def render_reference() -> str:
    """Human-readable language reference used by Engel Main surfaces."""
    opcode_lines = ", ".join(f"{op.name}=0x{int(op):02X}" for op in Opcode)
    return "\n".join(
        (
            "Engel MIPL/2 — Machine-Intent Packet Language",
            "",
            "Profile: mipl2-low-resource",
            "Compiler: deterministic Python standard library; no model, provider, network, or package install",
            f"Bounds: {MAX_PACKETS} packets · {MAX_WIRE_BYTES} wire bytes · {MAX_RESULT_CHARS} result characters",
            "Authority: non-authorizing; DISPATCH always requires an existing Engel engine and external gate",
            (
                "Agent work: AGENT + SKILL + TASK + ASSIGN bind one bounded work packet; "
                "creation, activation, grants, and execution remain separate audited steps"
            ),
            "",
            "Opcodes: " + opcode_lines,
            "",
            "Source format: MIPL/2 REQUEST, followed by OPCODE and one JSON argument object per line.",
            "Use `lift intent <request>` or `compile mipl <request>` for a safe preview; neither executes.",
        )
    )
