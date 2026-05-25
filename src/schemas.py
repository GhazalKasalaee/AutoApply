"""
Pydantic schemas for structured LLM outputs.
Defines the expected structure for outputs from various agents, including:
- CV Tailoring agent (TailoredLaTeX)
- CV Scoring agent (JobScore)
- CV Selector agent (CVSelection)
- Cover Letter Generator agent (CoverLetter)
- Outreach Message Generator agent (OutreachBundle, OutreachMessage)
"""
from typing import Literal
from pydantic import BaseModel, Field


# ── CV version type ──────────────────────────────────────────────────────────

CVVersion = Literal["MLE", "GENAI", "RESEARCH", "ARCHITECT"]


# ── Scorer output ────────────────────────────────────────────────────────────

class JobScore(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    skill_match_score: int = Field(ge=0, le=100)
    experience_match_score: int = Field(ge=0, le=100)
    recommended_cv_version: CVVersion
    top_strengths: list[str] = Field(min_length=2, max_length=4)
    top_concerns: list[str] = Field(min_length=1, max_length=4)
    should_apply: bool
    one_line_pitch: str = Field(max_length=400)


# ── CV Selector output ───────────────────────────────────────────────────────

class CVSelection(BaseModel):
    selected_cv: CVVersion
    confidence: int = Field(ge=0, le=100)
    reasoning: str = Field(max_length=500)
    key_cv_strengths: list[str] = Field(min_length=2, max_length=4)
    cv_gaps: list[str] = Field(min_length=0, max_length=3)


# ── Cover Letter output ──────────────────────────────────────────────────────

class CoverLetter(BaseModel):
    letter_text: str
    word_count: int = Field(ge=50, le=500)
    paragraph_count: int = Field(ge=3, le=5)
    key_phrases_mirrored: list[str] = Field(min_length=2, max_length=5)
    hook_sentence: str = Field(max_length=200)
    confidence_tone: Literal["confident", "balanced", "cautious"]


# ── Outreach output (NEW Day 5) ──────────────────────────────────────────────

OutreachTone = Literal["direct", "warm", "technical"]


class OutreachMessage(BaseModel):
    """A single outreach message variant."""

    tone: OutreachTone = Field(
        description="direct=cold recruiter; warm=alum/connection; technical=peer engineer"
    )
    message_text: str = Field(
        description="The full message ready to copy-paste into LinkedIn or email"
    )
    char_count: int = Field(
        ge=50, le=1500,
        description="Character count (LinkedIn limit: 300 for connection note, ~800 for DM)"
    )
    best_for: str = Field(
        max_length=150,
        description="One-line guidance on when to use this variant"
    )


class OutreachBundle(BaseModel):
    """Bundle of 3 outreach variants for the same target."""

    variants: list[OutreachMessage] = Field(
        min_length=3, max_length=3,
        description="Exactly 3 message variants: direct, warm, technical"
    )
    recipient_name: str = Field(description="Name of the person being contacted")
    recipient_role: str = Field(description="Their job title")
    job_context: str = Field(
        max_length=200,
        description="Brief reminder of the job this outreach is tied to"
    )