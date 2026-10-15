from __future__ import annotations

import asyncio

from app.services.ocr.base import OcrResult, ProviderError


class TextractProvider:
    """AWS Textract. Text only: strong on print, weak on handwriting.

    v1 measured 12.9% recall on 30 handwritten prescriptions with this engine,
    which is why it is no longer the default.
    """

    name = "textract"

    def __init__(self, region: str):
        import boto3

        self._client = boto3.client("textract", region_name=region)

    def _read_sync(self, image: bytes) -> OcrResult:
        try:
            response = self._client.detect_document_text(Document={"Bytes": image})
        except Exception as e:  # botocore raises a zoo of exception types
            raise ProviderError("AWS Textract could not read this image", str(e))
        lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return OcrResult(text="\n".join(lines), lines=lines, medicines=None)

    async def read(self, image: bytes, mime: str) -> OcrResult:
        return await asyncio.to_thread(self._read_sync, image)
