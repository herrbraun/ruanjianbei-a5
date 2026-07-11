from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, avatar, guide, knowledge, rag


app = FastAPI(title="AI Digital Human Tour Guide API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(avatar.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(guide.router, prefix="/api")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# In local/demo environments the backend can also host a built Vue bundle.
# This avoids requiring a separate Node listener and keeps browser API calls
# same-origin. The route is absent until a frontend production build exists.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"

if frontend_index.is_file():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def serve_frontend(frontend_path: str) -> FileResponse:
        if frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(frontend_index)
