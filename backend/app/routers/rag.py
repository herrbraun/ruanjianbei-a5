from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.knowledge import get_scenic_area_by_code, list_scenic_areas
from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.knowledge import RagSearchRequest, RagSearchResponse, ScenicAreaOut
from app.services.retrieval import RetrievalError, search_active_profile


router = APIRouter(tags=["rag"])


@router.get("/scenic-areas", response_model=list[ScenicAreaOut])
def read_public_scenic_areas(db: Session = Depends(get_db)) -> list[ScenicAreaOut]:
    return list_scenic_areas(db, enabled_only=True)


@router.post("/rag/search", response_model=RagSearchResponse)
def search_rag(payload: RagSearchRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RagSearchResponse:
    scenic_area = get_scenic_area_by_code(db, payload.scenic_area_code)
    if scenic_area is None or not scenic_area.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="景区不存在或已停用")
    try:
        return search_active_profile(db, scenic_area, payload.query, payload.top_k, current_user.id)
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
