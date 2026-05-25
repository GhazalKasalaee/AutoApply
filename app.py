"""
AutoApply AI — FINAL Bloomberg-Terminal Dashboard

Wow features:
- 4 views: Pipeline / Analytics / Activity / Outreach
- Live streaming agent execution
- Sankey funnel, calendar heatmap, agent graph diagram
- Cost tracker widget (top-right)
- .ics download buttons throughout
- Bloomberg terminal aesthetic (dark, amber, monospace)

Run: streamlit run app.py
"""
import json
import html
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from src.db import delete_job_record
from src.agents.cv_tailor import tailor_latex_cv

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.db import init_db, get_session, Job, OutreachContact, log_activity
from src.agents.graph import process_job, process_job_streaming
from src.agents.cover_letter import write_cover_letter
from src.agents.outreach import write_outreach
from src.calendar_utils import generate_application_ics, generate_followup_ics, generate_interview_ics
from src.cost_tracker import get_cost_summary, init_cost_tracker
from src import analytics
from src.auto_tailor import generate_auto_tailoring_suggestion, load_sample_cv


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG + THEMING
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AutoApply AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
init_cost_tracker()


# ══════════════════════════════════════════════════════════════════════════════
#  BLOOMBERG TERMINAL CSS
# ══════════════════════════════════════════════════════════════════════════════

BLOOMBERG_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

/* Global */
.stApp {
    background: #0a1620;
    color: #e8e8e8;
    font-family: 'JetBrains Mono', 'IBM Plex Mono', 'Courier New', monospace;
}

/* Background grain texture */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        radial-gradient(circle at 1px 1px, rgba(255, 176, 0, 0.03) 1px, transparent 0);
    background-size: 24px 24px;
    pointer-events: none;
    z-index: 0;
}

/* All text */
h1, h2, h3, h4, h5, h6 {
    color: #00d4d4 !important;
    font-family: 'JetBrains Mono', monospace !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 700;
}

h1 {
    border-bottom: none;
    padding-bottom: 0.5rem;
    text-shadow: none;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0d1f2d;
    border-right: 2px solid #00d4d4;
}

section[data-testid="stSidebar"] * {
    color: #e8e8e8;
    font-family: 'JetBrains Mono', monospace;
}

/* Buttons */
.stButton > button {
    background: #0a1620 !important;
    color: #00d4d4 !important;
    border: 2px solid #00d4d4 !important;
    border-radius: 0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
    transition: all 0.2s;
}

.stButton > button:hover {
    background: #00d4d4 !important;
    color: #0a1620 !important;
    box-shadow: 0 0 20px rgba(0, 212, 212, 0.6);
}

/* Primary buttons (green) */
.stButton > button[kind="primary"] {
    background: #001a00 !important;
    color: #00ff41 !important;
    border-color: #00ff41 !important;
}

.stButton > button[kind="primary"]:hover {
    background: #00ff41 !important;
    color: #000000 !important;
    box-shadow: 0 0 20px rgba(0, 255, 65, 0.6);
}

/* Inputs */
.stTextInput input,
.stTextArea textarea,
.stSelectbox > div > div {
    background: #0a0a0a !important;
    color: #e8e8e8 !important;
    border: 1px solid #333 !important;
    border-radius: 0 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #ffb000 !important;
    box-shadow: 0 0 10px rgba(255, 176, 0, 0.3) !important;
}

