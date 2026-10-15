"""Vision LLM providers: Gemini (default) and Claude.

Both are called over plain REST with httpx rather than through their SDKs, which
keeps the dependency list short and the request shape visible in one place.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import logging

import httpx

from app.services.ocr.base import OcrResult, ProviderError
from app.services.ocr.prompt import PROMPT, SCHEMA, parse_response

log = logging.getLogger("rxvision.ocr")

RETRY_STATUSES = {429, 500, 502, 503, 504}


async def _post(url: str, *, headers: dict, payload: dict, timeout: float, service: str) -> dict:
    """POST with one retry on rate limiting or a server error."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(2):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException:
                raise ProviderError(f"{service} took too long to respond. Try again.")
            except httpx.HTTPError as e:
                raise ProviderError(f"Could not reach {service}", str(e))

            if response.status_code in RETRY_STATUSES and attempt == 0:
                await asyncio.sleep(1.5)
                continue
            if response.status_code in (401, 403):
                raise ProviderError(f"{service} rejected the API key. Check the server configuration.")
            if response.status_code == 429:
                raise ProviderError(f"{service} rate limit reached. Try again in a minute.")
            if response.status_code >= 400:
                log.warning("%s error %s: %s", service, response.status_code, response.text[:500])
                raise ProviderError(f"{service} could not read this image", response.text[:500])
            return response.json()
    raise ProviderError(f"{service} is unavailable right now")


def _gemini_schema(node):
    """Gemini's schema dialect spells types in upper case."""
    node = copy.deepcopy(node)
    if isinstance(node, dict):
        if isinstance(node.get("type"), str):
            node["type"] = node["type"].upper()
        return {k: _gemini_schema(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_gemini_schema(v) for v in node]
    return node


class GeminiProvider:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, timeout: float = 45.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def read(self, image: bytes, mime: str) -> OcrResult:
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": PROMPT},
                        {"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": _gemini_schema(SCHEMA),
            },
        }
        data = await _post(
            self.URL.format(model=self.model),
            headers={"x-goog-api-key": self.api_key},
            payload=payload,
            timeout=self.timeout,
            service="Gemini",
        )
        try:
            candidate = data["candidates"][0]
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise ProviderError(
                "Gemini declined to read this image" if reason else "Gemini returned no result",
                str(data)[:500],
            )
        return parse_response(text)


class ClaudeProvider:
    name = "claude"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, timeout: float = 45.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def read(self, image: bytes, mime: str) -> OcrResult:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": mime,
                                       "data": base64.b64encode(image).decode()},
                        },
                        {"type": "text", "text": PROMPT + "\nRespond with only the JSON object."},
                    ],
                }
            ],
        }
        data = await _post(
            self.URL,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            payload=payload,
            timeout=self.timeout,
            service="Claude",
        )
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if not text:
            raise ProviderError("Claude returned no result", str(data)[:500])
        return parse_response(text)
