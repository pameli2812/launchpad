"""Goal inference from resume.

Minimisation strategy
---------------------
The LLM call is cached by resume content_hash in the DB.
If the same resume (same hash) has been inferred before, the stored goals are
returned instantly — 0 LLM calls, 0 API cost.

The hash is the same sha256[:12] stored in the resumes table at upload time,
so no extra DB column is needed.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from launchpad.utils.openai_helper import call_llm_json
except ImportError:
    from utils.openai_helper import call_llm_json

# GOAL_INFERENCE_SYSTEM = (
#     "You are a brutally honest career advisor. "
#     "Output ONLY valid JSON matching the schema specified. "
#     "No markdown fences, no preamble, no trailing prose."
# )
GOAL_INFERENCE_SYSTEM = (
    "You define generic, quantifiable job-evaluation metrics — reusable yardsticks "
    "for scoring any job posting 1-10. Metrics are evaluation criteria (seniority, pay, "
    "company size, domain fit), NEVER achievements copied from the resume. "
    "Output ONLY valid JSON matching the schema. No markdown, no preamble."
)
# _TASK = """\
# TASK: Extract 5-7 specific, scoreable career dimensions from this resume.

# Rules:
# - Each dimension must be independently measurable against a job description.
# - Labels: concise 2-4 word noun phrases (e.g. "Seniority Match", "AI/GenAI Depth").
# - description: one sentence citing specific resume evidence for this axis.
# - confidence: "high" (2+ data points) | "medium" (1 data point) | "low" (inferred).
# - No generic aspirations. No duplicate axes. Max 7. Order by relevance.

# Output JSON array (no wrapper):
# [{"id":str,"label":str,"description":str,"confidence":"high"|"medium"|"low","auto_inferred":true}]"""
_TASK = """\
TASK: Produce 6-8 GENERIC, quantifiable evaluation metrics for judging whether ANY job description is worth applying to. These metrics are job-agnostic yardsticks, NOT achievements from the resume.

Each metric is scored 1-10 when a job description is later evaluated against it.

Rules:
- Metrics must be evaluation CRITERIA, not resume accomplishments. 
  CORRECT: "Seniority Match", "Pay Scale", "Company Size", "Domain Relevance", "Work-Life Balance", "Growth Potential", "Location Fit", "Tech/Domain Overlap".
  WRONG: "Card Marketing Analytics", "Model Architecture", "Business Development" (these are resume points, never use them).
- The "description" explains WHAT THE METRIC MEASURES and HOW TO SCORE IT 1-10 for a job posting. It must NOT reference specific resume achievements.
  Example description for "Seniority Match": "How closely the role's seniority matches a Director-level target. Score 10 for Director/Head roles, 5 for Senior Manager, 1 for junior IC roles."
  Example for "Company Size": "Preference for established mid-to-large firms. Score 10 for MNCs/large enterprises, 5 for mid-size, 1 for early-stage startups."
- Use the candidate's background ONLY to calibrate the target (e.g. their seniority level, their domains), never to name a metric after a specific project.
- Incorporate the user's stated preferences into scoring guidance where relevant.
- confidence: "high" if the metric is clearly important given the profile, else "medium".

Output JSON array (no wrapper):
[{"id":str,"label":str,"description":str,"confidence":"high"|"medium"|"low","auto_inferred":true}]"""
# In-process cache: content_hash → goals list
# Survives for the lifetime of the uvicorn worker process.
_inference_cache: Dict[str, List[Dict[str, Any]]] = {}