/* Metrics */
[data-testid="stMetricValue"] {
    color: #00ff41 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}

[data-testid="stMetricLabel"] {
    color: #808080 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem !important;
}

[data-testid="stMetricDelta"] {
    color: #ffb000 !important;
}

/* Tables */
.stDataFrame {
    background: #0d1f2d !important;
    border: 1px solid #00d4d4 !important;
}

.stDataFrame table {
    background: #0d1f2d !important;
    color: #e8e8e8 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

.stDataFrame thead {
    background: #1a4d5c !important;
}

.stDataFrame thead th {
    color: #00d4d4 !important;
    text-transform: uppercase !important;
    font-weight: 700 !important;
    border-bottom: 2px solid #ffb000 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #0d1f2d;
    border-bottom: 2px solid #00d4d4;
    gap: 0;
}

.stTabs [data-baseweb="tab"] {
    background: #0a1620;
    color: #808080;
    border-radius: 0;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.75rem 1.5rem;
    border-right: 1px solid #1a4d5c;
}

.stTabs [aria-selected="true"] {
    background: #00d4d4 !important;
    color: #0a1620 !important;
    font-weight: 700;
}

/* Alerts */
.stAlert {
    background: #0d1f2d !important;
    border-left: 4px solid #00d4d4 !important;
    border-radius: 0 !important;
    color: #e8e8e8 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

div[data-testid="stAlert"][kind="success"] {
    border-left-color: #00ff41 !important;
}

div[data-testid="stAlert"][kind="error"] {
    border-left-color: #ff3838 !important;
}

div[data-testid="stAlert"][kind="warning"] {
    border-left-color: #ffb000 !important;
}

div[data-testid="stAlert"][kind="info"] {
    border-left-color: #00d4ff !important;
}

/* Radio buttons */
.stRadio > div {
    background: #0a0a0a;
    border: 1px solid #333;
    border-radius: 0;
    padding: 0.5rem;
}

.stRadio label {
    color: #e8e8e8 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Dividers */
hr {
    border-color: #1a4d5c !important;
    margin: 1.5rem 0 !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background: #0d1f2d !important;
    color: #00d4d4 !important;
    font-family: 'JetBrains Mono', monospace !important;
    border: 1px solid #1a4d5c !important;
    border-radius: 0 !important;
}

/* Custom terminal block */
.terminal-block {
    background: #0d1f2d;
    border: 1px solid #00d4d4;
    padding: 1rem;
    font-family: 'JetBrains Mono', monospace;
    color: #00ff41;
    font-size: 0.85rem;
    line-height: 1.6;
    box-shadow: inset 0 0 30px rgba(0, 212, 212, 0.05);
}

/* Cost widget */
.cost-widget {
    background: linear-gradient(135deg, #0d1f2d, #1a4d5c);
    border: 1px solid #00d4d4;
    padding: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #e8e8e8;
}

.cost-label { color: #808080; text-transform: uppercase; font-size: 0.65rem; }
.cost-value { color: #00ff41; font-weight: 700; font-size: 1rem; }
.cost-amber { color: #ffb000; }

/* Code blocks */
code {
    background: #1a1a1a !important;
    color: #ffb000 !important;
    border: 1px solid #333 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Sidebar header */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #00d4d4 !important;
    border-bottom: 2px solid #00d4d4;
    padding-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Streaming agent log */
.agent-log {
    background: #000000;
    color: #00ff41;
    padding: 1rem;
    border: 1px solid #00ff41;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    max-height: 400px;
    overflow-y: auto;
    box-shadow: 0 0 20px rgba(0, 255, 65, 0.1);
}

.agent-log .timestamp { color: #808080; }
.agent-log .agent-name { color: #ffb000; font-weight: 700; }
.agent-log .success { color: #00ff41; }
.agent-log .error { color: #ff3838; }
.agent-log .pending { color: #00d4ff; }

/* Header / logo */
.brand-header {
    border: 2px solid #00d4d4;
    background: linear-gradient(135deg, #0d1f2d, #1a3d4d);
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    border-radius: 4px;
    box-shadow: 0 0 15px rgba(0, 212, 212, 0.2);
}

.brand-logo {
    width: 60px;
    height: 60px;
    border: 2px solid #ffb000;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #00d4d4;
    font-weight: 700;
    font-size: 1.2rem;
    background: linear-gradient(135deg, #1a4d5c, #0d2d3d);
    border-radius: 4px;
}

.brand-logo img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 4px;
}

.brand-title {
    font-size: 1.1rem;
    color: #00d4d4;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.brand-subtitle {
    font-size: 0.75rem;
    color: #ffb000;
    letter-spacing: 0.03em;
}

/* Score badges */
.score-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    border: 1px solid;
    font-size: 0.8rem;
}

.score-strong { color: #00ff41; border-color: #00ff41; background: rgba(0, 255, 65, 0.1); }
.score-mid { color: #ffb000; border-color: #ffb000; background: rgba(255, 176, 0, 0.1); }
.score-weak { color: #ff3838; border-color: #ff3838; background: rgba(255, 56, 56, 0.1); }

/* Plotly chart container */
.js-plotly-plot {
    background: #000000 !important;
}

#MainMenu {visibility: hidden;}
header[data-testid="stHeader"] {visibility: hidden; height: 0 !important; min-height: 0 !important;}
footer {visibility: hidden;}

/* Prevent sidebar from collapsing:
   Streamlit "collapse" = translateX(-300px) + width:2px
   Override both so the sidebar is always visible */
section[data-testid="stSidebar"] {
    transform: none !important;
    transition: none !important;
    width: 300px !important;
    min-width: 300px !important;
}

/* Hide the collapse button — users can never trigger the hidden state */
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

.insight-box {
    border: 1px solid #1f1f1f;
    border-radius: 2px;
    padding: 0.75rem;
    margin-top: 0.4rem;
}

.insight-box ul {
    margin: 0.4rem 0 0 1.1rem;
    padding: 0;
}

.insight-title {
    font-weight: 700;
    color: #000000;
}

.strength-box {
    background: #ecfaef;
    color: #000000;
}

.gap-box {
    background: #fdeeee;
    color: #000000;
}
</style>
"""

st.markdown(BLOOMBERG_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR :: ADD JOB (RENDER EARLY)
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### ▶ INGEST JOB")

    user_input = st.text_area(
        "URL OR JD TEXT",
        height=140,
        placeholder=">> paste URL or full JD text...",
        key="job_input",
    )

    force_letter = st.checkbox("FORCE COVER LETTER", value=False)

    stream_mode = st.checkbox("LIVE STREAM AGENTS", value=True,
                              help="Show each agent firing in real time")

    if st.button("▶▶ EXECUTE PIPELINE", type="primary", use_container_width=True):
        if not user_input.strip():
            st.warning("⚠ NO INPUT PROVIDED")
        else:
            # Live streaming output panel
            log_placeholder = st.empty()
            log_lines = []

            def log(msg, level="info"):
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                color = {
                    "info": "#00d4ff",
                    "success": "#00ff41",
                    "error": "#ff3838",
                    "pending": "#ffb000",
                }.get(level, "#e8e8e8")
                log_lines.append(
                    f'<span class="timestamp">[{ts}]</span> '
                    f'<span style="color:{color}">{msg}</span>'
                )
                log_placeholder.markdown(
                    f'<div class="agent-log">{"<br>".join(log_lines)}</div>',
                    unsafe_allow_html=True,
                )

            log("⚡ Pipeline initiated", "pending")

            if stream_mode:
                final_state = {}
                try:
                    for node_name, update in process_job_streaming(
                        user_input, force_letter=force_letter
                    ):
                        if update is None:
                            log(f"▸ {node_name.upper()} :: ⚠ EMPTY UPDATE", "pending")
                            continue
                        if not isinstance(update, dict):
                            log(f"▸ {node_name.upper()} :: ⚠ INVALID UPDATE", "pending")
                            continue
                        emoji = {
                            "scraper": "🌐",
                            "scorer": "📊",
                            "cv_selector": "🎯",
                            "cover_letter": "✉️",
                            "evaluator": "⚖️",
                            "save": "💾",
                        }.get(node_name, "▸")

                        if update.get("error"):
                            log(f"{emoji} {node_name.upper()} :: ❌ {update['error']}", "error")
                        else:
                            details = []
                            if node_name == "scraper" and update.get("title"):
                                details.append(f"title={update['title'][:40]}")
                                details.append(f"company={update.get('company', '?')}")
                            elif node_name == "scorer":
                                details.append(f"score={update.get('overall_score')}/100")
                                details.append(f"cv=CV-{update.get('recommended_cv')}")
                            elif node_name == "cv_selector":
                                details.append(f"selected=CV-{update.get('selected_cv')}")
                                details.append(f"conf={update.get('cv_confidence')}%")
                            elif node_name == "cover_letter":
                                if update.get('cover_letter'):
                                    details.append(f"words={update.get('cover_letter_words')}")
                                    details.append(f"tone={update.get('letter_tone')}")
                                else:
                                    details.append("SKIPPED")
                            elif node_name == "evaluator":
                                if update.get('eval_recommendation'):
                                    details.append(f"action={update.get('eval_recommendation')}")
                            elif node_name == "save":
                                details.append(f"job_id={update.get('job_id')}")

                            time_ms = next(
                                (v for k, v in update.items() if k.endswith("_time_ms") and v is not None),
                                None
                            )
                            time_str = f" [{time_ms}ms]" if time_ms else ""

                            log(f"{emoji} {node_name.upper()} :: ✓ {' | '.join(details)}{time_str}", "success")

                        final_state.update(update)

                    log("✅ PIPELINE COMPLETE", "success")
                    log_activity("scored", job_id=final_state.get("job_id"))
                    time.sleep(1)
                    st.rerun()

                except Exception as e:
                    log(f"❌ FATAL ERROR :: {e}", "error")
            else:
                with st.spinner("EXECUTING..."):
                    result = process_job(user_input, force_letter=force_letter)
                if not result:
                    st.error("ERR :: Pipeline returned no result. Please retry.")
                elif result.get("error"):
                    st.error(f"ERR :: {result['error']}")
                else:
                    log_activity("scored", job_id=result.get("job_id"))
                    st.success(f"✓ {result.get('overall_score')}/100 :: CV-{result.get('selected_cv')}")
                    st.rerun()

    st.markdown("---")

    # Follow-up alerts
    followups = analytics.get_followup_suggestions()
    if followups:
        st.markdown(f"### ⚠ FOLLOWUPS :: {len(followups)}")
        for f in followups[:5]:
            st.markdown(
                f'<div style="padding: 0.3rem; border-left: 2px solid #ff3838; font-size: 0.75rem;">'
                f'<b style="color:#ffb000;">{f["name"]}</b><br>'
                f'<span style="color:#808080;">{f["role"]} :: {f["days_ago"]}d ago</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown(
        '<div style="font-size: 0.7rem; color: #808080;">'
        'AUTOAPPLY :: TERMINAL<br>'
        'BUILD 1.0 :: 2026<br>'
        '<a href="https://github.com/ghazalkasalaee/autoapply-ai" style="color:#00d4ff;">SOURCE</a>'
        '</div>',
        unsafe_allow_html=True,
    )




# ══════════════════════════════════════════════════════════════════════════════
#  MAIN CONTENT AREA
# ══════════════════════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════════════════════
#  HEADER + COST WIDGET
# ══════════════════════════════════════════════════════════════════════════════

header_col1, header_col2 = st.columns([3, 1])

with header_col1:
    st.markdown("""
    <div class="brand-header">
        <div>
            <div class="brand-title">⚙ AUTOAPPLY AI</div>
            <div class="brand-subtitle">Job Search Copilot · Pipeline + CV Tailoring + Outreach</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with header_col2:
    cost_data = get_cost_summary()
    st.markdown(f"""
    <div class="cost-widget">
        <div class="cost-label">SYS :: COST METER</div>
        <div style="margin-top: 0.3rem;">
            <span class="cost-label">TODAY</span>
            <span class="cost-value">${cost_data['today_cost']:.4f}</span>
        </div>
        <div>
            <span class="cost-label">WEEK</span>
            <span class="cost-amber">${cost_data['week_cost']:.4f}</span>
        </div>
        <div>
            <span class="cost-label">CALLS</span>
            <span class="cost-amber">{cost_data['total_calls']}</span>
            <span class="cost-label">| TOKENS</span>
            <span class="cost-amber">{cost_data['total_tokens']:,}</span>
        </div>
        <div>
            <span class="cost-label">UPTIME</span>
            <span class="cost-value">{cost_data['success_rate']}%</span>
            <span class="cost-label">| LAT</span>
            <span class="cost-amber">{cost_data['avg_latency_ms']}ms</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW SELECTOR
# ══════════════════════════════════════════════════════════════════════════════

view = st.radio(
    "VIEW",
    ["▣ PIPELINE", "▦ ANALYTICS", "▤ ACTIVITY", "▥ OUTREACH"],
    horizontal=True,
    label_visibility="collapsed",
)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR :: ADD JOB
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  VIEW 1 :: PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

if view == "▣ PIPELINE":
    df = analytics.get_jobs_df()

    if df.empty:
        st.info("▶ NO JOBS IN DATABASE. INGEST ONE VIA SIDEBAR →")
    else:
        # KPI Row
        st.markdown("### ▦ STATUS BOARD")
        cols = st.columns(6)
        for i, status in enumerate(analytics.STATUS_ORDER):
            count = int((df["status"] == status).sum())
            with cols[i]:
                st.metric(status.replace("_", " ").upper(), count)

        st.markdown("---")

        # Job table
        st.markdown(f"### ▤ JOB LEDGER :: {len(df)} ROWS")
        display = df.copy()
        display["score_display"] = display["score"].apply(lambda s: f"{int(s)}/100")
        display["letter"] = display["has_letter"].apply(lambda x: "✓" if x else "—")
        display["created_str"] = display["created"].apply(
            lambda d: d.strftime("%m/%d") if pd.notna(d) else ""
        )

        table_df = display[["score_display", "company", "title", "cv", "letter", "status", "created_str"]].copy()
        table_df.columns = ["FIT SCORE", "COMPANY", "TITLE", "CV", "LETTER", "STATUS", "ADDED"]
        st.dataframe(table_df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("▼ EXPORT CSV", csv, f"autoapply_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        with c2:
            json_bytes = df.to_json(orient="records", indent=2, date_format="iso").encode("utf-8")
            st.download_button("▼ EXPORT JSON", json_bytes, f"autoapply_{datetime.now().strftime('%Y%m%d')}.json", "application/json")

        st.markdown("---")

        # Job detail
        st.markdown("### ▶ JOB DETAIL")

        s = get_session()
        try:
            jobs = s.query(Job).order_by(Job.overall_score.desc()).all()
        finally:
            s.close()

        labels = [
            f"[{j.overall_score or 0:3d}] {j.company or 'Unknown'} :: {(j.title or 'Untitled')[:50]}"
            for j in jobs
        ]
        picked_label = st.selectbox("SELECT JOB", labels)
        picked = jobs[labels.index(picked_label)]

        score_data = json.loads(picked.scoring_json) if picked.scoring_json else {}

        # Detail tabs
        t1, t2, t3, t4, t5 = st.tabs(["▸ SCORE", "▸ LETTER", "▸ OUTREACH", "▸ CALENDAR", "▸ EDIT"])

        # Tab: Score
        with t1:
            response_statuses = {"phone_screen", "interview", "offer"}
            response_probability = 100 if (picked.status in response_statuses) else min(95, max(5, int((picked.overall_score or 0) * 0.85)))

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("SCORE", f"{picked.overall_score}/100")
            c2.metric("CV", f"CV-{picked.recommended_cv or '?'}")
            c3.metric("APPLY", "YES" if picked.should_apply else "NO")
            c4.metric("STATUS", (picked.status or "new").upper())
            c5.metric("RESPONSE PROB", f"{response_probability}%")

            if score_data.get("one_line_pitch"):
                st.markdown(f"**PITCH**: {score_data['one_line_pitch']}")

            cc1, cc2 = st.columns(2)
            with cc1:
                strengths = score_data.get("top_strengths", [])
                strengths_html = "".join(f"<li>{html.escape(item)}</li>" for item in strengths) or "<li>No strengths captured yet.</li>"
                st.markdown(
                    f'<div class="insight-box strength-box"><div class="insight-title">STRENGTHS</div><ul>{strengths_html}</ul></div>',
                    unsafe_allow_html=True,
                )
            with cc2:
                concerns = score_data.get("top_concerns", [])
                concerns_html = "".join(f"<li>{html.escape(item)}</li>" for item in concerns) or "<li>No gaps captured yet.</li>"
                st.markdown(
                    f'<div class="insight-box gap-box"><div class="insight-title">GAPS</div><ul>{concerns_html}</ul></div>',
                    unsafe_allow_html=True,
                )

            if picked.url:
                st.markdown(f"🔗 [SOURCE :: {picked.url[:60]}]({picked.url})")
            if (picked.overall_score or 0) >= 70:
                st.success("This JD is strong enough for tailoring. Focus on the highlighted gaps and ATS keywords below.")
            else:
                st.warning("This JD is a weaker match. Tailor cautiously or consider using a closer CV version first.")
            st.markdown("---")
            st.markdown("### 🛠 DYNAMIC TAILORING")
            st.info("""
            **Why Dynamic Tailoring?** Customize your CV for each JD to:
            - ✓ Boost ATS keyword match score (improves screening pass rate)
            - ✓ Reorder experience sections to highlight relevant projects first
            - ✓ Add missing technical keywords naturally
            - ✓ Export ready-to-send LaTeX CV

            **Auto-fill** will extract keywords from the JD and suggest ATS optimizations.
            """)
            
            # Auto-fill section
            st.markdown("#### 🤖 AUTO-FILL (Click button to populate fields from JD)")
            auto_fill_cols = st.columns([2, 1])
            with auto_fill_cols[0]:
                auto_fill_requested = st.checkbox("Enable auto-fill from JD", value=False, key=f"autofill_{picked.id}")
            with auto_fill_cols[1]:
                auto_fill_btn = st.button("🔄 AUTO-FILL NOW", key=f"autofill_btn_{picked.id}", use_container_width=True)
            
            # Initialize auto-fill state
            autofill_data = None
            if auto_fill_requested and auto_fill_btn:
                with st.spinner("Analyzing JD and extracting optimization suggestions..."):
                    sample_cv = load_sample_cv("data/cv_example.txt")
                    autofill_data = generate_auto_tailoring_suggestion(picked.description or "", sample_cv)
            
            with st.form(f"tailor_tex_{picked.id}"):
                st.caption("Edit specific CV aspects for this JD, then export a tailored `.tex` file.")
                summary_override = st.text_area(
                    "SUMMARY (optional override)",
                    placeholder="Write a JD-aligned summary version...",
                    value=autofill_data.get('summary_hint', '') if autofill_data else "",
                    height=90,
                )
                prioritized_projects_raw = st.text_area(
                    "PROJECT ORDER PRIORITY (one per line)",
                    placeholder="Fraud Detection Platform\nMLOps Automation Toolkit",
                    value="\n".join(autofill_data.get('projects_hint', [])) if autofill_data else "",
                    height=80,
                )
                ats_keywords_raw = st.text_area(
                    "ATS KEYWORDS (comma/newline separated)",
                    placeholder="python, llm, rag, langgraph, aws",
                    value=autofill_data.get('ats_keywords_str', '') if autofill_data else "",
                    height=80,
                )
                extra_instructions = st.text_area(
                    "EXTRA INSTRUCTIONS (optional)",
                    placeholder="Keep concise, achievement-first bullets.",
                    height=70,
                )

                source_mode = st.radio(
                    "BASE LATEX SOURCE",
                    ["Use file path", "Upload .tex", "Paste LaTeX"],
                    horizontal=True,
                    key=f"source_mode_{picked.id}",
                )

                base_tex_path_input = ""
                uploaded_tex = None
                selected_uploaded_name = ""
                pasted_tex = ""

                if source_mode == "Use file path":
                    base_tex_path_input = st.text_input(
                        "LATEX FILE PATH",
                        value="data/base_cv.tex",
                        key=f"base_tex_path_{picked.id}",
                    )
                elif source_mode == "Upload .tex":
                    uploaded_tex = st.file_uploader(
                        "UPLOAD ONE OR MORE LATEX FILES",
                        type=["tex"],
                        accept_multiple_files=True,
                        key=f"upload_tex_{picked.id}",
                    )
                    if uploaded_tex:
                        selected_uploaded_name = st.selectbox(
                            "SELECT LATEX FILE TO TAILOR",
                            [item.name for item in uploaded_tex],
                            key=f"selected_upload_{picked.id}",
                        )
                else:
                    pasted_tex = st.text_area(
                        "PASTE LATEX",
                        placeholder="\\documentclass...",
                        height=180,
                        key=f"paste_tex_{picked.id}",
                    )

                generate_tex = st.form_submit_button("▶ GENERATE TAILORED .TEX CV", type="primary")

            if generate_tex:
                base_tex = ""
                if source_mode == "Use file path":
                    candidate_path = Path(base_tex_path_input)
                    if not candidate_path.exists():
                        st.error(f"⚠ File not found: {candidate_path}")
                    else:
                        base_tex = candidate_path.read_text(encoding="utf-8")
                elif source_mode == "Upload .tex":
                    if not uploaded_tex:
                        st.error("⚠ Please upload a `.tex` file.")
                    else:
                        chosen_file = next((item for item in uploaded_tex if item.name == selected_uploaded_name), uploaded_tex[0])
                        base_tex = chosen_file.getvalue().decode("utf-8", errors="ignore")
                else:
                    if not pasted_tex.strip():
                        st.error("⚠ Please paste LaTeX content.")
                    else:
                        base_tex = pasted_tex

                if base_tex:
                    prioritized_projects = [line.strip() for line in prioritized_projects_raw.splitlines() if line.strip()]
                    ats_keywords = [token.strip() for token in ats_keywords_raw.replace("\n", ",").split(",") if token.strip()]

                    with st.spinner("Optimizing ATS keywords and ordering sections..."):
                        tailored = tailor_latex_cv(
                            picked.description or "",
                            base_tex,
                            summary_override=summary_override.strip() or None,
                            prioritized_projects=prioritized_projects,
                            ats_keywords=ats_keywords,
                            extra_instructions=extra_instructions.strip() or None,
                        )
                        st.success("✓ Tailored LaTeX ready")
                        if tailored.modifications_made:
                            st.markdown("**Applied modifications**")
                            for change in tailored.modifications_made:
                                st.markdown(f"- {change}")
                        if tailored.section_adjustments:
                            st.markdown("**Section adjustments**")
                            for section_note in tailored.section_adjustments:
                                st.markdown(f"- {section_note}")
                        if tailored.plain_text_summary:
                            st.text_area(
                                "PLAIN-TEXT CHANGE SUMMARY",
                                value=tailored.plain_text_summary,
                                height=160,
                                key=f"plain_text_summary_{picked.id}",
                            )
                        st.download_button(
                            label="▼ DOWNLOAD .TEX",
                            data=tailored.latex_code,
                            file_name=f"cv_{(picked.company or 'target').replace(' ', '_')}.tex",
                            mime="text/plain",
                            key=f"download_tailored_tex_{picked.id}",
                        )
                        st.download_button(
                            label="▼ DOWNLOAD CHANGE NOTES .TXT",
                            data=tailored.plain_text_summary or "",
                            file_name=f"cv_{(picked.company or 'target').replace(' ', '_')}_notes.txt",
                            mime="text/plain",
                            key=f"download_tailored_txt_{picked.id}",
                        )
        # Tab: Letter
        with t2:
            if picked.cover_letter:
                st.text_area("COVER LETTER", picked.cover_letter, height=380, key=f"l_{picked.id}")

                cc1, cc2 = st.columns(2)
                cc1.metric("WORDS", picked.cover_letter_words or 0)
                cc2.metric("KEYWORD MATCH", f"{int((picked.keyword_overlap_pct or 0) * 100)}%")

                if picked.eval_recommendation:
                    color = {
                        "send_as_is": "success",
                        "revise_minor": "warning",
                        "rewrite": "error",
                    }.get(picked.eval_recommendation, "info")
                    icon = {
                        "send_as_is": "✅",
                        "revise_minor": "⚠️",
                        "rewrite": "❌",
                    }.get(picked.eval_recommendation, "ℹ️")
                    st.markdown(f"**{icon} EVAL VERDICT :: {picked.eval_recommendation.upper().replace('_', ' ')}**")

                if st.button("◀ REGENERATE", key=f"regen_{picked.id}"):
                    with st.spinner("REWRITING..."):
                        new_l = write_cover_letter(
                            job_description=picked.description or "",
                            title=picked.title or "Role",
                            company=picked.company or "Company",
                            selected_cv=picked.recommended_cv or "GENAI",
                            overall_score=picked.overall_score or 75,
                            top_strengths=score_data.get("top_strengths", []),
                            top_concerns=score_data.get("top_concerns", []),
                            one_line_pitch=score_data.get("one_line_pitch", ""),
                        )
                        ss = get_session()
                        try:
                            dbj = ss.get(Job, picked.id)
                            dbj.cover_letter = new_l.letter_text
                            dbj.cover_letter_words = new_l.word_count
                            ss.commit()
                            st.rerun()
                        finally:
                            ss.close()
            else:
                st.info("▶ NO LETTER YET")
                if st.button("▶ GENERATE NOW", type="primary"):
                    with st.spinner("WRITING..."):
                        new_l = write_cover_letter(
                            job_description=picked.description or "",
                            title=picked.title or "Role",
                            company=picked.company or "Company",
                            selected_cv=picked.recommended_cv or "GENAI",
                            overall_score=picked.overall_score or 75,
                            top_strengths=score_data.get("top_strengths", []),
                            top_concerns=score_data.get("top_concerns", []),
                            one_line_pitch=score_data.get("one_line_pitch", ""),
                        )
                        ss = get_session()
                        try:
                            dbj = ss.get(Job, picked.id)
                            dbj.cover_letter = new_l.letter_text
                            dbj.cover_letter_words = new_l.word_count
                            ss.commit()
                            st.rerun()
                        finally:
                            ss.close()

        # Tab: Outreach
        with t3:
            st.markdown("**▶ ADD CONTACT**")
            with st.form(f"contact_{picked.id}"):
                cn1, cn2 = st.columns(2)
                with cn1:
                    c_name = st.text_input("NAME", placeholder="Sarah Chen")
                with cn2:
                    c_role = st.text_input("ROLE", placeholder="Recruiter")
                c_ctx = st.text_input("CONTEXT", placeholder="Polytechnique alum / mutual friend / saw post on ___")
                submitted = st.form_submit_button("▶ GENERATE 3 VARIANTS")

            if submitted and c_name:
                with st.spinner("WRITING VARIANTS..."):
                    bundle = write_outreach(
                        recipient_name=c_name, recipient_role=c_role,
                        job_company=picked.company or "", job_title=picked.title or "",
                        selected_cv=picked.recommended_cv or "GENAI",
                        overall_score=picked.overall_score or 75,
                        context=c_ctx,
                    )
                    ss = get_session()
                    try:
                        contact = OutreachContact(
                            job_id=picked.id, name=c_name, role=c_role,
                            context_note=c_ctx, messages_json=bundle.model_dump_json(),
                        )
                        ss.add(contact)
                        ss.commit()
                        log_activity("outreach", job_id=picked.id)
                        st.rerun()
                    finally:
                        ss.close()

            # Existing contacts
            ss = get_session()
            try:
                contacts = ss.query(OutreachContact).filter_by(job_id=picked.id).all()
            finally:
                ss.close()

            if contacts:
                st.markdown("---")
                st.markdown(f"**▶ CONTACTS :: {len(contacts)}**")
                for c in contacts:
                    with st.expander(f"▸ {c.name} :: {c.role or 'N/A'}"):
                        if c.messages_json:
                            bundle = json.loads(c.messages_json)
                            for v in bundle.get("variants", []):
                                st.markdown(f"**[{v['tone'].upper()}]** :: {v['char_count']}c :: _{v['best_for']}_")
                                st.text_area("", v["message_text"], height=110,
                                             key=f"m_{c.id}_{v['tone']}", label_visibility="collapsed")

                        mc1, mc2, mc3 = st.columns(3)
                        with mc1:
                            if not c.sent_at:
                                if st.button("▶ MARK SENT", key=f"s_{c.id}"):
                                    ss = get_session()
                                    try:
                                        dbc = ss.get(OutreachContact, c.id)
                                        dbc.sent_at = datetime.utcnow()
                                        ss.commit()
                                        st.rerun()
                                    finally:
                                        ss.close()
                            else:
                                d = (datetime.utcnow() - c.sent_at).days
                                st.caption(f"SENT {d}d AGO")
                        with mc2:
                            if c.sent_at and not c.responded:
                                if st.button("✓ RESPONDED", key=f"r_{c.id}"):
                                    ss = get_session()
                                    try:
                                        dbc = ss.get(OutreachContact, c.id)
                                        dbc.responded = True
                                        dbc.response_at = datetime.utcnow()
                                        ss.commit()
                                        st.rerun()
                                    finally:
                                        ss.close()
                            elif c.responded:
                                st.success("REPLIED")
                        with mc3:
                            if c.sent_at and not c.responded:
                                if st.button("📅 FOLLOW-UP .ICS", key=f"f_{c.id}"):
                                    ss = get_session()
                                    try:
                                        dbc = ss.get(OutreachContact, c.id)
                                        dbj = ss.get(Job, dbc.job_id)
                                        fp = generate_followup_ics(dbc, dbj)
                                        with open(fp, "rb") as f:
                                            st.download_button("▼ DOWNLOAD", f.read(),
                                                               file_name=fp.name, mime="text/calendar",
                                                               key=f"dl_f_{c.id}")
                                    finally:
                                        ss.close()

        # Tab: Calendar
        with t4:
            st.markdown("### ▶ CALENDAR EVENTS")
            st.markdown("Auto-sync to Google Calendar if OAuth is configured, or download `.ics` for manual import.")

            from src.calendar_utils import (
                google_calendar_setup_status,
                save_google_oauth_credentials,
                push_to_google_calendar,
            )

            setup_ok, setup_message = google_calendar_setup_status()
            if setup_ok:
                st.success(setup_message)
            else:
                st.warning(setup_message)

            with st.expander("ℹ️ Setup Google Calendar (optional)"):
                st.markdown(
                    """
You need **both** a Client ID and Client Secret for Google Calendar OAuth.

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Google Calendar API**
4. Create an **OAuth 2.0 Client ID** for a **Desktop app**
5. Copy the Client ID and Client Secret into the form below
6. Save `credentials.json` in the project root
7. Restart the app and approve the browser login
                    """
                )

                client_id = st.text_input("CLIENT ID", value="", key=f"gc_client_id_{picked.id}")
                client_secret = st.text_input("CLIENT SECRET", value="", type="password", key=f"gc_client_secret_{picked.id}")
                project_id = st.text_input("PROJECT ID", value="AutoApply AI", key=f"gc_project_id_{picked.id}")
                pasted_json = st.text_area(
                    "OR PASTE FULL OAuth JSON HERE",
                    value="",
                    height=120,
                    key=f"gc_json_{picked.id}",
                    placeholder='{"installed": {...}}',
                )

                save_left, save_right = st.columns(2)
                with save_left:
                    if st.button("SAVE CREDENTIALS.JSON", key=f"save_gc_{picked.id}"):
                        try:
                            if pasted_json.strip():
                                creds_payload = json.loads(pasted_json)
                                if not isinstance(creds_payload, dict):
                                    raise ValueError("OAuth JSON must be an object.")
                                creds_path = Path("credentials.json")
                                creds_path.write_text(json.dumps(creds_payload, indent=2), encoding="utf-8")
                                st.success(f"Saved {creds_path}")
                            else:
                                if not client_id.strip() or not client_secret.strip():
                                    raise ValueError("Client ID and Client Secret are required if you are not pasting JSON.")
                                creds_path = save_google_oauth_credentials(client_id, client_secret, project_id)
                                st.success(f"Saved {creds_path}")
                            st.info("Restart the app, then try syncing again.")
                        except Exception as e:
                            st.error(f"Could not save credentials.json: {e}")
                with save_right:
                    st.caption("If you only have a Client ID, you still need the Client Secret for OAuth to work.")

            cal_c1, cal_c2 = st.columns(2)

            with cal_c1:
                st.markdown("**📋 APPLICATION REMINDER**")
                days_ahead = st.number_input("Days from now", min_value=1, max_value=30, value=2, key=f"days_{picked.id}")
                if st.button("▶ SYNC TO CALENDAR", key=f"gen_app_{picked.id}"):
                    with st.spinner("Creating calendar event..."):
                        fp = generate_application_ics(picked, days_ahead=days_ahead)
                        
                        # Try Google Calendar auto-sync
                        from src.calendar_utils import push_to_google_calendar
                        reminder_dt = (datetime.now() + timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0, microsecond=0)
                        
                        google_event_id = push_to_google_calendar(
                            title=f"📋 Apply: {picked.company or 'Unknown'} — {picked.title or 'Job'}",
                            description=f"Score: {picked.overall_score}/100\\nCV: CV-{picked.recommended_cv or 'GENAI'}\\nURL: {picked.url or 'N/A'}",
                            start_dt=reminder_dt,
                            end_dt=reminder_dt + timedelta(minutes=30),
                        )
                    
                    if google_event_id:
                        st.success(f"✅ Synced to Google Calendar")
                    else:
                        st.info(f"📥 Google Calendar unavailable—{setup_message}. Download .ics to import manually")
                    
                    with open(fp, "rb") as f:
                        st.download_button("▼ DOWNLOAD .ICS", f.read(),
                                           file_name=fp.name, mime="text/calendar",
                                           key=f"dl_app_{picked.id}")
                    st.success(f"✓ Event for {(datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')}")

            with cal_c2:
                st.markdown("**🎤 INTERVIEW**")
                int_date = st.date_input("Date", value=datetime.now().date() + timedelta(days=7), key=f"id_{picked.id}")
                int_time = st.time_input("Time", value=datetime.now().time().replace(hour=14, minute=0), key=f"it_{picked.id}")
                duration = st.selectbox("Duration", [30, 45, 60, 90, 120], index=2, key=f"dur_{picked.id}")
                interviewer = st.text_input("Interviewer name", key=f"int_{picked.id}")

                if st.button("▶ SYNC TO CALENDAR", key=f"gen_int_{picked.id}"):
                    with st.spinner("Creating interview event..."):
                        int_dt = datetime.combine(int_date, int_time)
                        fp = generate_interview_ics(picked, int_dt, duration, interviewer=interviewer)
                        
                        # Try Google Calendar auto-sync
                        from src.calendar_utils import push_to_google_calendar
                        google_event_id = push_to_google_calendar(
                            title=f"🎤 Interview: {picked.company or 'Unknown'} — {picked.title or 'Role'}",
                            description=f"Interviewer: {interviewer}\\nDuration: {duration} min\\nScore: {picked.overall_score}/100\\nCV: CV-{picked.recommended_cv or 'GENAI'}",
                            start_dt=int_dt,
                            end_dt=int_dt + timedelta(minutes=duration),
                        )
                    
                    if google_event_id:
                        st.success(f"✅ Synced to Google Calendar")
                    else:
                        st.info(f"📥 Google Calendar unavailable—{setup_message}. Download .ics to import manually")
                    
                    with open(fp, "rb") as f:
                        st.download_button("▼ DOWNLOAD .ICS", f.read(),
                                           file_name=fp.name, mime="text/calendar",
                                           key=f"dl_int_{picked.id}")
                    st.success(f"✓ Interview scheduled :: {int_dt.strftime('%Y-%m-%d %H:%M')}")

        # Tab: Edit
        with t5:
            with st.form(f"edit_{picked.id}"):
                nt = st.text_input("TITLE", value=picked.title or "")
                nc = st.text_input("COMPANY", value=picked.company or "")
                nu = st.text_input("URL", value=picked.url or "")
                nn = st.text_area("NOTES", value=picked.notes or "", height=120)
                ns = st.selectbox("STATUS", analytics.STATUS_ORDER,
                                  index=analytics.STATUS_ORDER.index(picked.status) if picked.status in analytics.STATUS_ORDER else 0)
                nd = st.date_input("DEADLINE", value=picked.deadline.date() if picked.deadline else None)

                if st.form_submit_button("▶ SAVE"):
                    ss = get_session()
                    try:
                        dbj = ss.get(Job, picked.id)
                        dbj.title = nt
                        dbj.company = nc
                        dbj.url = nu
                        dbj.notes = nn
                        dbj.status = ns
                        if nd:
                            dbj.deadline = datetime.combine(nd, datetime.min.time())
                        if ns == "applied" and not dbj.applied_date:
                            dbj.applied_date = datetime.utcnow()
                            log_activity("applied", job_id=picked.id)
                        if ns in ("phone_screen", "interview") and not dbj.response_date:
                            dbj.response_date = datetime.utcnow()
                        ss.commit()
                        st.rerun()
                    finally:
                        ss.close()

            st.markdown("---")
            st.markdown("**Danger Zone**")
            confirm_delete = st.checkbox(
                "I understand this permanently deletes the selected job record.",
                key=f"confirm_delete_{picked.id}",
            )
            if st.button("DELETE JOB RECORD", type="primary", key=f"delete_job_{picked.id}"):
                if not confirm_delete:
                    st.error("Please confirm deletion first.")
                else:
                    delete_job_record(picked.id)
                    st.warning("Job deleted.")
                    time.sleep(0.8)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW 2 :: ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

elif view == "▦ ANALYTICS":
    df = analytics.get_jobs_df()

    if df.empty:
        st.info("▶ NO DATA YET")
    else:
        # KPI row
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("TOTAL", len(df))
        c2.metric("APPLIED", int((df["status"] != "new").sum()))
        c3.metric("RESPONSES", int(df["status"].isin(["phone_screen", "interview", "offer"]).sum()))
        c4.metric("AVG SCORE", f"{df['score'].mean():.1f}")
        c5.metric("STRONG FITS", int((df["score"] >= 75).sum()))

        st.markdown("---")
        st.markdown("### ▶ FIT + RESPONSE INSIGHTS")
        chart_c1, chart_c2 = st.columns(2)
        with chart_c1:
            st.plotly_chart(analytics.score_histogram(df), use_container_width=True, config={"displayModeBar": False})
        with chart_c2:
            st.plotly_chart(analytics.response_probability_chart(df), use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW 3 :: ACTIVITY (HEATMAP)
# ══════════════════════════════════════════════════════════════════════════════

elif view == "▤ ACTIVITY":
    st.markdown("### ▶ ACTIVITY HEATMAP")

    days = st.slider("DAYS BACK", min_value=30, max_value=180, value=90, step=15)
    st.plotly_chart(analytics.activity_heatmap(days_back=days), use_container_width=True,
                    config={"displayModeBar": False})

    st.markdown("---")

    # Cost summary
    cost_data = get_cost_summary()
    st.markdown("### ▶ SYSTEM USAGE")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TOTAL CALLS", cost_data['total_calls'])
    c2.metric("TOTAL TOKENS", f"{cost_data['total_tokens']:,}")
    c3.metric("TOTAL COST", f"${cost_data['total_cost']:.4f}")
    c4.metric("AVG LATENCY", f"{cost_data['avg_latency_ms']}ms")

    if cost_data["by_agent"]:
        st.markdown("---")
        st.markdown("### ▶ COST BY AGENT")
        agent_df = pd.DataFrame([
            {"AGENT": a.upper(), "CALLS": v["calls"], "TOKENS": v["tokens"],
             "COST": f"${v['cost']:.4f}", "AVG LATENCY": f"{v['avg_latency']}ms"}
            for a, v in cost_data["by_agent"].items()
        ])
        st.dataframe(agent_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW 4 :: OUTREACH
# ══════════════════════════════════════════════════════════════════════════════

elif view == "▥ OUTREACH":
    contacts_df = analytics.get_contacts_df()

    if contacts_df.empty:
        st.info("▶ NO OUTREACH CONTACTS. ADD VIA A JOB'S OUTREACH TAB →")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CONTACTS", len(contacts_df))
        sent = int(contacts_df["sent_at"].notna().sum())
        c2.metric("SENT", sent)
        resp = int(contacts_df["responded"].sum())
        c3.metric("RESPONDED", resp)
        rate = round(resp / sent * 100, 1) if sent else 0
        c4.metric("RESPONSE RATE", f"{rate}%")

        st.markdown("---")

        # Follow-ups
        followups = analytics.get_followup_suggestions()
        if followups:
            st.warning(f"⚠ {len(followups)} CONTACTS NEED FOLLOW-UP (>7 DAYS, NO RESPONSE)")
            for f in followups:
                st.markdown(f"  ▪ **{f['name']}** ({f['role']}) :: {f['days_ago']}d ago :: JOB #{f['job_id']}")
            st.markdown("---")

        st.markdown("### ▶ ALL CONTACTS")
        display = contacts_df[["name", "role", "context", "days_since_sent", "responded"]].copy()
        display.columns = ["NAME", "ROLE", "CONTEXT", "DAYS SENT", "REPLIED"]
        display["REPLIED"] = display["REPLIED"].map({True: "✓", False: "—"})
        st.dataframe(display, use_container_width=True, hide_index=True)

        csv = contacts_df.to_csv(index=False).encode("utf-8")
        st.download_button("▼ EXPORT CSV", csv,
                           f"contacts_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
