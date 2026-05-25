"""
AutoApply AI — Unified CLI Entry Point

Replaces 6 separate test scripts with a single, professional CLI.
Built with Typer (FastAPI-style for the command line).

Commands:
    python main.py score <job_url_or_text>      Score a single job
    python main.py serve                         Launch Streamlit dashboard
    python main.py load-cvs [--force]            Load CVs into ChromaDB
    python main.py test [--day N]                Run tests (all or specific day)
    python main.py demo                          Interactive guided demo
    python main.py export [--format csv|json]    Export job database
    python main.py stats                         Print pipeline analytics
    python main.py calendar <job_id>             Generate .ics for a job
    python main.py status                        System health check

Examples:
    python main.py score "https://jobs.example.com/role/123"
    python main.py serve --port 8502
    python main.py test --day 3
    python main.py demo
"""
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from rich import box

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

app = typer.Typer(
    name="autoapply",
    help="🎯 AutoApply AI — Multi-agent system for job application automation",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
)

console = Console()


# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = """
[bold #00ff41]
  ╔═══════════════════════════════════════════════════════╗
  ║       █████╗ ██╗   ██╗████████╗ ██████╗               ║
  ║      ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗              ║
  ║      ███████║██║   ██║   ██║   ██║   ██║              ║
  ║      ██╔══██║██║   ██║   ██║   ██║   ██║              ║
  ║      ██║  ██║╚██████╔╝   ██║   ╚██████╔╝              ║
  ║      ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝               ║
  ║         AUTOAPPLY AI ::  v1.0 ::  TERMINAL            ║
  ╚═══════════════════════════════════════════════════════╝
[/bold #00ff41]
"""


def show_banner():
    console.print(BANNER)


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def score(
    job_input: str = typer.Argument(..., help="Job URL or full JD text"),
    force_letter: bool = typer.Option(False, "--force-letter", "-f", help="Generate cover letter even if score < 70"),
    no_save: bool = typer.Option(False, "--no-save", help="Don't persist to database"),
):
    show_banner()

    from src.agents.graph import process_job

    with console.status("[bold #ffb000]Running 5-agent pipeline...[/]", spinner="dots"):
        result = process_job(job_input, force_letter=force_letter)

    if result.get("error"):
        console.print(f"[bold red]❌ Error:[/] {result['error']}")
        raise typer.Exit(1)

    # Render result as a table
    score_val = result.get("overall_score", 0)
    color = "#00ff41" if score_val >= 75 else "#ffb000" if score_val >= 55 else "#ff3838"

    table = Table(title=f"[bold {color}]Score: {score_val}/100[/]", box=box.DOUBLE)
    table.add_column("Field", style="dim", width=20)
    table.add_column("Value", style="bold")

    table.add_row("Company", result.get("company", "Unknown"))
    table.add_row("Title", result.get("title", "Unknown"))
    table.add_row("CV Selected", f"CV-{result.get('selected_cv', '?')}")
    table.add_row("CV Confidence", f"{result.get('cv_confidence', 0)}%")
    table.add_row("Should Apply", "✅ YES" if result.get("should_apply") else "❌ NO")
    table.add_row("Letter Words", str(result.get("cover_letter_words", 0)))
    table.add_row("Job ID", str(result.get("job_id", "—")))

    console.print(table)

    if result.get("one_line_pitch"):
        console.print(Panel(
            f"[italic]{result['one_line_pitch']}[/italic]",
            title="💬 One-line pitch",
            border_style=color,
        ))

    if result.get("cover_letter"):
        console.print(Panel(
            result["cover_letter"][:500] + "...",
            title="✉️  Cover Letter Preview",
            border_style="#00d4ff",
        ))


@app.command()
def serve(
    port: int = typer.Option(8501, "--port", "-p", help="Port to run Streamlit on"),
    host: str = typer.Option("localhost", "--host", "-h", help="Host to bind to"),
):
    """
    🚀 Launch the Streamlit dashboard.
    """
    show_banner()
    console.print(f"[bold #00ff41]Starting dashboard at http://{host}:{port}[/]")

    import subprocess
    subprocess.run([
        "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.address", host,
    ])


@app.command(name="load-cvs")
def load_cvs(
    force: bool = typer.Option(False, "--force", help="Reload even if CVs already exist"),
):
    """
    📚 Load your 4 CV variants into ChromaDB.

    Reads from data/cvs/{cv_mle, cv_genai, cv_research, cv_architect}.txt
    """
    show_banner()
    from src.agents.cv_selector import load_cvs_into_chromadb

    with console.status("[bold #ffb000]Embedding CVs into ChromaDB...[/]"):
        load_cvs_into_chromadb(force_reload=force)

    console.print("[bold #00ff41]✅ CVs loaded successfully[/]")


@app.command()
def test():
    """
    🧪 Run the public smoke test.
    """
    show_banner()
    import subprocess
    test_file = Path("scripts/Test.py")
    if not test_file.exists():
        console.print(f"[bold red]❌ {test_file} not found[/]")
        raise typer.Exit(1)

    console.print("[bold #00d4ff]Running the public smoke test...[/]\n")
    subprocess.run([sys.executable, str(test_file)])


@app.command()
def demo():
    """
    🎬 Run an interactive guided demo of the full pipeline.

    Walks through scraping → scoring → CV selection → cover letter
    using a sample job description.
    """
    show_banner()
    console.print("[bold #00d4ff]🎬 AutoApply AI Demo[/]")
    console.print("[dim]This demo runs the full pipeline on a sample job.[/]\n")

    SAMPLE_JD = """
    Senior AI Engineer — Example AI Platform Team
    Remote · Hybrid

    Design, build, and productionize LLM-powered and agentic applications,
    including retrieval-augmented generation (RAG), multi-step reasoning workflows,
    structured outputs, and prompt safety.
    Build and consume tool servers, defining schemas, endpoints, and access boundaries.

    Required: Extensive Python, LLM-powered apps, tool servers, microservices.
    """

    console.print(Panel(SAMPLE_JD, title="📋 Sample Job", border_style="dim"))

    if not typer.confirm("\nRun pipeline on this JD?", default=True):
        raise typer.Exit()

    from src.agents.graph import process_job
    result = process_job(SAMPLE_JD, force_letter=True)

    if result.get("error"):
        console.print(f"[red]Demo failed: {result['error']}[/]")
        raise typer.Exit(1)

    console.print("\n[bold #00ff41]Demo complete![/]")
    console.print(f"Score: {result.get('overall_score')}/100")
    console.print(f"Selected CV: CV-{result.get('selected_cv')}")
    console.print(f"Cover letter: {result.get('cover_letter_words')} words")
    console.print(f"\nLaunch dashboard with: [bold]python main.py serve[/]")


@app.command()
def export(
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv or json"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output filename"),
):
    """
    📤 Export job database to CSV or JSON.
    """
    show_banner()
    from src import analytics

    df = analytics.get_jobs_df()

    if df.empty:
        console.print("[yellow]No jobs in database yet[/]")
        raise typer.Exit()

    if output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"autoapply_export_{ts}.{format}"

    if format == "csv":
        df.to_csv(output, index=False)
    elif format == "json":
        df.to_json(output, orient="records", indent=2, date_format="iso")
    else:
        console.print(f"[red]Unknown format: {format}[/]")
        raise typer.Exit(1)

    console.print(f"[bold #00ff41]✅ Exported {len(df)} jobs to {output}[/]")


@app.command()
def stats():
    """
    📊 Print pipeline analytics to the terminal.
    """
    show_banner()
    from src import analytics

    df = analytics.get_jobs_df()
    if df.empty:
        console.print("[yellow]No jobs yet. Score some first![/]")
        raise typer.Exit()

    table = Table(title="📊 AutoApply Stats", box=box.HEAVY_EDGE)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold #00ff41")

    table.add_row("Total Jobs", str(len(df)))
    table.add_row("Applied", str((df["status"] != "new").sum()))
    table.add_row("In Pipeline", str(df["status"].isin(["applied", "phone_screen", "interview"]).sum()))
    table.add_row("Offers", str((df["status"] == "offer").sum()))
    table.add_row("Avg Score", f"{df['score'].mean():.1f}/100")
    table.add_row("Strong-fit jobs (≥75)", str((df["score"] >= 75).sum()))

    console.print(table)

    rates = analytics.funnel_conversion_rates(df)
    if rates:
        rates_table = Table(title="🔻 Conversion Funnel", box=box.HEAVY_EDGE)
        rates_table.add_column("Stage", style="dim")
        rates_table.add_column("Rate", style="bold #ffb000")
        for stage, rate in rates.items():
            rates_table.add_row(stage.replace("_", " → ").title(), f"{rate}%")
        console.print(rates_table)


@app.command()
def calendar(
    job_id: int = typer.Argument(..., help="Job ID to generate calendar event for"),
    days_ahead: int = typer.Option(2, "--days-ahead", "-d", help="Days before deadline for reminder"),
):
    """
    📅 Generate an .ics calendar file for a job application reminder.
    """
    show_banner()
    from src.calendar_utils import generate_application_ics
    from src.db import get_session, Job

    session = get_session()
    try:
        job = session.get(Job, job_id)
        if not job:
            console.print(f"[red]Job #{job_id} not found[/]")
            raise typer.Exit(1)

        filepath = generate_application_ics(job, days_ahead=days_ahead)
        console.print(f"[bold #00ff41]✅ Calendar event saved: {filepath}[/]")
        console.print(f"[dim]Import this .ics file into Google Calendar, Apple Calendar, or Outlook.[/]")
    finally:
        session.close()


@app.command()
def status():
    """
    🔍 System health check — verifies all dependencies and data files.
    """
    show_banner()
    console.print("[bold #00d4ff]System Health Check[/]\n")

    checks = []

    # Python imports
    for module, name in [
        ("langgraph", "LangGraph"),
        ("chromadb", "ChromaDB"),
        ("google.generativeai", "Gemini SDK"),
        ("streamlit", "Streamlit"),
        ("plotly", "Plotly"),
        ("typer", "Typer"),
        ("rich", "Rich"),
    ]:
        try:
            __import__(module)
            checks.append((name, True, "Installed"))
        except ImportError:
            checks.append((name, False, "MISSING — run pip install"))

    # Env files
    env_file = Path(".env")
    checks.append((".env file", env_file.exists(),
                   "OK" if env_file.exists() else "Missing — copy .env.example"))

    # Data files
    persona = Path("data/persona.txt")
    checks.append(("persona.txt", persona.exists(),
                   "OK" if persona.exists() else "Missing"))

    cv_dir = Path("data/cvs")
    cvs = list(cv_dir.glob("*.txt")) if cv_dir.exists() else []
    checks.append((f"CV files ({len(cvs)}/4)", len(cvs) >= 4,
                   f"{len(cvs)} found" if cvs else "Missing"))

    # ChromaDB
    chroma_dir = Path("chroma_db")
    checks.append(("ChromaDB", chroma_dir.exists(),
                   "Initialized" if chroma_dir.exists() else "Not initialized — run load-cvs"))

    # Database
    db_file = Path("autoapply.db")
    checks.append(("SQLite DB", db_file.exists(),
                   f"{db_file.stat().st_size // 1024} KB" if db_file.exists() else "Not yet created"))

    # Render
    table = Table(box=box.HEAVY)
    table.add_column("Check", style="dim", width=22)
    table.add_column("Status", width=10)
    table.add_column("Details")

    for name, ok, details in checks:
        status_icon = "[bold #00ff41]✅[/]" if ok else "[bold red]❌[/]"
        table.add_row(name, status_icon, details)

    console.print(table)

    if all(ok for _, ok, _ in checks):
        console.print("\n[bold #00ff41]🎉 All systems operational[/]")
    else:
        console.print("\n[bold yellow]⚠️  Some checks failed — see details above[/]")


if __name__ == "__main__":
    app()