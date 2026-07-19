from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.crud.insights import recover_stale_insights
from app.database import SessionLocal
from app.routers import admin_analytics, auth, avatar, guide, insights, knowledge, media, rag, routes, spots, tts
from app.services.insight_report import recover_stale_reports


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.resolved_database_url.startswith("sqlite"):
        yield
        return
    with SessionLocal() as db:
        recover_stale_insights(db, datetime.now(timezone.utc) - timedelta(minutes=10))
        recover_stale_reports(db, datetime.now(timezone.utc) - timedelta(minutes=10))
    yield


app = FastAPI(title="AI Digital Human Tour Guide API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-TTS-Provider", "X-Audio-Format", "X-Audio-Sample-Rate"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(avatar.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(guide.router, prefix="/api")
app.include_router(spots.router, prefix="/api")
app.include_router(routes.router, prefix="/api")
app.include_router(routes.admin_router, prefix="/api")
app.include_router(admin_analytics.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(media.router)
app.include_router(tts.router, prefix="/api")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# In local/demo environments the backend can also host a built Vue bundle.
# This avoids requiring a separate Node listener and keeps browser API calls
# same-origin. The route is absent until a frontend production build exists.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"
frontend_animations = frontend_dist / "animations"
static_root = Path(__file__).resolve().parents[1] / "static"

static_root.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_root), name="static")

if frontend_index.is_file():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")
    if frontend_animations.is_dir():
        app.mount("/animations", StaticFiles(directory=frontend_animations), name="frontend-animations")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def serve_frontend(frontend_path: str) -> FileResponse:
        if frontend_path.startswith(("api/", "uploads/")):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(frontend_index)
