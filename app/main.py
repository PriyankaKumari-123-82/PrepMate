from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, career, chat, dashboard, documents, educator, practice, settings
from app.config import get_settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Alembic owns production schema changes; this makes SQLite/local demos immediate.
    Base.metadata.create_all(engine)
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="PrepMate API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(practice.router)
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(educator.router)
app.include_router(settings.router)
app.include_router(career.router)


@app.get("/health")
def health():
    return {"status": "ok"}
