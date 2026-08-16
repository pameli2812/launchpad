# Core ATS Analyzer Module
# Orchestrates all ATS scoring and analysis

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from .ats_keywords import (
    ATS_KEYWORDS_BY_ROLE, SKILL_CATEGORIES, STRONG_ACTION_VERBS, WEAK_ACTION_VERBS,
    ATS_PLATFORM_ADJUSTMENTS, ROLE_EXPERIENCE_YEARS
)


class IssueLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AnalysisResult:
    """Standard result format for all analyzers"""
    score: int  # 0-100
    status: str  # Excellent, Good, Fair, Poor
    issues: List[Dict[str, Any]]  # List of issues with level and detail
    recommendations: List[Dict[str, Any]]  # Prioritized recommendations
    details: Dict[str, Any]  # Additional analysis details


class ContactInfoAnalyzer:
    """Analyze contact information completeness"""
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze contact information.
        
        Checks:
        - Email validity
        - Phone number
        - LinkedIn URL
        - GitHub (optional but valuable)
        - Location
        - Portfolio/website
        """
        issues = []
        recommendations = []
        score = 100
        detected = {
            "email": False,
            "phone": False,
            "linkedin": False,
            "github": False,
            "location": False,
            "website": False
        }
        
        # Check email
        contact_info = parsed_resume.get("contact_information", {})
        email = contact_info.get("email", "")
        if email and re.match(r"^[^@]+@[^@]+\.[a-z]{2,}$", email):
            detected["email"] = True
        else:
            issues.append({
                "level": IssueLevel.CRITICAL.value,
                "message": "Valid email not detected",
                "detail": "ATS systems rely on email for contact. Ensure email is clearly visible."
            })
            score -= 15
        
        # Check phone
        phone = contact_info.get("phone", "")
        if phone and re.search(r"\d{7,}", phone):
            detected["phone"] = True
        else:
            issues.append({
                "level": IssueLevel.CRITICAL.value,
                "message": "Phone number not detected",
                "detail": "Include a valid phone number in your contact section."
            })
            score -= 15
        
        # Check LinkedIn
        linkedin = contact_info.get("linkedin", "")
        if linkedin and "linkedin" in linkedin.lower():
            detected["linkedin"] = True
        else:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": "Add LinkedIn profile",
                "detail": "LinkedIn is standard for professional resumes. Include your profile URL."
            })
            score -= 10
        
        # Check GitHub (optional but valued)
        github = contact_info.get("github", "")
        if github and ("github" in github.lower() or "gitlab" in github.lower()):
            detected["github"] = True
        else:
            recommendations.append({
                "level": IssueLevel.MEDIUM.value,
                "message": "GitHub profile not found",
                "detail": "Add your GitHub/GitLab profile to showcase your code."
            })
            score -= 8
        
        # Check location
        location = contact_info.get("location", "")
        if location:
            detected["location"] = True
        else:
            recommendations.append({
                "level": IssueLevel.LOW.value,
                "message": "Location not specified",
                "detail": "Including your location helps recruiters filter candidates."
            })
            score -= 5
        
        # Check portfolio/website
        website = contact_info.get("website") or contact_info.get("portfolio", "")
        if website:
            detected["website"] = True
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={"detected": detected}
        )


class StructureAnalyzer:
    """Analyze resume structure and required sections"""
    
    REQUIRED_SECTIONS = {
        "name": True,
        "email": True,
        "phone": True,
        "linkedin": False,
        "summary": False,
        "skills": True,
        "experience": True,
        "education": True,
        "projects": False,
        "certifications": False,
        "awards": False,
        "publications": False
    }
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any]) -> AnalysisResult:
        """Analyze resume structure completeness"""
        issues = []
        recommendations = []
        score = 100
        sections_found = {}
        
        # Check for required sections
        for section, required in StructureAnalyzer.REQUIRED_SECTIONS.items():
            exists = bool(parsed_resume.get(section) or parsed_resume.get(f"{section}s"))
            sections_found[section] = exists
            
            if required and not exists:
                issues.append({
                    "level": IssueLevel.CRITICAL.value,
                    "message": f"Missing '{section}' section",
                    "detail": f"'{section}' is a critical section that ATS systems expect."
                })
                score -= 12
            elif not required and not exists:
                recommendations.append({
                    "level": IssueLevel.LOW.value,
                    "message": f"Consider adding '{section}' section",
                    "detail": f"Adding {section} can strengthen your resume."
                })
                score -= 3
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={"sections_found": sections_found}
        )


class SkillsAnalyzer:
    """Analyze skills section for diversity and categorization"""
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze skills section.
        
        Checks:
        - Skill count
        - Categorization
        - Diversity
        - Duplicates
        - Relevance
        """
        issues = []
        recommendations = []
        score = 100
        
        skills = parsed_resume.get("skills", [])
        if isinstance(skills, list):
            skill_list = []
            for skill_item in skills:
                if isinstance(skill_item, dict):
                    skill_list.extend(skill_item.get("skills", []))
                elif isinstance(skill_item, str):
                    skill_list.extend(skill_item.split(","))
        else:
            skill_list = []
        
        # Deduplicate and clean
        skill_set = set(s.strip().lower() for s in skill_list if s.strip())
        
        # Check skill count
        if len(skill_set) < 10:
            issues.append({
                "level": IssueLevel.MEDIUM.value,
                "message": f"Low skill count ({len(skill_set)})",
                "detail": "Aim for at least 10-15 relevant skills."
            })
            score -= 15
        elif len(skill_set) > 50:
            recommendations.append({
                "level": IssueLevel.MEDIUM.value,
                "message": f"High skill count ({len(skill_set)})",
                "detail": "Consider consolidating to 15-25 most relevant skills."
            })
            score -= 10
        
        # Categorize skills
        categorized = SkillsAnalyzer._categorize_skills(skill_set)
        categories_count = sum(1 for v in categorized.values() if v)
        
        if categories_count < 3:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": "Limited skill diversity",
                "detail": "Try to cover multiple skill categories (languages, tools, cloud, etc.)"
            })
            score -= 15
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={
                "skill_count": len(skill_set),
                "unique_skills": list(skill_set)[:20],
                "categorized": categorized
            }
        )
    
    @staticmethod
    def _categorize_skills(skills: set) -> Dict[str, List[str]]:
        """Categorize skills into technical categories"""
        categorized = {cat: [] for cat in SKILL_CATEGORIES.keys()}
        
        for skill in skills:
            for category, keywords in SKILL_CATEGORIES.items():
                if any(keyword.lower() in skill for keyword in keywords):
                    categorized[category].append(skill)
                    break
        
        return {k: v for k, v in categorized.items() if v}


