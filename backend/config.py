from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=False)


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'ai-analytic-platform.db'}").strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _origins() -> tuple[str, ...]:
    value = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Analytic Platform"
    environment: str = os.getenv("ENVIRONMENT", "development").lower()
    database_url: str = _database_url()
    jwt_secret: str = os.getenv("JWT_SECRET", "local-development-secret-change-me")
    jwt_algorithm: str = "HS256"
    session_minutes: int = int(os.getenv("SESSION_MINUTES", "10080"))
    cookie_name: str = "ai_analytic_platform_session"
    cors_origins: tuple[str, ...] = _origins()
    frontend_dir: Path = ROOT_DIR / "frontend" / "dist"
    data_dir: Path = Path(os.getenv("DATA_DIR", str(ROOT_DIR / "data")))
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_api_url: str = os.getenv(
        "GROQ_API_URL",
        "https://api.groq.com/openai/v1/chat/completions",
    ).strip()
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    embedding_cache_dir: Path = Path(os.getenv("EMBEDDING_CACHE_DIR", str(ROOT_DIR / ".cache" / "fastembed")))
    embedding_local_files_only: bool = os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "false").lower() == "true"
    embedding_batch_size: int = max(1, min(64, int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))))
    embedding_threads: int = max(1, min(8, int(os.getenv("EMBEDDING_THREADS", "1"))))
    rag_top_k: int = max(1, min(12, int(os.getenv("RAG_TOP_K", "6"))))

    @property
    def secure_cookie(self) -> bool:
        return self.environment == "production"


settings = Settings()
