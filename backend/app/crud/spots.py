from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.spot import ScenicSpot, SpotMediaAsset, SpotTag
from app.schemas.spots import SpotCreate, SpotMediaCreate, SpotMediaUpdate, SpotUpdate


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        value = tag.strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value[:50])
    return result


def serialize_media(asset: SpotMediaAsset, *, include_spot_name: bool = False) -> dict:
    return {
        "id": asset.id,
        "spot_id": asset.spot_id,
        "spot_name": asset.spot.name if include_spot_name and asset.spot else None,
        "media_type": asset.media_type,
        "url": asset.url,
        "description": asset.description,
        "sort_order": asset.sort_order,
        "status": asset.status,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


def serialize_spot(spot: ScenicSpot, *, include_disabled_media: bool = False) -> dict:
    media = [
        serialize_media(asset)
        for asset in spot.media_assets
        if include_disabled_media or asset.status == "enabled"
    ]
    return {
        "id": spot.id,
        "external_id": spot.external_id,
        "scenic_area": spot.scenic_area,
        "spot_type": spot.spot_type,
        "name": spot.name,
        "summary": spot.summary,
        "description": spot.description,
        "location": spot.location,
        "opening_hours": spot.opening_hours,
        "landscape_parameters": spot.landscape_parameters,
        "cultural_context": spot.cultural_context,
        "highlights": spot.highlights,
        "notes": spot.notes,
        "source_name": spot.source_name,
        "recommended_duration_minutes": spot.recommended_duration_minutes,
        "priority": spot.priority,
        "status": spot.status,
        "cover_image_url": spot.cover_image_url,
        "tags": [tag.name for tag in spot.tags],
        "media_assets": media,
        "created_at": spot.created_at,
        "updated_at": spot.updated_at,
    }


def list_spots(
    db: Session,
    *,
    include_disabled: bool = False,
    tag: str | None = None,
    keyword: str | None = None,
    scenic_area: str | None = None,
    spot_type: str | None = None,
) -> list[ScenicSpot]:
    stmt = select(ScenicSpot).options(selectinload(ScenicSpot.tags), selectinload(ScenicSpot.media_assets))

    if not include_disabled:
        stmt = stmt.where(ScenicSpot.status == "enabled")
    if tag:
        stmt = stmt.join(ScenicSpot.tags).where(func.lower(SpotTag.name) == tag.strip().lower())
    if scenic_area:
        stmt = stmt.where(ScenicSpot.scenic_area == scenic_area.strip())
    if spot_type:
        stmt = stmt.where(ScenicSpot.spot_type == spot_type)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                ScenicSpot.external_id.ilike(pattern),
                ScenicSpot.name.ilike(pattern),
                ScenicSpot.summary.ilike(pattern),
                ScenicSpot.description.ilike(pattern),
                ScenicSpot.location.ilike(pattern),
                ScenicSpot.cultural_context.ilike(pattern),
                ScenicSpot.highlights.ilike(pattern),
            )
        )

    return list(db.scalars(stmt.order_by(ScenicSpot.priority.desc(), ScenicSpot.id.asc())).unique())


def get_spot(db: Session, spot_id: int, *, include_disabled: bool = False) -> ScenicSpot | None:
    stmt = (
        select(ScenicSpot)
        .options(selectinload(ScenicSpot.tags), selectinload(ScenicSpot.media_assets))
        .where(ScenicSpot.id == spot_id)
    )
    if not include_disabled:
        stmt = stmt.where(ScenicSpot.status == "enabled")
    return db.scalar(stmt)


def replace_tags(spot: ScenicSpot, tags: list[str]) -> None:
    spot.tags.clear()
    spot.tags.extend(SpotTag(name=tag) for tag in normalize_tags(tags))


def spot_payload_data(payload: SpotCreate | SpotUpdate) -> dict:
    data = payload.model_dump(exclude={"tags"})
    if data.get("cover_image_url") is not None:
        data["cover_image_url"] = str(data["cover_image_url"])
    if data.get("external_id"):
        data["external_id"] = data["external_id"].strip()
    return data


def create_spot(db: Session, payload: SpotCreate) -> ScenicSpot:
    spot = ScenicSpot(**spot_payload_data(payload))
    replace_tags(spot, payload.tags)
    db.add(spot)
    db.commit()
    db.refresh(spot)
    return get_spot(db, spot.id, include_disabled=True) or spot


def update_spot(db: Session, spot: ScenicSpot, payload: SpotUpdate) -> ScenicSpot:
    for key, value in spot_payload_data(payload).items():
        setattr(spot, key, value)
    replace_tags(spot, payload.tags)
    db.commit()
    db.refresh(spot)
    return get_spot(db, spot.id, include_disabled=True) or spot


def update_spot_status(db: Session, spot: ScenicSpot, status: str) -> ScenicSpot:
    spot.status = status
    db.commit()
    db.refresh(spot)
    return get_spot(db, spot.id, include_disabled=True) or spot


def list_media_assets(db: Session, *, spot_id: int | None = None) -> list[SpotMediaAsset]:
    stmt = select(SpotMediaAsset).options(selectinload(SpotMediaAsset.spot))
    if spot_id is not None:
        stmt = stmt.where(SpotMediaAsset.spot_id == spot_id)
    return list(db.scalars(stmt.order_by(SpotMediaAsset.spot_id, SpotMediaAsset.sort_order, SpotMediaAsset.id)))


def get_media_asset(db: Session, asset_id: int) -> SpotMediaAsset | None:
    return db.scalar(
        select(SpotMediaAsset).options(selectinload(SpotMediaAsset.spot)).where(SpotMediaAsset.id == asset_id)
    )


def media_payload_data(payload: SpotMediaCreate | SpotMediaUpdate) -> dict:
    data = payload.model_dump()
    data["url"] = str(data["url"])
    return data


def create_media_asset(db: Session, payload: SpotMediaCreate) -> SpotMediaAsset:
    asset = SpotMediaAsset(**media_payload_data(payload))
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return get_media_asset(db, asset.id) or asset


def update_media_asset(db: Session, asset: SpotMediaAsset, payload: SpotMediaUpdate) -> SpotMediaAsset:
    for key, value in media_payload_data(payload).items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return get_media_asset(db, asset.id) or asset


def delete_media_asset(db: Session, asset: SpotMediaAsset) -> None:
    db.delete(asset)
    db.commit()
