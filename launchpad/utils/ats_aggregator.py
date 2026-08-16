# ATS Score Aggregator and Report Generator

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import asdict

from .ats_analyzer import (
    ContactInfoAnalyzer, StructureAnalyzer, SkillsAnalyzer, ActionVerbAnalyzer,
    KeywordAnalyzer, ExperienceQualityAnalyzer, AIReadinessAnalyzer,
    AnalysisResult, IssueLevel
)
from .ats_keywords import ATS_PLATFORM_ADJUSTMENTS


class ScoreAggregator:
    """Aggregate individual analyzer scores into overall ATS score"""
    
    # Scoring weights (must sum to 100)
    WEIGHTS = {
        "parsing": 0.20,
        "structure": 0.15,
        "keywords": 0.20,
        "formatting": 0.10,
        "experience": 0.15,
        "skills": 0.10,
        "action_verbs": 0.05,
        "contact": 0.05
    }
    
    @staticmethod
    def aggregate(analysis_results: Dict[str, AnalysisResult]) -> Dict[str, Any]:
        """
        Aggregate individual scores using weighted average.
        
        Args:
            analysis_results: Dict of analyzer name -> AnalysisResult
            
        Returns:
            Aggregated report with overall score and breakdown
        """
        weighted_scores = {}
        
        # Map analyzer results to scoring categories
        category_mapping = {
            "contact": analysis_results.get("contact", AnalysisResult(50, "Poor", [], [], {})).score,
            "structure": analysis_results.get("structure", AnalysisResult(50, "Poor", [], [], {})).score,
            "keywords": analysis_results.get("keywords", AnalysisResult(50, "Poor", [], [], {})).score,
            "skills": analysis_results.get("skills", AnalysisResult(50, "Poor", [], [], {})).score,
            "action_verbs": analysis_results.get("action_verbs", AnalysisResult(50, "Poor", [], [], {})).score,
            "experience": analysis_results.get("experience", AnalysisResult(50, "Poor", [], [], {})).score,
            "parsing": analysis_results.get("parsing", AnalysisResult(50, "Poor", [], [], {})).score,
            "formatting": analysis_results.get("formatting", AnalysisResult(50, "Poor", [], [], {})).score,
            "ai_readiness": analysis_results.get("ai_readiness", AnalysisResult(50, "Poor", [], [], {})).score,
        }
        
        # Calculate weighted scores
        total_weighted_score = 0
        for category, weight in ScoreAggregator.WEIGHTS.items():
            score = category_mapping.get(category, 50)
            weighted_scores[category] = score
            total_weighted_score += score * weight
        
        # AI readiness is additional context, not in main weights
        ai_readiness_score = category_mapping.get("ai_readiness", 50)
        
        # Round to nearest integer
        overall_score = round(total_weighted_score)
        overall_score = max(0, min(100, overall_score))
        
        # Determine grade
        if overall_score >= 90:
            grade = "A"
            status = "Excellent"
        elif overall_score >= 80:
            grade = "B"
            status = "Good"
        elif overall_score >= 70:
            grade = "C"
            status = "Fair"
        elif overall_score >= 60:
            grade = "D"
            status = "Needs Improvement"
        else:
            grade = "F"
            status = "Poor"
        
        return {
            "overall_score": overall_score,
            "grade": grade,
            "status": status,
            "breakdown": {
                "parsing": weighted_scores.get("parsing", 50),
                "structure": weighted_scores.get("structure", 50),
                "keywords": weighted_scores.get("keywords", 50),
                "formatting": weighted_scores.get("formatting", 50),
                "experience": weighted_scores.get("experience", 50),
                "skills": weighted_scores.get("skills", 50),
                "action_verbs": weighted_scores.get("action_verbs", 50),
                "contact": weighted_scores.get("contact", 50),
                "ai_readiness": ai_readiness_score
            },
            "weighted_breakdown": {
                "parsing": {"score": weighted_scores.get("parsing", 50), "weight": 0.20},
                "structure": {"score": weighted_scores.get("structure", 50), "weight": 0.15},
                "keywords": {"score": weighted_scores.get("keywords", 50), "weight": 0.20},
                "formatting": {"score": weighted_scores.get("formatting", 50), "weight": 0.10},
                "experience": {"score": weighted_scores.get("experience", 50), "weight": 0.15},
                "skills": {"score": weighted_scores.get("skills", 50), "weight": 0.10},
                "action_verbs": {"score": weighted_scores.get("action_verbs", 50), "weight": 0.05},
                "contact": {"score": weighted_scores.get("contact", 50), "weight": 0.05},
            }
        }


