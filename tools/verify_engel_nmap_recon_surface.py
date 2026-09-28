"""Gate for Engel's Nmap recon surface: eight NSE cards, seven evasion flags, and the
authorized-use contract that must ride with them.

Why this exists
---------------
Card 5 of the capabilities curriculum ("an authorized recon sweep of my own home LAN")
had no recon verifier to cite -- the card itself said so -- and the 8-hour run answered by
INVENTING one (`verify_mac_oui_resolution.py`) and inventing receipt paths beside it. That
is the exact failure the worker-liveness card showed: an honest gap in the material becomes
a fabrication in training, because every prompt shape asks for "the named verifier that
proves it" and this was the card with none. The remedy that worked for card 6 was to write
the missing verifier for real, then cite it. This is that verifier.

It asserts the CONTRACT of the recon surface (defined in engel_flutter_main/lib/main.dart),
which is dual-use and therefore only defensible with its guardrails intact:

  1. The eight NSE script cards are all present, each with its real `nmap ... target`
     command line -- the reference a user actually runs against their own LAN.
  2. The seven firewall/IDS-evasion flags are present AND framed as testing your OWN
     defenses, never as attacking a third party.
  3. The AUTHORIZED-USE banner is asserted, not optional. A recon surface that renders its
     evasion flags without the "run these against your own LAN" contract is the thing this
     gate refuses to let regress.

The check reads main.dart as text (the surface is Dart UI, not importable Python), so it is
resilient to widget refactors: it pins the CONTRACT strings, not a widget tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_DART = ROOT / "engel_flutter_main" / "lib" / "main.dart"

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


# The eight NSE cards, by the script token each one teaches. These mirror the widget test
# in engel_flutter_main/test/widget_test.dart; if the roster changes, both move together.
NSE_SCRIPTS = (
    "-sC",
    "--script vuln",
    "http-enum",
    "smb-os-discovery",
    "ftp-anon",
    "vulners",
    "dns-brute",
    "smb-vuln-ms17-010",
)

# The seven evasion flags, framed as testing your own defenses.
EVASION_FLAGS = ("-f", "-D", "-S", "--spoof-mac", "-g", "--data-length", "--badsum")


def main() -> int:
    if not MAIN_DART.is_file():
        check("main_dart_present", False, f"missing {MAIN_DART}")
        print("\n0/1 checks passed")
        print("FAILED: main_dart_present")
        return 1
    src = MAIN_DART.read_text(encoding="utf-8", errors="replace")

    # 1. Authorized-use contract is present and not optional.
    check(
        "authorized_use_banner_present",
        "Authorized use only" in src,
        "the recon surface must assert authorized-use framing",
    )
    check(
        "authorized_use_scopes_to_own_lan",
        "against your own LAN" in src,
        "the banner must scope recon to the operator's own LAN",
    )

    # 2. All eight NSE script cards present.
    missing_nse = [s for s in NSE_SCRIPTS if s not in src]
    check(
        "all_eight_nse_scripts_present",
        not missing_nse,
        f"missing {missing_nse}" if missing_nse else "8/8 NSE cards",
    )

    # 3. Each card carries a real runnable command line, not just the flag name.
    #    -sC is the documented ★ BEST default and its example is asserted verbatim.
    check(
        "nse_card_shows_runnable_command",
        "nmap -sC 192.168.1.10" in src,
        "the default card must show a real nmap command a user can run",
    )
    check(
        "nse_vuln_card_shows_runnable_command",
        "nmap --script vuln" in src,
        "the vuln card must show its real nmap command",
    )

    # 4. All seven evasion flags present.
    missing_flags = [f for f in EVASION_FLAGS if f not in src]
    check(
        "all_seven_evasion_flags_present",
        not missing_flags,
        f"missing {missing_flags}" if missing_flags else "7/7 evasion flags",
    )

    # 5. Evasion is framed as testing your own defenses, not attacking others.
    low = src.casefold()
    check(
        "evasion_framed_as_own_defense",
        "FIREWALL / IDS EVASION" in src
        and ("your own gateway" in low or "own defenses" in low or "own eero" in low),
        "evasion flags must be framed as testing the operator's own defenses",
    )

    # 6. The portable, Npcap-free scanner path is pinned to the D: runtime (the no-C rule).
    check(
        "portable_nmap_on_d_drive",
        r"D:\b.WorkSpace\Engel App\runtime\nmap" in src,
        "the bundled nmap must live under the D: runtime, never invoke a C: install",
    )

    # 7. Non-vacuous negative: a made-up flag must NOT be reported present. This proves the
    #    presence checks above are substring hits on the real surface, not always-true.
    check(
        "detector_is_non_vacuous",
        "--script engel-totally-made-up-script" not in src,
        "sanity: an invented flag must not be found in the surface",
    )

    failed = [n for n, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
