"""Closing the loop: the patient callback.

Real path: trigger a Vapi outbound call (or SMS) using the approved script.
Mock path (default): log the call so the demo runs without telephony.

Set VAPI_API_KEY + VAPI_PHONE_NUMBER_ID to go live. Everything else stays the
same — this is the one spot that talks to the outside world, so it's the one
spot that's explicitly gated and mockable.
"""

from __future__ import annotations

import os

import httpx


def send_callback(to_number: str | None, script: str) -> dict:
    api_key = os.environ.get("VAPI_API_KEY")
    phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID")

    if not (api_key and phone_number_id and to_number):
        print("\n[callback:MOCK] would call", to_number or "<no number>")
        print("[callback:MOCK] script:", script, "\n")
        return {"mode": "mock", "delivered": False, "script": script}

    # Real Vapi outbound call. The assistant reads the script verbatim.
    resp = httpx.post(
        "https://api.vapi.ai/call",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "phoneNumberId": phone_number_id,
            "customer": {"number": to_number},
            "assistant": {
                "firstMessage": script,
                "model": {"provider": "anthropic", "model": "claude-haiku-4-5",
                          "messages": [{"role": "system",
                                        "content": "Read the first message, answer brief "
                                        "follow-up questions, never state coverage decisions, "
                                        "and offer a nurse callback for anything clinical."}]},
            },
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    return {"mode": "live", "delivered": True, "vapi": resp.json()}
