from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AuthIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


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

