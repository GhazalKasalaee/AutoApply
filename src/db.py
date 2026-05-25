"""
Database models and utilities for AutoApply AI.
- eval_quality, eval_recommendation, keyword_overlap_pct columns on Job
- ApplicationActivity table for daily activity heatmap
"""
from datetime import datetime, date

from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Text, DateTime,
    Float, Date, ForeignKey, text
)
from sqlalchemy.orm import declarative_base, Session, relationship

from src.config import DB_PATH


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    url                   = Column(String, nullable=True)
    title                 = Column(String, nullable=True)
    company               = Column(String, nullable=True)
    description           = Column(Text, nullable=True)
    overall_score         = Column(Integer, nullable=True)
    recommended_cv        = Column(String, nullable=True)
    should_apply          = Column(Boolean, nullable=True)
    scoring_json          = Column(Text, nullable=True)
    cover_letter          = Column(Text, nullable=True)
    cover_letter_words    = Column(Integer, nullable=True)

    # Evaluator outputs (NEW)
    eval_quality          = Column(Integer, nullable=True)
    eval_recommendation   = Column(String, nullable=True)
    keyword_overlap_pct   = Column(Float, nullable=True)

    status                = Column(String, default="new")
    notes                 = Column(Text, nullable=True)
    applied_date          = Column(DateTime, nullable=True)
    response_date         = Column(DateTime, nullable=True)
    deadline              = Column(DateTime, nullable=True)
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contacts              = relationship("OutreachContact", back_populates="job", cascade="all, delete-orphan")


class OutreachContact(Base):
    __tablename__ = "outreach_contacts"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    job_id          = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    name            = Column(String, nullable=False)
    role            = Column(String, nullable=True)
    linkedin_url    = Column(String, nullable=True)
    context_note    = Column(Text, nullable=True)
    messages_json   = Column(Text, nullable=True)
    selected_message = Column(Text, nullable=True)
    sent_at         = Column(DateTime, nullable=True)
    responded       = Column(Boolean, default=False)
    response_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    job             = relationship("Job", back_populates="contacts")


class ApplicationActivity(Base):
    """Daily activity log for the GitHub-style heatmap calendar."""
    __tablename__ = "application_activity"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    activity_date   = Column(Date, nullable=False, index=True)
    activity_type   = Column(String, nullable=False)  # "scored", "applied", "outreach", "interview"
    count           = Column(Integer, default=1)
    job_id          = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine, checkfirst=True)

    with engine.connect() as conn:
        existing = {
            row["name"]
            for row in conn.execute(text("PRAGMA table_info(jobs)")).mappings()
        }

        columns_to_add = {
            "notes": "TEXT",
            "applied_date": "DATETIME",
            "response_date": "DATETIME",
            "deadline": "DATETIME",
            "cover_letter_words": "INTEGER",
            "eval_quality": "INTEGER",
            "eval_recommendation": "TEXT",
            "keyword_overlap_pct": "REAL",
        }

        for name, col_type in columns_to_add.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {col_type}"))
        conn.commit()


def get_session() -> Session:
    return Session(engine)


def log_activity(activity_type: str, job_id: int = None, count: int = 1):
    """Log a daily activity for the heatmap."""
    init_db()
    s = get_session()
    try:
        act = ApplicationActivity(
            activity_date=date.today(),
            activity_type=activity_type,
            count=count,
            job_id=job_id,
        )
        s.add(act)
        s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()


def delete_job_record(job_id: int):
    """Permanently delete a job and its associated contacts."""
    init_db()
    s = get_session()
    try:
        job = s.get(Job, job_id)
        if job:
            s.delete(job)
            s.commit()
    except Exception as e:
        s.rollback()
        raise e
    finally:
        s.close()       