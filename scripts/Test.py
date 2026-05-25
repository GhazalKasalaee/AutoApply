"""
Public smoke test for AutoApply AI.

This replaces the homework-style day1–day6 scripts with one generic
end-to-end check that uses placeholder companies, contacts, and job
descriptions only.

Run: python scripts/Test.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PROJECT_ROOT, CV_PATH
from src.db import init_db, get_session, Job
from src.agents.scorer import score_job
from src.agents.graph import process_job
from src.agents.cv_selector import load_cvs_into_chromadb, select_cv
from src.agents.cover_letter import write_cover_letter
from src.agents.outreach import write_outreach
from src.calendar_utils import (
    generate_application_ics,
    generate_followup_ics,
    generate_interview_ics,
)


SAMPLE_JD = """
Senior AI Engineer — Example AI Platform Team
Remote · Hybrid

Design, build, and productionize LLM-powered and agentic applications.
Focus on retrieval-augmented generation (RAG), multi-step workflows,
structured outputs, evaluation, and prompt safety.
Build and consume tool servers, define schemas and endpoints, and ensure
systems are testable, observable, and resilient.

Required: Python, LLM applications, tool servers, microservices, and cloud APIs.
"""


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def check_example_files() -> None:
    banner("1) Example files")
    persona = PROJECT_ROOT / "data" / "persona.txt"
    example_cv = PROJECT_ROOT / "data" / "my_cv.txt"
    example_cvs = sorted((PROJECT_ROOT / "data" / "cvs").glob("*.txt"))

    assert persona.exists(), f"Missing persona file: {persona}"
    assert example_cv.exists(), f"Missing CV file: {example_cv}"
    assert len(example_cvs) >= 4, "Need at least 4 CV variants in `data/cvs/`"

    print(f"✅ Persona: {persona.name}")
    print(f"✅ CV: {example_cv.name} ({example_cv.stat().st_size} bytes)")
    print(f"✅ CV variants: {len(example_cvs)} files")


def check_scoring() -> dict:
    banner("2) Scoring")
    cv_text = CV_PATH.read_text(encoding="utf-8")
    score = score_job(SAMPLE_JD, cv_text)

    print(f"✅ Score: {score.overall_score}/100")
    print(f"✅ Recommended CV: {score.recommended_cv_version}")
    print(f"✅ Apply decision: {score.should_apply}")
    return score.model_dump()


def check_cv_selection() -> str:
    banner("3) CV selection")
    load_cvs_into_chromadb(force_reload=True)
    selection = select_cv(SAMPLE_JD)

    print(f"✅ Selected CV: {selection.selected_cv}")
    print(f"✅ Confidence: {selection.confidence}%")
    print(f"✅ Reasoning: {selection.reasoning}")
    return selection.selected_cv


def check_pipeline() -> dict:
    banner("4) Full pipeline")
    result = process_job(SAMPLE_JD, force_letter=True)

    if result.get("error"):
        raise RuntimeError(result["error"])

    print(f"✅ Title: {result.get('title')}")
    print(f"✅ Company: {result.get('company')}")
    print(f"✅ Score: {result.get('overall_score')}/100")
    print(f"✅ Job ID: {result.get('job_id')}")
    return result


def check_letter_and_outreach(result: dict) -> None:
    banner("5) Cover letter + outreach")

    selected_cv = result.get("selected_cv") or "GENAI"
    company = result.get("company") or "Example AI Platform Team"
    title = result.get("title") or "Senior AI Engineer"
    overall_score = int(result.get("overall_score") or 80)
    strengths = result.get("top_strengths") or ["Retrieval-augmented generation", "Workflow orchestration"]
    concerns = result.get("top_gaps") or ["Domain-specific experience to validate"]
    pitch_options = [
        "RAG and agentic workflows.",
        "RAG, tool servers, and observability.",
    ]

    last_error = None
    letter = None
    for pitch in pitch_options:
        try:
            letter = write_cover_letter(
                job_description=SAMPLE_JD,
                title=title,
                company=company,
                selected_cv=selected_cv,
                overall_score=overall_score,
                top_strengths=strengths[:2],
                top_concerns=concerns[:1],
                one_line_pitch=pitch,
            )
            break
        except Exception as error:
            last_error = error

    if letter is None:
        raise RuntimeError(f"Cover letter generation failed after retries: {last_error}")

    outreach = write_outreach(
        recipient_name="Jordan Lee",
        recipient_role="Hiring Manager",
        job_company=company,
        job_title=title,
        selected_cv=selected_cv,
        overall_score=overall_score,
        context="Shared interest in AI systems and product delivery",
    )

    print(f"✅ Cover letter words: {letter.word_count}")
    print(f"✅ Outreach variants: {len(outreach.variants)}")


def check_calendar_outputs(result: dict) -> None:
    banner("6) Calendar exports")
    job = SimpleNamespace(
        id=result.get("job_id") or 1,
        company=result.get("company") or "Example AI Platform Team",
        title=result.get("title") or "Senior AI Engineer",
        overall_score=result.get("overall_score") or 80,
        recommended_cv=result.get("selected_cv") or "GENAI",
        cover_letter=result.get("cover_letter") or "",
        cover_letter_words=result.get("cover_letter_words") or 0,
        url=result.get("url") or None,
    )
    contact = SimpleNamespace(
        id=1,
        name="Jordan Lee",
        role="Hiring Manager",
        sent_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    app_path = generate_application_ics(job)
    followup_path = generate_followup_ics(contact, job)
    interview_path = generate_interview_ics(job, datetime.now(timezone.utc) + timedelta(days=2))

    print(f"✅ Application ICS: {app_path.name}")
    print(f"✅ Follow-up ICS: {followup_path.name}")
    print(f"✅ Interview ICS: {interview_path.name}")


def check_database(result: dict) -> None:
    banner("7) Database persistence")
    init_db()
    session = get_session()
    try:
        jobs = session.query(Job).all()
        print(f"✅ Jobs in database: {len(jobs)}")
        if result.get("job_id"):
            print(f"✅ Latest job id: {result['job_id']}")
    finally:
        session.close()


def main() -> None:
    print("\n🎯 AutoApply AI — Public Smoke Test")
    print("This single script replaces the old day1–day6 homework files.\n")

    init_db()
    check_example_files()
    check_scoring()
    check_cv_selection()
    result = check_pipeline()
    check_letter_and_outreach(result)
    check_calendar_outputs(result)
    check_database(result)

    banner("DONE")
    print("✅ All public smoke checks passed.")
    print("Next: `python main.py serve` or deploy to Hugging Face Spaces.")


if __name__ == "__main__":
    main()
