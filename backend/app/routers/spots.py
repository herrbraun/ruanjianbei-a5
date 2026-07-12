from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud.spots import (
    create_media_asset,
    create_spot,
    delete_media_asset,
    get_media_asset,
    get_spot,
    list_media_assets,
    list_spots,
    serialize_media,
    serialize_spot,
    update_media_asset,
    update_spot,
    update_spot_status,
)
from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user, require_admin
from app.schemas.spots import (
    SpotCreate,
    SpotMediaCreate,
    SpotMediaResponse,
    SpotMediaUpdate,
    SpotResponse,
    SpotStatusUpdate,
    SpotUpdate,
)

router = APIRouter(tags=["spots"])


def commit_conflict(exc: IntegrityError, db: Session) -> HTTPException:
    db.rollback()
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="External ID or media URL already exists")


@router.get("/spots", response_model=list[SpotResponse])
def read_spots(
    tag: str | None = Query(default=None, max_length=50),
    keyword: str | None = Query(default=None, max_length=120),
    scenic_area: str | None = Query(default=None, max_length=120),
    spot_type: str | None = Query(default=None, pattern="^(attraction|area|service)$"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return [
        serialize_spot(spot)
        for spot in list_spots(db, tag=tag, keyword=keyword, scenic_area=scenic_area, spot_type=spot_type)
    ]


@router.get("/spots/{spot_id}", response_model=SpotResponse)
def read_spot(spot_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    spot = get_spot(db, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    return serialize_spot(spot)


@router.get("/admin/spots", response_model=list[SpotResponse])
def read_admin_spots(
    scenic_area: str | None = Query(default=None, max_length=120),
    spot_type: str | None = Query(default=None, pattern="^(attraction|area|service)$"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    return [
        serialize_spot(spot, include_disabled_media=True)
        for spot in list_spots(db, include_disabled=True, scenic_area=scenic_area, spot_type=spot_type)
    ]


@router.post("/admin/spots", response_model=SpotResponse, status_code=status.HTTP_201_CREATED)
def create_admin_spot(payload: SpotCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    try:
        return serialize_spot(create_spot(db, payload), include_disabled_media=True)
    except IntegrityError as exc:
        raise commit_conflict(exc, db) from exc


@router.put("/admin/spots/{spot_id}", response_model=SpotResponse)
def update_admin_spot(
    spot_id: int,
    payload: SpotUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = get_spot(db, spot_id, include_disabled=True)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    try:
        return serialize_spot(update_spot(db, spot, payload), include_disabled_media=True)
    except IntegrityError as exc:
        raise commit_conflict(exc, db) from exc


@router.patch("/admin/spots/{spot_id}/status", response_model=SpotResponse)
def update_admin_spot_status(
    spot_id: int,
    payload: SpotStatusUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = get_spot(db, spot_id, include_disabled=True)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    return serialize_spot(update_spot_status(db, spot, payload.status), include_disabled_media=True)


@router.get("/admin/media", response_model=list[SpotMediaResponse])
def read_admin_media(
    spot_id: int | None = Query(default=None, gt=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    return [serialize_media(asset, include_spot_name=True) for asset in list_media_assets(db, spot_id=spot_id)]


@router.post("/admin/media", response_model=SpotMediaResponse, status_code=status.HTTP_201_CREATED)
def create_admin_media(
    payload: SpotMediaCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if get_spot(db, payload.spot_id, include_disabled=True) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    try:
        return serialize_media(create_media_asset(db, payload), include_spot_name=True)
    except IntegrityError as exc:
        raise commit_conflict(exc, db) from exc


@router.put("/admin/media/{asset_id}", response_model=SpotMediaResponse)
def update_admin_media(
    asset_id: int,
    payload: SpotMediaUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    asset = get_media_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
    if get_spot(db, payload.spot_id, include_disabled=True) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    try:
        return serialize_media(update_media_asset(db, asset, payload), include_spot_name=True)
    except IntegrityError as exc:
        raise commit_conflict(exc, db) from exc


@router.delete("/admin/media/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_media(
    asset_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    asset = get_media_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
    delete_media_asset(db, asset)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
