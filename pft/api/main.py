"""FastAPI application. Every route lives under /api so the frontend can proxy it."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pft.api.accounts import router as accounts_router
from pft.api.dashboard import router as dashboard_router
from pft.api.exports import router as exports_router
from pft.api.recurring import router as recurring_router
from pft.api.reports import router as reports_router
from pft.domain.exceptions import (
    AccountNotFoundError,
    DuplicateTransactionError,
    FinanceError,
    StorageError,
    TransactionNotFoundError,
)

HOST = "127.0.0.1"
PORT = 8000

app = FastAPI(title="Personal Finance Tracker")
app.include_router(exports_router)
app.include_router(accounts_router)
app.include_router(dashboard_router)
app.include_router(recurring_router)
app.include_router(reports_router)


def _status_for(error: FinanceError) -> int:
    if isinstance(error, AccountNotFoundError | TransactionNotFoundError):
        return 404
    if isinstance(error, DuplicateTransactionError):
        return 409
    if isinstance(error, StorageError):
        return 500
    return 422


@app.exception_handler(FinanceError)
async def finance_error_handler(request: Request, exc: FinanceError) -> JSONResponse:
    """Every domain error reaches React as {code, message, field}."""
    return JSONResponse(status_code=_status_for(exc), content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def request_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """A malformed request body uses the same shape instead of FastAPI's default."""
    first = exc.errors()[0]
    field = str(first["loc"][-1]) if first["loc"] else None
    message = f"{field or 'request'}: {first['msg']}"
    return JSONResponse(
        status_code=422, content={"code": "invalid_request", "message": message, "field": field}
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    """Serve the API on localhost only; the app has no auth."""
    import uvicorn

    uvicorn.run("pft.api.main:app", host=HOST, port=PORT, reload=False)
