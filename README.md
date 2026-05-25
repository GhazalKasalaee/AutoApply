---
title: AutoApply AI
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: "1.57.0"
app_file: app.py
pinned: true
---

# AutoApply AI — Your AI Job-Application Copilot

> Turn a job post into a tailored CV, cover letter, and outreach plan in minutes. Built for fast, high-quality applications with clear analytics and zero fluff.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple)](https://github.com/langchain-ai/langgraph)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.57-red)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-ready-blue)](#docker)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENCE)

---

## Why It’s Useful

- **Speed without sacrificing quality**: Tailor content fast, with structured scoring and reviewer feedback.
- **End‑to‑end flow**: From job post → CV + cover letter → outreach + follow‑ups.
- **Built for scale**: Track cost, latency, and outcomes as you apply more.

---

## How It Works (3 Steps)

1. **Input a job post** (URL or raw description)
2. **AI evaluates fit + tailors content** (CV selection, letter, outreach)
3. **Review and export** (analytics, calendar, contact tracking)

---

## Pipeline Overview

Paste a job posting URL or raw JD text into the sidebar → a 6-node LangGraph pipeline fires in sequence:

```
JD Input
  └─► Scraper       — extracts title, company, description from URL or raw text
        └─► Scorer      — RAG over CV variants, LLM fit score (0–100) + strengths/gaps
              └─► CV Selector   — picks the best CV variant with confidence %
                    └─► Cover Letter  — drafts a tailored letter (optional, score-gated)
                          └─► Evaluator    — LLM-as-judge: send_as_is / revise_minor / rewrite
                                └─► Save        — persists to SQLite, logs cost + latency
```

The dashboard then shows:
- **Pipeline view** — job ledger, fit scores, per-job detail tabs (score breakdown, letter, outreach, calendar, edit)
- **Analytics view** — score histogram, response probability chart
- **Activity view** — heatmap, per-agent cost/token/latency breakdown
- **Outreach view** — contact manager, follow-up alerts, response tracking

---

## Who It’s For

- AI/ML engineers and researchers applying to competitive roles
- Professionals who apply at scale and need consistent quality
- Anyone who wants measurable, data‑driven job search output

## Key Design Decisions

| Choice | Why |
|---|---|
| LangGraph DAG | Explicit state transitions; each node isolated and testable |
| LLM-as-judge evaluator | No hardcoded rules — the model grades its own output |
| RAG over CV variants | Matches JD keywords against multiple CVs before scoring |
| SQLite + SQLAlchemy | Zero-infra persistence; portable for demos |
| Streaming callbacks | Real-time UI feedback without polling |
| Cost tracker | Per-agent token/latency logging — enterprise-grade observability |

---

## Stack

- **Orchestration**: LangGraph 0.2+, LangChain Core
- **LLM**: Google Gemini (via `google-generativeai`)
- **Vector DB**: ChromaDB + sentence-transformers
- **Frontend**: Streamlit 1.57, Plotly
- **Database**: SQLite via SQLAlchemy
- **Scraping**: Playwright, BeautifulSoup4
- **CLI**: Typer + Rich
- **Calendar**: Google Calendar API (optional OAuth)
- **Deploy**: Docker, Hugging Face Spaces

---

## Quick Start

```bash
git clone https://github.com/ghazalkasalaee/autoapply-ai.git
cd autoapply-ai

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your GEMINI_API_KEY to .env

streamlit run app.py
```

### CLI

```bash
python main.py status     # check config
python main.py load-cvs   # index CV variants into ChromaDB
python main.py demo       # run a sample JD through the pipeline
python main.py serve      # launch the Streamlit dashboard
```

---

## Docker

```bash
docker build -t autoapply-ai .
docker run -p 7860:7860 -e GEMINI_API_KEY=your_key autoapply-ai
```

---

## Project Structure

```
autoapply-ai/
├── app.py                  # Streamlit dashboard
├── main.py                 # Typer CLI
├── src/
│   ├── agents/
│   │   ├── graph.py        # LangGraph pipeline (6 nodes)
│   │   ├── scraper.py      # URL + raw-text JD extraction
│   │   ├── scorer.py       # RAG fit scoring
│   │   ├── cv_selector.py  # CV variant selection
│   │   ├── cover_letter.py # Letter generation
│   │   ├── evaluator.py    # LLM-as-judge
│   │   └── cv_tailor.py    # LaTeX CV tailoring
│   ├── db.py               # SQLAlchemy models + session
│   ├── analytics.py        # Plotly charts + KPI queries
│   ├── cost_tracker.py     # Per-agent cost/latency logging
│   ├── calendar_utils.py   # .ics export + Google Calendar OAuth
│   └── auto_tailor.py      # Auto-fill ATS keyword extraction
├── data/
│   └── cvs/                # CV variant templates (gitignored personal data)
├── Dockerfile
└── requirements.txt
```

---

## Roadmap

- Add multi‑language CV templates
- Improve ATS keyword coverage
- Add application outcome tracking

---

## Contributing

Issues and PRs are welcome. If you’re adding a feature, open a short proposal first so we align on scope.

---

