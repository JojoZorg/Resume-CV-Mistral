"""Application configuration via environment variables."""
import os


class Settings:
    # "ollama" | "openai" | "none"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "")

    # Cloud providers must be no-training / enterprise endpoints.
    NO_TRAINING_NOTE: str = os.getenv(
        "NO_TRAINING_NOTE",
        "If a cloud LLM is configured, point it at a no-training / enterprise "
        "endpoint. Your CV and JD are never retained beyond the request.",
    )

    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    # Minimum text characters per PDF page before we suspect a scanned document.
    TEXT_PER_PAGE_FLOOR: int = int(os.getenv("TEXT_PER_PAGE_FLOOR", "120"))

    CORS_ORIGINS: list = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]


settings = Settings()