def auto_infer_goals_from_resume(
    resume_text: str,
    content_hash: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Infer 5-7 scoreable dimensions from resume content.

    Pass content_hash (sha256[:12] from the resumes DB row) to enable the
    in-process cache — repeated clicks on "Generate Goals" for the same resume
    return instantly without calling the LLM again.
    """
    # Check in-process cache first
    if content_hash and content_hash in _inference_cache:
        logger.info("goal_inference: cache hit for hash %s", content_hash)
        return _inference_cache[content_hash]

    try:
        raw = call_llm_json(
            cached_context=resume_text,
            task=_TASK,
            system=GOAL_INFERENCE_SYSTEM,
        )
        result = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(result, list):
            raise ValueError(f"Expected list, got {type(result)}")

        goals = []
        seen: set = set()
        for item in result:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("id") or "").strip() or f"goal_{uuid.uuid4().hex[:6]}"
            while gid in seen:
                gid = f"{gid}_2"
            seen.add(gid)
            goals.append({
                "id": gid,
                "label": str(item.get("label") or gid).strip(),
                "description": str(item.get("description") or "").strip(),
                "confidence": _norm_confidence(item.get("confidence")),
                "auto_inferred": True,
            })

        if not goals:
            raise ValueError("LLM returned empty list")

        goals = goals[:7]

        # Store in cache
        if content_hash:
            _inference_cache[content_hash] = goals
            logger.info("goal_inference: cached result for hash %s", content_hash)

        return goals

    except Exception as exc:
        logger.warning("goal_inference LLM failed: %s — using heuristics", exc)
        result = _fallback_infer_goals(resume_text)
        if content_hash:
            _inference_cache[content_hash] = result
        return result


def _norm_confidence(value: Any) -> str:
    if not value:
        return "medium"
    v = str(value).strip().lower()
    return v if v in ("high", "medium", "low") else "medium"


# ── Heuristic fallback ────────────────────────────────────────────────────────

# def _fallback_infer_goals(resume_text: str) -> List[Dict[str, Any]]:
#     text_lower = resume_text.lower()
#     goals: List[Dict[str, Any]] = []

#     def add(gid, label, desc, conf="medium"):
#         goals.append({"id": gid, "label": label, "description": desc,
#                       "confidence": conf, "auto_inferred": True})

#     if any(w in text_lower for w in ("vp ", "vice president", "director", "head of", "principal")):
#         add("seniority_match", "Seniority Match", "Resume shows VP/Director-level titles.", "high")
#     elif any(w in text_lower for w in ("senior", "lead", "staff", "manager")):
#         add("seniority_match", "Seniority Match", "Resume shows senior IC or manager titles.", "high")
#     else:
#         add("seniority_match", "Seniority Match", "Seniority inferred from years of experience.", "medium")

#     domain_map = [
#         (["product manager", "product management", " pm ", "roadmap", "prd"],
#          "Product Management Depth", "Evidence of PM ownership: roadmaps, PRDs, launches."),
#         (["machine learning", "deep learning", "llm", "generative ai", "genai", "agentic"],
#          "AI/GenAI Depth", "Resume cites LLM, agentic AI, or ML work."),
#         (["data science", "analytics", "sql", "python", "jupyter"],
#          "Data & Analytics Depth", "Resume demonstrates data analysis expertise."),
#         (["backend", "api", "microservice", "distributed", "scala", "java", "golang"],
#          "Backend Engineering Depth", "Resume shows backend/systems engineering experience."),
#         (["frontend", "react", "vue", "angular", "typescript", "ux"],
#          "Frontend / UX Depth", "Resume demonstrates frontend or design-system ownership."),
#         (["devops", "kubernetes", "terraform", "ci/cd", "cloud", "aws", "gcp", "azure"],
#          "Cloud & Infrastructure", "Resume shows cloud/DevOps platform experience."),
#         (["growth", "a/b test", "experiment", "funnel", "retention"],
#          "Growth & Experimentation", "Resume shows growth-loop or A/B testing work."),
#     ]
#     for keywords, label, desc in domain_map:
#         if any(kw in text_lower for kw in keywords):
#             slug = label.lower().replace(" ", "_").replace("/", "_").replace("&", "and")[:30]
#             add(slug, label, desc, "high")
#             break

#     if any(w in text_lower for w in ("managed", "led a team", "team of", "direct report", "hired")):
#         add("team_leadership", "Team Leadership", "Resume shows direct people-management.", "high")
#     if any(w in text_lower for w in ("b2b", "enterprise sales", "saas")):
#         add("b2b_saas_exp", "B2B SaaS Experience", "Resume contains B2B or enterprise SaaS context.", "high")
#     elif any(w in text_lower for w in ("b2c", "consumer", "marketplace")):
#         add("b2c_exp", "B2C / Consumer Experience", "Resume shows B2C product experience.", "high")
#     if any(w in text_lower for w in ("launched", "built from scratch", "greenfield", "founding")):
#         add("zero_to_one", "0→1 Product Experience", "Resume references a greenfield launch.", "medium")
#     if any(w in text_lower for w in ("revenue", "arr", "mrr", "nps", "churn", "%", "million")):
#         add("growth_metrics", "Growth Metrics & Analytics", "Resume quantifies business impact.", "medium")

#     fillers = [
#         ("cross_func_collab", "Cross-functional Collaboration",
#          "Inferred from multi-team coordination language.", "low"),
#         ("communication_skills", "Communication & Storytelling",
#          "Inferred from writing/presenting mentions.", "low"),
#         ("technical_foundation", "Technical Foundation",
#          "General technical literacy inferred from tools.", "low"),
#     ]
#     for fid, flabel, fdesc, fconf in fillers:
#         if len(goals) >= 5:
#             break
#         add(fid, flabel, fdesc, fconf)

#     return goals[:7]

def _fallback_infer_goals(resume_text: str) -> List[Dict[str, Any]]:
    return [
        {"id": "seniority_match", "label": "Seniority Match",
         "description": "How well the role's seniority matches the target level. 10 = Director/Head, 5 = Senior Manager, 1 = junior.",
         "confidence": "high", "auto_inferred": True},
        {"id": "pay_scale", "label": "Pay Scale",
         "description": "Expected compensation vs target. 10 = clearly above market, 5 = at market, 1 = below.",
         "confidence": "medium", "auto_inferred": True},
        {"id": "company_size", "label": "Company Size",
         "description": "Preference for established firms. 10 = MNC/large, 5 = mid-size, 1 = early startup.",
         "confidence": "high", "auto_inferred": True},
        {"id": "domain_relevance", "label": "Domain Relevance",
         "description": "Overlap with existing domain experience. 10 = exact domain, 5 = adjacent, 1 = unrelated.",
         "confidence": "high", "auto_inferred": True},
        {"id": "role_fit", "label": "Role Fit",
         "description": "Match between JD responsibilities and core skills. 10 = strong match, 1 = weak.",
         "confidence": "high", "auto_inferred": True},
        {"id": "growth_potential", "label": "Growth Potential",
         "description": "Career progression the role offers. 10 = clear step up, 5 = lateral, 1 = step back.",
         "confidence": "medium", "auto_inferred": True},
        {"id": "location_fit", "label": "Location / Work Mode Fit",
         "description": "Match to location and remote/hybrid preference. 10 = ideal, 1 = poor.",
         "confidence": "medium", "auto_inferred": True},
    ]