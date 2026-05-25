"""
LangGraph orchestration — FINAL VERSION.

UPDATES:
- Each node sets current_agent for cost tracking
- Optional progress callback for live UI streaming
- LLM-as-judge evaluator node added after cover letter
- Returns timing info for the streaming dashboard
"""
import time
from typing import TypedDict, Optional, Callable

from langgraph.graph import StateGraph, END

from src.agents.scraper import scrape_job, ScraperResult
from src.agents.scorer import score_job
from src.agents.cv_selector import select_cv
from src.agents.cover_letter import write_cover_letter
from src.agents.evaluator import evaluate_cover_letter, check_keyword_overlap
from src.db import get_session, Job, init_db
from src.config import CV_PATH
from src.llm import set_current_agent


# ── State Schema ──────────────────────────────────────────────────────────────

class JobState(TypedDict):
    # Input
    raw_input: str
    force_letter: bool

    # After scraper
    title: Optional[str]
    company: Optional[str]
    description: Optional[str]
    url: Optional[str]
    scraper_time_ms: Optional[int]

    # After scorer
    overall_score: Optional[int]
    recommended_cv: Optional[str]
    should_apply: Optional[bool]
    score_json: Optional[str]
    one_line_pitch: Optional[str]
    top_strengths: Optional[list]
    top_concerns: Optional[list]
    scorer_time_ms: Optional[int]

    # After CV selector
    selected_cv: Optional[str]
    cv_confidence: Optional[int]
    cv_reasoning: Optional[str]
    cv_strengths: Optional[list]
    cv_gaps: Optional[list]
    cv_selector_time_ms: Optional[int]

    # After cover letter
    cover_letter: Optional[str]
    cover_letter_words: Optional[int]
    cover_letter_hook: Optional[str]
    jd_keywords_mirrored: Optional[list]
    letter_tone: Optional[str]
    cover_letter_time_ms: Optional[int]

    # After evaluator (NEW)
    eval_quality: Optional[int]
    eval_specificity: Optional[int]
    eval_jd_alignment: Optional[int]
    eval_voice: Optional[int]
    eval_recommendation: Optional[str]
    eval_ai_isms: Optional[list]
    eval_missed_keywords: Optional[list]
    keyword_overlap_pct: Optional[float]
    evaluator_time_ms: Optional[int]

    # After save
    job_id: Optional[int]

    # Errors
    error: Optional[str]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def scraper_node(state: JobState) -> dict:
    set_current_agent("scraper")
    start = time.time()
    try:
        result: ScraperResult = scrape_job(state["raw_input"])
        return {
            "title": result.title,
            "company": result.company,
            "description": result.description,
            "url": result.source_url,
            "scraper_time_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {"error": str(e), "scraper_time_ms": int((time.time() - start) * 1000)}


def scorer_node(state: JobState) -> dict:
    set_current_agent("scorer")
    if state.get("error"):
        return {}
    start = time.time()

    cv_text = CV_PATH.read_text(encoding="utf-8") if CV_PATH.exists() else ""
    description = state.get("description", "")
    if not description:
        return {"error": "No JD to score"}

    try:
        score = score_job(description, cv_text)
        return {
            "overall_score": score.overall_score,
            "recommended_cv": score.recommended_cv_version,
            "should_apply": score.should_apply,
            "score_json": score.model_dump_json(indent=2),
            "one_line_pitch": score.one_line_pitch,
            "top_strengths": score.top_strengths,
            "top_concerns": score.top_concerns,
            "scorer_time_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {"error": f"Scoring failed: {e}"}


def cv_selector_node(state: JobState) -> dict:
    set_current_agent("cv_selector")
    if state.get("error"):
        return {}
    start = time.time()

    try:
        selection = select_cv(state.get("description", ""))
        return {
            "selected_cv": selection.selected_cv,
            "cv_confidence": selection.confidence,
            "cv_reasoning": selection.reasoning,
            "cv_strengths": selection.key_cv_strengths,
            "cv_gaps": selection.cv_gaps,
            "cv_selector_time_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "selected_cv": state.get("recommended_cv"),
            "cv_confidence": 50,
            "cv_reasoning": f"Fallback: {e}",
            "cv_strengths": [],
            "cv_gaps": [],
            "cv_selector_time_ms": int((time.time() - start) * 1000),
        }


def cover_letter_node(state: JobState) -> dict:
    set_current_agent("cover_letter")
    if state.get("error"):
        return {}

    should_apply = state.get("should_apply", False)
    force = state.get("force_letter", False)
    if not should_apply and not force:
        return {
            "cover_letter": None,
            "cover_letter_words": 0,
            "letter_tone": "skipped",
            "cover_letter_time_ms": 0,
        }

    start = time.time()
    try:
        letter = write_cover_letter(
            job_description=state.get("description", ""),
            title=state.get("title", "Role"),
            company=state.get("company", "Company"),
            selected_cv=state.get("selected_cv") or state.get("recommended_cv", "GENAI"),
            overall_score=state.get("overall_score", 75),
            top_strengths=state.get("top_strengths") or [],
            top_concerns=state.get("top_concerns") or [],
            one_line_pitch=state.get("one_line_pitch", ""),
        )
        return {
            "cover_letter": letter.letter_text,
            "cover_letter_words": letter.word_count,
            "cover_letter_hook": letter.hook_sentence,
            "jd_keywords_mirrored": letter.key_phrases_mirrored,
            "letter_tone": letter.confidence_tone,
            "cover_letter_time_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "cover_letter": None,
            "letter_tone": "error",
            "cover_letter_time_ms": int((time.time() - start) * 1000),
        }


def evaluator_node(state: JobState) -> dict:
    """NEW: LLM-as-judge evaluation of the cover letter."""
    set_current_agent("evaluator")
    if state.get("error") or not state.get("cover_letter"):
        return {}

    start = time.time()
    try:
        eval_result = evaluate_cover_letter(
            letter_text=state["cover_letter"],
            job_description=state.get("description", ""),
            company=state.get("company", ""),
            title=state.get("title", ""),
        )

        overlap = check_keyword_overlap(
            state["cover_letter"],
            state.get("description", ""),
        )

        return {
            "eval_quality": eval_result.overall_quality,
            "eval_specificity": eval_result.specificity_score,
            "eval_jd_alignment": eval_result.jd_alignment_score,
            "eval_voice": eval_result.voice_authenticity_score,
            "eval_recommendation": eval_result.recommendation,
            "eval_ai_isms": eval_result.detected_ai_isms,
            "eval_missed_keywords": eval_result.missing_jd_keywords,
            "keyword_overlap_pct": round(overlap["overlap_pct"], 3),
            "evaluator_time_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {"evaluator_time_ms": int((time.time() - start) * 1000)}


def save_node(state: JobState) -> dict:
    set_current_agent("save")
    if state.get("error"):
        return {}

    init_db()
    session = get_session()
    try:
        final_cv = state.get("selected_cv") or state.get("recommended_cv")
        job = Job(
            url=state.get("url"),
            title=state.get("title", "Untitled"),
            company=state.get("company", "Unknown"),
            description=state.get("description", ""),
            overall_score=state.get("overall_score"),
            recommended_cv=final_cv,
            should_apply=state.get("should_apply"),
            scoring_json=state.get("score_json"),
            cover_letter=state.get("cover_letter"),
            cover_letter_words=state.get("cover_letter_words"),
            eval_quality=state.get("eval_quality"),
            eval_recommendation=state.get("eval_recommendation"),
            keyword_overlap_pct=state.get("keyword_overlap_pct"),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return {"job_id": job.id}
    except Exception as e:
        session.rollback()
        return {"error": f"Save failed: {e}"}
    finally:
        session.close()


# ── Build ─────────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(JobState)
    g.add_node("scraper", scraper_node)
    g.add_node("scorer", scorer_node)
    g.add_node("cv_selector", cv_selector_node)
    g.add_node("cover_letter", cover_letter_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("save", save_node)

    g.set_entry_point("scraper")
    g.add_edge("scraper", "scorer")
    g.add_edge("scorer", "cv_selector")
    g.add_edge("cv_selector", "cover_letter")
    g.add_edge("cover_letter", "evaluator")
    g.add_edge("evaluator", "save")
    g.add_edge("save", END)

    return g.compile()


pipeline = build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def process_job(url_or_text: str, force_letter: bool = False) -> JobState:
    """Run the full 6-agent pipeline (scraper, scorer, cv_selector, cover_letter, evaluator, save)."""
    initial: JobState = {
        "raw_input": url_or_text,
        "force_letter": force_letter,
        **{k: None for k in [
            "title", "company", "description", "url", "scraper_time_ms",
            "overall_score", "recommended_cv", "should_apply", "score_json",
            "one_line_pitch", "top_strengths", "top_concerns", "scorer_time_ms",
            "selected_cv", "cv_confidence", "cv_reasoning", "cv_strengths",
            "cv_gaps", "cv_selector_time_ms",
            "cover_letter", "cover_letter_words", "cover_letter_hook",
            "jd_keywords_mirrored", "letter_tone", "cover_letter_time_ms",
            "eval_quality", "eval_specificity", "eval_jd_alignment", "eval_voice",
            "eval_recommendation", "eval_ai_isms", "eval_missed_keywords",
            "keyword_overlap_pct", "evaluator_time_ms",
            "job_id", "error",
        ]},
    }
    return pipeline.invoke(initial)


def process_job_streaming(url_or_text: str, force_letter: bool = False):
    """
    Generator version that yields after each node — for live UI streaming.
    Use in Streamlit with st.empty() to show progress in real time.

    Yields:
        (node_name, partial_state)
    """
    initial: JobState = {
        "raw_input": url_or_text,
        "force_letter": force_letter,
        **{k: None for k in [
            "title", "company", "description", "url", "scraper_time_ms",
            "overall_score", "recommended_cv", "should_apply", "score_json",
            "one_line_pitch", "top_strengths", "top_concerns", "scorer_time_ms",
            "selected_cv", "cv_confidence", "cv_reasoning", "cv_strengths",
            "cv_gaps", "cv_selector_time_ms",
            "cover_letter", "cover_letter_words", "cover_letter_hook",
            "jd_keywords_mirrored", "letter_tone", "cover_letter_time_ms",
            "eval_quality", "eval_specificity", "eval_jd_alignment", "eval_voice",
            "eval_recommendation", "eval_ai_isms", "eval_missed_keywords",
            "keyword_overlap_pct", "evaluator_time_ms",
            "job_id", "error",
        ]},
    }
    for chunk in pipeline.stream(initial, stream_mode="updates"):
        # Each chunk is {node_name: state_update}
        for node_name, update in chunk.items():
            yield node_name, update