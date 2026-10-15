from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AuthIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    account_type: Literal["student", "teacher"] = "student"
    first_name: str | None = Field(default=None, min_length=1, max_length=100)


class ProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


ProviderName = Literal["openai", "anthropic", "gemini", "mistral", "groq", "cohere", "zai"]


class ModelSettingsUpdate(BaseModel):
    generation_provider: ProviderName
    generation_model: str = Field(min_length=1, max_length=150)
    embedding_provider: ProviderName
    embedding_model: str = Field(min_length=1, max_length=150)


class ProviderKeyCreate(BaseModel):
    provider: ProviderName
    api_key: str = Field(min_length=8, max_length=1000)
    label: str | None = Field(default=None, max_length=100)
    make_default: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentOut(ORMModel):
    id: int
    title: str
    filename: str
    page_count: int
    status: str
    progress: int
    error: str | None
    created_at: datetime


class ConceptOut(ORMModel):
    id: int
    name: str
    summary: str
    chapter: str | None
    order_idx: int
    mastery: float = 0.3


class ChunkOut(ORMModel):
    id: int
    page_start: int
    page_end: int
    section: str | None
    text: str


class TestCreate(BaseModel):
    mode: str = Field(pattern="^(practice|mock)$")
    document_ids: list[int] = Field(min_length=1)
    count: int = Field(default=10, ge=1, le=100)


class PublicQuestion(ORMModel):
    id: int
    concept_id: int
    type: str
    stem: str
    options: list[str] | None
    difficulty: str


class AttemptOut(BaseModel):
    id: int
    mode: str
    questions: list[PublicQuestion]


class AnswerIn(BaseModel):
    question_id: int
    response: str
    time_taken_s: int | None = Field(default=None, ge=0)


class AnswerFeedback(BaseModel):
    correct: bool
    marks: float
    answer: str
    explanation: str
    source_quote: str
    page: int


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    document_ids: list[int] = Field(min_length=1)
    k: int = Field(default=4, ge=1, le=10)


class Citation(BaseModel):
    document_id: int
    document_title: str
    page: int
    quote: str
    score: float


class ChatOut(BaseModel):
    answer: str
    citations: list[Citation]


class SubjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    profile: dict[str, Any] = Field(default_factory=dict)


class SubjectOut(ORMModel):
    id: int
    name: str
    profile: dict[str, Any]


class CourseCreate(BaseModel):
    subject_id: int
    title: str = Field(min_length=2, max_length=250)
    term: str | None = Field(default=None, max_length=100)


class CourseOut(ORMModel):
    id: int
    subject_id: int
    title: str
    term: str | None
    status: str
    created_at: datetime


class UnitCreate(BaseModel):
    title: str = Field(min_length=2, max_length=250)
    order_idx: int = Field(default=0, ge=0)


class OutcomeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=3, max_length=2000)
    bloom_level: Literal["remember", "understand", "apply", "analyse", "evaluate", "create"] = "understand"


class GenerateArtifactIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    course_id: int | None = None
    document_ids: list[int] = Field(min_length=1)
    topic: str = Field(min_length=2, max_length=1000)
    artifact_type: Literal["assessment", "lesson_plan", "notes", "slides", "worksheet", "course_plan"]
    constraints: dict[str, Any] = Field(default_factory=dict)


class ArtifactPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    body: dict[str, Any] | None = None


class ArtifactOut(ORMModel):
    id: int
    course_id: int | None
    run_id: int | None
    artifact_type: str
    title: str
    status: str
    version: int
    body: dict[str, Any]
    sources: list[dict[str, Any]]
    warnings: list[str]
    created_at: datetime
    updated_at: datetime


class DecisionIn(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    comment: str | None = Field(default=None, max_length=2000)
