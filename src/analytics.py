from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.db import init_db, get_session, Job, OutreachContact, ApplicationActivity
from src.cost_tracker import get_cost_summary

COLORS = {
    "bg_primary": "#000000",
    "bg_secondary": "#0a0a0a",
    "bg_tertiary": "#1a1a1a",
    "amber": "#71AADC",          # Bloomberg amber (primary accent)
    "green": "#00ff41",          # Matrix green (success)
    "red": "#ff3838",            # Alert red
    "cyan": "#00d4ff",           # Info / data
    "magenta": "#ff00ff",        # Highlight
    "text_primary": "#e8e8e8",
    "text_dim": "#808080",
    "grid": "#222222",
}

STATUS_COLORS = {
    "new": "#404040",
    "applied": "#00d4ff",
    "phone_screen": "#ff00ff",
    "interview": "#0008ff",
    "offer": "#00ff41",
    "rejected": "#ff3838",
}

STATUS_ORDER = ["new", "applied", "phone_screen", "interview", "offer", "rejected"]


def _premium_layout(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    """Apply Bloomberg-terminal styling to any plotly figure."""
    fig.update_layout(
        title=dict(
            text=title.upper(),
            font=dict(
                family="JetBrains Mono, Courier New, monospace",
                size=14,
                color=COLORS["amber"],
            ),
            x=0.02,
        ),
        plot_bgcolor=COLORS["bg_primary"],
        paper_bgcolor=COLORS["bg_primary"],
        font=dict(
            family="JetBrains Mono, Courier New, monospace",
            color=COLORS["text_primary"],
            size=11,
        ),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        showlegend=False,
    )
    fig.update_xaxes(
        gridcolor=COLORS["grid"],
        linecolor=COLORS["amber"],
        zerolinecolor=COLORS["grid"],
        tickfont=dict(color=COLORS["text_dim"]),
    )
    fig.update_yaxes(
        gridcolor=COLORS["grid"],
        linecolor=COLORS["amber"],
        zerolinecolor=COLORS["grid"],
        tickfont=dict(color=COLORS["text_dim"]),
    )
    return fig

# ── Data loaders ─────────────────────────────────────────────────────────────

def get_jobs_df() -> pd.DataFrame:
    """Load all jobs as a DataFrame."""
    init_db()
    s = get_session()
    try:
        jobs = s.query(Job).all()
        rows = []
        for j in jobs:
            rows.append({
                "id": j.id,
                "company": j.company or "Unknown",
                "title": j.title or "Untitled",
                "score": j.overall_score or 0,
                "cv": j.recommended_cv or "N/A",
                "should_apply": j.should_apply,
                "status": j.status or "new",
                "has_letter": bool(j.cover_letter),
                "eval_quality": j.eval_quality,
                "keyword_overlap": j.keyword_overlap_pct,
                "created": j.created_at,
                "applied_date": j.applied_date,
                "response_date": j.response_date,
                "deadline": j.deadline,
            })
    finally:
        s.close()
    return pd.DataFrame(rows)


def get_contacts_df() -> pd.DataFrame:
    init_db()
    s = get_session()
    try:
        contacts = s.query(OutreachContact).all()
        rows = [{
            "id": c.id, "job_id": c.job_id, "name": c.name,
            "role": c.role or "Unknown", "context": c.context_note or "",
            "sent_at": c.sent_at, "responded": c.responded,
            "response_at": c.response_at,
            "days_since_sent": (datetime.utcnow() - c.sent_at).days if c.sent_at else None,
        } for c in contacts]
    finally:
        s.close()
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 1: SANKEY FUNNEL
# ══════════════════════════════════════════════════════════════════════════════

def sankey_funnel(df: pd.DataFrame) -> go.Figure:
    """
    Interactive Sankey diagram showing flow through application stages.
    Much more visually impressive than a basic funnel.
    """
    if df.empty:
        fig = go.Figure()
        return _premium_layout(fig, "APPLICATION FUNNEL — NO DATA", height=350)

    counts = df["status"].value_counts().to_dict()

    # Define stages and flows
    nodes = ["NEW", "APPLIED", "SCREEN", "INTERVIEW", "OFFER", "REJECTED"]
    node_colors = [
        STATUS_COLORS["new"],
        STATUS_COLORS["applied"],
        STATUS_COLORS["phone_screen"],
        STATUS_COLORS["interview"],
        STATUS_COLORS["offer"],
        STATUS_COLORS["rejected"],
    ]

    new_count = counts.get("new", 0)
    applied_count = counts.get("applied", 0) + counts.get("phone_screen", 0) + counts.get("interview", 0) + counts.get("offer", 0) + counts.get("rejected", 0)
    screen_count = counts.get("phone_screen", 0) + counts.get("interview", 0) + counts.get("offer", 0)
    interview_count = counts.get("interview", 0) + counts.get("offer", 0)
    offer_count = counts.get("offer", 0)
    rejected_count = counts.get("rejected", 0)

    # source, target, value (links)
    sources = []
    targets = []
    values = []
    link_colors = []

    # NEW → APPLIED
    if applied_count > 0:
        sources.append(0); targets.append(1); values.append(applied_count)
        link_colors.append("rgba(0, 212, 255, 0.5)")
    # NEW → REJECTED (skipped without applying = current "new" pool minus applied)
    if new_count > 0:
        sources.append(0); targets.append(5); values.append(new_count)
        link_colors.append("rgba(255, 56, 56, 0.2)")
    # APPLIED → SCREEN
    if screen_count > 0:
        sources.append(1); targets.append(2); values.append(screen_count)
        link_colors.append("rgba(255, 0, 255, 0.5)")
    # APPLIED → REJECTED
    apply_no_response = applied_count - screen_count - rejected_count
    if apply_no_response > 0:
        sources.append(1); targets.append(5); values.append(apply_no_response)
        link_colors.append("rgba(255, 56, 56, 0.3)")
    # SCREEN → INTERVIEW
    if interview_count > 0:
        sources.append(2); targets.append(3); values.append(interview_count)
        link_colors.append("rgba(255, 176, 0, 0.5)")
    # INTERVIEW → OFFER
    if offer_count > 0:
        sources.append(3); targets.append(4); values.append(offer_count)
        link_colors.append("rgba(0, 255, 65, 0.6)")
    # REJECTED already counted above

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color=COLORS["amber"], width=1),
            label=nodes,
            color=node_colors,
            customdata=[counts.get(s.lower().replace(" ", "_"), 0) for s in nodes],
            hovertemplate="<b>%{label}</b><br>Jobs: %{value}<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            hovertemplate="<b>%{source.label}</b> → <b>%{target.label}</b><br>%{value} jobs<extra></extra>",
        ),
    )])

    return _premium_layout(fig, "APPLICATION FLOW — SANKEY", height=400)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 2: GITHUB-STYLE CALENDAR HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

