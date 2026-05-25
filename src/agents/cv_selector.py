"""
CV Selector Agent: uses RAG (ChromaDB embeddings + LLM reasoning)
to pick the best CV version for a given job description.

Architecture:
  1. RETRIEVE — Query ChromaDB with the job description to find semantically
     similar CV sections. ChromaDB uses all-MiniLM-L6-v2 embeddings locally.
  2. REASON — Send the top-matching CVs + job description to Gemini for
     final selection with structured reasoning.

Why two stages?
  - Embeddings give fast similarity ranking (cosine distance)
  - LLM adds nuanced reasoning ("this CV mentions LangGraph which maps
    to the JD's agent orchestration requirement")
  - Together they're more reliable than either alone

Usage:
    from src.agents.cv_selector import select_cv, load_cvs_into_chromadb

    # One-time setup (run once, persists to disk)
    load_cvs_into_chromadb()

    # Select best CV for a job
    result = select_cv("We need an ML engineer who...")
    print(result.selected_cv)    # "MLE"
    print(result.reasoning)      # "The JD emphasizes production pipelines..."
"""
from pathlib import Path

import chromadb

from src.config import PROJECT_ROOT
from src.llm import call_llm_structured
from src.schemas import CVSelection, CVVersion


# ── Paths ────────────────────────────────────────────────────────────────────

CVS_DIR = PROJECT_ROOT / "data" / "cvs"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "candidate_cvs"

# CV version metadata — helps the LLM understand each CV's focus
CV_METADATA = {
    "MLE": {
        "focus": "Production ML engineering, MLOps, model deployment, CI/CD pipelines",
        "best_for": "Roles emphasizing scalable ML systems, cloud deployment, MLflow, Docker",
    },
    "GENAI": {
        "focus": "Agentic AI, LLM applications, RAG pipelines, LangGraph, prompt engineering",
        "best_for": "Roles emphasizing LLM integration, chatbots, agents, vector search, GenAI",
    },
    "RESEARCH": {
        "focus": "AI research, efficient Transformers, quantization, IEEE publications",
        "best_for": "Research scientist roles, academic labs, R&D positions valuing publications",
    },
    "ARCHITECT": {
        "focus": "Solutions architecture, enterprise AI strategy, cross-functional delivery",
        "best_for": "Senior/architect roles, system design, build-vs-buy decisions, stakeholder management",
    },
}


# ── ChromaDB Setup ───────────────────────────────────────────────────────────

def _get_collection() -> chromadb.Collection:
    """Get or create the ChromaDB collection for CVs."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def load_cvs_into_chromadb(force_reload: bool = False) -> None:
    """
    Load CV text files from data/cvs/ into ChromaDB.
    
    Expected files: cv_mle.txt, cv_genai.txt, cv_research.txt, cv_architect.txt
    
    Each CV is stored as a single document with its version as the ID.
    ChromaDB auto-generates embeddings using all-MiniLM-L6-v2.

    Args:
        force_reload: If True, delete and re-add all CVs. Use when you update CV content.
    """
    collection = _get_collection()

    # Check if already loaded
    existing = collection.get()
    if existing["ids"] and not force_reload:
        print(f"  ChromaDB already has {len(existing['ids'])} CVs loaded: {existing['ids']}")
        print("  Use force_reload=True to refresh.")
        return

    # If force reloading, delete existing
    if force_reload and existing["ids"]:
        collection.delete(ids=existing["ids"])
        print("  Cleared existing CVs from ChromaDB.")

    # Load CV files
    cv_files = {
        "MLE": CVS_DIR / "cv_mle.txt",
        "GENAI": CVS_DIR / "cv_genai.txt",
        "RESEARCH": CVS_DIR / "cv_research.txt",
        "ARCHITECT": CVS_DIR / "cv_architect.txt",
    }

    documents = []
    ids = []
    metadatas = []

    for version, filepath in cv_files.items():
        if not filepath.exists():
            print(f"  ⚠️  Missing: {filepath} — skipping {version}")
            continue

        text = filepath.read_text(encoding="utf-8").strip()
        if len(text) < 100:
            print(f"  ⚠️  {filepath} is too short ({len(text)} chars) — skipping")
            continue

        documents.append(text)
        ids.append(version)
        metadatas.append(CV_METADATA.get(version, {}))
        print(f"  ✅ Loaded {version}: {len(text)} chars from {filepath.name}")

    if not documents:
        raise FileNotFoundError(
            f"No CV files found in {CVS_DIR}/\n"
            f"Expected: cv_mle.txt, cv_genai.txt, cv_research.txt, cv_architect.txt\n"
            f"Run: python scripts/load_cvs.py"
        )

    # Add to ChromaDB (embeddings generated automatically)
    collection.add(
        documents=documents,
        ids=ids,
        metadatas=metadatas,
    )
    print(f"\n  ✅ {len(documents)} CVs loaded into ChromaDB at {CHROMA_DIR}")


# ── Retrieval ────────────────────────────────────────────────────────────────

def _retrieve_top_cvs(job_description: str, n_results: int = 4) -> dict:
    """
    Query ChromaDB to find the most semantically similar CVs.
    
    Returns all CVs ranked by similarity — even for 4 docs, the ranking
    provides useful signal (which CV is closest vs. furthest).
    """
    collection = _get_collection()

    # Check collection has documents
    count = collection.count()
    if count == 0:
        raise RuntimeError(
            "ChromaDB collection is empty. Run: python scripts/load_cvs.py"
        )

    results = collection.query(
        query_texts=[job_description[:3000]],  # Truncate for embedding model
        n_results=min(n_results, count),
        include=["documents", "metadatas", "distances"],
    )

    return {
        "ids": results["ids"][0],
        "documents": results["documents"][0],
        "metadatas": results["metadatas"][0],
        "distances": results["distances"][0],  # Lower = more similar (cosine)
    }


# ── LLM Reasoning ───────────────────────────────────────────────────────────

CV_SELECTOR_PROMPT = """You are an expert recruiter selecting which CV version a candidate should use for a specific job.

