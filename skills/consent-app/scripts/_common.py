"""Shared helpers for the consent-app skill scripts.

stdlib-only (`urllib`) so the scripts have zero pip dependencies. The
skill never authenticates as a user — the Consent App user creates an
API key in the mobile app and provides the plaintext (`cak_...`) to the
skill via the `CONSENT_API_KEY` env var (or `--api-key` CLI arg). That
key is the only configuration; the endpoints below are fixed.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# === Endpoints ===

API_BASE_URL = "https://api.consent.app"
WEB_BASE_URL = "https://consent.app"


# === Env loading ===

def _load_dotenv(env_path: Path) -> None:
    """Load KEY=VALUE pairs from `env_path` into os.environ. Shell wins."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config() -> dict:
    """Load optional `.env` next to the scripts and return the skill config."""
    _load_dotenv(Path(__file__).parent / ".env")
    return {
        "base_url": API_BASE_URL,
        "api_key": os.environ.get("CONSENT_API_KEY", ""),
    }


def require_api_key(cli_value: str = "") -> str:
    """Return the plaintext API key from the CLI arg or env, or exit(2)."""
    key = (cli_value or os.environ.get("CONSENT_API_KEY", "")).strip()
    if not key:
        print(
            "ERROR: no Consent App API key provided.\n"
            "Pass --api-key <cak_...> or set CONSENT_API_KEY in the environment.\n"
            "The user creates the key in the Consent App mobile app and gives "
            "you the plaintext exactly once.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


# === HTTP helpers ===

def _request(method: str, url: str, headers: dict, payload) -> tuple[int, dict]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"error": body}


def api_call(method: str, base_url: str, path: str, api_key: str, *, payload=None) -> tuple[int, dict]:
    """Call the consent backend with X-API-Key auth."""
    headers = {"X-API-Key": api_key}
    return _request(method, f"{base_url}{path}", headers, payload)


def pp(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def consent_request_url(request_id: str) -> str:
    return f"{WEB_BASE_URL}/approve/{request_id}"