def activity_heatmap(days_back: int = 90) -> go.Figure:
    """
    GitHub-contributions-style heatmap of daily activity.
    Each cell = a day, colored by intensity.
    """
    s = get_session()
    try:
        cutoff_date = date.today() - timedelta(days=days_back)
        activities = s.query(ApplicationActivity).filter(
            ApplicationActivity.activity_date >= cutoff_date
        ).all()
        # Also count jobs scored per day from Job.created_at
        jobs = s.query(Job).filter(
            Job.created_at >= datetime.combine(cutoff_date, datetime.min.time())
        ).all()
    finally:
        s.close()

    # Build daily counts
    daily_counts = {}
    for a in activities:
        d = a.activity_date
        daily_counts[d] = daily_counts.get(d, 0) + a.count
    for j in jobs:
        d = j.created_at.date() if j.created_at else None
        if d:
            daily_counts[d] = daily_counts.get(d, 0) + 1

    # Build grid: 13 weeks × 7 days
    today = date.today()
    start = today - timedelta(days=days_back)
    # Align to Monday
    start = start - timedelta(days=start.weekday())

    weeks = []
    week_dates = []
    current_week = []
    current_dates = []

    d = start
    while d <= today:
        current_week.append(daily_counts.get(d, 0))
        current_dates.append(d.isoformat())

        if d.weekday() == 6:  # Sunday — close the week
            weeks.append(current_week)
            week_dates.append(current_dates)
            current_week = []
            current_dates = []
        d += timedelta(days=1)

    if current_week:
        # Pad with empty days to complete the week
        while len(current_week) < 7:
            current_week.append(None)
            current_dates.append(None)
        weeks.append(current_week)
        week_dates.append(current_dates)

    # Transpose: rows are days of week, columns are weeks
    z = list(zip(*weeks))
    text_data = list(zip(*week_dates))

    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    week_labels = [f"W{i+1}" for i in range(len(weeks))]


    colorscale = [
        [0.0, "#0a0a0a"],
        [0.001, "#1a1a1a"],  
        [0.25, "#3a2800"],
        [0.5, "#7a5500"],
        [0.75, "#cc8500"],
        [1.0, COLORS["amber"]],
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=week_labels,
        y=days_of_week,
        colorscale=colorscale,
        showscale=False,
        xgap=2,
        ygap=2,
        text=text_data,
        hovertemplate="<b>%{text}</b><br>Activity: %{z}<extra></extra>",
    ))

    return _premium_layout(fig, f"ACTIVITY :: LAST {days_back} DAYS", height=220)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 3: LANGGRAPH STATE MACHINE VISUALIZATION
