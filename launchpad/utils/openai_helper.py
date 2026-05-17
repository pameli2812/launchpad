import os
import re
import json
from collections import Counter
from dotenv import load_dotenv
import requests

load_dotenv()

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")


def call_ollama_json(prompt: str, timeout: int = 120) -> str:
    """Call Ollama and return response string (expects JSON content)."""
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3
            },
            timeout=timeout
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        # Strip markdown fences if model wraps JSON in ```json ... ```
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        return raw
    except requests.exceptions.ConnectionError:
        raise Exception(f"Ollama not running at {OLLAMA_API_URL}. Start it with: ollama serve")
    except Exception as exc:
        raise Exception(f"Ollama error: {str(exc)}")


def call_ollama(prompt: str, timeout: int = 120) -> str:
    """Call Ollama and return plain text response."""
    return call_ollama_json(prompt, timeout)


def _normalize_text(text):
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _extract_keywords(text, limit=20):
    stopwords = {
        "and", "for", "with", "from", "that", "this", "have", "will",
        "should", "their", "these", "those", "about", "your", "yourself",
        "using", "use", "also", "such", "into", "through", "other",
        "within", "between", "under", "more", "than", "which"
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
        "Local fallback analysis (Ollama unavailable):",
        f"Estimated compatibility score: {score}%.",
        "Missing skills: " + (", ".join(missing_skills) if missing_skills else "None found."),
        "ATS suggestions: " + " ".join(suggestions),
        f"Recommendation: {recommendation}",
    ]
    if error:
        analysis.append(f"Fallback reason: {type(error).__name__}: {str(error)}")
    return "\n\n".join(analysis)