"""
Calendar integration for AutoApply AI.

Two integration paths:
  1. .ics file export (works with Google Cal, Apple Cal, Outlook — no auth)
  2. Google Calendar API (OAuth, automatic sync)

The .ics path is always available. Google Calendar requires:
  pip install google-api-python-client google-auth-oauthlib

Calendar events created:
  - Application deadline reminder (2 days before)
  - Follow-up reminder (7 days after outreach with no response)
  - Interview scheduling
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.config import PROJECT_ROOT


CALENDAR_DIR = PROJECT_ROOT / "data" / "calendar"
CALENDAR_DIR.mkdir(parents=True, exist_ok=True)


def build_google_oauth_payload(client_id: str, client_secret: str, project_id: str = "AutoApply AI") -> dict:
    """Build a Google OAuth client payload in the installed-app format."""
    return {
        "installed": {
            "client_id": client_id.strip(),
            "project_id": project_id.strip() or "AutoApply AI",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret.strip(),
            "redirect_uris": ["http://localhost"],
        }
    }


def save_google_oauth_credentials(client_id: str, client_secret: str, project_id: str = "AutoApply AI") -> Path:
    """Write `credentials.json` in the project root from copied OAuth fields."""
    payload = build_google_oauth_payload(client_id, client_secret, project_id)
    creds_path = PROJECT_ROOT / "credentials.json"
    creds_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return creds_path


def google_calendar_setup_status() -> tuple[bool, str]:
    """Return whether Google Calendar sync is ready and how to fix it if not."""
    try:
        import googleapiclient.discovery  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
    except Exception:
        return False, "Install Google Calendar packages (`google-api-python-client`, `google-auth-oauthlib`)."

    creds_path = PROJECT_ROOT / "credentials.json"
    if not creds_path.exists():
        template_path = PROJECT_ROOT / "credentials.json.template"
        if template_path.exists():
            return False, "Create `credentials.json` from `credentials.json.template` by pasting your client id and client secret."
        return False, "Missing `credentials.json` in the project root."

    try:
        payload = json.loads(creds_path.read_text(encoding="utf-8"))
    except Exception:
        return False, "`credentials.json` is not valid JSON."

    installed = payload.get("installed") or payload.get("web")
    if not installed:
        return False, "`credentials.json` must contain an `installed` or `web` OAuth client block."

    if not installed.get("client_id") or not installed.get("client_secret"):
        return False, "`credentials.json` is missing `client_id` or `client_secret`."

    return True, "Google Calendar OAuth credentials are configured."


# ── .ics generation (zero dependencies) ──────────────────────────────────────

def _ics_datetime(dt: datetime) -> str:
    """Format datetime as iCalendar UTC string."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _make_uid(prefix: str, job_id: int) -> str:
    """Generate a unique iCalendar UID."""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{job_id}-{ts}@autoapply.ai"


