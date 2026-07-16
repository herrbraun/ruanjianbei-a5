from __future__ import annotations

from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse


router = APIRouter(tags=["media"])
USER_AVATAR_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads" / "avatars"
USER_AVATAR_PATTERN = re.compile(r"^user-\d+-[0-9a-f]{32}\.(?:png|jpg|webp)$")


@router.get("/uploads/avatars/{filename}", include_in_schema=False)
def read_user_avatar(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename or not USER_AVATAR_PATTERN.fullmatch(safe_name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    path = USER_AVATAR_DIRECTORY / safe_name
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
