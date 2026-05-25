"""
Auto-fill utility for Dynamic Tailoring based on JD and sample CV.
Extracts keywords, skills, projects, and sections automatically.
"""
import re
from pathlib import Path
from typing import Optional


def extract_keywords_from_jd(jd_text: str) -> list[str]:
    """Extract technical keywords and key phrases from job description."""
    if not jd_text:
        return []
    
    # Common tech stack keywords
    tech_keywords = {
        'python', 'java', 'javascript', 'typescript', 'golang', 'rust', 'c++', 'csharp',
        'fastapi', 'django', 'flask', 'nodejs', 'express', 'react', 'vue', 'angular',
        'sql', 'postgres', 'mysql', 'mongodb', 'redis', 'elasticsearch',
        'docker', 'kubernetes', 'aws', 'gcp', 'azure', 'terraform', 'ansible',
        'git', 'ci/cd', 'jenkins', 'gitlab', 'github', 'circleci',
        'machine learning', 'deep learning', 'llm', 'rag', 'langchain', 'langgraph',
        'ai', 'gpt', 'bert', 'transformers', 'pytorch', 'tensorflow', 'scikit-learn',
        'apis', 'rest', 'grpc', 'graphql', 'websockets',
        'agile', 'scrum', 'kanban', 'devops', 'microservices',
        'mlops', 'data engineering', 'etl', 'analytics',
    }
    
    jd_lower = jd_text.lower()
    found_keywords = []
    
    for keyword in tech_keywords:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, jd_lower):
            found_keywords.append(keyword)
    
    # Extract multi-word skills and tools with pattern matching
    # Look for things like "Machine Learning", "Cloud Platform", etc.
    skill_patterns = [
        r'(?:experience with|knowledge of|expertise in|proficient in|strong)\s+([a-z\s]{3,40}?)(?:[,;.]|and)',
        r'([a-z]{3,20})\s+(?:development|engineering|platform|system)',
    ]
    
    for pattern in skill_patterns:
        matches = re.findall(pattern, jd_lower, re.IGNORECASE)
        for match in matches:
            match_clean = match.strip()
            if 3 < len(match_clean) < 40 and match_clean not in found_keywords:
                found_keywords.append(match_clean)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in found_keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique_keywords.append(kw)
    
    return unique_keywords[:15]  # Return top 15 keywords


def extract_responsibilities_from_jd(jd_text: str) -> list[str]:
    """Extract main responsibilities/requirements from JD."""
    if not jd_text:
        return []
    
    # Look for bullet points or numbered lists
    patterns = [
        r'^\s*[-•*]\s+(.{10,150}?)$',
        r'^\s*\d+\.\s+(.{10,150}?)$',
    ]
    
    responsibilities = []
    for pattern in patterns:
        matches = re.findall(pattern, jd_text, re.MULTILINE)
        responsibilities.extend(matches)
    
    # Clean up and limit to top responsibilities
    cleaned = [r.strip() for r in responsibilities if len(r.strip()) > 10]
    return cleaned[:8]


def load_sample_cv(cv_path: Optional[str] = None) -> str:
    """Load sample CV from file or return default text."""
    if cv_path is None:
        cv_path = "data/cv_example.txt"
    
    try:
        path = Path(cv_path)
        if path.exists():
            return path.read_text(encoding='utf-8')
    except Exception:
        pass
    
    # Default if file not found
    return """
SUMMARY
- AI Engineer with 3+ years building ML systems, RAG pipelines, and production APIs

EXPERIENCE
- Built RAG system with vector search, improving accuracy by 28%
- Deployed agentic workflows with task routing and monitoring
- Developed FastAPI services with 99.9% uptime

SKILLS
- Python, FastAPI, LangGraph, SQL, Docker, AWS, CI/CD
- Machine Learning, Deep Learning, LLM/RAG systems
- DevOps, Microservices, Data Engineering
"""


def generate_auto_tailoring_suggestion(jd_text: str, cv_text: Optional[str] = None) -> dict:
    """
    Generate auto-fill suggestions for Dynamic Tailoring form.
    
    Returns dict with:
    - ats_keywords: Extracted technical keywords
    - projects: Suggested project priorities based on JD
    - summary_hint: Suggested summary rewrite approach
    """
    if cv_text is None:
        cv_text = load_sample_cv()
    
    keywords = extract_keywords_from_jd(jd_text)
    responsibilities = extract_responsibilities_from_jd(jd_text)
    
    # Create a summary hint based on JD emphasis
    summary_hint = "Focus on: " + ", ".join(keywords[:5]) if keywords else "Align with JD requirements"
    
    # Suggest project priorities by looking for project-related keywords
    project_keywords = [k for k in keywords if any(x in k.lower() for x in ['system', 'platform', 'framework', 'tool', 'pipeline'])]
    
    return {
        'ats_keywords': keywords,
        'ats_keywords_str': ', '.join(keywords),
        'responsibilities': responsibilities,
        'summary_hint': summary_hint,
        'projects_hint': project_keywords,
    }


def extract_projects_from_cv(cv_text: str) -> list[str]:
    """Extract project names/descriptions from CV."""
    projects = []
    
    # Look for project sections
    project_patterns = [
        r'(?:^|\n)(?:PROJECT|project)s?.*?(?:^|\n)[-•]\s+([^\n]+)',
        r'(?:^|\n)[-•]\s+([A-Z][^:\n]+)(?:\s*:|$)',
    ]
    
    for pattern in project_patterns:
        matches = re.findall(pattern, cv_text, re.MULTILINE | re.IGNORECASE)
        projects.extend(matches)
    
    # Clean up
    cleaned = [p.strip() for p in projects if 5 < len(p.strip()) < 100]
    return cleaned[:10]
