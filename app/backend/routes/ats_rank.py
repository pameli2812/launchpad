# ATS Rank API Route
# Endpoint: POST /api/ats/analyze

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from auth.deps import get_current_user
from database import get_conn
from launchpad.utils.ats_aggregator import ATSReportGenerator
from launchpad.utils.ats_keywords import ATS_KEYWORDS_BY_ROLE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ats", tags=["ATS Rank"])


class ATSAnalyzeRequest(BaseModel):
    """Request model for ATS analysis"""
    resume_id: str = Field(..., description="Resume file/name to analyze")
    role: str = Field("full_stack_engineer", description="Target job role for keyword matching")
    job_description: Optional[str] = Field(None, description="Optional JD for comparison")


class ATSScoreResponse(BaseModel):
    """ATS analysis response"""
    overall_score: int
    grade: str
    status: str
    summary: str
    breakdown: Dict[str, int]
    critical_issues: list
    recommendations: list
    ats_compatibility: Dict[str, Any]


@router.get("/debug/resumes", summary="[DEBUG] Check resumes for current user")
async def debug_resumes(user: dict = Depends(get_current_user)):
    """Debug endpoint to check what resumes exist for the current user"""
    user_id = str(user["id"])
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT resume_name, user_id FROM resumes WHERE user_id = %s::uuid",
            (user_id,)
        )
        rows = await cur.fetchall()
        return {
            "user_id": user_id,
            "user_email": user.get("email"),
            "resumes": [{"name": r[0], "user_id": str(r[1])} for r in rows],
            "count": len(rows)
        }


@router.get("/roles", summary="Get available job roles")
async def get_available_roles():
    """Return list of available job roles for ATS scoring"""
    roles = [
        {"id": "backend_engineer", "label": "Backend Engineer"},
        {"id": "frontend_engineer", "label": "Frontend Engineer"},
        {"id": "full_stack_engineer", "label": "Full Stack Engineer"},
        {"id": "data_engineer", "label": "Data Engineer"},
        {"id": "devops_engineer", "label": "DevOps Engineer"},
        {"id": "ai_ml_engineer", "label": "AI/ML Engineer"},
        {"id": "product_manager", "label": "Product Manager"},
        {"id": "qa_engineer", "label": "QA Engineer"},
    ]
    return {
        "roles": roles,
        "total": len(roles)
    }


