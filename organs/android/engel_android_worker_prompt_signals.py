#!/usr/bin/env python3
"""Shared prompt signals for Android remote-worker UI and Meeting Room routing."""
from __future__ import annotations


def normalize_prompt_low(text: str) -> str:
    return str(text or "").casefold()


def is_android_lan_pairing_request(text: str) -> bool:
    """True when the user is asking for a WiFi/LAN pairing code, not a code artifact."""
    low = normalize_prompt_low(text)
    if "pairing code" not in low and not ("pair" in low and "code" in low):
        return False
    return any(
        token in low
        for token in (
            "wifi",
            "wi-fi",
            "wi fi",
            "widi",
            "wireless",
            "lan",
            "android",
            "phone",
            "remote worker",
            "worker",
            "engel remote",
            "connect",
            "pair phones",
            "pair android",
        )
    )


def mentions_android_worker_lane(text: str) -> bool:
    """True when the prompt is about Android/remote worker phones or LAN pairing."""
    low = normalize_prompt_low(text)
    mentions_android_worker = "android" in low and "worker" in low
    mentions_remote_worker = "remote worker" in low or "remote workers" in low
    mentions_phone_worker = "phone" in low and "worker" in low
    mentions_phone = ("phone" in low or "phones" in low) and any(
        token in low
        for token in ("pair", "connect", "wake", "usb", "android", "worker", "remote")
    )
    mentions_pairing_lane = "pairing code" in low and any(
        token in low for token in ("wifi", "wi-fi", "wi fi", "widi", "wireless", "lan", "android", "phone", "remote")
    )
    mentions_usb_pairing = "usb" in low and any(
        token in low for token in ("pair", "connect", "phone", "phones", "android", "worker")
    )
    return (
        mentions_android_worker
        or mentions_remote_worker
        or mentions_phone_worker
        or mentions_phone
        or mentions_pairing_lane
        or mentions_usb_pairing
        or "adb" in low
    )
