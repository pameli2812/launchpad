"""LLM provider chain with prompt caching.

Provider order is configurable via LLM_PROVIDERS env var (default: anthropic,openai,ollama).
First provider that returns valid JSON wins.  Falls through on any error.

Cache contract
--------------
Callers MUST split their prompt into:
  cached_context  — large stable content (resume + JD + goals).  Sent with
                    cache_control=ephemeral so calls 2+ hit the Anthropic cache.
                    Must be byte-identical across calls for cache hits to work.
  task            — volatile per-call instructions and schema.
  system          — must also be byte-identical across calls.

Minimum cacheable prefix on claude-sonnet-4-6 is ~2 048 tokens.  Shorter
prefixes are accepted silently (no error) but cache_read_input_tokens stays 0.

Entry points
------------
  call_llm_json(cached_context, task, system, ...)   preferred
  call_ollama_json(prompt, ...)                       back-compat shim (no caching)
"""

import contextvars
import json
import logging
import os
import re
from collections import Counter

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Per-user API key override ─────────────────────────────────────────────────
# Set by a FastAPI dependency at the start of each authed request (see
# routes/llm_keys_dep.py). Provider functions consult this first, fall back to
# the process-wide env vars when empty. ContextVars are async-safe and isolate
# per-request automatically.

_user_keys_var: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "user_llm_keys", default={}
)


def set_user_keys(keys: dict[str, str]) -> None:
    """Set per-request user API keys. Pass `{}` to clear."""
    _user_keys_var.set(keys or {})


def _user_key(provider: str) -> str | None:
    return _user_keys_var.get().get(provider)

# ── Provider config ───────────────────────────────────────────────────────────

LLM_PROVIDERS = [
    p.strip()
    for p in os.getenv("LLM_PROVIDERS", "anthropic,openai,ollama").split(",")
    if p.strip()
]

ANTHROPIC_MODEL      = os.getenv("ANTHROPIC_MODEL",      "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8192"))
ANTHROPIC_THINKING   = os.getenv("ANTHROPIC_THINKING",   "disabled").lower()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",   "mistral")

_anthropic_client = None
_openai_client    = None

DEFAULT_SYSTEM = (
    "You are a precise career-advisor assistant. "
    "Output ONLY valid JSON matching the schema specified in the user's task. "
    "No markdown fences, no preamble, no trailing prose."
)


# ── Lazy client init ──────────────────────────────────────────────────────────

def _get_anthropic_client():
    """Per-request: if the user has a key set, build a fresh client with it.
    Otherwise reuse the env-key client (cheap — Anthropic() is just an httpx wrapper)."""
    try:
        import anthropic
    except ImportError:
        return None
    user_key = _user_key("anthropic")
    if user_key:
        return anthropic.Anthropic(api_key=user_key)
    global _anthropic_client
    if _anthropic_client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return None
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _get_openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None
    user_key = _user_key("openai")
    if user_key:
        return OpenAI(api_key=user_key)
    global _openai_client
    if _openai_client is None:
        if not os.getenv("OPENAI_API_KEY"):
            return None
        _openai_client = OpenAI()
    return _openai_client


def _ensure_gemini_configured():
    """Returns (genai_module, api_key) to use for THIS call, or None if unconfigured.

    Gemini's SDK has a single global `configure(api_key=...)` call rather than a
    constructor — so when a per-user key is in play we call configure() again
    just before each request. Cheap; no client is held across calls.
    """
    try:
        import google.generativeai as genai  # type: ignore[import-untyped]
    except ImportError:
        return None
    key = _user_key("gemini") or os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai


# ── JSON fence stripper ───────────────────────────────────────────────────────

def _strip_json_fences(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    return raw


# ── Provider implementations ──────────────────────────────────────────────────

def _call_anthropic(cached_context: str, task: str, system: str, timeout: int) -> str:
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("Anthropic not configured (set ANTHROPIC_API_KEY)")

    user_content = []
    # Only add the cache block when there is actually content to cache.
    # An empty cached_context with cache_control wastes tokens on the overhead.
    if cached_context.strip():
        user_content.append({
            "type": "text",
            "text": cached_context,
            "cache_control": {"type": "ephemeral"},
        })
    user_content.append({"type": "text", "text": task})

    kwargs: dict = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    if ANTHROPIC_THINKING == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}

    response = client.with_options(timeout=timeout).messages.create(**kwargs)

    usage = response.usage
    logger.info(
        "anthropic cache: read=%d write=%d fresh=%d out=%d",
        usage.cache_read_input_tokens or 0,
        usage.cache_creation_input_tokens or 0,
        usage.input_tokens,
        usage.output_tokens,
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    return _strip_json_fences(text)


def _call_openai(cached_context: str, task: str, system: str, timeout: int) -> str:
    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI not configured (set OPENAI_API_KEY)")

    user_msg = f"{cached_context}\n\n{task}" if cached_context.strip() else task

    resp = client.with_options(timeout=timeout).chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def _call_ollama(cached_context: str, task: str, system: str, timeout: int) -> str:
    parts = [f"System:\n{system}"]
    if cached_context.strip():
        parts.append(cached_context)
    parts.append(task)

    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": "\n\n".join(parts),
                  "stream": False, "temperature": 0.3},
            timeout=timeout,
        )
        response.raise_for_status()
        return _strip_json_fences(response.json().get("response", ""))
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Ollama not running at {OLLAMA_API_URL}. Start with: ollama serve"
        )


