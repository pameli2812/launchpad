"""Data models for the resume analyzer v2."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Goal:
    id: str
    label: str
    description: str
    confidence: str = "high"  # high, medium, low
    auto_inferred: bool = False
    misalignment_note: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class GoalSet:
    id: str
    name: str
    goals: List[Goal]
    created_at: datetime
    is_active: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "goals": [g.to_dict() for g in self.goals],
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }


@dataclass
class ExtractedJD:
    title: str
    company: str
    seniority: str
    reports_to: Optional[str]
    team_size: Optional[str]
    key_requirements: List[str]
    nice_to_have: List[str]
    domain: str
    company_stage: str
    location_policy: str
    full_text: str
    url: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ScoreDetail:
    goal_id: str
    dimension: str
    score: float
    remark: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Scorecard:
    scores: List[ScoreDetail]
    overall_fit: float
    verdict: str  # apply, borderline, skip
    summary: str
    gaps: List[str]

    def to_dict(self):
        return {
            "scores": [s.to_dict() for s in self.scores],
            "overall_fit": self.overall_fit,
            "verdict": self.verdict,
            "summary": self.summary,
            "gaps": self.gaps,
        }


@dataclass
class VerifyAttempt:
    attempt_number: int
    score_before: float
    score_after: float
    delta: float
    gaps_closed: List[str]
    gaps_remaining: List[str]
    verdict: str  # good_to_proceed, apply_with_caveats, needs_more_work
    verdict_message: str
    timestamp: datetime

    def to_dict(self):
        return {
            "attempt_number": self.attempt_number,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "delta": self.delta,
            "gaps_closed": self.gaps_closed,
            "gaps_remaining": self.gaps_remaining,
            "verdict": self.verdict,
            "verdict_message": self.verdict_message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HistoryEntry:
    jd_id: str
    analyzed_at: datetime
    goal_set_id: str
    goal_set_name: str
    goal_set_snapshot: List[Dict[str, Any]]
    resume_id: str
    resume_snapshot_hash: str
    scorecard: Dict[str, Any]
    verdict: str
    overall_fit: float
    status: str  # draft, pending, applied, skipped
    changes_generated: bool = False
    verify_attempts: List[Dict[str, Any]] = None
    jd_title: str = ""
    company: str = ""
    url: Optional[str] = None

    def __post_init__(self):
        if self.verify_attempts is None:
            self.verify_attempts = []

    def to_dict(self):
        return {
            "jd_id": self.jd_id,
            "analyzed_at": self.analyzed_at.isoformat(),
            "goal_set_id": self.goal_set_id,
            "goal_set_name": self.goal_set_name,
            "goal_set_snapshot": self.goal_set_snapshot,
            "resume_id": self.resume_id,
            "resume_snapshot_hash": self.resume_snapshot_hash,
            "scorecard": self.scorecard,
            "verdict": self.verdict,
            "overall_fit": self.overall_fit,
            "status": self.status,
            "changes_generated": self.changes_generated,
            "verify_attempts": self.verify_attempts,
            "jd_title": self.jd_title,
            "company": self.company,
            "url": self.url,
        }
