"""Outbound calls: the system's one connection to the outside world.

The coordination work is outbound phone calls (suppliers, the PCP office, the
patient). This places one via Vapi when configured, and otherwise logs it so the
demo runs with no telephony. It is the single spot that talks to an external system,
so it is the single spot that is explicitly gated and mockable.

Set VAPI_API_KEY + VAPI_PHONE_NUMBER_ID to go live.
"""

from __future__ import annotations

import os

import httpx


def send_outbound(to_number: str | None, script: str) -> dict:
    api_key = os.environ.get("VAPI_API_KEY")
    phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID")

    if not (api_key and phone_number_id and to_number):
        print("\n[outbound:MOCK] would call", to_number or "<no number>")
        print("[outbound:MOCK] script:", script, "\n")
        return {"mode": "mock", "delivered": False, "script": script}

    resp = httpx.post(
        "https://api.vapi.ai/call",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "phoneNumberId": phone_number_id,
            "customer": {"number": to_number},
            "assistant": {
                "firstMessage": script,
                "model": {
                    "provider": "anthropic",
                    "model": "claude-haiku-4-5-20251001",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Read the first message, answer brief follow-up "
                            "questions, never state coverage decisions, and offer a "
                            "care-advocate callback for anything clinical.",
                        }
                    ],
                },
            },
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    return {"mode": "live", "delivered": True, "vapi": resp.json()}
