from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.ocr.base import OcrProvider

PROVIDERS = ("gemini", "claude", "textract", "mock")


def _aws_configured() -> bool:
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


def configured(settings: Settings | None = None) -> dict[str, bool]:
    s = settings or get_settings()
    return {
        "gemini": bool(s.gemini_api_key),
        "claude": bool(s.anthropic_api_key),
        "textract": _aws_configured(),
        "mock": True,
    }


def active_name(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    choice = s.ocr_provider.lower()
    available = configured(s)
    if choice != "auto":
        if choice not in PROVIDERS:
            raise ValueError(f"unknown OCR_PROVIDER {choice!r}")
        return choice
    return next(p for p in PROVIDERS if available[p])


def build(name: str, settings: Settings | None = None) -> OcrProvider:
    s = settings or get_settings()
    if name == "gemini":
        from app.services.ocr.llm import GeminiProvider

        if not s.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        return GeminiProvider(s.gemini_api_key, s.gemini_model, s.ocr_timeout_seconds)
    if name == "claude":
        from app.services.ocr.llm import ClaudeProvider

        if not s.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        return ClaudeProvider(s.anthropic_api_key, s.claude_model, s.ocr_timeout_seconds)
    if name == "textract":
        from app.services.ocr.textract import TextractProvider

        return TextractProvider(s.aws_region)
    if name == "mock":
        from app.services.ocr.mock import MockProvider

        return MockProvider()
    raise ValueError(f"unknown provider {name!r}")


_override: OcrProvider | None = None


def set_provider(provider: OcrProvider | None) -> None:
    """Tests inject a provider here."""
    global _override
    _override = provider
    _cached.cache_clear()


@lru_cache
def _cached(name: str) -> OcrProvider:
    return build(name)


def get_provider(name: str | None = None) -> OcrProvider:
    if _override is not None:
        return _override
    return _cached(name or active_name())
