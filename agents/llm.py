"""RationRight — optional OpenAI-compatible narrative layer (Phase 10).

The LLM is used ONLY for human-readable narrative text: Agent 2's verified
``explanation``, Agent 3's case ``summary``, and Agent 4's alert ``message``.
Every deterministic calculation (time difference, geographic distance,
validation, thresholds, evidence preservation, IDs, severity, status,
confidence) remains in code and is NEVER delegated to the LLM.

The OpenAI-compatible Chat Completions REST API is called with the Python
standard library (``urllib``) — no third-party SDK, no install. Any
OpenAI-compatible endpoint works: OpenAI (``https://api.openai.com/v1``) or
OpenRouter (``https://openrouter.ai/api/v1``) via ``RATIONRIGHT_LLM_BASE_URL``.

Activation and fail-open behavior:

- The layer activates only when BOTH ``RATIONRIGHT_LLM_ENABLED`` is truthy
  (e.g. ``1``) AND ``OPENAI_API_KEY`` is set. Without either, the deterministic
  templates are used unchanged and the workflow behaves exactly as before.
- On ANY failure — no key, network error, timeout, HTTP error, empty or
  unusable response, or a response that uses forbidden guilt language — the
  deterministic ``fallback`` text is used and a warning is logged. The LLM
  layer never raises and never fails the workflow.

Configuration (read from the environment; ``agents/env.load_env_file`` loads a
git-ignored ``.env`` for local development):

- ``RATIONRIGHT_LLM_ENABLED`` — opt-in switch (``1``/``true``/``yes``/``on``).
- ``OPENAI_API_KEY`` — the API key (OpenAI or OpenRouter). Server-side only.
- ``RATIONRIGHT_LLM_BASE_URL`` — base URL, e.g. ``https://openrouter.ai/api/v1``
  (required for ``sk-or-v1-...`` OpenRouter keys). Defaults to OpenAI.
- ``RATIONRIGHT_LLM_MODEL`` — model name (default ``gpt-4o-mini``).

The prompt is built only from supplied facts (IDs, timestamps, coordinates,
calculated evidence, thresholds, severity). No secrets, keys, or credentials
are ever sent to the model or written to logs.

Import::

    from agents.llm import maybe_generate, generate_narrative, llm_enabled
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("rationright.llm")

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
MAX_NARRATIVE_CHARS = 800
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TOKENS = 300

# Safety net: if the model returns text implying guilt, fall back to the
# deterministic template. RationRight is decision support, never an accuser.
FORBIDDEN_PHRASES = (
    "fraud confirmed",
    "fraudster",
    "guilty beneficiary",
    "fraudulent beneficiary",
    "committed fraud",
    "is guilty",
)

_SYSTEM_PROMPTS = {
    "agent_2_explanation": (
        "You are RationRight's Anomaly Investigator (verification stage). Write a short "
        "human-readable explanation (2-3 sentences) of a VERIFIED anomaly finding. Use ONLY "
        "the facts supplied in the user message: finding ID, anomaly ID and type, transaction "
        "IDs, beneficiary ID, the calculated time difference, the calculated geographic "
        "distance, and the configured thresholds. Never invent facts, IDs, numbers, "
        "locations, or people. Never claim fraud, guilt, or wrongdoing — this is a "
        "'potential anomaly' that was 'verified against the supplied transaction data' and "
        "'requires human verification'. Return only the explanation text."
    ),
    "agent_3_summary": (
        "You are RationRight's Evidence Case Builder. Write a concise case summary (2-3 "
        "sentences) for a human reviewer. Use ONLY the facts supplied in the user message: "
        "case, finding, and anomaly IDs; transaction IDs; beneficiary IDs; the calculated "
        "time difference and geographic distance; severity; and confidence. State that the "
        "values were calculated from the supplied transaction timestamps and coordinates. "
        "Never invent facts or numbers. Never claim fraud or guilt — this is a potential "
        "anomaly that requires human review. Return only the summary text."
    ),
    "agent_4_message": (
        "You are RationRight's Alert Generator. Write a short alert message (1-2 sentences) "
        "for a human reviewer. Use ONLY the facts supplied in the user message: case ID, "
        "severity, the verified evidence values (time difference and geographic distance), "
        "and the recommended action. Never invent facts or numbers. Never claim fraud or "
        "guilt — this is a 'potential anomaly' that 'requires human verification'. Return "
        "only the message text."
    ),
    "scenario_interpretation": (
        "You are RationRight's Decision Support advisor. A deterministic what-if "
        "simulation was computed from the real database. Explain IN YOUR OWN WORDS "
        "(2-4 sentences) what the scenario means for the operator and what they should do. "
        "Use ONLY the values supplied in the user message (baseline and scenario demand, "
        "stock, coverage days, reorder threshold, delay, risk classification) — never "
        "invent numbers, prices, or facts. This is decision support, not a prediction: "
        "frame the outcome as a scenario result, not a guarantee. Return plain text only."
    ),
    "alert_explanation": (
        "You are RationRight's Early Warning advisor. A deterministic monitoring rule "
        "detected a condition in the real database. Write a concise explanation "
        "(2-4 sentences) for an operator: what happened, why it matters, and what they "
        "should consider doing. Use ONLY the facts supplied in the user message: alert "
        "type, entity, commodity, the calculated current value, the configured threshold, "
        "the difference, and the evidence values. Never invent numbers, dates, or facts. "
        "This is decision support, not a prediction: the alert reflects the current "
        "monitored state. Return plain text only."
    ),
    "executive_summary": (
        "You are RationAI's Executive Command Center analyst. Write a concise executive "
        "summary (3-5 sentences) for a government administrator. Use ONLY the structured "
        "facts supplied in the user message: KPI values, active-alert counts by severity, "
        "the top alerts and AI insights (with their entities), district risk highlights, "
        "data quality, and data freshness. Never invent numbers, locations, alerts, or "
        "sources. Never claim live/verified data or certainty. Frame the state as the "
        "current monitored picture, not a prediction. Return plain text only."
    ),
}


def llm_enabled() -> bool:
    """True only when the operator explicitly opted in AND a key is present."""
    return _env_truthy("RATIONRIGHT_LLM_ENABLED") and bool(os.environ.get("OPENAI_API_KEY"))


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes", "on")


def maybe_generate(kind: str, context: dict, fallback: str, generator=None) -> str:
    """Return an LLM narrative when available; otherwise the deterministic fallback.

    ``generator`` is an optional callable (dependency injection for tests and
    callers that want a custom client): ``generator(kind, context, fallback)``
    must return a string. When ``generator`` is None the real API path is used,
    but only when ``llm_enabled()``. Never raises: any failure, unusable
    response, or disabled state returns ``fallback`` unchanged.
    """
    if generator is not None:
        try:
            return _sanitize(generator(kind, context, fallback), fallback)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Narrative generator failed for %s; using deterministic fallback: %s",
                kind,
                exc,
            )
            return fallback
    if not llm_enabled():
        return fallback
    return generate_narrative(kind, context, fallback)


def generate_narrative(kind: str, context: dict, fallback: str,
                       timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Attempt an OpenAI-compatible chat completion for ``kind``; never raise.

    On success returns the sanitized narrative; on any failure returns
    ``fallback``. The key is read from the environment at call time and is
    never logged.
    """
    if not llm_enabled():
        return fallback

    system_prompt = _SYSTEM_PROMPTS.get(kind)
    if system_prompt is None:
        logger.warning("LLM narrative skipped: unknown kind %r", kind)
        return fallback

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("RATIONRIGHT_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = (
        os.environ.get("RATIONRIGHT_LLM_BASE_URL", "").strip().rstrip("/")
        or DEFAULT_BASE_URL
    )
    if not api_key:
        return fallback

    try:
        text = _chat_completion(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_text=_format_context(context),
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "LLM narrative generation failed (%s); using deterministic fallback",
            exc,
        )
        return fallback
    return _sanitize(text, fallback)


