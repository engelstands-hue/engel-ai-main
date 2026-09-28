from __future__ import annotations

from typing import Any


SURFACE_NAME = "Core Continuity Dashboard Status Surface V1"
SURFACE_TITLE = "Controlled Approved Library Chain"
SURFACE_TYPE = "core_continuity_dashboard_status_surface"

STATUS = [
    "STATUS_SURFACE_ONLY",
    "READ_ONLY_VIEW",
    "CORE_CONTINUITY_VISIBLE",
    "CONTROLLED_LIBRARY_CHAIN_VISIBLE",
    "NO_QUEUE_MUTATION",
    "NO_RECEIPT_MUTATION",
    "NO_APPROVAL_ACTION",
    "NO_IMPORT_ACTION",
    "NO_FILE_OPERATION_ACTION",
    "NOT_TRUSTED_MEMORY",
    "NO_LEARNING_TRIGGER",
    "NO_RUNTIME_TRIGGER",
]

DISPLAY_BADGES = [
    "READ ONLY",
    "METADATA ONLY",
    "TOKEN REQUIRED",
    "NOT TRUSTED MEMORY",
    "NO QUEUE MUTATION",
    "NO AUTOMATION",
]

APPROVAL_TOKENS = [
    "APPROVE_CREATE_LIBRARY_QUEUE_RECORD",
    "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT",
    "APPROVE_MARK_APPROVED_FOR_REFERENCE",
]

TOKEN_BOUNDARY = [
    "tokens are narrow human approval gates",
    "tokens do not grant import/copy/move/sync/scanning/indexing/training/runtime/memory authority",
    "tokens do not bypass Prompt Injection Guard, Untrusted Content Guard, Authority Hierarchy, or memory proposal rules",
]

SAFETY_BOUNDARY_STATEMENTS = [
    "Queue metadata is not material content.",
    "Queue record is not approval.",
    "Queue record is not receipt.",
    "Queue record is not trusted memory.",
    "Receipt metadata is not trusted memory.",
    "Approved-for-reference is not trusted memory.",
    "Approved-for-reference is not model training permission.",
    "Approved-for-reference is not runtime permission.",
    "Manual import receipt records human action after the fact.",
    "Bounded file presence check does not prove file safety or trust.",
    "Anything Engel may remember requires a separate memory candidate proposal and human approval.",
    "Separate memory candidate proposal is required for anything Engel may remember.",
]

GLOBAL_DISABLED_BEHAVIOR = [
    "no queue records are created",
    "no receipts are created",
    "no approvals are created",
    "no imports are performed",
    "no file operations are performed",
    "no scans are started",
    "no indexing or embeddings are created",
    "no model behavior is changed",
    "no trusted-memory writes are performed",
    "no queue workers or background workers are started",
    "no route/startup/source changes are made",
    "no provider/network/browser behavior is added",
    "no package-manager behavior is added",
]

BOUNDED_FILE_PRESENCE_CHECKER = {
    "name": "Bounded File Presence Checker V1",
    "status": "BOUNDED_CHECK_ONLY / EXPLICIT_PATH_ONLY / NO_RECURSIVE_SCAN / NO_FILE_CONTENT_READ / NO_IMPORT / NO_INDEXING / NOT_TRUSTED_MEMORY",
    "display_lines": [
        "accepts one explicit path",
        "path must stay under `engel_library\\approved_library`",
        "must stay under approved_library",
        "returns only `exists` / `not_exists`",
        "returns exists/not_exists only",
        "does not read file contents",
        "no content read",
        "does not scan folders",
        "no folder scan",
        "does not recurse",
        "no recursion",
        "does not hash",
        "no hashing",
        "does not import",
        "no import",
        "does not index",
        "no indexing",
        "does not execute",
        "does not write memory",
        "no trust assertion",
        "does not prove safety, truth, approval, or trust",
    ],
}

