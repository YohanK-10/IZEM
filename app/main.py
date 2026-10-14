from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Added SessionLocal, AuthToken, and UserRole to imports
from fastapi.responses import JSONResponse
from app.models.db import init_db
from app.routes import auth
from app.routes.api import router as api_router
import app.routes.admin_signoff  # registers admin + signoff search routes onto api_router
from app.services.ai_job_queue import ai_job_queue


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await ai_job_queue.start()
    try:
        yield
    finally:
        await ai_job_queue.stop()


app = FastAPI(
    title="IZEM",
    description="AI-assisted queue and feedback system for educational environments",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(SecurityHeadersMiddleware)

# Allow Vue dev server (and Docker frontend) to call the API
_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SPA_DIST = Path("frontend/dist")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(api_router)
app.include_router(auth.router)


@app.get("/")
async def root():
    if (_SPA_DIST / "index.html").exists():
        return FileResponse(_SPA_DIST / "index.html")
    raise HTTPException(status_code=503, detail="Frontend build not found")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": getattr(exc, "detail", "Not found")}, status_code=404)
    # Let the SPA handle client-side 404s
    index = _SPA_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Not found"}, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return JSONResponse({"detail": getattr(exc, "detail", "Forbidden")}, status_code=403)


@app.exception_handler(400)
async def bad_request_handler(request: Request, exc):
    return JSONResponse({"detail": getattr(exc, "detail", "Bad request")}, status_code=400)

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_fallback(full_path: str):
    """Serve Vue SPA for any unmatched route (production build only)."""
    requested = _SPA_DIST / full_path
    if requested.is_file():
        return FileResponse(requested)
    index = _SPA_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