# JOB DESCRIPTION
{job_description}

# AVAILABLE CVs (ranked by semantic similarity, most similar first)

{cv_summaries}

# EMBEDDING SIMILARITY SCORES
{similarity_scores}

# YOUR TASK
Select the SINGLE best CV version for this job. Consider:
1. The embedding similarity scores (lower distance = more similar)
2. The specific requirements in the JD (skills, experience level, domain)
3. Which CV's framing, bullet points, and emphasis best match what the recruiter wants to see
4. Any hard requirements that a specific CV addresses better

Return your selection as JSON matching the schema."""


def select_cv(job_description: str) -> CVSelection:
    """
    Select the best CV version for a job description using RAG.
    
    Stage 1: ChromaDB retrieval (embedding similarity)
    Stage 2: LLM reasoning (structured selection with explanation)
    
    Args:
        job_description: The full job description text.
        
    Returns:
        CVSelection with selected_cv, confidence, reasoning, etc.
    """
    # Stage 1: Retrieve
    results = _retrieve_top_cvs(job_description)

    # Build CV summaries for the LLM
    cv_summaries_parts = []
    similarity_parts = []

    for i, (cv_id, doc, meta, dist) in enumerate(zip(
        results["ids"],
        results["documents"],
        results["metadatas"],
        results["distances"],
    )):
        # Truncate each CV to ~1500 chars for the prompt
        truncated = doc[:1500]
        focus = meta.get("focus", "N/A")
        best_for = meta.get("best_for", "N/A")

        cv_summaries_parts.append(
            f"## CV-{cv_id} (Rank #{i+1})\n"
            f"Focus: {focus}\n"
            f"Best for: {best_for}\n"
            f"Content preview:\n{truncated}\n"
        )
        similarity_parts.append(
            f"- CV-{cv_id}: cosine distance = {dist:.4f} "
            f"({'most similar' if i == 0 else 'less similar'})"
        )

    prompt = CV_SELECTOR_PROMPT.format(
        job_description=job_description[:4000],
        cv_summaries="\n".join(cv_summaries_parts),
        similarity_scores="\n".join(similarity_parts),
    )

    # Stage 2: Reason
    return call_llm_structured(prompt, CVSelection)


# ── Convenience ──────────────────────────────────────────────────────────────

def get_cv_text(version: CVVersion) -> str:
    """Load the full text of a specific CV version."""
    filepath = CVS_DIR / f"cv_{version.lower()}.txt"
    if not filepath.exists():
        raise FileNotFoundError(f"CV file not found: {filepath}")
    return filepath.read_text(encoding="utf-8")