# ══════════════════════════════════════════════════════════════════════════════

def agent_graph_diagram() -> go.Figure:
    """
    Interactive visualization of the LangGraph state machine.
    Shows nodes and edges with the system flow.
    """
    # Node positions (manual layout for clean look)
    nodes = {
        "START":       (0.05, 0.5),
        "Scraper":     (0.20, 0.5),
        "Scorer":      (0.35, 0.5),
        "CV Selector": (0.50, 0.5),
        "Cover Letter":(0.65, 0.5),
        "Evaluator":   (0.80, 0.5),
        "Save":        (0.92, 0.5),
        "END":         (0.98, 0.5),
    }
    node_descriptions = {
        "START":        "Pipeline entry",
        "Scraper":      "requests → Playwright → LLM parser",
        "Scorer":       "Gemini + Pydantic (8 fields)",
        "CV Selector":  "ChromaDB RAG + LLM reasoning",
        "Cover Letter": "Persona-prompted, 4-paragraph",
        "Evaluator":    "LLM-as-judge quality scoring",
        "Save":         "SQLite persistence",
        "END":          "Pipeline exit",
    }
    node_colors = [
        COLORS["text_dim"],
        COLORS["cyan"],
        COLORS["amber"],
        COLORS["magenta"],
        COLORS["amber"],
        COLORS["green"],
        COLORS["cyan"],
        COLORS["text_dim"],
    ]

    # Edges as arrows
    edge_x = []
    edge_y = []
    node_order = list(nodes.keys())
    for i in range(len(node_order) - 1):
        x0, y0 = nodes[node_order[i]]
        x1, y1 = nodes[node_order[i + 1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    fig = go.Figure()

    # Edges
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(color=COLORS["amber"], width=2),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Nodes
    fig.add_trace(go.Scatter(
        x=[p[0] for p in nodes.values()],
        y=[p[1] for p in nodes.values()],
        mode="markers+text",
        marker=dict(
            size=50,
            color=node_colors,
            line=dict(color=COLORS["amber"], width=2),
        ),
        text=list(nodes.keys()),
        textposition="bottom center",
        textfont=dict(color=COLORS["text_primary"], size=11, family="JetBrains Mono"),
        customdata=[node_descriptions[k] for k in nodes.keys()],
        hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
        showlegend=False,
    ))

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0.2, 0.8])
    fig.update_layout(
        title=dict(
            text="LANGGRAPH STATE MACHINE :: 6-NODE PIPELINE",
            font=dict(family="JetBrains Mono", size=14, color=COLORS["amber"]),
            x=0.02,
        ),
        plot_bgcolor=COLORS["bg_primary"],
        paper_bgcolor=COLORS["bg_primary"],
        height=200,
        margin=dict(l=20, r=20, t=50, b=40),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 4: COST TIMELINE
# ══════════════════════════════════════════════════════════════════════════════

def cost_timeline_chart() -> go.Figure:
    """Line chart of cumulative cost over time."""
    from src.cost_tracker import LLMCall, engine
    from sqlalchemy.orm import Session

    s = Session(engine)
    try:
        calls = s.query(LLMCall).order_by(LLMCall.timestamp).all()
    finally:
        s.close()

    if not calls:
        fig = go.Figure()
        return _premium_layout(fig, "COST :: NO DATA", height=300)

    df = pd.DataFrame([{
        "timestamp": c.timestamp,
        "cost": c.cost_usd,
        "tokens": c.input_tokens + c.output_tokens,
        "agent": c.agent_name or "unknown",
    } for c in calls])

    df["cumulative_cost"] = df["cost"].cumsum()
    df["cumulative_tokens"] = df["tokens"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["cumulative_cost"],
        mode="lines",
        line=dict(color=COLORS["green"], width=2),
        name="Cost (USD)",
        fill="tozeroy",
        fillcolor="rgba(0, 255, 65, 0.1)",
        hovertemplate="<b>%{x}</b><br>$%{y:.4f}<extra></extra>",
    ))

    return _premium_layout(fig, "CUMULATIVE COST :: USD", height=300)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 5: AGENT LATENCY BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════

