"""Goal inference from resume."""

import json
import re
from typing import List, Dict, Any

try:
    from launchpad.utils.openai_helper import call_ollama_json
except ImportError:
    from utils.openai_helper import call_ollama_json


def auto_infer_goals_from_resume(resume_text: str) -> List[Dict[str, Any]]:
    """Auto-infer 5-7 career goals from resume content."""
    
    prompt = f"""System:
You are a career strategy advisor. A user has uploaded their resume 
but not described their career goals. Infer 5–7 likely goals from 
the resume content alone.

Rules:
- Base goals on actual career trajectory shown in the resume.
- Be specific: seniority level, domain, stage, team scope.
- Do NOT project aspirations beyond what the resume supports.
- Output ONLY JSON. No preamble.

Schema:
[{{ "id": string, "label": string, "description": string, "auto_inferred": true }}]

Resume: {resume_text}"""

    try:
        result = call_ollama_json(prompt)
        if isinstance(result, str):
            result = json.loads(result)
        return result if isinstance(result, list) else []
    except Exception as e:
        # Fallback: extract from resume manually
        return _fallback_infer_goals(resume_text)


def _fallback_infer_goals(resume_text: str) -> List[Dict[str, Any]]:
    """Fallback goal inference using regex/heuristics."""
    goals = []
    text_lower = resume_text.lower()
    
    # Detect seniority level
    if "senior" in text_lower or "lead" in text_lower or "manager" in text_lower:
        goals.append({
            "id": "goal_1",
            "label": "Senior/Leadership Role",
            "description": "Progress to senior individual contributor or management role",
            "auto_inferred": True
        })
    elif "intern" in text_lower or "junior" in text_lower or "associate" in text_lower:
        goals.append({
            "id": "goal_1",
            "label": "Mid-level Technical Role",
            "description": "Advance to mid-level individual contributor",
            "auto_inferred": True
        })
    else:
        goals.append({
            "id": "goal_1",
            "label": "Growth-focused Role",
            "description": "Find roles with learning and growth opportunities",
            "auto_inferred": True
        })
    
    # Detect domain
    domains = {
        "ai": "AI/ML",
        "machine learning": "AI/ML",
        "data science": "Data Science",
        "cloud": "Cloud/DevOps",
        "backend": "Backend",
        "frontend": "Frontend",
        "fullstack": "Full Stack",
        "product": "Product",
    }
    
    for keyword, domain in domains.items():
        if keyword in text_lower:
            goals.append({
                "id": f"goal_{len(goals) + 1}",
                "label": f"{domain} Focus",
                "description": f"Continue specializing in {domain}",
                "auto_inferred": True
            })
            break
    
    # Detect company stage preference
    if "startup" in text_lower or "early-stage" in text_lower:
        goals.append({
            "id": f"goal_{len(goals) + 1}",
            "label": "Startup/Early-Stage",
            "description": "Work in dynamic startup or early-stage environments",
            "auto_inferred": True
        })
    elif "enterprise" in text_lower or "fortune" in text_lower or "large" in text_lower:
        goals.append({
            "id": f"goal_{len(goals) + 1}",
            "label": "Enterprise/Scale",
            "description": "Work in large-scale enterprise environments",
            "auto_inferred": True
        })
    
    # Add generic goals if less than 5
    if len(goals) < 5:
        goals.append({
            "id": f"goal_{len(goals) + 1}",
            "label": "Competitive Compensation",
            "description": "Achieve market-competitive salary and benefits",
            "auto_inferred": True
        })
    
    return goals[:7]  # Cap at 7
