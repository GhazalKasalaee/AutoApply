"""
Scraper Agent: given a URL or raw text, returns structured job info.

Strategy:
  1. If raw text (not a URL): send to LLM for title/company extraction
  2. If URL: try requests → Playwright → raise error
  3. Always parse with LLM to extract title, company, clean description
"""
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

from src.llm import call_llm_text


@dataclass
class ScraperResult:
    title: str
    company: str
    description: str
    source_url: str | None


def is_url(text: str) -> bool:
    """Return True if text looks like a URL."""
    stripped = text.strip()
    return stripped.startswith(("http://", "https://")) and len(stripped.split()) <= 3


def _clean_job_slug(slug: str) -> str:
    """Turn a URL slug into readable title text."""
    slug = unquote(slug or "").strip("/-_")
    slug = re.sub(r"[?#].*$", "", slug)
    slug = re.sub(r"\b\d{3,}\b", "", slug)
    slug = slug.replace("-", " ").replace("_", " ").replace("/", " ")
    slug = re.sub(r"\s+", " ", slug).strip()

    stop_words = {
        "jobs", "job", "careers", "career", "apply", "application", "applynow",
        "opening", "openings", "role", "position", "vacancy", "details", "view",
        "req", "requisition", "posting", "id", "p", "page", "jobid", "job-posting",
    }
    parts = [part for part in slug.split() if part.lower() not in stop_words]
    return " ".join(parts).strip() or "Unknown"


def _domain_to_company(url: str) -> str:
    """Guess a company name from the hostname."""
    host = urlparse(url).netloc.lower()
    if not host:
        return "Unknown"

    host = host.split("@")[-1]
    host = host.split(":")[0]
    labels = [label for label in host.split(".") if label and label not in {"www", "jobs", "careers", "boards"}]
    if len(labels) >= 2 and labels[-1] in {"com", "ca", "org", "net", "io", "co"}:
        labels = labels[:-1]
    if not labels:
        return "Unknown"

    candidate = labels[-2] if len(labels) > 1 and labels[-1] in {"jobs", "careers", "boards"} else labels[-1]
    candidate = candidate.replace("-", " ").replace("_", " ")
    return candidate.title().strip() or "Unknown"


def _derive_url_hints(url: str, page_title: str = "", og_title: str = "") -> dict[str, str]:
    """Extract fallback title/company hints from URL and page metadata."""
    parsed = urlparse(url)
    slug = _clean_job_slug(parsed.path.split("/")[-1])

    title_hint = ""
    for candidate in (og_title, page_title):
        if not candidate:
            continue
        cleaned = re.split(r"\s[\-|•|\||@]\s|\s\|\s|\s-\s", candidate)[0].strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) >= 4:
            title_hint = cleaned
            break

    if not title_hint or title_hint.lower() in {"jobs", "careers", "open positions", "open roles"}:
        title_hint = slug

    company_hint = _domain_to_company(url)
    if page_title and " - " in page_title:
        suffix = page_title.split(" - ")[-1].strip()
        if len(suffix) >= 2:
            company_hint = suffix
    elif og_title and " - " in og_title:
        suffix = og_title.split(" - ")[-1].strip()
        if len(suffix) >= 2:
            company_hint = suffix

    return {
        "page_title": page_title or "",
        "og_title": og_title or "",
        "url_slug": slug or "Unknown",
        "title_hint": title_hint or "Unknown",
        "company_hint": company_hint or "Unknown",
    }


def _extract_with_requests(url: str) -> tuple[str | None, dict[str, str]]:
    """Fast path: try plain HTTP request."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.5 Safari/605.1.15"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code} — skipping requests method")
            return None, _derive_url_hints(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        og_title_tag = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "title"})
        og_title = og_title_tag.get("content", "").strip() if og_title_tag else ""

        # Remove noise
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean = "\n".join(lines)
        metadata = _derive_url_hints(url, page_title=page_title, og_title=og_title)
        return (clean if len(clean) > 200 else None, metadata)
    except Exception as e:
        print(f"  requests failed: {e}")
        return None, _derive_url_hints(url)


def _extract_with_playwright(url: str) -> tuple[str | None, dict[str, str]]:
    """Slow path: real browser via Playwright."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # Let JS render
            page_title = page.title()
            og_title = ""
            content = page.inner_text("body")
            browser.close()
            return (content if len(content) > 200 else None, _derive_url_hints(url, page_title=page_title, og_title=og_title))
    except Exception as e:
        print(f"  Playwright failed: {e}")
        return None, _derive_url_hints(url)