class RecommendationEngine:
    """Generate prioritized improvement recommendations"""
    
    @staticmethod
    def generate_recommendations(analysis_results: Dict[str, AnalysisResult]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect and prioritize recommendations from all analyzers.
        
        Args:
            analysis_results: Dict of analyzer name -> AnalysisResult
            
        Returns:
            Recommendations grouped by priority level
        """
        recommendations_by_level = {
            IssueLevel.CRITICAL.value: [],
            IssueLevel.HIGH.value: [],
            IssueLevel.MEDIUM.value: [],
            IssueLevel.LOW.value: []
        }
        
        # Collect all issues and recommendations
        all_recommendations = []
        
        for analyzer_name, result in analysis_results.items():
            # Add issues as critical recommendations
            for issue in result.issues:
                all_recommendations.append({
                    "level": issue.get("level", IssueLevel.CRITICAL.value),
                    "message": issue.get("message", ""),
                    "detail": issue.get("detail", ""),
                    "source": analyzer_name
                })
            
            # Add recommendations
            for rec in result.recommendations:
                all_recommendations.append({
                    "level": rec.get("level", IssueLevel.MEDIUM.value),
                    "message": rec.get("message", ""),
                    "detail": rec.get("detail", ""),
                    "source": analyzer_name
                })
        
        # Group by level
        for rec in all_recommendations:
            level = rec.get("level", IssueLevel.LOW.value)
            if level in recommendations_by_level:
                recommendations_by_level[level].append(rec)
        
        # Remove duplicates and sort by priority
        for level in recommendations_by_level:
            unique_recs = []
            seen = set()
            for rec in recommendations_by_level[level]:
                key = (rec.get("message", ""), rec.get("detail", ""))
                if key not in seen:
                    unique_recs.append(rec)
                    seen.add(key)
            recommendations_by_level[level] = unique_recs
        
        return recommendations_by_level


class ATSCompatibilityCalculator:
    """Calculate ATS compatibility scores for different platforms"""
    
    @staticmethod
    def calculate(overall_score: int, breakdown: Dict[str, int]) -> Dict[str, int]:
        """
        Calculate platform-specific ATS compatibility scores.
        
        Each platform has different parsing and keyword matching strategies.
        We adjust the overall score based on each platform's strengths/weaknesses.
        
        Args:
            overall_score: Overall ATS score (0-100)
            breakdown: Category breakdown scores
            
        Returns:
            Platform-specific scores
        """
        platform_scores = {}
        
        for platform_key, platform_config in ATS_PLATFORM_ADJUSTMENTS.items():
            score = overall_score * platform_config["base_score_adjustment"]
            
            # Boost score for platform strengths
            for strength in platform_config["strengths"]:
                if strength in breakdown:
                    boost = (breakdown[strength] - 75) * 0.05  # Small boost if category is strong
                    score += max(0, boost)
            
            # Reduce score for platform weaknesses
            for weakness in platform_config["weaknesses"]:
                if weakness in breakdown:
                    penalty = (100 - breakdown[weakness]) * 0.05  # Penalty if category is weak
                    score -= max(0, penalty)
            
            # Round and constrain
            score = round(max(0, min(100, score)))
            platform_scores[platform_key] = score
        
        return platform_scores


class ATSReportGenerator:
    """Generate comprehensive ATS analysis report"""
    
    @staticmethod
    def generate(
        parsed_resume: Dict[str, Any],
        role: str = "full_stack_engineer",
        analysis_results: Optional[Dict[str, AnalysisResult]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive ATS report.
        
        Args:
            parsed_resume: Extracted resume data
            role: Target job role
            analysis_results: Optional pre-computed analysis results
            
        Returns:
            Comprehensive ATS report
        """
        # Run all analyzers if results not provided
        if analysis_results is None:
            analysis_results = {
                "contact": ContactInfoAnalyzer.analyze(parsed_resume),
                "structure": StructureAnalyzer.analyze(parsed_resume),
                "skills": SkillsAnalyzer.analyze(parsed_resume),
                "action_verbs": ActionVerbAnalyzer.analyze(parsed_resume),
                "keywords": KeywordAnalyzer.analyze(parsed_resume, role=role),
                "experience": ExperienceQualityAnalyzer.analyze(parsed_resume),
                "ai_readiness": AIReadinessAnalyzer.analyze(parsed_resume),
                # These would be implemented in parsing and formatting analyzers
                "parsing": AnalysisResult(85, "Good", [], [], {}),
                "formatting": AnalysisResult(80, "Good", [], [], {}),
            }
        
        # Aggregate scores
        aggregated = ScoreAggregator.aggregate(analysis_results)
        
        # Generate recommendations
        recommendations = RecommendationEngine.generate_recommendations(analysis_results)
        
        # Calculate platform compatibility
        platform_scores = ATSCompatibilityCalculator.calculate(
            aggregated["overall_score"],
            aggregated["breakdown"]
        )
        
        # Create summary
        summary = ATSReportGenerator._create_summary(aggregated, recommendations)
        
        # Collect critical issues
        critical_issues = [
            rec["message"] for rec in recommendations.get(IssueLevel.CRITICAL.value, [])
        ]
        
        # Collect high-priority recommendations
        high_recommendations = [
            rec["message"] for rec in recommendations.get(IssueLevel.HIGH.value, [])
        ][:3]  # Top 3
        
        return {
            "generated_at": datetime.now().isoformat(),
            "role": role,
            "overall_score": aggregated["overall_score"],
            "grade": aggregated["grade"],
            "status": aggregated["status"],
            "summary": summary,
            "breakdown": aggregated["breakdown"],
            "weighted_breakdown": aggregated["weighted_breakdown"],
            "critical_issues": critical_issues,
            "recommendations": high_recommendations,
            "all_recommendations": recommendations,
            "ats_compatibility": {
                platform_key: {
                    "name": config["name"],
                    "score": platform_scores.get(platform_key, 0)
                }
                for platform_key, config in ATS_PLATFORM_ADJUSTMENTS.items()
            },
            "details": {
                analyzer_name: {
                    "score": result.score,
                    "status": result.status,
                    "details": result.details
                }
                for analyzer_name, result in analysis_results.items()
            }
        }
    
    @staticmethod
    def _create_summary(aggregated: Dict[str, Any], recommendations: Dict[str, List[Dict[str, Any]]]) -> str:
        """Create human-readable summary"""
        score = aggregated["overall_score"]
        status = aggregated["status"]
        
        critical_count = len(recommendations.get(IssueLevel.CRITICAL.value, []))
        high_count = len(recommendations.get(IssueLevel.HIGH.value, []))
        
        if score >= 90:
            base = "Your resume is highly ATS-compatible with excellent formatting and structure."
        elif score >= 80:
            base = "Your resume has strong ATS compatibility. A few improvements can boost your score."
        elif score >= 70:
            base = "Your resume is moderately ATS-compatible. Consider addressing the key issues below."
        else:
            base = "Your resume needs significant improvements for ATS compatibility."
        
        if critical_count > 0:
            details = f" {critical_count} critical issues require attention."
        elif high_count > 0:
            details = f" Focus on the {high_count} high-priority recommendations."
        else:
            details = " Keep improving by addressing the suggestions below."
        
        return base + details


# Export for use in API routes
__all__ = [
    'ScoreAggregator',
    'RecommendationEngine',
    'ATSCompatibilityCalculator',
    'ATSReportGenerator'
]
