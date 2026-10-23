import re

import pymupdf

from app.database import SessionLocal
from app.models import Resume
from app.schemas import ResumeProfile, ResumeSkill
from app.services.llm import llm
from app.services.storage import read_pdf


SKILL_ALIASES = {
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "React": ["react", "react.js", "reactjs"],
    "FastAPI": ["fastapi"],
    "SQL": ["sql", "postgresql", "mysql", "sqlite"],
    "Git": ["git", "github", "gitlab"],
    "Docker": ["docker", "containerization"],
    "AWS": ["aws", "amazon web services"],
    "Machine Learning": ["machine learning", "ml"],
    "Data Structures": ["data structures", "dsa", "algorithms"],
    "Communication": ["communication", "presentation"],
}


def extract_pdf_text(data: bytes) -> str:
    pdf = pymupdf.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text("text").strip() for page in pdf).strip()


def fallback_profile(text: str) -> ResumeProfile:
    normalized = text.casefold()
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    skills = []
    for name, aliases in SKILL_ALIASES.items():
        matches = [line[:300] for line in lines if any(re.search(rf"\b{re.escape(alias)}\b", line.casefold()) for alias in aliases)]
        if matches:
            skills.append(ResumeSkill(name=name, evidence=matches[:3], confidence=0.7))
    interests = [name for name, aliases in SKILL_ALIASES.items() if any(alias in normalized for alias in aliases)][:10]
    return ResumeProfile(summary=" ".join(lines[:4])[:1200], skills=skills, interests=interests)


async def parse_profile(text: str) -> ResumeProfile:
    if not llm.client:
        return fallback_profile(text)
    try:
        return await llm.json(
            "Extract only explicit resume facts. Never infer age, gender, ethnicity, health, religion, or other sensitive attributes. Every skill must include short verbatim evidence and a confidence from 0 to 1. Return JSON matching the requested schema.",
            f"RESUME:\n{text[:30000]}",
            ResumeProfile,
        )
    except Exception:
        return fallback_profile(text)


async def process_resume(resume_id: int) -> None:
    with SessionLocal() as db:
        resume = db.get(Resume, resume_id)
        if not resume:
            return
        try:
            resume.status = "extracting"
            db.commit()
            text = extract_pdf_text(read_pdf(resume.storage_path))
            if len(text) < 40:
                raise ValueError("The resume contains too little selectable text")
            resume.raw_text = text
            resume.status = "parsing"
            db.commit()
            profile = await parse_profile(text)
            resume.parsed_profile = profile.model_dump()
            resume.status = "review_required"
            resume.error = None
            db.commit()
        except Exception as exc:
            db.rollback()
            resume = db.get(Resume, resume_id)
            if resume:
                resume.status = "failed"
                resume.error = str(exc)
                db.commit()