class ActionVerbAnalyzer:
    """Analyze action verbs used in experience bullets"""
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any]) -> AnalysisResult:
        """Analyze action verb usage in experience section"""
        issues = []
        recommendations = []
        score = 100
        
        experience = parsed_resume.get("experience", [])
        bullets = []
        
        for job in experience:
            if isinstance(job, dict):
                bullets.extend(job.get("achievements", []) or [])
        
        if not bullets:
            return AnalysisResult(
                score=50,
                status="Fair",
                issues=[{"level": IssueLevel.MEDIUM.value, "message": "No experience bullets found"}],
                recommendations=[],
                details={}
            )
        
        weak_bullet_count = 0
        strong_bullet_count = 0
        
        for bullet in bullets:
            bullet_text = bullet.lower() if isinstance(bullet, str) else str(bullet).lower()
            
            # Check for weak verbs
            if any(verb in bullet_text for verb in WEAK_ACTION_VERBS):
                weak_bullet_count += 1
            # Check for strong verbs
            elif any(verb in bullet_text for verb in [v for verbs in STRONG_ACTION_VERBS.values() for v in verbs]):
                strong_bullet_count += 1
        
        weak_percentage = (weak_bullet_count / len(bullets)) * 100 if bullets else 0
        
        if weak_percentage > 30:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": f"Many weak action verbs ({weak_percentage:.0f}%)",
                "detail": f"Replace weak verbs like 'worked' with strong verbs like 'designed', 'optimized', 'led'."
            })
            score -= 20
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={
                "total_bullets": len(bullets),
                "strong_bullets": strong_bullet_count,
                "weak_bullets": weak_bullet_count,
                "weak_percentage": weak_percentage
            }
        )


