from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
SAMPLE_CSV = BACKEND_DIR / "app" / "data" / "sample_medicines.csv"

DEV_SECRET = "dev-only-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://rx:rx@localhost:5432/rxvision"

    jwt_secret: str = DEV_SECRET
    jwt_ttl_days: int = 7
    cookie_name: str = "rx_session"
    cookie_secure: bool = False

    ocr_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-5-5"
    aws_region: str = "ap-south-1"
    ocr_timeout_seconds: float = 45.0

    storage_dir: Path = BACKEND_DIR / "var" / "images"
    index_cache_dir: Path = BACKEND_DIR / "var" / "cache"
    medicine_csv: Path = SAMPLE_CSV

    max_upload_mb: int = 10
    match_threshold: int = 68
    rate_limit_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret == DEV_SECRET:
        raise RuntimeError("JWT_SECRET must be set in production")
    return settings
