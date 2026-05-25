"""
Cost & Token Tracker (Differentiator #2)

Wraps the LLM call so every invocation records:
  - Timestamp
  - Agent name
  - Tokens used (input + output)
  - Estimated cost
  - Latency

Dashboard widget shows running totals and per-agent breakdown.
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, Session

from src.config import DB_PATH



PRICING = {
    "gemini-3.1-flash-lite": {"input": 0.00, "output": 0.00},  # free tier
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


# Reuse the same DB
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    timestamp     = Column(DateTime, default=datetime.utcnow, index=True)
    agent_name    = Column(String, nullable=True)     # "scorer", "cv_selector", etc.
    model         = Column(String, nullable=True)
    input_tokens  = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd      = Column(Float, default=0.0)
    latency_ms    = Column(Integer, default=0)
    success       = Column(Integer, default=1)        # 1=ok, 0=failed
    error         = Column(String, nullable=True)


def init_cost_tracker():
    Base.metadata.create_all(engine, checkfirst=True)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens / 1_000_000) * pricing["input"] + \
           (output_tokens / 1_000_000) * pricing["output"]


def estimate_tokens(text: str) -> int:

    return max(1, len(text or "") // 4)


def log_llm_call(
    agent_name: str,
    model: str = "gemini-3.1-flash-lite",
    input_text: str = "",
    output_text: str = "",
    latency_ms: int = 0,
    success: bool = True,
    error: str = None,
):
    """
    Log a single LLM call. Called automatically by the LLM wrapper.
    """
    init_cost_tracker()
    in_tokens = estimate_tokens(input_text)
    out_tokens = estimate_tokens(output_text)
    cost = estimate_cost(model, in_tokens, out_tokens)

    session = Session(engine)
    try:
        call = LLMCall(
            agent_name=agent_name,
            model=model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            success=1 if success else 0,
            error=error,
        )
        session.add(call)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


# ── Aggregations for the dashboard ────────────────────────────────────────────

def get_cost_summary() -> dict:
    """Return cost/usage summary for the dashboard widget."""
    from datetime import timedelta

    init_cost_tracker()
    session = Session(engine)
    try:
        calls = session.query(LLMCall).all()
    finally:
        session.close()

    if not calls:
        return {
            "total_calls": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "today_cost": 0.0,
            "today_tokens": 0,
            "week_cost": 0.0,
            "avg_latency_ms": 0,
            "success_rate": 100.0,
            "by_agent": {},
        }

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total_cost = sum(c.cost_usd for c in calls)
    total_tokens = sum(c.input_tokens + c.output_tokens for c in calls)
    today_calls = [c for c in calls if c.timestamp >= today_start]
    week_calls = [c for c in calls if c.timestamp >= week_start]

    # By agent breakdown
    by_agent = {}
    for c in calls:
        agent = c.agent_name or "unknown"
        if agent not in by_agent:
            by_agent[agent] = {"calls": 0, "cost": 0.0, "tokens": 0, "avg_latency": 0}
        by_agent[agent]["calls"] += 1
        by_agent[agent]["cost"] += c.cost_usd
        by_agent[agent]["tokens"] += c.input_tokens + c.output_tokens
        by_agent[agent]["avg_latency"] += c.latency_ms

    for agent in by_agent:
        n = by_agent[agent]["calls"]
        by_agent[agent]["avg_latency"] = by_agent[agent]["avg_latency"] // n if n else 0

    return {
        "total_calls": len(calls),
        "total_cost": round(total_cost, 4),
        "total_tokens": total_tokens,
        "today_cost": round(sum(c.cost_usd for c in today_calls), 4),
        "today_tokens": sum(c.input_tokens + c.output_tokens for c in today_calls),
        "week_cost": round(sum(c.cost_usd for c in week_calls), 4),
        "avg_latency_ms": int(sum(c.latency_ms for c in calls) / len(calls)),
        "success_rate": round(sum(c.success for c in calls) / len(calls) * 100, 1),
        "by_agent": by_agent,
    }