class KeywordAnalyzer:
    """Analyze keyword coverage for selected role"""
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any], role: str = "full_stack_engineer") -> AnalysisResult:
        """
        Analyze keyword coverage against role-specific keywords.
        
        Args:
            parsed_resume: Extracted resume data
            role: Target job role (default: full_stack_engineer)
        """
        issues = []
        recommendations = []
        score = 100
        
        # Get role keywords
        role_key = role.lower().replace(" ", "_")
        keywords_config = ATS_KEYWORDS_BY_ROLE.get(role_key, ATS_KEYWORDS_BY_ROLE["full_stack_engineer"])
        
        # Extract all text from resume
        resume_text = ActionVerbAnalyzer._extract_all_text(parsed_resume).lower()
        
        # Check required keywords
        required_found = []
        required_missing = []
        
        for keyword in keywords_config["required"]:
            if keyword.lower() in resume_text:
                required_found.append(keyword)
            else:
                required_missing.append(keyword)
        
        # Check preferred keywords
        preferred_found = []
        for keyword in keywords_config["preferred"]:
            if keyword.lower() in resume_text:
                preferred_found.append(keyword)
        
        # Check AI keywords
        ai_found = []
        for keyword in keywords_config["ai_keywords"]:
            if keyword.lower() in resume_text:
                ai_found.append(keyword)
        
        # Calculate coverage
        required_coverage = (len(required_found) / len(keywords_config["required"]) * 100) if keywords_config["required"] else 100
        preferred_coverage = (len(preferred_found) / len(keywords_config["preferred"]) * 100) if keywords_config["preferred"] else 100
        ai_coverage = (len(ai_found) / len(keywords_config["ai_keywords"]) * 100) if keywords_config["ai_keywords"] else 50
        
        # Score based on coverage
        if required_coverage < 50:
            issues.append({
                "level": IssueLevel.CRITICAL.value,
                "message": f"Low required keyword coverage ({required_coverage:.0f}%)",
                "detail": f"Missing: {', '.join(required_missing[:3])}"
            })
            score -= 30
        elif required_coverage < 75:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": f"Add missing required keywords",
                "detail": f"Missing: {', '.join(required_missing[:3])}"
            })
            score -= 15
        
        if ai_coverage < 20:
            recommendations.append({
                "level": IssueLevel.MEDIUM.value,
                "message": "Limited AI/modern tech keywords",
                "detail": "Consider adding AI, LLM, or cloud keywords to stay current."
            })
            score -= 10
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={
                "role": role,
                "required_coverage": required_coverage,
                "preferred_coverage": preferred_coverage,
                "ai_coverage": ai_coverage,
                "required_found": required_found,
                "required_missing": required_missing,
                "preferred_found": preferred_found[:10],
                "ai_found": ai_found
            }
        )
    
    @staticmethod
    def _extract_all_text(parsed_resume: Dict[str, Any]) -> str:
        """Extract all text from parsed resume"""
        text_parts = []
        
        for key, value in parsed_resume.items():
            if isinstance(value, str):
                text_parts.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict):
                        text_parts.extend(ActionVerbAnalyzer._extract_all_text(item).split())
        
        return " ".join(text_parts)