CHAIN_COMPONENTS = [
    {
        "step": 1,
        "pipeline_label": "Draft Schema",
        "name": "Manual Queue Record Draft Schema V1",
        "status": "SCHEMA_ONLY / DRAFT_RECORD_SHAPE_ONLY / HUMAN_AUTHORITY_REQUIRED / NO_REAL_QUEUE_RECORDS / NO_QUEUE_WRITER / NO_ACTIVE_QUEUE_RUNTIME / NO_QUEUE_WORKER / NO_AUTOMATIC_IMPORT / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Defines the exact queue metadata draft shape before any future real queue record can exist.",
        "safety_boundary": "Schema only. It is not a queue writer, not approval, not a receipt, and not trusted memory.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "",
        "read_only": True,
        "explicitly_does_not_do": ["write queue records", "approve materials", "create receipts", "import files"],
    },
    {
        "step": 2,
        "pipeline_label": "Queue Create Approval Contract",
        "name": "Manual Queue Record Create Approval Contract V1",
        "status": "CONTRACT_ONLY / APPROVAL_BOUNDARY_ONLY / HUMAN_APPROVAL_REQUIRED / NO_QUEUE_WRITER / NO_REAL_QUEUE_RECORDS / NO_ACTIVE_QUEUE_RUNTIME / NO_QUEUE_WORKER / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Defines the human approval boundary and future narrow token for queue metadata writes.",
        "safety_boundary": "Approval contract only. The token is a narrow human gate and does not create writer behavior by itself.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "APPROVE_CREATE_LIBRARY_QUEUE_RECORD",
        "read_only": True,
        "explicitly_does_not_do": ["write records", "approve reference use", "import files", "write trusted memory"],
    },
    {
        "step": 3,
        "pipeline_label": "Queue Record Writer",
        "name": "Manual Queue Record Writer V1",
        "status": "METADATA_WRITER_ONLY / HUMAN_APPROVAL_REQUIRED / APPROVAL_TOKEN_REQUIRED / QUEUE_RECORD_METADATA_ONLY / NO_MATERIAL_IMPORT / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Writes bounded repo-local queue metadata only after exact human approval token.",
        "safety_boundary": "Queue record writer writes metadata only. Queue metadata is not material content, approval, receipt, or trusted memory.",
        "writes_metadata": True,
        "requires_approval_token": True,
        "approval_token": "APPROVE_CREATE_LIBRARY_QUEUE_RECORD",
        "read_only": False,
        "explicitly_does_not_do": ["read material contents", "import/copy/move/sync files", "scan folders", "approve materials"],
    },
    {
        "step": 4,
        "pipeline_label": "Queue Record Viewer",
        "name": "Queue Record Viewer V1",
        "status": "READ_ONLY_VIEWER / METADATA_ONLY / NO_QUEUE_MUTATION / NO_APPROVAL_ACTION / NO_RECEIPT_ACTION / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Displays bounded repo-local queue metadata records without mutation.",
        "safety_boundary": "Read-only metadata viewer. It cannot edit, create, delete, approve, receive, import, execute, or trust records.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "",
        "read_only": True,
        "explicitly_does_not_do": ["edit records", "create records", "approve records", "write trusted memory"],
    },
    {
        "step": 5,
        "pipeline_label": "Receipt Draft Surface",
        "name": "Human Review Receipt Draft Surface V1",
        "status": "RECEIPT_DRAFT_ONLY / HUMAN_GUIDED / NO_REAL_RECEIPTS / NO_APPROVAL_ACTION / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Helps prepare draft-only human review receipt metadata previews.",
        "safety_boundary": "Draft surface only. A draft is not a real receipt, not approval, and not trusted memory.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "",
        "read_only": True,
        "explicitly_does_not_do": ["write receipts", "approve materials", "import files", "write trusted memory"],
    },
    {
        "step": 6,
        "pipeline_label": "Receipt Writer",
        "name": "Human Review Receipt Writer V1",
        "status": "RECEIPT_METADATA_WRITER_ONLY / HUMAN_APPROVAL_REQUIRED / APPROVAL_TOKEN_REQUIRED / NO_APPROVAL_ACTION / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Writes bounded repo-local receipt metadata only after exact human approval token.",
        "safety_boundary": "Receipt metadata only. A receipt record is not reference approval and not trusted memory.",
        "writes_metadata": True,
        "requires_approval_token": True,
        "approval_token": "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT",
        "read_only": False,
        "explicitly_does_not_do": ["approve materials", "import/copy/move/sync files", "scan folders", "write trusted memory"],
    },
    {
        "step": 7,
        "pipeline_label": "Approved-for-Reference Contract",
        "name": "Approved-for-Reference Decision Contract V1",
        "status": "CONTRACT_ONLY / REFERENCE_DECISION_BOUNDARY_ONLY / HUMAN_APPROVAL_REQUIRED / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Defines the reference-only decision boundary before reference metadata can be written.",
        "safety_boundary": "Approved-for-reference is research/reference only. It is not trusted memory, model training permission, runtime permission, or execution permission.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "APPROVE_MARK_APPROVED_FOR_REFERENCE",
        "read_only": True,
        "explicitly_does_not_do": ["write reference metadata", "import files", "train models", "load runtime content"],
    },
    {
        "step": 8,
        "pipeline_label": "Approved-for-Reference Metadata Writer",
        "name": "Approved-for-Reference Metadata Writer V1",
        "status": "REFERENCE_METADATA_WRITER_ONLY / HUMAN_APPROVAL_REQUIRED / APPROVAL_TOKEN_REQUIRED / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Writes bounded reference metadata only after exact human approval token and queue/receipt validation.",
        "safety_boundary": "Reference metadata only. It is not trusted memory, not training permission, not runtime permission, and not execution permission.",
        "writes_metadata": True,
        "requires_approval_token": True,
        "approval_token": "APPROVE_MARK_APPROVED_FOR_REFERENCE",
        "read_only": False,
        "explicitly_does_not_do": ["import/copy/move files", "read or summarize material contents", "index/embed content", "write trusted memory"],
    },
    {
        "step": 9,
        "pipeline_label": "Manual Import Assistant Contract",
        "name": "Manual Approved Library Import Assistant Contract V1",
        "status": "CONTRACT_ONLY / HUMAN_GUIDED_IMPORT_PLANNING_ONLY / NO_FILE_OPERATIONS / NO_AUTOMATIC_IMPORT / NO_COPY / NO_MOVE / NO_SYNC / NOT_TRUSTED_MEMORY",
        "purpose": "Defines future human-guided placement instructions and reminders only.",
        "safety_boundary": "Planning contract only. The human remains the actor; Engel does not copy, move, sync, scan, or import files.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "",
        "read_only": True,
        "explicitly_does_not_do": ["copy files", "move files", "sync folders", "probe storage locations"],
    },
    {
        "step": 10,
        "pipeline_label": "Manual Import Receipt",
        "name": "Manual Import Receipt V1",
        "status": "RECEIPT_TEMPLATE_ONLY / HUMAN_RECORDED_ACTION / NO_FILE_OPERATIONS / NOT_TRUSTED_MEMORY / NO_LEARNING_TRIGGER / NO_RUNTIME_TRIGGER",
        "purpose": "Defines an after-the-fact human-recorded receipt for manual placement into approved_library.",
        "safety_boundary": "Receipt template only. It records a human action after the fact and performs no file operation.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "",
        "read_only": True,
        "explicitly_does_not_do": ["move files", "copy files", "import files", "prove file safety"],
    },
    {
        "step": 11,
        "pipeline_label": "Bounded File Presence Checker",
        "name": "Bounded File Presence Checker V1",
        "status": BOUNDED_FILE_PRESENCE_CHECKER["status"],
        "purpose": "Checks whether one explicit path under approved_library exists or does not exist.",
        "safety_boundary": "Explicit path presence only. It does not prove safety, truth, approval, or trust.",
        "writes_metadata": False,
        "requires_approval_token": False,
        "approval_token": "",
        "read_only": True,
        "explicitly_does_not_do": ["read file contents", "scan folders", "hash files", "import or index files"],
    },
]