def agent_latency_chart() -> go.Figure:
    """Bar chart of average latency per agent."""
    summary = get_cost_summary()
    by_agent = summary.get("by_agent", {})

    if not by_agent:
        fig = go.Figure()
        return _premium_layout(fig, "AGENT LATENCY :: NO DATA", height=300)

    agents = list(by_agent.keys())
    latencies = [by_agent[a]["avg_latency"] for a in agents]
    calls = [by_agent[a]["calls"] for a in agents]

    fig = go.Figure(data=[go.Bar(
        x=agents,
        y=latencies,
        marker=dict(
            color=latencies,
            colorscale=[[0, COLORS["green"]], [0.5, COLORS["amber"]], [1, COLORS["red"]]],
            line=dict(color=COLORS["amber"], width=1),
        ),
        text=[f"{l}ms<br>{c} calls" for l, c in zip(latencies, calls)],
        textposition="outside",
        textfont=dict(family="JetBrains Mono", color=COLORS["text_primary"]),
        hovertemplate="<b>%{x}</b><br>Avg latency: %{y}ms<br>Calls: %{customdata}<extra></extra>",
        customdata=calls,
    )])

    return _premium_layout(fig, "AGENT LATENCY :: AVG MS", height=300)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 6: SCORE DISTRIBUTION
# ══════════════════════════════════════════════════════════════════════════════

def score_histogram(df: pd.DataFrame) -> go.Figure:
    """Histogram of fit scores."""
    if df.empty:
        fig = go.Figure()
        return _premium_layout(fig, "FIT SCORE DISTRIBUTION :: NO DATA", height=300)

    fig = go.Figure(data=[go.Histogram(
        x=df["score"],
        nbinsx=10,
        marker=dict(
            color=COLORS["amber"],
            line=dict(color=COLORS["amber"], width=1),
        ),
        hovertemplate="<b>Score: %{x}</b><br>Count: %{y}<extra></extra>",
    )])
    fig.add_vline(
        x=75, line_dash="dash", line_color=COLORS["green"],
        annotation_text="STRONG FIT", annotation_position="top",
        annotation_font_color=COLORS["green"],
    )
    fig.add_vline(
        x=55, line_dash="dash", line_color=COLORS["cyan"],
        annotation_text="MODERATE", annotation_position="top",
        annotation_font_color=COLORS["cyan"],
    )
    return _premium_layout(fig, "FIT SCORE DISTRIBUTION", height=300)


# ══════════════════════════════════════════════════════════════════════════════
#  CHART 7: CV PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

