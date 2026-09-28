#!/usr/bin/env python3
"""Gate for Engel's LAN device fingerprint engine.

The whole point of complete identification is that it stays HONEST — this codebase
forbids invented facts, and a device inventory that guesses is worse than one that
admits "unknown". So the checks here enforce the honest-unknown contract:

  * OUI resolves real globally-administered MACs to real vendors (full 30k DB).
  * A locally-administered / randomized MAC is NEVER given an OUI vendor.
  * A vendor is NEVER promoted to a product model (OUI = NIC maker, not product).
  * Every asserted field traces to an evidence entry (evidence-or-omit).
  * Broadcast / multicast addresses are not reported as devices.
  * identification_level matches the evidence actually present.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / "tools")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main() -> int:
    import engel_lan_fingerprint as fp

    # ---- OUI resolver ----
    db = fp._load_oui()
    check("oui_db_loaded", len(db) > 20000, f"{len(db)} prefixes")
    check("oui_resolves_vizio", fp.mac_vendor("3C-9B-D6-4D-C0-D8")[0] == "Vizio")
    check("oui_resolves_dell", fp.mac_vendor("EC-F4-BB-E9-B1-C0")[0] == "Dell")
    check("oui_overlay_covers_eero", fp.mac_vendor("94-CD-FD-38-50-D2")[0] == "eero inc.")

    # randomized / locally-administered MAC must NOT get a vendor
    vendor, randomized = fp.mac_vendor("7A-12-42-32-74-23")
    check("randomized_mac_flagged", randomized is True)
    check("randomized_mac_no_vendor", vendor == "Private/randomized MAC",
          "a privacy MAC must never be attributed to a NIC vendor")

    # unknown OUI is honest, echoes the real prefix, never a guess
    unknown = fp.mac_vendor("02-00-00-11-22-33")  # LA bit set -> randomized branch
    check("la_bit_detected_even_for_unknown", unknown[1] is True)
    fake = fp.mac_vendor("F0-F0-F0-11-22-33")  # not in DB, globally administered
    check("unknown_oui_is_honest", fake[0].startswith("Unknown OUI ("), fake[0])

    # ---- classification never invents ----
    bare = {"oui_vendor": "Unknown OUI (aa:bb:cc)", "open_ports": [], "mac_randomized": False}
    dtype, _ = fp.classify(bare)
    check("no_signal_stays_unknown", dtype == "unknown",
          "a device with no discriminating signal must not be typed")
    check("bare_device_level_unknown",
          fp.identification_level({**bare, "device_type": "unknown"}) == "UNKNOWN")

    # vendor alone must NOT reach FULLY_IDENTIFIED (no model, no corroboration)
    vendor_only = {"oui_vendor": "Dell", "device_type": "unknown",
                   "model_guess": {"value": None}, "open_ports": []}
    check("vendor_alone_not_fully",
          fp.identification_level(vendor_only) != "FULLY_IDENTIFIED",
          "OUI vendor alone is not complete identification")

    # a self-reported model + type + corroboration IS fully identified
    full = {"oui_vendor": "Vizio", "device_type": "TV/streaming",
            "model_guess": {"value": "V435-J01", "verified": True},
            "open_ports": [8008, 9000], "vendor_report": {"google_cast": {"model": "x"}}}
    check("self_reported_model_is_fully",
          fp.identification_level(full) == "FULLY_IDENTIFIED")

    # ---- broadcast/multicast filtering exists in source ----
    src = (ROOT / "tools" / "engel_lan_fingerprint.py").read_text(encoding="utf-8")
    check("filters_broadcast_ip", '.endswith(".255")' in src)
    check("filters_broadcast_mac", "_BROADCAST_MACS" in src)
    check("filters_multicast", "224 <= first <= 239" in src)
    check("evidence_or_omit_rule", 'evidence.append' in src and '"observed_at"' in src)

    # ---- live latest report, if present, obeys the contract ----
    latest = ROOT / "runtime" / "device_swarm" / "device_lan_fingerprint_latest.json"
    if latest.is_file():
        import json
        data = json.loads(latest.read_text(encoding="utf-8"))
        devices = data.get("devices", [])
        check("live_report_has_devices", bool(devices), f"{len(devices)} devices")
        no_broadcast = all(not d["ip"].endswith(".255") for d in devices)
        check("live_no_broadcast", no_broadcast)
        rand_clean = all(
            not (d.get("mac_randomized") and d.get("oui_vendor", "") not in
                 ("Private/randomized MAC", ""))
            for d in devices
        )
        check("live_randomized_never_vendored", rand_clean)
        model_clean = all(
            (d.get("model_guess") or {}).get("value") is None
            or (d.get("model_guess") or {}).get("verified") is True
            for d in devices
        )
        check("live_models_are_self_reported_only", model_clean,
              "every asserted model must be device-self-reported, not inferred")
        every_fact_evidenced = all(bool(d.get("evidence")) for d in devices if
                                   d.get("identification_level") != "UNKNOWN")
        check("live_identified_devices_carry_evidence", every_fact_evidenced)
    else:
        check("live_report_present", False, "run engel_lan_fingerprint.py first (optional)")

    failed = [n for n, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
