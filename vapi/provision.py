"""Provision the DME intake assistant onto a Vapi phone number, via the API.

Reads the assistant shape from vapi/assistant.json and the system prompt from
vapi/system_prompt.md, points the assistant's server at our webhook, creates it,
and attaches it to the phone number. One shot; idempotent enough for a demo.

Env (from .env):  VAPI_API_KEY (private), VAPI_PHONE_NUMBER_ID, WEBHOOK_URL
Run:  WEBHOOK_URL=https://xxxx.ngrok.app/vapi/webhook python -m vapi.provision
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
API = "https://api.vapi.ai"


def main() -> int:
    key = os.environ["VAPI_API_KEY"]
    phone_id = os.environ["VAPI_PHONE_NUMBER_ID"]
    webhook = os.environ["WEBHOOK_URL"]

    cfg = json.loads((HERE / "assistant.json").read_text())
    system_prompt = (HERE / "system_prompt.md").read_text()

    assistant = {
        "name": cfg["name"],
        "firstMessage": cfg["firstMessage"],
        "server": {"url": webhook, "headers": {"ngrok-skip-browser-warning": "true"}},
        "serverMessages": ["tool-calls", "end-of-call-report"],
        "model": {
            "provider": "anthropic",
            "model": cfg["model"]["model"],
            "temperature": cfg["model"].get("temperature", 0.4),
            "messages": [{"role": "system", "content": system_prompt}],
            "tools": cfg["model"]["tools"],
        },
    }

    headers = {"Authorization": f"Bearer {key}"}
    with httpx.Client(timeout=30.0) as c:
        r = c.post(f"{API}/assistant", headers=headers, json=assistant)
        if r.status_code >= 300:
            print(f"create assistant FAILED [{r.status_code}]:\n{r.text}")
            return 1
        aid = r.json()["id"]
        print(f"created assistant: {aid}")

        r2 = c.patch(f"{API}/phone-number/{phone_id}", headers=headers,
                     json={"assistantId": aid})
        if r2.status_code >= 300:
            print(f"attach to phone-number FAILED [{r2.status_code}]:\n{r2.text}")
            return 1
        num = r2.json().get("number", "<number>")
        print(f"attached to phone number {num} -> assistant {aid}")
        print(f"server/webhook: {webhook}")
        print("\nReady. Call the number and the console will populate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
