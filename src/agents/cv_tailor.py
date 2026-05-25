"""Agent to dynamically tailor a LaTeX CV for a specific job description."""
from typing import Optional

from pydantic import BaseModel, Field
from src.llm import call_llm_structured

class TailoredLaTeX(BaseModel):
    latex_code: str = Field(description="The fully compilable LaTeX string")
    modifications_made: list[str] = Field(default_factory=list, description="Summary of ATS keywords added or sections reordered")
    section_adjustments: list[str] = Field(
        default_factory=list,
        description="Specific CV sections that were changed or should be changed for this JD"
    )
    plain_text_summary: str = Field(
        default="",
        description="Copy-paste-ready plain text summary of the tailoring decisions"
    )

def tailor_latex_cv(
    job_description: str,
    base_latex_string: str,
    summary_override: Optional[str] = None,
    prioritized_projects: Optional[list[str]] = None,
    ats_keywords: Optional[list[str]] = None,
    extra_instructions: Optional[str] = None,
) -> TailoredLaTeX:
    prioritized_projects = prioritized_projects or []
    ats_keywords = ats_keywords or []

    user_directives = []
    if summary_override:
        user_directives.append(
            f"- Replace summary with this text intent while preserving LaTeX format: {summary_override.strip()}"
        )
    if prioritized_projects:
        user_directives.append(
            "- Prioritize and order project bullets/entries to highlight these first: "
            + ", ".join(prioritized_projects)
        )
    if ats_keywords:
        user_directives.append(
            "- Ensure these ATS keywords appear naturally (when truthful): "
            + ", ".join(ats_keywords)
        )
    if extra_instructions:
        user_directives.append(f"- Additional user instructions: {extra_instructions.strip()}")

    directives_block = "\n".join(user_directives) if user_directives else "- No extra directives provided."

    prompt = f"""You are an expert ATS resume optimizer and LaTeX engineer.
    
    # JOB DESCRIPTION
    {job_description[:4000]}
    
    # BASE LATEX CV
    {base_latex_string}
    
    # TASK
    1. Analyze the JD for core technical keywords.
    2. Rewrite the LaTeX \\summary{{}} section to align with the JD.
    3. Reorder the \\item bullet points in the Experience section to push the most relevant achievements to the top.
    4. Inject missing ATS keywords naturally into the text.
    5. Return explicit section-level adjustments so the user knows exactly what changed.
    6. Provide a plain-text summary that can be copied directly into a notes field or application tracker.
    7. DO NOT break any LaTeX syntax, formatting, or document structure. Return ONLY valid, compilable LaTeX.

    # USER DIRECTIVES (HIGHEST PRIORITY)
    {directives_block}
    
    Return valid JSON for the schema fields: latex_code, modifications_made, section_adjustments, plain_text_summary."""
    
    return call_llm_structured(prompt, TailoredLaTeX)