@router.post("/analyze", response_model=ATSScoreResponse, summary="Analyze resume for ATS compatibility")
async def analyze_ats(
    request: ATSAnalyzeRequest,
    user: dict = Depends(get_current_user)
):
    """
    Analyze resume for ATS compatibility.
    
    **Authentication**: JWT Bearer token required
    
    **Parameters**:
    - `resume_id`: Resume file name or ID to analyze
    - `role`: Target job role (default: full_stack_engineer)
    - `job_description`: Optional job description for keyword matching
    
    **Response**: ATS analysis with score breakdown and recommendations
    
    **Example**:
    ```bash
    curl -X POST http://localhost:8000/api/ats/analyze \\
      -H "Authorization: Bearer <token>" \\
      -H "Content-Type: application/json" \\
      -d '{
        "resume_id": "john_doe.pdf",
        "role": "backend_engineer",
        "job_description": "Seeking Python developer..."
      }'
    ```
    """
    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    
    logger.info(f"[ATS] POST /analyze request - User: {user_email} | Resume: {request.resume_id} | Role: {request.role}")
    
    try:
        # Get resume text from database
        async with get_conn() as conn:
            cur = await conn.execute(
                """
                SELECT resume_text FROM resumes
                WHERE resume_name = %s AND user_id = %s::uuid
                """,
                (request.resume_id, user_id)
            )
            row = await cur.fetchone()
            
            if not row:
                logger.warning(f"[ATS] Resume not found - User: {user_email} | Resume: {request.resume_id}")
                raise HTTPException(status_code=404, detail=f"Resume '{request.resume_id}' not found")
            
            resume_text = row[0]
        
        # Parse resume (use existing parser from setup.py)
        # For now, simulate parsed resume structure
        # In production, use the existing extract_resume_data() function
        parsed_resume = _parse_resume_for_ats(resume_text)
        
        # Generate ATS report
        logger.debug(f"[ATS] Generating report - User: {user_email} | Role: {request.role}")
        report = ATSReportGenerator.generate(
            parsed_resume=parsed_resume,
            role=request.role
        )
        
        logger.info(f"[ATS] Analysis complete - User: {user_email} | Score: {report['overall_score']}/100")
        
        # Build response
        return ATSScoreResponse(
            overall_score=report["overall_score"],
            grade=report["grade"],
            status=report["status"],
            summary=report["summary"],
            breakdown=report["breakdown"],
            critical_issues=report["critical_issues"],
            recommendations=report["recommendations"],
            ats_compatibility={
                platform: platform_info["score"]
                for platform, platform_info in report["ats_compatibility"].items()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ATS] Analysis failed - User: {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"ATS analysis failed: {str(e)}")


@router.get("/report/{report_id}", summary="Get detailed ATS report")
async def get_ats_report(
    report_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get detailed ATS report (future: store reports in database).
    
    Currently returns the full analysis from POST /analyze.
    Future enhancement: Persist reports and allow retrieval by ID.
    """
    logger.info(f"[ATS] GET /report/{report_id} - User: {user.get('email', 'unknown')}")
    
    return {
        "message": "Report retrieval feature coming soon",
        "report_id": report_id,
        "note": "Full reports are returned directly from the analyze endpoint"
    }


def _parse_resume_for_ats(resume_text: str) -> Dict[str, Any]:
    """
    Parse resume text into structured format for ATS analysis.
    
    This is a simplified parser. In production, integrate with the existing
    resume parser from setup.py or scorecard.py.
    """
    parsed = {
        "contact_information": {
            "email": _extract_email(resume_text),
            "phone": _extract_phone(resume_text),
            "linkedin": _extract_linkedin(resume_text),
            "github": _extract_github(resume_text),
            "location": _extract_location(resume_text),
            "website": None,
            "portfolio": None
        },
        "summary": _extract_section(resume_text, r"(?i)(summary|professional summary|objective)"),
        "skills": _extract_skills_section(resume_text),
        "experience": _extract_experience(resume_text),
        "education": _extract_education(resume_text),
        "projects": _extract_projects(resume_text),
        "certifications": _extract_certifications(resume_text),
        "name": _extract_name(resume_text),
    }
    return parsed


def _extract_email(text: str) -> str:
    """Extract email address from resume"""
    import re
    match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
    return match.group(1) if match else ""


def _extract_phone(text: str) -> str:
    """Extract phone number from resume"""
    import re
    match = re.search(r'(\+?1?\s?)?(\d{3}[-.\s]?)?\d{3}[-.\s]?\d{4}', text)
    return match.group(0) if match else ""


def _extract_linkedin(text: str) -> str:
    """Extract LinkedIn URL from resume"""
    import re
    match = re.search(r'linkedin\.com/in/[\w-]+', text, re.IGNORECASE)
    return match.group(0) if match else ""


def _extract_github(text: str) -> str:
    """Extract GitHub URL from resume"""
    import re
    match = re.search(r'github\.com/[\w-]+', text, re.IGNORECASE)
    return match.group(0) if match else ""


def _extract_location(text: str) -> str:
    """Extract location from resume (simplified)"""
    lines = text.split('\n')
    if lines:
        # Usually location is in first 3 lines
        for line in lines[:3]:
            if len(line) < 50 and any(word in line.lower() for word in ['city', 'state', 'country']):
                return line.strip()
    return ""


def _extract_name(text: str) -> str:
    """Extract name from resume (first line usually)"""
    lines = text.split('\n')
    if lines:
        first_line = lines[0].strip()
        if len(first_line) < 50 and len(first_line.split()) >= 2:
            return first_line
    return ""


def _extract_section(text: str, pattern: str) -> str:
    """Extract a resume section"""
    import re
    match = re.search(f'{pattern}:?\\s*(.+?)(?=\\n[A-Z]|$)', text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_skills_section(text: str) -> list:
    """Extract skills section"""
    import re
    pattern = r'(?i)(skills?|technical skills?|core competencies):?(.*?)(?=\n[A-Z]|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        skills_text = match.group(2)
        # Split by common delimiters
        skills = re.split(r'[,;•\n]', skills_text)
        skills = [s.strip() for s in skills if s.strip()]
        return [{"skills": skills}]
    
    return []


def _extract_experience(text: str) -> list:
    """Extract experience section"""
    # Simplified extraction
    import re
    
    pattern = r'(?i)(experience|professional experience|work experience):(.*?)(?=\n[A-Z]|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        exp_text = match.group(2)
        # Split by job entries (usually marked by dates or company names)
        jobs = re.split(r'\n(?=[A-Z][a-z]+ \d{4}|[A-Z][a-z]+ at )', exp_text)
        
        experiences = []
        for job in jobs:
            if job.strip():
                bullets = re.split(r'\n•|-', job)
                achievements = [b.strip() for b in bullets if b.strip()]
                experiences.append({
                    "title": achievements[0] if achievements else "",
                    "achievements": achievements[1:] if len(achievements) > 1 else []
                })
        
        return experiences
    
    return []


def _extract_education(text: str) -> list:
    """Extract education section"""
    import re
    
    pattern = r'(?i)(education|academic):(.*?)(?=\n[A-Z]|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        edu_text = match.group(2)
        degrees = re.split(r'\n+', edu_text)
        return [{"school": d.strip()} for d in degrees if d.strip()]
    
    return []


def _extract_projects(text: str) -> list:
    """Extract projects section"""
    import re
    
    pattern = r'(?i)(projects?|portfolio):(.*?)(?=\n[A-Z]|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        projects_text = match.group(2)
        projects = re.split(r'\n-|\n•', projects_text)
        return [{"name": p.strip()} for p in projects if p.strip()]
    
    return []


def _extract_certifications(text: str) -> list:
    """Extract certifications section"""
    import re
    
    pattern = r'(?i)(certification|licenses?|awards?):(.*?)(?=\n[A-Z]|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        certs_text = match.group(2)
        certs = re.split(r'\n-|\n•', certs_text)
        return [{"name": c.strip()} for c in certs if c.strip()]
    
    return []

