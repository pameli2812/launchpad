"""LLM provider chain with prompt caching.

Order is configurable via LLM_PROVIDERS (default: anthropic,openai,ollama).
Each provider is tried in order; the first one that returns parseable JSON wins.

For cache hits to work, callers MUST split their prompt into:
  - cached_context: large stable content (resume + JD + goals), placed first
                    with cache_control so subsequent calls reuse it.
  - task:           volatile task-specific instructions and schema, placed last.
The `system` prompt also has to be byte-identical across calls — anything in
the prefix invalidates everything after it.

Two entry points:
  - call_llm_json(cached_context, task, system, ...) — preferred, gets cache hits
  - call_ollama_json(prompt, ...)                    — back-compat shim, no caching
"""

import json
import logging
import os
import re
from collections import Counter

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Provider chain — comma-separated, tried in order. Override with LLM_PROVIDERS.
LLM_PROVIDERS = [
    p.strip()
    for p in os.getenv("LLM_PROVIDERS", "anthropic,openai,ollama").split(",")
    if p.strip()
]

# Anthropic config
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8192"))
# Enable adaptive thinking by setting ANTHROPIC_THINKING=adaptive
ANTHROPIC_THINKING = os.getenv("ANTHROPIC_THINKING", "disabled").lower()

# OpenAI config
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Ollama config
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Lazy-initialized clients
_anthropic_client = None
_openai_client = None

DEFAULT_SYSTEM = (
    "You are a precise career-advisor assistant. "
    "Output ONLY valid JSON matching the schema specified in the user's task. "
    "No markdown fences, no preamble, no trailing prose."
)


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
        except ImportError:
            return None
        if not os.getenv("ANTHROPIC_API_KEY"):
            return None
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
        except ImportError:
            return None
        if not os.getenv("OPENAI_API_KEY"):
            return None
        _openai_client = OpenAI()
    return _openai_client


def _strip_json_fences(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    return raw


def _call_anthropic(cached_context: str, task: str, system: str, timeout: int) -> str:
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("Anthropic not configured (set ANTHROPIC_API_KEY)")

    user_content = []
    if cached_context:
        # Place the stable content first with cache_control so calls 2+ hit the cache.
        # Minimum cacheable prefix on Sonnet 4.6 is ~2048 tokens — under that, caching
        # silently no-ops (no error, cache_read_input_tokens stays 0).
        user_content.append(
            {
                "type": "text",
                "text": cached_context,
                "cache_control": {"type": "ephemeral"},
            }
        )
    user_content.append({"type": "text", "text": task})

    kwargs = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    if ANTHROPIC_THINKING == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}

    response = client.with_options(timeout=timeout).messages.create(**kwargs)

    usage = response.usage
    if usage.cache_read_input_tokens or usage.cache_creation_input_tokens:
        logger.info(
            "anthropic[%s] cache: read=%d write=%d fresh=%d output=%d",
            ANTHROPIC_MODEL,
            usage.cache_read_input_tokens,
            usage.cache_creation_input_tokens,
            usage.input_tokens,
            usage.output_tokens,
        )

    # With adaptive thinking, response.content has ThinkingBlock(s) before TextBlock.
    text = next((b.text for b in response.content if b.type == "text"), "")
    return _strip_json_fences(text)


def _call_openai(cached_context: str, task: str, system: str, timeout: int) -> str:
    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI not configured (set OPENAI_API_KEY)")

    user_message = (cached_context + "\n\n" + task) if cached_context else task

    resp = client.with_options(timeout=timeout).chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def _call_ollama(cached_context: str, task: str, system: str, timeout: int) -> str:
    # Ollama's /api/generate uses a single prompt string, so caching doesn't apply here.
    prompt_parts = [f"System:\n{system}"]
    if cached_context:
        prompt_parts.append(cached_context)
    prompt_parts.append(task)
    prompt = "\n\n".join(prompt_parts)

    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        return _strip_json_fences(raw)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Ollama not running at {OLLAMA_API_URL}. Start it with: ollama serve"
        )


_PROVIDER_DISPATCH = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "ollama": _call_ollama,
}


