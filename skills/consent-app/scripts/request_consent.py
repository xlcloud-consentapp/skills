#!/usr/bin/env python3
"""Send a consent request via the user-provided API key, then wait for the decision.

Usage:
  python request_consent.py <title> <description> [--ttl SECONDS] [--api-key cak_...]

The plaintext Consent App API key is read from --api-key or, if absent,
from the CONSENT_API_KEY environment variable. The user creates this key
in the Consent App mobile app and provides it to the skill; the skill
never persists it and never signs the user in.

Flow:
  1. POST /api/consentRequests with X-API-Key.
  2. Polls GET /api/consentRequests/{id}/status until the user decides
     or the TTL elapses.

Exit codes:
  0 — approved
  1 — rejected / withdrawn / request expired or closed / timeout / API error
  2 — no API key provided
"""

import argparse
import sys
import time

from _common import api_call, consent_request_url, load_config, pp, require_api_key

POLL_INTERVAL = 2
DEFAULT_TTL_SEC = 300  # backend hard-caps to 300; out-of-range falls back to 60


def wait_for_decision(base_url: str, plaintext: str, request_id: str, timeout: int) -> str:
    print(f"\nWaiting up to {timeout}s for the user's decision ...")
    waited = 0
    last = None
    while waited <= timeout:
        status, data = api_call(
            "GET", base_url, f"/api/consentRequests/{request_id}/status",
            plaintext,
        )
        if status != 200:
            raise RuntimeError(f"status poll returned {status}: {data}")
        cur = data.get("status")
        if cur and cur != "pending":
            print(f"  decision: {cur}")
            return cur
        # Still undecided — but the request may no longer be answerable, in which case
        # no decision is ever coming and there is nothing to wait for.
        lifecycle = data.get("lifecycleStatus")
        if lifecycle in ("expired", "closed"):
            print(f"  request {lifecycle}; no decision possible")
            return lifecycle
        if cur != last:
            print(f"  status: {cur or '(unknown)'}")
            last = cur
        else:
            print(f"  ... still {cur} ({waited}s)")
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
    raise TimeoutError(f"no consent decision within {timeout}s")


def main():
    parser = argparse.ArgumentParser(description="Send a consent request from this skill.")
    parser.add_argument("title", help="Short title shown to the user")
    parser.add_argument("description", help="What exactly will happen if approved")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_SEC,
                        help=f"Seconds the request stays open (1-300, default {DEFAULT_TTL_SEC})")
    parser.add_argument("--api-key", default="",
                        help="Plaintext Consent App API key (cak_...). "
                             "Defaults to $CONSENT_API_KEY.")
    args = parser.parse_args()

    cfg = load_config()
    plaintext = require_api_key(args.api_key or cfg["api_key"])

    print("=== Request Consent ===")
    print(f"Backend:  {cfg['base_url']}\n")

    print("--- 1. POST /api/consentRequests ---")
    status, data = api_call(
        "POST", cfg["base_url"], "/api/consentRequests",
        plaintext,
        payload={
            "title": args.title,
            # shortDescription is the plain-text summary the mobile inbox list
            # renders; the title doubles as it for a plain approve/reject.
            "shortDescription": args.title,
            "description": args.description,
            "ttlSec": args.ttl,
            # content must carry at least one step. A field-less step renders
            # just the title/description with no form to fill.
            "content": {"steps": [{"title": "Consent", "fields": []}]},
        },
    )
    if status == 401:
        print("ERROR: API key rejected (401). The user may have revoked it.")
        pp(data)
        sys.exit(1)
    if status != 201:
        print(f"ERROR: /api/consentRequests returned {status}")
        pp(data)
        sys.exit(1)
    pp(data)
    request_id = data["requestId"]

    print(f"\n  Consent Request URL: {consent_request_url(request_id)}")

    try:
        decision = wait_for_decision(cfg["base_url"], plaintext, request_id, args.ttl)
    except TimeoutError as e:
        print(f"TIMEOUT: {e}")
        sys.exit(1)

    print("\n=== Done ===")
    sys.exit(0 if decision == "approved" else 1)


if __name__ == "__main__":
    main()
