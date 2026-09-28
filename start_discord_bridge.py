"""Retired laptop Discord starter.

Production Engel Discord replies come from CT 246
``tools/engel_discord_bridge.py`` (``engel-discord-bridge.service``).

This file used to start a second bot on the ROG laptop with an echo hook
(``Thanks for the message. You said:``). That stole the Discord gateway from
Engel AI Main and made the bot look like it was not answering correctly.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("This laptop starter is retired.")
    print("Engel Discord replies come from CT 246: tools/engel_discord_bridge.py")
    print("Starting a second bot here would steal the gateway and echo messages.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
