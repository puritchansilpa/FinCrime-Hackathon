"""[Workstream A] xAI LLM client and note-extraction fallback (task A7).

Off by default. It is used only when the run is started with --llm AND the XAI_API_KEY
environment variable is set. The event provides an xAI key and the organisers confirmed
they score with xAI. Python standard library only (urllib); no account login is needed,
the key alone authenticates.

The LLM never decides anything. It only reads a note the regex parser could not read,
and every value it returns is checked against the note text in code: a name, date or
country that does not appear in the text is dropped (unknown), never trusted.

Determinism: temperature 0, a fixed seed, a pinned dated model, a JSON schema for the
answer, and an in-memory cache so the same note always gives the same answer within a
run. Set LLM_CACHE_FILE to also keep answers on disk across runs (development only).
Any error (network, timeout, bad JSON, bad key) means "unknown", which leans towards REVIEW.

Settings (environment variables):
  XAI_API_KEY      required to enable
  XAI_MODEL        default below; pin a dated model, not a floating alias
  LLM_TIMEOUT      seconds per request (default 30)
  LLM_CACHE_FILE   optional JSON file for answers across runs
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from . import fallbacks, normalize

API_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4.20-0309-non-reasoning"   # dated, non-reasoning: fast and stable for extraction
SEED = 7

_state = {"requested": False, "cache": {}, "calls": 0, "failures": 0, "loaded_file": None}


# --- switch ----------------------------------------------------------------------------

def configure(use_llm: bool) -> None:
    """Called once per run from __main__ with the --llm flag."""
    _state["requested"] = bool(use_llm)
    if enabled():
        _load_cache_file()


def enabled() -> bool:
    return _state["requested"] and bool(os.environ.get("XAI_API_KEY"))


def stats() -> dict:
    return {"calls": _state["calls"], "failures": _state["failures"], "cached": len(_state["cache"])}


# --- transport ---------------------------------------------------------------------------

def _load_cache_file():
    path = os.environ.get("LLM_CACHE_FILE")
    if path and _state["loaded_file"] != path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                _state["cache"].update(json.load(fh))
        except (OSError, ValueError) as exc:
            print(f"warning: could not read LLM cache {path}: {exc}", file=sys.stderr)
        _state["loaded_file"] = path


def _save_cache_file():
    path = os.environ.get("LLM_CACHE_FILE")
    if path:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(_state["cache"], fh, ensure_ascii=False, sort_keys=True)
        except OSError as exc:
            print(f"warning: could not write LLM cache {path}: {exc}", file=sys.stderr)


def _post(payload: dict, timeout: float) -> dict:
    """One HTTPS request to xAI (replaced by a fake in tests)."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + os.environ.get("XAI_API_KEY", ""),
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _first_json_object(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
    return None


def chat_json(system: str, user: str, schema: dict, name: str = "answer"):
    """Ask for one JSON object matching schema. Returns a dict, or None on any failure.

    Also usable by Workstream B's LLM pieces (B7).
    """
    if not enabled():
        return None
    model = os.environ.get("XAI_MODEL") or DEFAULT_MODEL
    key = hashlib.sha256(json.dumps([model, system, user, schema], sort_keys=True)
                         .encode("utf-8")).hexdigest()
    if key in _state["cache"]:
        return _state["cache"][key]

    payload = {
        "model": model,
        "temperature": 0,
        "top_p": 1,
        "seed": SEED,
        "max_tokens": 1000,   # room for a reasoning model if XAI_MODEL points at one
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": name, "strict": True, "schema": schema}},
    }
    timeout = float(os.environ.get("LLM_TIMEOUT", "30"))

    answer = None
    for attempt in range(3):
        _state["calls"] += 1
        try:
            reply = _post(payload, timeout)
            content = reply["choices"][0]["message"]["content"]
            answer = _first_json_object(content if isinstance(content, str) else json.dumps(content))
            if isinstance(answer, dict):
                break
            answer = None
        except urllib.error.HTTPError as exc:
            print(f"warning: LLM call failed (HTTP {exc.code})", file=sys.stderr)
            if exc.code == 400 and ("seed" in payload or "response_format" in payload):
                # A model that rejects an optional parameter: retry without it, asking for
                # plain JSON instead (the reply is still parsed and checked against the text).
                payload = {k: v for k, v in payload.items() if k not in ("seed", "response_format")}
                payload["messages"] = [{"role": "system", "content": system +
                                        " Reply with only one JSON object matching this schema: " +
                                        json.dumps(schema)},
                                       {"role": "user", "content": user}]
                continue
            if exc.code in (401, 403, 404):
                break                    # bad key or unknown model: retrying will not help
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            print(f"warning: LLM call failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    if answer is None:
        _state["failures"] += 1
        return None  # not cached: a later run may succeed
    _state["cache"][key] = answer
    _save_cache_file()
    return answer


# --- note extraction fallbacks -------------------------------------------------------------

_KYC_SYSTEM = (
    "You extract fields from one identity-verification note written by a bank's onboarding team. "
    "Copy values exactly as they are written in the note; do not reformat, translate or infer. "
    "Use null for anything the note does not state. Never guess."
)
_KYC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "date_of_birth", "document_country", "check_date", "result"],
    "properties": {
        "name": {"type": ["string", "null"], "description": "the verified person's or company's name, verbatim"},
        "date_of_birth": {"type": ["string", "null"], "description": "date of birth or incorporation, verbatim"},
        "document_country": {"type": ["string", "null"], "description": "country that issued the document, verbatim"},
        "check_date": {"type": ["string", "null"], "description": "date the check was done, verbatim"},
        "result": {"type": ["string", "null"], "enum": ["approved", "rejected", "expired", None]},
    },
}