class ExperienceQualityAnalyzer:
    """Analyze quality of experience bullets (quantification, impact, STAR method)"""
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze experience quality.
        
        Checks:
        - Quantified achievements (metrics, percentages, numbers)
        - Impact statements
        - STAR method (Situation, Task, Action, Result)
        - Leadership indicators
        """
        issues = []
        recommendations = []
        score = 100
        
        experience = parsed_resume.get("experience", [])
        bullets = []
        
        for job in experience:
            if isinstance(job, dict):
                bullets.extend(job.get("achievements", []) or [])
        
        if not bullets:
            return AnalysisResult(
                score=50,
                status="Fair",
                issues=[{"level": IssueLevel.MEDIUM.value, "message": "No experience bullets found"}],
                recommendations=[],
                details={}
            )
        
        quantified_count = 0
        impact_count = 0
        
        for bullet in bullets:
            bullet_text = str(bullet).lower()
            
            # Check for quantification (numbers, %, dollars)
            if re.search(r'\d+%|\$\d+|(\d+)x|\d+\s*(hours?|days?|months?|years?|projects?|users?|servers?|requests?)', bullet_text):
                quantified_count += 1
            
            # Check for impact keywords
            if any(word in bullet_text for word in ["impact", "result", "achieved", "improved", "reduced", "increased", "gained"]):
                impact_count += 1
        
        quantified_percentage = (quantified_count / len(bullets)) * 100 if bullets else 0
        impact_percentage = (impact_count / len(bullets)) * 100 if bullets else 0
        
        # Scoring
        if quantified_percentage < 40:
            recommendations.append({
                "level": IssueLevel.CRITICAL.value,
                "message": f"Only {quantified_percentage:.0f}% of bullets have quantified metrics",
                "detail": "Add numbers, percentages, and impact metrics to experience bullets (e.g., '30% faster', '50+ users')."
            })
            score -= 25
        elif quantified_percentage < 60:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": "Increase quantified achievements",
                "detail": "Aim for at least 60% of bullets to have measurable metrics."
            })
            score -= 15
        
        if impact_percentage < 50:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": "Emphasize business impact",
                "detail": "Use phrases like 'achieved', 'improved', 'reduced' to highlight results."
            })
            score -= 10
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={
                "total_bullets": len(bullets),
                "quantified_count": quantified_count,
                "quantified_percentage": quantified_percentage,
                "impact_count": impact_count,
                "impact_percentage": impact_percentage
            }
        )


class AIReadinessAnalyzer:
    """Analyze AI/modern tech readiness of resume"""
    
    AI_KEYWORDS = [
        "ai", "machine learning", "deep learning", "llm", "large language model",
        "openai", "claude", "gpt", "gemini", "hugging face",
        "rag", "retrieval augmented generation", "embedding", "vector",
        "prompt engineering", "fine-tuning", "rlhf",
        "multimodal", "transformer", "attention mechanism",
        "agent", "agentic", "autonomous",
        "mlops", "model training", "inference",
        "gpu", "cuda", "tensorflow", "pytorch", "keras"
    ]
    
    MODERN_TECH_KEYWORDS = [
        "kubernetes", "docker", "microservices", "serverless",
        "cloud", "aws", "gcp", "azure",
        "ci/cd", "github", "gitlab",
        "rest api", "graphql", "grpc",
        "nosql", "mongodb", "redis", "elasticsearch"
    ]
    
    @staticmethod
    def analyze(parsed_resume: Dict[str, Any]) -> AnalysisResult:
        """Analyze AI and modern tech presence in resume"""
        issues = []
        recommendations = []
        score = 80  # Base score for presence in AI field
        
        resume_text = KeywordAnalyzer._extract_all_text(parsed_resume).lower()
        
        # Check for AI keywords
        ai_found = []
        for keyword in AIReadinessAnalyzer.AI_KEYWORDS:
            if keyword.lower() in resume_text:
                ai_found.append(keyword)
        
        # Check for modern tech
        modern_tech_found = []
        for keyword in AIReadinessAnalyzer.MODERN_TECH_KEYWORDS:
            if keyword.lower() in resume_text:
                modern_tech_found.append(keyword)
        
        # Score based on coverage
        if len(ai_found) == 0:
            recommendations.append({
                "level": IssueLevel.MEDIUM.value,
                "message": "No AI/ML keywords detected",
                "detail": "Consider adding AI/ML experience or mentioning AI tools you've used."
            })
            score -= 20
        elif len(ai_found) < 3:
            recommendations.append({
                "level": IssueLevel.LOW.value,
                "message": "Limited AI presence",
                "detail": "Adding more AI/ML keywords can help with modern job searches."
            })
            score -= 10
        
        if len(modern_tech_found) < 5:
            recommendations.append({
                "level": IssueLevel.HIGH.value,
                "message": "Limited modern tech presence",
                "detail": "Add cloud platforms, containers, CI/CD, or API experience."
            })
            score -= 15
        
        score = max(0, min(100, score))
        
        return AnalysisResult(
            score=score,
            status="Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor",
            issues=issues,
            recommendations=recommendations,
            details={
                "ai_keywords_found": ai_found[:10],
                "ai_keywords_count": len(ai_found),
                "modern_tech_found": modern_tech_found[:10],
                "modern_tech_count": len(modern_tech_found)
            }
        )


# Continue in next file for more analyzers...