def build_controlled_library_chain_status() -> dict[str, Any]:
    return {
        "surface_name": SURFACE_NAME,
        "surface_title": SURFACE_TITLE,
        "surface_type": SURFACE_TYPE,
        "status": list(STATUS),
        "badges": list(DISPLAY_BADGES),
        "components": [dict(component) for component in CHAIN_COMPONENTS],
        "approval_tokens": list(APPROVAL_TOKENS),
        "token_boundary": list(TOKEN_BOUNDARY),
        "safety_boundary": list(SAFETY_BOUNDARY_STATEMENTS),
        "bounded_file_presence_checker": dict(BOUNDED_FILE_PRESENCE_CHECKER),
        "disabled_behavior": list(GLOBAL_DISABLED_BEHAVIOR),
        "implementation_mode": "module-only read-only status surface",
        "not_trusted_memory": True,
        "no_queue_mutation": True,
        "no_receipt_mutation": True,
        "no_approval_action": True,
        "no_import_action": True,
        "no_file_operation_action": True,
    }


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def render_controlled_library_chain_status() -> str:
    status = build_controlled_library_chain_status()
    lines = [
        "# " + str(status["surface_title"]),
        "",
        "Surface:",
        str(status["surface_name"]),
        "",
        "Status:",
        " / ".join(str(item) for item in status["status"]),
        "",
        "Badges:",
        " | ".join(str(item) for item in status["badges"]),
        "",
        "Pipeline:",
    ]
    for component in status["components"]:
        lines.extend(
            [
                "",
                str(component["step"]) + ". " + str(component["pipeline_label"]),
                "Name: " + str(component["name"]),
                "Status: " + str(component["status"]),
                "Purpose: " + str(component["purpose"]),
                "Safety boundary: " + str(component["safety_boundary"]),
                "Writes metadata: " + yes_no(bool(component["writes_metadata"])),
                "Requires approval token: " + yes_no(bool(component["requires_approval_token"])),
                "Read-only: " + yes_no(bool(component["read_only"])),
            ]
        )
        if component.get("approval_token"):
            lines.append("Approval token: " + str(component["approval_token"]))
        lines.append("Explicitly does not do: " + "; ".join(str(item) for item in component["explicitly_does_not_do"]))

    lines.extend(
        [
            "",
            "Approval Tokens:",
            *["- " + str(token) for token in status["approval_tokens"]],
            "",
            "Token Boundary:",
            *["- " + str(line) for line in status["token_boundary"]],
            "",
            "Safety Boundary:",
            *["- " + str(line) for line in status["safety_boundary"]],
            "",
            "Bounded File Presence Checker V1:",
            *["- " + str(line) for line in status["bounded_file_presence_checker"]["display_lines"]],
            "",
            "Disabled Behavior:",
            *["- " + str(line) for line in status["disabled_behavior"]],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    print(render_controlled_library_chain_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
