"""FastAPI entry point for the local traffic lookup backend."""
from contextlib import closing
import logging
import os
from pathlib import Path
import sqlite3
from time import perf_counter

from fastapi import FastAPI, HTTPException

from scripts.query_catalog import DEFAULT_DB

from .schemas import ChatRequest, ChatResponse, HealthResponse
from .service import chat, connect_catalog, health

logger = logging.getLogger("uvicorn.error")


def create_app(db_path: Path | None = None) -> FastAPI:
    catalog_path = db_path or Path(os.environ.get("CATALOG_DB_PATH") or DEFAULT_DB)
    app = FastAPI(title="Chatbot tra cứu xử phạt giao thông", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    def health_check() -> HealthResponse:
        try:
            return health(catalog_path)
        except sqlite3.Error as error:
            logger.warning("catalog health unavailable: %s", error)
            raise HTTPException(503, detail="Catalog SQLite chưa sẵn sàng.") from error

    @app.post("/chat", response_model=ChatResponse)
    def chat_endpoint(request: ChatRequest) -> ChatResponse:
        start = perf_counter()
        try:
            with closing(connect_catalog(catalog_path)) as con:
                result = chat(con, request)
        except sqlite3.Error as error:
            logger.warning("catalog lookup unavailable: %s", error)
            raise HTTPException(503, detail="Catalog SQLite chưa sẵn sàng.") from error
        logger.info(
            "chat intent=%s answer_type=%s latency_ms=%.1f",
            result.intent, result.answer_type, (perf_counter() - start) * 1000,
        )
        return result

    return app


app = create_app()
