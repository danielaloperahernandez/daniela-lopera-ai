"""FastAPI microservice: turn an uploaded PDF into validated structured JSON.

Endpoints:
    GET  /health          - liveness + which provider/model is configured
    POST /extract         - multipart PDF upload -> ExtractionResponse

Auth: a shared secret in the ``x-api-key`` header (set DOC_API_KEY). n8n sends this so the
service is not open to the world even when exposed via a tunnel.
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ai_core import get_settings

from .extraction import extract_pdf_text, parse_invoice
from .schemas import ExtractionResponse, HealthResponse

app = FastAPI(
    title="Document Intelligence API",
    version="0.1.0",
    description="Extract structured data from PDFs using RAG-style LLM parsing.",
)

MAX_BYTES = 10 * 1024 * 1024  # 10 MB upload cap


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Reject requests without the shared secret (if one is configured)."""
    expected = os.getenv("DOC_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing x-api-key")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        provider=settings.llm_provider,
        model=settings.chat_model_name,
    )


@app.post("/extract", response_model=ExtractionResponse, dependencies=[Depends(require_api_key)])
async def extract(file: UploadFile = File(...)) -> ExtractionResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")

    try:
        text, pages = extract_pdf_text(content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc

    if not text:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found (is this a scanned image PDF?).",
        )

    try:
        data = parse_invoice(text)
    except Exception as exc:  # noqa: BLE001
        # Surface a clean 502 so n8n's Error Trigger can branch and retry/notify.
        raise HTTPException(status_code=502, detail=f"LLM extraction failed: {exc}") from exc

    return ExtractionResponse(
        success=True,
        filename=file.filename or "upload.pdf",
        pages=pages,
        characters=len(text),
        data=data,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
    # Consistent error envelope so the n8n flow can read `error` reliably.
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )
