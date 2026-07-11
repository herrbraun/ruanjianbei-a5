from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.avatar import AvatarVariant, DigitalHuman, ScenicAvatarConfig


def list_digital_humans(db: Session) -> list[DigitalHuman]:
    statement = select(DigitalHuman).options(selectinload(DigitalHuman.variants)).order_by(DigitalHuman.name)
    return list(db.scalars(statement))


def get_digital_human(db: Session, digital_human_id: int) -> DigitalHuman | None:
    return db.scalar(
        select(DigitalHuman).options(selectinload(DigitalHuman.variants)).where(DigitalHuman.id == digital_human_id)
    )


def get_avatar_variant(db: Session, avatar_variant_id: int) -> AvatarVariant | None:
    return db.scalar(
        select(AvatarVariant)
        .options(selectinload(AvatarVariant.digital_human), selectinload(AvatarVariant.scenic_configs))
        .where(AvatarVariant.id == avatar_variant_id)
    )


def list_scenic_avatar_configs(db: Session, scenic_area_id: int, *, enabled_only: bool = False) -> list[ScenicAvatarConfig]:
    statement = (
        select(ScenicAvatarConfig)
        .options(selectinload(ScenicAvatarConfig.avatar_variant).selectinload(AvatarVariant.digital_human))
        .where(ScenicAvatarConfig.scenic_area_id == scenic_area_id)
        .order_by(ScenicAvatarConfig.sort_order, ScenicAvatarConfig.id)
    )
    if enabled_only:
        statement = statement.join(AvatarVariant).join(DigitalHuman).where(
            ScenicAvatarConfig.is_enabled.is_(True), DigitalHuman.is_enabled.is_(True), AvatarVariant.validation_status == "ready"
        )
    return list(db.scalars(statement))


def get_scenic_avatar_config(db: Session, scenic_area_id: int, avatar_variant_id: int, *, enabled_only: bool = False) -> ScenicAvatarConfig | None:
    configs = list_scenic_avatar_configs(db, scenic_area_id, enabled_only=enabled_only)
    return next((config for config in configs if config.avatar_variant_id == avatar_variant_id), None)


def default_scenic_avatar_config(db: Session, scenic_area_id: int) -> ScenicAvatarConfig | None:
    configs = list_scenic_avatar_configs(db, scenic_area_id, enabled_only=True)
    return next((config for config in configs if config.is_default), configs[0] if configs else None)


def create_scenic_avatar_config(
    db: Session,
    *,
    scenic_area_id: int,
    avatar_variant_id: int,
    is_enabled: bool,
    is_default: bool,
    sort_order: int,
    commit: bool = True,
) -> ScenicAvatarConfig:
    if is_default:
        db.execute(
            update(ScenicAvatarConfig)
            .where(ScenicAvatarConfig.scenic_area_id == scenic_area_id)
            .values(is_default=False)
        )
    config = ScenicAvatarConfig(
        scenic_area_id=scenic_area_id,
        avatar_variant_id=avatar_variant_id,
        is_enabled=is_enabled,
        is_default=is_default and is_enabled,
        sort_order=sort_order,
    )
    db.add(config)
    if commit:
        db.commit()
        db.refresh(config)
    else:
        db.flush()
    return config


def update_scenic_avatar_config(db: Session, config: ScenicAvatarConfig, **values: object) -> ScenicAvatarConfig:
    is_enabled = values.get("is_enabled", config.is_enabled)
    is_default = values.get("is_default", config.is_default)
    if is_default:
        db.execute(
            update(ScenicAvatarConfig)
            .where(ScenicAvatarConfig.scenic_area_id == config.scenic_area_id, ScenicAvatarConfig.id != config.id)
            .values(is_default=False)
        )
    for field, value in values.items():
        setattr(config, field, value)
    if not is_enabled:
        config.is_default = False
    elif is_default:
        config.is_default = True
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