def call_llm_json(
    cached_context: str,
    task: str,
    system: str = DEFAULT_SYSTEM,
    timeout: int = 120,
) -> str:
    """Call the provider chain and return a JSON string (caller json.loads's it).

    The function validates that the response is parseable JSON before returning —
    if a provider returns garbage, it falls through to the next one. This is the
    "Anthropic stops giving good responses → fall back to OpenAI → fall back to
    Ollama" behavior the user asked for.

    Args:
        cached_context: Large stable content (resume + JD + goals). Placed in a
            user-message block with cache_control. To get cache hits across
            multiple calls, this string must be byte-identical between calls.
        task: Volatile task-specific instructions and schema.
        system: System prompt. Must also be stable across calls for cache hits.
        timeout: Per-provider request timeout in seconds.
    """
    last_error = None
    tried = []
    for provider in LLM_PROVIDERS:
        fn = _PROVIDER_DISPATCH.get(provider)
        if fn is None:
            continue
        try:
            raw = fn(cached_context, task, system, timeout)
            # Validate JSON before returning — garbage responses fall through.
            json.loads(raw)
            if tried:
                logger.info("LLM provider %r succeeded after %s failed", provider, tried)
            return raw
        except Exception as e:
            tried.append(provider)
            logger.warning("LLM provider %r failed: %s", provider, e)
            last_error = e
            continue
    raise RuntimeError(
        f"All LLM providers in chain {LLM_PROVIDERS!r} failed. Last error: {last_error}"
    )


def call_ollama_json(prompt: str, timeout: int = 120) -> str:
    """Back-compat shim — routes through the full provider chain.

    Prefer call_llm_json(cached_context, task, ...) when you have content that
    repeats across multiple calls (resume + JD + goals); this entry point puts
    everything in the volatile slot so nothing gets cached.
    """
    return call_llm_json(
        cached_context="",
        task=prompt,
        system=DEFAULT_SYSTEM,
        timeout=timeout,
    )


def call_ollama(prompt: str, timeout: int = 120) -> str:
    return call_ollama_json(prompt, timeout)


# ─────────────────────────────────────────────
# Local fallback (no LLM) — used by analyze_resume() as a last resort
# ─────────────────────────────────────────────

def _normalize_text(text):
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _extract_keywords(text, limit=20):
    stopwords = {
        "and", "for", "with", "from", "that", "this", "have", "will",
        "should", "their", "these", "those", "about", "your", "yourself",
        "using", "use", "also", "such", "into", "through", "other",
        "within", "between", "under", "more", "than", "which",
    }
    tokens = [w for w in _normalize_text(text).split() if len(w) > 3 and w not in stopwords]
    counts = Counter(tokens)
    return [word for word, _ in counts.most_common(limit)]


def analyze_resume(resume, jd):
    prompt = f"""Analyze this resume against the job description and provide:
1. Match summary
2. Missing skills
3. ATS suggestions
4. Resume improvements
5. Whether candidate should apply

Resume:
{resume}

Job Description:
{jd}"""
    try:
        return call_ollama(prompt)
    except Exception as exc:
        return _local_analysis(resume, jd, error=exc)


def _local_analysis(resume, jd, error=None):
    resume_words = set(_normalize_text(resume).split())
    jd_keywords = _extract_keywords(jd, limit=30)
    missing_skills = [kw for kw in jd_keywords if kw not in resume_words][:10]

    suggestions = []
    if len(resume.strip()) < 200:
        suggestions.append("Add more resume detail and achievements to improve keyword coverage.")
    if "experience" not in resume.lower():
        suggestions.append("Include an 'Experience' section with clear role and achievement details.")
    if not suggestions:
        suggestions.append("Focus on adding concrete results, metrics, and relevant keywords from the job description.")

    score = round(100 * (1 - len(missing_skills) / max(len(jd_keywords), 1)), 2)
    recommendation = (
        "Strongly recommended to apply." if score > 80
        else ("Can apply with improvements." if score > 65
              else "Needs significant resume updates before applying.")
    )

    analysis = [
        "Local fallback analysis (all LLM providers unavailable):",
        f"Estimated compatibility score: {score}%.",
        "Missing skills: " + (", ".join(missing_skills) if missing_skills else "None found."),
        "ATS suggestions: " + " ".join(suggestions),
        f"Recommendation: {recommendation}",
    ]
    if error:
        analysis.append(f"Fallback reason: {type(error).__name__}: {str(error)}")
    return "\n\n".join(analysis)
