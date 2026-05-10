import os
import re
import requests
import json
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")


def call_ollama_json(prompt: str, timeout: int = 120) -> str:
    """Call Ollama API and return JSON response."""
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.5
            },
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.ConnectionError:
        raise Exception("Ollama not running on " + OLLAMA_API_URL)
    except Exception as exc:
        raise Exception(f"Ollama error: {str(exc)}")


def call_ollama(prompt: str, timeout: int = 120) -> str:
    """Call Ollama API and return text response."""
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


def _local_analysis(resume, jd, error=None):
    resume_words = set(_normalize_text(resume).split())
    jd_keywords = _extract_keywords(jd, limit=30)
    missing_skills = [kw for kw in jd_keywords if kw not in resume_words]

    if len(missing_skills) > 10:
        missing_skills = missing_skills[:10]

    suggestions = []
    if len(resume.strip()) < 200:
        suggestions.append("Add more resume detail and achievements to improve keyword coverage.")
    if "experience" not in resume.lower():
        suggestions.append("Include an 'Experience' section with clear role and achievement details.")
    if "education" not in resume.lower() and "degree" not in resume.lower():
        suggestions.append("Include your education, certifications, and training details.")
    if not suggestions:
        suggestions.append("Focus on adding concrete results, metrics, and relevant keywords from the job description.")

    score = round(100 * (1 - len(missing_skills) / max(len(jd_keywords), 1)), 2)
    recommendation = "Strongly recommended to apply." if score > 80 else (
        "Can apply with improvements." if score > 65 else "Needs significant resume updates before applying."
    )

    analysis = [
        "Local fallback analysis (Ollama unavailable):",
        f"Estimated compatibility score: {score}%.",
        "Match summary: Basic keyword coverage is checked from the job description.",
    ]

    if missing_skills:
        analysis.append("Missing skills: " + ", ".join(missing_skills))
    else:
        analysis.append("No obvious missing keywords from the job description were found.")

    analysis.append("ATS suggestions: " + " ".join(suggestions))
    analysis.append("Resume improvements: Add relevant keywords, quantifiable achievements, and a clear experience section.")
    analysis.append(f"Recommendation: {recommendation}")

    if error:
        analysis.append(f"Fallback reason: {type(error).__name__}: {str(error)}")

    return "\n\n".join(analysis)


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
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "No response from Ollama")
    except requests.exceptions.ConnectionError:
        return _local_analysis(resume, jd, error="Ollama not running on " + OLLAMA_API_URL)
    except Exception as exc:
        return _local_analysis(resume, jd, error=exc)


def generate_improved_resume(resume, jd, analysis):
    prompt = f"""Based on the following resume, job description, and analysis, create an improved version of the resume that addresses the feedback and better matches the job requirements.

Original Resume:
{resume}

Job Description:
{jd}

Analysis Feedback:
{analysis}

Please provide an improved resume that:
1. Incorporates relevant keywords from the job description
2. Addresses the missing skills and suggestions
3. Maintains professional formatting
4. Highlights relevant experience and achievements
5. Is ATS-friendly

Return only the improved resume content, no additional explanations."""

    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7
            },
            timeout=90
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "Failed to generate improved resume")
    except Exception as exc:
        return _generate_local_improved_resume(resume, jd, analysis)


def _generate_local_improved_resume(resume, jd, analysis):
    """Fallback function to generate improved resume using local logic"""
    jd_keywords = _extract_keywords(jd, limit=15)

    # Extract sections from original resume
    sections = {}
    current_section = "General"
    lines = resume.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if it's a section header
        if len(line) < 50 and (line.isupper() or ':' in line):
            current_section = line.replace(':', '').strip()
            sections[current_section] = []
        else:
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append(line)

    # Build improved resume
    improved_resume = []

    # Add professional summary if missing
    if "SUMMARY" not in sections and "PROFESSIONAL SUMMARY" not in sections:
        improved_resume.append("PROFESSIONAL SUMMARY")
        improved_resume.append("Experienced professional with expertise in " + ", ".join(jd_keywords[:5]) + ".")
        improved_resume.append("")

    # Add experience section with keywords
    if "EXPERIENCE" in sections:
        improved_resume.append("EXPERIENCE")
        for exp in sections["EXPERIENCE"]:
            # Try to incorporate keywords naturally
            improved_exp = exp
            for keyword in jd_keywords[:3]:
                if keyword.lower() not in exp.lower():
                    improved_exp += f" - {keyword.title()}"
                    break
            improved_resume.append(improved_exp)
        improved_resume.append("")

    # Add skills section with job keywords
    improved_resume.append("SKILLS")
    skills_list = jd_keywords[:10]
    improved_resume.append(", ".join(skills_list))
    improved_resume.append("")

    # Add other sections
    for section, content in sections.items():
        if section not in ["EXPERIENCE", "SKILLS", "SUMMARY", "PROFESSIONAL SUMMARY"]:
            improved_resume.append(section.upper())
            improved_resume.extend(content)
            improved_resume.append("")

    return "\n".join(improved_resume)
