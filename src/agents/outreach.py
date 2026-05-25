"""
Outreach Writer Agent

Generates personalized LinkedIn DMs and cold emails for networking outreach
tied to a specific job application.

Architecture:
  Persona prompt (voice) +
  Saved job context (company, role, your CV, your score) +
  Recipient info (name, role, optional context) →
  3 message variants (direct / warm / technical) in proper LinkedIn lengths

Usage:
    from src.agents.outreach import write_outreach

    messages = write_outreach(
        recipient_name="Sarah Chen",
        recipient_role="Senior Technical Recruiter",
        job_company="Example AI Platform Team",
        job_title="Senior AI Engineer",
        selected_cv="GENAI",
        overall_score=88,
        context="Polytechnique alum",  # optional
    )
    for variant in messages.variants:
        print(f"{variant.tone}: {variant.message_text}")
"""
from pathlib import Path

from src.config import PROJECT_ROOT
from src.llm import call_llm_structured
from src.schemas import OutreachBundle
from src.agents.cv_selector import get_cv_text


PERSONA_PATH = PROJECT_ROOT / "data" / "persona.txt"


OUTREACH_PROMPT = """You are the candidate described in persona.txt writing personalized outreach messages.

# YOUR VOICE & BACKGROUND
{persona}

# THE OUTREACH CONTEXT
You are reaching out to someone at a company where you just applied (or want to apply).

Recipient: {recipient_name}
Their role: {recipient_role}
Company: {job_company}
Job you applied to: {job_title}
Your fit score: {overall_score}/100
Selected CV version: {selected_cv}
Additional context about this person: {context}

Your strongest CV proof points for this role:
{cv_preview}

# YOUR TASK
Generate THREE outreach message variants:

1. DIRECT (2-3 sentences, LinkedIn DM, ~300-500 chars)
   Use when: cold outreach to a recruiter or hiring manager with no prior connection.
   - Lead with your most relevant credential
   - Mention the specific role
   - End with a specific 10-15 min ask

2. WARM (3-4 sentences, LinkedIn DM, ~400-700 chars)
   Use when: there is a connection (alum, mutual contact, shared community).
   - Acknowledge the connection naturally in sentence 1
   - Bridge to the role/your background
   - Soft ask — "happy to share more" or "would value your perspective"

3. TECHNICAL (3-5 sentences, LinkedIn DM, ~500-800 chars)
   Use when: target is a senior engineer or technical leader.
   - Open with a technical observation (their work, the company's challenge)
   - Mirror their domain language
   - Position as peer-to-peer
   - Specific ask for technical conversation

# ABSOLUTE PROHIBITIONS
NEVER use these phrases:
- "Hope you're doing well"
- "I came across your profile"
- "I would love to pick your brain"
- "Let me know if you have time"
- "Looking forward to connecting"
- "Reaching out because"
- "Hi [name], I hope this message finds you well"
- ANY opening longer than 1 sentence before getting to the point

# RULES
- LinkedIn DMs: NO sign-off, NO "Best regards" (too formal)
- Lead with the person's first name only ("Hi Sarah" not "Hi Ms. Chen")
- Every sentence must do work — no filler
- Mirror the JD's terminology naturally (e.g. "agentic AI" if the role uses that)
- Be specific about your background — use 1-2 numbers from your CV
- If context mentions something specific (alum, mutual friend, recent post), USE IT in the relevant variant

Return all 3 variants as JSON matching the schema."""


def write_outreach(
    recipient_name: str,
    recipient_role: str,
    job_company: str,
    job_title: str,
    selected_cv: str = "GENAI",
    overall_score: int = 75,
    context: str = "",
) -> OutreachBundle:
    """
    Generate 3 outreach message variants for a job-tied networking contact.

    Args:
        recipient_name: First+last name of the person you're messaging
        recipient_role: Their job title (e.g. "Senior Technical Recruiter")
        job_company: Company where you applied
        job_title: Role you applied to
        selected_cv: Which CV version (MLE/GENAI/RESEARCH/ARCHITECT)
        overall_score: Your fit score for this job
        context: Optional — connection details (alum, mutual friend, recent post)

    Returns:
        OutreachBundle with 3 variants (direct/warm/technical)
    """
    # Load persona
    if not PERSONA_PATH.exists():
        raise FileNotFoundError(
            f"persona.txt not found at {PERSONA_PATH}. Run Day 4 setup first."
        )
    persona = PERSONA_PATH.read_text(encoding="utf-8")

    # Load CV for proof points
    try:
        cv_text = get_cv_text(selected_cv)
        cv_preview = cv_text[:1500]
    except FileNotFoundError:
        cv_preview = "[CV text not available — use general background from persona]"

    prompt = OUTREACH_PROMPT.format(
        persona=persona,
        recipient_name=recipient_name or "the recipient",
        recipient_role=recipient_role or "Unknown role",
        job_company=job_company or "the company",
        job_title=job_title or "the role",
        overall_score=overall_score,
        selected_cv=selected_cv,
        cv_preview=cv_preview,
        context=context or "No additional context provided. Treat as cold outreach.",
    )

    return call_llm_structured(prompt, OutreachBundle)