"""Shared Engel product names for backend contracts.

These constants keep new backend surfaces Engel-branded while allowing older
contract receipts to remain readable through explicit legacy aliases.
"""

from __future__ import annotations


ENGEL_CORE_NAME = "Engel Core"
ENGEL_COMMUNICATION_ROUTER_NAME = "Engel Communication Router"
ENGEL_BROWSER_RESEARCH_NAME = "Engel Browser Research"
ENGEL_REMOTE_WORKER_CONTROLLER_NAME = "Engel Remote Worker Controller"
ENGEL_CODE_COMPANION_NAME = "Engel Code Companion"

LEGACY_COMMUNICATION_QUEEN_NAME = "Communication Queen"
LEGACY_BROWSER_QUEEN_NAME = "Browser Queen"
LEGACY_REMOTE_QUEEN_NAME = "Remote Queen"
LEGACY_QUEEN_LINKS_NAME = "Queen Links"

ENGEL_COMMUNICATION_ROUTER_ALIASES = {
    ENGEL_COMMUNICATION_ROUTER_NAME,
    LEGACY_COMMUNICATION_QUEEN_NAME,
}


def is_engel_communication_router_name(value: object) -> bool:
    return str(value) in ENGEL_COMMUNICATION_ROUTER_ALIASES
