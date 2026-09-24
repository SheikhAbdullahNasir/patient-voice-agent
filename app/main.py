"""App entry point: creates the FastAPI app and makes every error use the same envelope."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routes import dashboard, patients, vapi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")

app = FastAPI(title="Patient Registration API")
app.include_router(patients.router)
app.include_router(vapi.router)
app.include_router(dashboard.router)


def error_response(status: int, message: str, fields: list | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"data": None, "error": {"message": message, "fields": fields or []}},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if any(e["type"] == "json_invalid" for e in errors):
        return error_response(400, "Request body is not valid JSON")
    fields = []
    for err in errors:
        loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        message = err["msg"].removeprefix("Value error, ")
        fields.append({"field": ".".join(loc), "message": message})
    summary = "; ".join(
        f"{f['field']}: {f['message']}" if f["field"] else f["message"] for f in fields
    )
    return error_response(422, f"Validation failed - {summary}", fields)


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    return error_response(exc.status_code, str(exc.detail))


@app.exception_handler(Exception)
async def unexpected_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return error_response(500, "Internal server error")


@app.get("/health")
def health():
    return {"data": {"status": "ok"}, "error": None}