def _parse_jd_with_llm(raw_text: str, url: str | None = None, metadata: dict[str, str] | None = None) -> ScraperResult:
    """
    Use Gemini to extract structured job info from raw text.
    Works for both scraped HTML text AND directly pasted JD text.
    
    FIXED in Day 3: increased truncation to 6000 chars, better prompt.
    """
    truncated = raw_text[:6000]

    metadata = metadata or {}

    prompt = f"""You are a job posting parser. Extract the following fields from this text.

URL HINTS:
- page_title: {metadata.get('page_title', '')}
- og_title: {metadata.get('og_title', '')}
- url_slug: {metadata.get('url_slug', '')}
- title_hint: {metadata.get('title_hint', '')}
- company_hint: {metadata.get('company_hint', '')}

TEXT:
{truncated}

Return EXACTLY this format with no extra text or markdown:
TITLE: <the exact job title, e.g. "Machine Learning Engineer" or "AI Research Scientist">
COMPANY: <the company name, e.g. "Ericsson" or "RBC">
LOCATION: <city and province/state, e.g. "Toronto, ON" or "Remote">
DESCRIPTION: <the full job description including responsibilities and requirements>

Rules:
- For TITLE: extract the specific job title. If multiple titles appear, pick the primary one.
- For COMPANY: extract the company name (not the staffing agency unless no other company is mentioned).
- If you truly cannot find a field, use "Unknown".
- For DESCRIPTION: include responsibilities, requirements, qualifications, and any salary info.
- Do NOT add any commentary or markdown formatting."""

    result = call_llm_text(prompt, temperature=0.1)

    title = "Unknown"
    company = "Unknown"
    location = "Unknown"
    description = raw_text[:4000]  # fallback

    lines = [line.strip() for line in result.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line.startswith("TITLE:"):
            title = line[6:].strip().strip('"').strip("'")
        elif line.startswith("COMPANY:"):
            company = line[8:].strip().strip('"').strip("'")
        elif line.startswith("LOCATION:"):
            location = line[9:].strip().strip('"').strip("'")
        elif line.startswith("DESCRIPTION:"):
            # Everything from here to the end is the description
            description = "\n".join(lines[i:]).replace("DESCRIPTION:", "", 1).strip()
            break

    # Clean up empty values and apply URL/meta fallbacks
    if not title or title.lower() in ("unknown", "n/a", "none", ""):
        title = metadata.get("title_hint", "Unknown")
    if not company or company.lower() in ("unknown", "n/a", "none", ""):
        company = metadata.get("company_hint", "Unknown")

    # Last-resort cleanup for noisy titles like "Jobs at Company"
    bad_title_patterns = ("jobs", "careers", "open positions", "apply now")
    if title.lower() in bad_title_patterns:
        title = metadata.get("title_hint", title)

    if company.lower() in bad_title_patterns:
        company = metadata.get("company_hint", company)

    return ScraperResult(
        title=title,
        company=company,
        description=description,
        source_url=url,
    )


def scrape_job(url_or_text: str) -> ScraperResult:
    """
    Main entry point for the Scraper Agent.

    Args:
        url_or_text: Either a job posting URL or raw JD text.

    Returns:
        ScraperResult with title, company, description, and source_url.
        
    FIXED in Day 3:
    - Pasted text now goes through LLM for title/company extraction
    - URL scraping more robust
    """
    # ── Raw text pasted directly ──
    if not is_url(url_or_text):
        print("  Input is raw text (not a URL) — parsing with LLM...")
        return _parse_jd_with_llm(url_or_text.strip(), url=None)

    # ── URL provided ──
    url = url_or_text.strip()
    print(f"  Scraping URL: {url}")

    # Strategy 1: plain HTTP
    raw, metadata = _extract_with_requests(url)
    if raw:
        print("  ✅ Got text via requests")
        return _parse_jd_with_llm(raw, url, metadata=metadata)

    # Strategy 2: real browser
    print("  Trying Playwright (headless browser)...")
    raw, metadata = _extract_with_playwright(url)
    if raw:
        print("  ✅ Got text via Playwright")
        return _parse_jd_with_llm(raw, url, metadata=metadata)

    # Strategy 3: give up gracefully
    raise ValueError(
        f"Could not extract content from: {url}\n"
        "This usually means the site blocks automated access.\n"
        "💡 TIP: Copy the job description text and paste it directly instead of using the URL."
    )