"""
Scorer Agent: takes a job description and a CV, returns a JobScore.
"""
from src.llm import call_llm_structured
from src.schemas import JobScore


SCORER_PROMPT_TEMPLATE = """You are an expert technical recruiter scoring a job for an AI/ML candidate.

# THE CANDIDATE'S BACKGROUND
{cv_text}

# THE JOB DESCRIPTION
{job_description}

# YOUR TASK
Score this job's fit for the candidate. Be brutally honest.

Scoring guidance:
- 90-100: Dream-fit. Skills, experience level, and domain all align. Apply immediately.
- 75-89:  Strong fit. Most requirements met, minor gaps. Apply with confidence.
- 60-74:  Reasonable fit. Some overlap, but real gaps exist. Worth applying if interested.
- 40-59:  Stretch. Significant mismatches in experience or domain. Apply only if exceptional company.
- 0-39:   Poor fit. Wrong domain, wrong level, or wrong skills. Skip.

For recommended_cv_version, choose based on the role's primary focus:
- MLE = Production ML engineering, MLOps, model deployment, pipelines, cloud infrastructure
- GENAI = LLM applications, agentic AI, RAG pipelines, LangChain/LangGraph, prompt engineering
- RESEARCH = AI research, publications, quantization, efficient architectures, academic roles
- ARCHITECT = Solutions architecture, enterprise AI strategy, cross-functional leadership, system design

Important:
- Check years of experience required vs. candidate's ~3 years. Flag honestly if insufficient.
- Check for hard requirements (specific languages, certifications, security clearance) candidate lacks.
- The one_line_pitch should be specific to THIS job, not generic.

Return your evaluation as JSON matching the schema."""


def score_job(job_description: str, cv_text: str) -> JobScore:
    """
    Score a job description against a candidate's CV.

    Args:
        job_description: The full JD text
        cv_text: The candidate's CV (or summary)

    Returns:
        JobScore with overall_score, recommended_cv, etc.
    """
    prompt = SCORER_PROMPT_TEMPLATE.format(
        cv_text=cv_text,
        job_description=job_description[:8000],  # Don't send huge JDs
    )
    return call_llm_structured(prompt, JobScore)