def _call_gemini(cached_context: str, task: str, system: str, timeout: int) -> str:
    genai = _ensure_gemini_configured()
    if genai is None:
        raise RuntimeError("Gemini not configured (set GEMINI_API_KEY)")

    # Gemini doesn't have an explicit cache_control on inline content the way
    # Anthropic does (its caching API uses separate CachedContent objects).
    # For parity with the OpenAI path we just concatenate; we can add explicit
    # cached_content later if/when it pays off for this workload.
    user_message = f"{cached_context}\n\n{task}" if cached_context.strip() else task

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system,
    )
    response = model.generate_content(
        user_message,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.3,
        },
        request_options={"timeout": timeout},
    )
    # response.text raises if blocked; let it bubble — the provider chain catches.
    return _strip_json_fences(response.text or "")


_PROVIDER_DISPATCH = {
    "anthropic": _call_anthropic,
    "openai":    _call_openai,
    "gemini":    _call_gemini,
    "ollama":    _call_ollama,
}


# ── Main entry point ──────────────────────────────────────────────────────────

def call_llm_json(
    cached_context: str,
    task: str,
    system: str = DEFAULT_SYSTEM,
    timeout: int = 120,
) -> str:
    """Try each provider in order; return first valid JSON string.

    Logs the raw response at DEBUG level when JSON parsing fails so you can
    see exactly what the model returned without needing to add print statements.
    """
    last_error: Exception | None = None
    tried: list[str] = []

    for provider in LLM_PROVIDERS:
        fn = _PROVIDER_DISPATCH.get(provider)
        if fn is None:
            continue
        try:
            raw = fn(cached_context, task, system, timeout)
            json.loads(raw)   # validate — raises ValueError if garbage
            if tried:
                logger.info("Provider %r succeeded after %s failed", provider, tried)
            return raw
        except Exception as exc:
            logger.debug("Provider %r raw response before error: %.300s", provider,
                         locals().get("raw", "<no response>"))
            logger.warning("Provider %r failed: %s", provider, exc)
            tried.append(provider)
            last_error = exc

    raise RuntimeError(
        f"All providers {LLM_PROVIDERS!r} failed. Last error: {last_error}"
    )


# ── Back-compat shim ──────────────────────────────────────────────────────────

def call_ollama_json(prompt: str, timeout: int = 120) -> str:
    """Routes through the full provider chain with no caching.

    Prefer call_llm_json(cached_context, task) when the context repeats across
    calls — this puts everything in the volatile slot so nothing is cached.
    """
    return call_llm_json(cached_context="", task=prompt,
                         system=DEFAULT_SYSTEM, timeout=timeout)


def call_ollama(prompt: str, timeout: int = 120) -> str:
    return call_ollama_json(prompt, timeout)


# ── Local fallback ────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _extract_keywords(text: str, limit: int = 20) -> list[str]:
    stopwords = {
        "and","for","with","from","that","this","have","will","should","their",
        "these","those","about","your","yourself","using","use","also","such",
        "into","through","other","within","between","under","more","than","which",
    }
    tokens = [w for w in _normalize_text(text).split()
              if len(w) > 3 and w not in stopwords]
    counts = Counter(tokens)
    return [w for w, _ in counts.most_common(limit)]


def analyze_resume(resume: str, jd: str) -> str:
    prompt = (
        "Analyze this resume against the job description and provide:\n"
        "1. Match summary\n2. Missing skills\n3. ATS suggestions\n"
        "4. Resume improvements\n5. Whether candidate should apply\n\n"
        f"Resume:\n{resume}\n\nJob Description:\n{jd}"
    )
    try:
        return call_ollama(prompt)
    except Exception as exc:
        return _local_analysis(resume, jd, error=exc)


def _local_analysis(resume: str, jd: str, error: Exception | None = None) -> str:
    resume_words = set(_normalize_text(resume).split())
    jd_keywords  = _extract_keywords(jd, limit=30)
    missing      = [kw for kw in jd_keywords if kw not in resume_words][:10]

    notes = []
    if len(resume.strip()) < 200:
        notes.append("Add more detail and achievements to improve keyword coverage.")
    if "experience" not in resume.lower():
        notes.append("Include an Experience section with clear role and achievement details.")
    if not notes:
        notes.append("Add concrete results, metrics, and relevant keywords from the JD.")

    score = round(100 * (1 - len(missing) / max(len(jd_keywords), 1)), 2)
    rec   = ("Strongly recommended to apply." if score > 80
             else "Can apply with improvements." if score > 65
             else "Needs significant updates before applying.")

    lines = [
        "Local fallback analysis (all LLM providers unavailable):",
        f"Estimated compatibility: {score}%.",
        "Missing skills: " + (", ".join(missing) if missing else "None found."),
        "Suggestions: " + " ".join(notes),
        f"Recommendation: {rec}",
    ]
    if error:
        lines.append(f"Fallback reason: {type(error).__name__}: {error}")
    return "\n\n".join(lines)