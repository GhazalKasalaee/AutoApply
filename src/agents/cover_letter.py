"""
Cover Letter Writer Agent

Architecture:
  1. Load persona.txt — your voice, background, anti-patterns
  2. Load the selected CV text — the specific version chosen by RAG
  3. Build a rich prompt combining: persona + CV + JD + score context
  4. Call Gemini → structured CoverLetter output
  5. Return both the formatted letter and structured metadata

Design principles:
  - Persona prompt is the "voice layer" — loaded once, reused per job
  - CV text is the "evidence layer" — specific to the selected version
  - JD is the "context layer" — drives keyword mirroring
  - Score context helps calibrate tone (high score = confident, low = careful)

Usage:
    from src.agents.cover_letter import write_cover_letter

    result = write_cover_letter(
        job_description="...",
        title="Senior AI Engineer",
        company="Example AI Platform Team",
        selected_cv="GENAI",
        overall_score=88,
        top_strengths=["LangGraph expertise", "RAG pipelines"],
        top_concerns=["OAuth 2.0 gap"],
        one_line_pitch="My LangGraph pipeline..."
    )
    print(result.letter_text)
    print(result.word_count)
"""
from pathlib import Path

from src.config import PROJECT_ROOT
from src.llm import call_llm_structured
from src.schemas import CoverLetter
from src.agents.cv_selector import get_cv_text, CVVersion


# ── File paths ────────────────────────────────────────────────────────────────

PERSONA_PATH = PROJECT_ROOT / "data" / "persona.txt"


# ── Prompt templates ─────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """{persona}

You are writing a cover letter AS "YOUR NAME" for a specific job.
Your goal: write a cover letter that sounds unmistakably human, specific,
and confident — never generic, never AI-sounding, never sycophantic.
"""

COVER_LETTER_PROMPT = """Write a cover letter for "YOUR NAME" for this specific job.

## JOB DETAILS
Company: {company}
Role: {title}
Score: {overall_score}/100 ({"strong fit — be confident" if overall_score >= 75 else "moderate fit — be honest about strengths, don't oversell"})

## JD (key sections)
{job_description}

## SELECTED CV VERSION: {selected_cv}
This is the specific CV that was selected for this role. Use the accomplishments
from this version as your primary evidence. Do not invent facts not in the CV.

{cv_text}

## SCORE CONTEXT
Top strengths (reference these):
{top_strengths}

Concerns (do NOT hide, but don't lead with):
{top_concerns}

Suggested opening angle: {one_line_pitch}

## YOUR TASK
Write a 4-paragraph cover letter following ALL rules in the persona prompt.
The letter should:
1. Open with a specific hook tied to this company's actual needs (not "I am writing...")
2. Prove the fit with 2-3 specific numbers from the CV above
3. Show you understand THIS company's challenge specifically
4. Close with confidence and a specific ask

Return as JSON matching the schema. The letter_text field should be the
complete formatted letter including greeting and sign-off."""


# ── Main function ─────────────────────────────────────────────────────────────

def write_cover_letter(
    job_description: str,
    title: str,
    company: str,
    selected_cv: CVVersion,
    overall_score: int,
    top_strengths: list[str],
    top_concerns: list[str],
    one_line_pitch: str,
) -> CoverLetter:
    """
    Write a tailored cover letter using persona prompting.

    Args:
        job_description: Full JD text
        title: Job title (e.g. "Senior AI Engineer")
        company: Company name (e.g. "Example AI Platform Team")
        selected_cv: Which CV version was selected (MLE/GENAI/RESEARCH/ARCHITECT)
        overall_score: Score from scorer agent (0-100)
        top_strengths: List of strengths from scorer
        top_concerns: List of concerns from scorer
        one_line_pitch: Opening angle from scorer

    Returns:
        CoverLetter with letter_text, word_count, paragraph_count, key_phrases
    """
    # Load persona
    if not PERSONA_PATH.exists():
        raise FileNotFoundError(
            f"Persona file not found: {PERSONA_PATH}\n"
            "Copy persona.txt to data/persona.txt"
        )
    persona = PERSONA_PATH.read_text(encoding="utf-8")

    # Load selected CV text
    try:
        cv_text = get_cv_text(selected_cv)
        cv_preview = cv_text[:2500]  # Enough for context without blowing the prompt
    except FileNotFoundError:
        cv_preview = f"[CV-{selected_cv} text not available — use general background]"

    # Build system prompt (persona)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(persona=persona)

    # Build user prompt
    strengths_text = "\n".join(f"- {s}" for s in top_strengths) if top_strengths else "- Strong technical background"
    concerns_text = "\n".join(f"- {c}" for c in top_concerns) if top_concerns else "- None identified"

    # Determine tone guidance based on score
    tone_guidance = "strong fit — be confident" if (overall_score or 75) >= 75 else "moderate fit — be honest about strengths, don't oversell"

    user_prompt = f"""Write a cover letter for the candidate described in persona.txt for this specific job.

## JOB DETAILS
Company: {company or "the company"}
Role: {title or "this role"}
Score: {overall_score or 75}/100 ({tone_guidance})

## JD (key sections)
{job_description[:3000]}

## SELECTED CV VERSION: {selected_cv}
This is the specific CV that was selected for this role. Use the accomplishments
from this version as your primary evidence. Do not invent facts not in the CV.

{cv_preview}

## SCORE CONTEXT
Top strengths (reference these):
{strengths_text}

Concerns (do NOT hide, but don't lead with):
{concerns_text}

Suggested opening angle: {one_line_pitch or "My background directly addresses the core requirements of this role."}

## YOUR TASK
Write a 4-paragraph cover letter following ALL rules in the persona prompt.
The letter should:
1. Open with a specific hook tied to this company's actual needs (not "I am writing...")
2. Prove the fit with 2-3 specific numbers from the CV above
3. Show you understand THIS company's challenge specifically
4. Close with confidence and a specific ask

Return as JSON matching the schema. The letter_text field should be the
complete formatted letter including greeting and sign-off."""

    # Combine for the LLM call
    full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

    return call_llm_structured(full_prompt, CoverLetter)


# ── Convenience: plain text getter ────────────────────────────────────────────

def get_cover_letter_text(
    job_description: str,
    title: str,
    company: str,
    selected_cv: CVVersion,
    overall_score: int = 75,
    top_strengths: list[str] | None = None,
    top_concerns: list[str] | None = None,
    one_line_pitch: str = "",
) -> str:
    """
    Convenience wrapper that returns just the letter text string.
    Useful for quick testing without the full pipeline.
    """
    result = write_cover_letter(
        job_description=job_description,
        title=title,
        company=company,
        selected_cv=selected_cv,
        overall_score=overall_score,
        top_strengths=top_strengths or [],
        top_concerns=top_concerns or [],
        one_line_pitch=one_line_pitch,
    )
    return result.letter_text