def _chat_completion(api_key: str, base_url: str, model: str, system_prompt: str,
                     user_text: str, timeout: float) -> str:
    """POST a chat completion to an OpenAI-compatible endpoint via urllib.

    Raises on any HTTP or transport error; the caller converts failures into
    the deterministic fallback.
    """
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions", data=payload, method="POST"
    )
    request.add_header("Authorization", f"Bearer {api_key}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("completion response contained no choices")
    content = choices[0].get("message", {}).get("content")
    return content


def _format_context(context: dict) -> str:
    """Render the supplied facts as a plain list of key: value lines."""
    lines = []
    for key, value in context.items():
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
        else:
            rendered = str(value)
        lines.append(f"- {key}: {rendered}")
    return "\n".join(lines)


def _sanitize(text, fallback: str) -> str:
    """Return ``text`` only if it is usable and safe; otherwise ``fallback``."""
    if not isinstance(text, str):
        return fallback
    cleaned = " ".join(text.split())
    if not cleaned:
        return fallback
    if len(cleaned) > MAX_NARRATIVE_CHARS:
        logger.warning("LLM narrative exceeded %d chars; using deterministic fallback",
                       MAX_NARRATIVE_CHARS)
        return fallback
    lowered = cleaned.lower()
    if any(phrase in lowered for phrase in FORBIDDEN_PHRASES):
        logger.warning("LLM narrative used forbidden guilt language; using deterministic fallback")
        return fallback
    return cleaned