def cv_performance_chart(df: pd.DataFrame) -> go.Figure:
    """Response rate by CV version."""
    if df.empty or df["cv"].nunique() == 0:
        fig = go.Figure()
        return _premium_layout(fig, "CV PERFORMANCE :: NO DATA", height=300)

    df = df.copy()
    df["got_response"] = df["status"].isin(["phone_screen", "interview", "offer"])
    grouped = df.groupby("cv").agg(
        applied=("status", lambda x: (x != "new").sum()),
        responses=("got_response", "sum"),
    ).reset_index()
    grouped["rate"] = (grouped["responses"] / grouped["applied"].replace(0, 1) * 100).round(1)

    fig = go.Figure(data=[go.Bar(
        x=grouped["cv"],
        y=grouped["rate"],
        marker=dict(color=COLORS["amber"], line=dict(color=COLORS["amber"], width=1)),
        text=[f"{r}%" for r in grouped["rate"]],
        textposition="outside",
        textfont=dict(family="JetBrains Mono", color=COLORS["green"]),
        hovertemplate="<b>CV-%{x}</b><br>%{customdata} applied<br>%{y}% response<extra></extra>",
        customdata=grouped["applied"],
    )])
    return _premium_layout(fig, "CV RESPONSE RATE", height=300)


def response_probability_chart(df: pd.DataFrame) -> go.Figure:
    """Estimated response probability by fit-score bucket."""
    if df.empty:
        fig = go.Figure()
        return _premium_layout(fig, "RESPONSE PROBABILITY :: NO DATA", height=300)

    scored = df.copy()
    scored["score"] = pd.to_numeric(scored["score"], errors="coerce")
    scored = scored.dropna(subset=["score"])
    if scored.empty:
        fig = go.Figure()
        return _premium_layout(fig, "RESPONSE PROBABILITY :: NO DATA", height=300)

    bins = [0, 50, 65, 75, 85, 101]
    labels = ["0-49", "50-64", "65-74", "75-84", "85-100"]
    scored["score_bucket"] = pd.cut(scored["score"], bins=bins, labels=labels, right=False)
    scored["got_response"] = scored["status"].isin(["phone_screen", "interview", "offer"])

    grouped = (
        scored.groupby("score_bucket", observed=False)
        .agg(total_jobs=("id", "count"), responses=("got_response", "sum"))
        .reset_index()
    )
    grouped["probability"] = (grouped["responses"] / grouped["total_jobs"].replace(0, 1) * 100).round(1)

    fig = go.Figure(data=[go.Bar(
        x=grouped["score_bucket"],
        y=grouped["probability"],
        marker=dict(color=COLORS["cyan"], line=dict(color=COLORS["amber"], width=1)),
        text=[f"{p}%" if t > 0 else "—" for p, t in zip(grouped["probability"], grouped["total_jobs"])],
        textposition="outside",
        textfont=dict(family="JetBrains Mono", color=COLORS["text_primary"]),
        customdata=grouped[["total_jobs", "responses"]],
        hovertemplate=(
            "<b>Bucket %{x}</b><br>Response probability: %{y}%"
            "<br>Total jobs: %{customdata[0]}<br>Responses: %{customdata[1]}<extra></extra>"
        ),
    )])

    fig.update_yaxes(range=[0, 100], title="Probability %")
    return _premium_layout(fig, "RESPONSE PROBABILITY BY FIT SCORE", height=300)


# ── Business rules ────────────────────────────────────────────────────────────

def get_followup_suggestions() -> list[dict]:
    s = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        contacts = s.query(OutreachContact).filter(
            OutreachContact.sent_at != None,
            OutreachContact.sent_at < cutoff,
            OutreachContact.responded == False,
        ).all()
        return [{
            "name": c.name, "role": c.role,
            "days_ago": (datetime.utcnow() - c.sent_at).days,
            "job_id": c.job_id, "contact_id": c.id,
        } for c in contacts]
    finally:
        s.close()


def funnel_conversion_rates(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    counts = df["status"].value_counts().to_dict()
    applied = sum(counts.get(s, 0) for s in ["applied", "phone_screen", "interview", "offer", "rejected"])
    screen = sum(counts.get(s, 0) for s in ["phone_screen", "interview", "offer"])
    interview = sum(counts.get(s, 0) for s in ["interview", "offer"])
    offer = counts.get("offer", 0)

    pct = lambda n, d: round(n / d * 100, 1) if d > 0 else 0.0
    return {
        "applied_to_screen": pct(screen, applied),
        "screen_to_interview": pct(interview, screen),
        "interview_to_offer": pct(offer, interview),
        "applied_to_offer": pct(offer, applied),
    }