def generate_ics_event(
    title: str,
    description: str,
    start_dt: datetime,
    end_dt: Optional[datetime] = None,
    location: str = "",
    uid: str = "autoapply-event@autoapply.ai",
) -> str:
    """Generate a single iCalendar event as a string."""
    if end_dt is None:
        end_dt = start_dt + timedelta(minutes=30)

    # Escape special chars for iCalendar
    def escape(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AutoApply AI//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{_ics_datetime(datetime.utcnow())}
DTSTART:{_ics_datetime(start_dt)}
DTEND:{_ics_datetime(end_dt)}
SUMMARY:{escape(title)}
DESCRIPTION:{escape(description)}
LOCATION:{escape(location)}
STATUS:CONFIRMED
SEQUENCE:0
BEGIN:VALARM
TRIGGER:-PT1H
ACTION:DISPLAY
DESCRIPTION:Reminder: {escape(title)}
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics


def generate_application_ics(job, days_ahead: int = 2) -> Path:
    """
    Generate an .ics reminder for a job application.

    Args:
        job: Job ORM object
        days_ahead: How many days before deadline to schedule reminder (default: 2)

    Returns:
        Path to the saved .ics file
    """
    company = job.company or "Unknown"
    title = job.title or "Job Application"

    # Default: remind to apply tomorrow
    reminder_dt = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    reminder_dt += timedelta(days=days_ahead)

    desc_lines = [
        f"🎯 Apply to: {title} at {company}",
        f"📊 Fit Score: {job.overall_score or '?'}/100",
        f"📄 Use CV: CV-{job.recommended_cv or 'GENAI'}",
    ]
    if job.cover_letter:
        desc_lines.append(f"✉️  Cover letter ready ({job.cover_letter_words or 0} words)")
    if job.url:
        desc_lines.append(f"🔗 {job.url}")

    description = "\n".join(desc_lines)

    ics_content = generate_ics_event(
        title=f"📋 Apply: {company} — {title}",
        description=description,
        start_dt=reminder_dt,
        end_dt=reminder_dt + timedelta(minutes=30),
        location=job.url or "",
        uid=_make_uid("apply", job.id),
    )

    filename = f"apply_{job.id}_{company.replace(' ', '_')}.ics"
    filepath = CALENDAR_DIR / filename
    filepath.write_text(ics_content, encoding="utf-8")
    return filepath


def generate_followup_ics(contact, job, days_ahead: int = 7) -> Path:
    """
    Generate an .ics reminder to follow up with a networking contact.

    Args:
        contact: OutreachContact ORM object
        job: Associated Job ORM object
        days_ahead: Days from sent_at to schedule followup (default: 7)
    """
    if not contact.sent_at:
        raise ValueError("Cannot create followup reminder for unsent contact")

    reminder_dt = contact.sent_at + timedelta(days=days_ahead)
    reminder_dt = reminder_dt.replace(hour=10, minute=0)

    desc = (
        f"💬 Follow up with {contact.name}\n"
        f"📋 Role: {contact.role or 'Unknown'}\n"
        f"🏢 Re: {job.company or 'Unknown'} — {job.title or 'Application'}\n"
        f"📨 Original message sent: {contact.sent_at.strftime('%Y-%m-%d')}"
    )

    ics_content = generate_ics_event(
        title=f"⏰ Follow up: {contact.name}",
        description=desc,
        start_dt=reminder_dt,
        end_dt=reminder_dt + timedelta(minutes=15),
        uid=_make_uid("followup", contact.id),
    )

    filename = f"followup_{contact.id}_{contact.name.replace(' ', '_')}.ics"
    filepath = CALENDAR_DIR / filename
    filepath.write_text(ics_content, encoding="utf-8")
    return filepath


def generate_interview_ics(
    job,
    interview_datetime: datetime,
    duration_minutes: int = 60,
    location: str = "Video call",
    interviewer: str = "",
) -> Path:
    """Generate an .ics for a scheduled interview."""
    desc_lines = [
        f"🎯 Interview: {job.title or 'Role'} at {job.company or 'Company'}",
        f"👤 Interviewer: {interviewer}" if interviewer else "",
        f"📊 Your fit score: {job.overall_score or '?'}/100",
        f"📄 CV used: CV-{job.recommended_cv or 'GENAI'}",
        f"💡 Tip: Review your cover letter and prepare 3 questions",
    ]
    desc = "\n".join(l for l in desc_lines if l)

    ics_content = generate_ics_event(
        title=f"🎤 Interview: {job.company} — {job.title}",
        description=desc,
        start_dt=interview_datetime,
        end_dt=interview_datetime + timedelta(minutes=duration_minutes),
        location=location,
        uid=_make_uid("interview", job.id),
    )

    filename = f"interview_{job.id}_{interview_datetime.strftime('%Y%m%d')}.ics"
    filepath = CALENDAR_DIR / filename
    filepath.write_text(ics_content, encoding="utf-8")
    return filepath


# ── Google Calendar ────────────────────────────────

def push_to_google_calendar(
    title: str,
    description: str,
    start_dt: datetime,
    end_dt: Optional[datetime] = None,
) -> Optional[str]:
    """
    Push an event directly to the user's Google Calendar.

    Returns the event ID if successful, None otherwise.

    MANUAL SETUP INSTRUCTIONS (No Download Required):
        1. Go to: https://console.cloud.google.com/
        2. Create a new project or select existing one
        3. Search for "Google Calendar API" and enable it
        4. Go to Credentials → Create OAuth 2.0 (Desktop app)
        5. Copy your Client ID and Client Secret
        6. Open credentials.json.template in project root
        7. Paste your Client ID and Secret into the template
        8. Rename to credentials.json and save in project root
        9. Restart the app—first run will open browser for OAuth login
        10. Authorize the app to access your calendar
        11. Token auto-saved; future runs sync silently 📅

    REQUIREMENTS:
        pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
    """
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        return None

    SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
    token_path = CALENDAR_DIR / "google_token.json"
    creds_path = PROJECT_ROOT / "credentials.json"

    creds = None
    
    # Try to load cached token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as refresh_error:
                print(f"Token refresh failed: {refresh_error}")
                creds = None
        
        if not creds and creds_path.exists():
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
                token_path.write_text(creds.to_json())
            except Exception as oauth_error:
                print(f"OAuth flow failed: {oauth_error}. Falling back to .ics export.")
                return None
        elif not creds:
            return None

    try:
        service = build("calendar", "v3", credentials=creds)

        if end_dt is None:
            end_dt = start_dt + timedelta(minutes=30)

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "email", "minutes": 1440},  # 24h email
                ],
            },
        }

        created = service.events().insert(calendarId="primary", body=event).execute()
        return created.get("id")
    except Exception as calendar_error:
        print(f"Google Calendar push failed: {calendar_error}. Falling back to .ics export.")
        return None