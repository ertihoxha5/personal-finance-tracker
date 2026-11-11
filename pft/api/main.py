"""FastAPI application. Every route lives under /api so the frontend can proxy it."""

from __future__ import annotations

from fastapi import FastAPI

HOST = "127.0.0.1"
PORT = 8000

app = FastAPI(title="Personal Finance Tracker")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    """Serve the API on localhost only; the app has no auth."""
    import uvicorn

    uvicorn.run("pft.api.main:app", host=HOST, port=PORT, reload=False)