_RES_SYSTEM = (
    "You read one customer-support note and list the countries the customer says they lived or "
    "worked in. Copy each country exactly as written. Use an empty list if there are none."
)
_RES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["countries"],
    "properties": {"countries": {"type": "array", "items": {"type": "string"}}},
}


def _in_text(value, text) -> bool:
    if not value or not text:
        return False
    norm = lambda s: re.sub(r"\s+", " ", str(s)).strip().casefold()
    return norm(value) in norm(text)


def _parse_date(s):
    return normalize.parse_date(s) or fallbacks.parse_date(s)


def _country(s):
    return normalize.to_country(s) or fallbacks.to_country(s)


def extract_kyc_note(text: str, created_at: str = None):
    """LLM fallback for a kyc note. Same shape as notes_parse.parse_kyc_note, or None.

    A value is kept only if it appears verbatim in the note and parses.
    """
    if not enabled() or not text:
        return None
    ans = chat_json(_KYC_SYSTEM, "Note:\n" + text, _KYC_SCHEMA, "kyc_note")
    if not ans:
        return None
    name = ans.get("name") if _in_text(ans.get("name"), text) else None
    dob_raw = ans.get("date_of_birth") if _in_text(ans.get("date_of_birth"), text) else None
    dob = _parse_date(dob_raw) if dob_raw else None
    country_raw = ans.get("document_country") if _in_text(ans.get("document_country"), text) else None
    check_raw = ans.get("check_date") if _in_text(ans.get("check_date"), text) else None
    result = ans.get("result") if ans.get("result") in ("approved", "rejected", "expired") else None
    if name is None and dob is None:
        return None
    return {
        "name": name,
        "dob": dob,
        "dob_raw": dob_raw if dob else None,
        "doc_country": _country(country_raw) if country_raw else None,
        "doc_type": None,
        "provider": None,
        "checked_at": (_parse_date(check_raw) if check_raw else None) or _parse_date(created_at),
        "result": result,
        "llm": True,
    }


def extract_residence_countries(text: str) -> list:
    """LLM fallback for a residence note: countries named in the text, validated in code."""
    if not enabled() or not text:
        return []
    ans = chat_json(_RES_SYSTEM, "Note:\n" + text, _RES_SCHEMA, "residence_note")
    if not ans or not isinstance(ans.get("countries"), list):
        return []
    out = {_country(c) for c in ans["countries"] if isinstance(c, str) and _in_text(c, text)}
    return sorted(c for c in out if c)
