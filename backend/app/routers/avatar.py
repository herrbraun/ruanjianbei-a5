from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.avatar import (
    create_scenic_avatar_config,
    default_scenic_avatar_config,
    get_avatar_variant,
    get_digital_human,
    get_scenic_avatar_config,
    list_digital_humans,
    list_scenic_avatar_configs,
    update_scenic_avatar_config,
)
from app.crud.knowledge import get_scenic_area_by_code, get_scenic_area_by_id
from app.database import get_db
from app.models.avatar import AvatarVariant, DigitalHuman, ScenicAvatarConfig
from app.models.user import User
from app.routers.auth import get_current_user, require_admin
from app.schemas.avatar import (
    AvatarVariantOut,
    AvatarVariantUpdate,
    DigitalHumanCreate,
    DigitalHumanOut,
    DigitalHumanUpdate,
    ScenicAvatarConfigUpdate,
    ScenicAvatarListOut,
    ScenicAvatarOut,
    VoiceOptionOut,
)
from app.services.avatar_storage import (
    AvatarStorageError,
    content_sha256,
    delete_stored_vrm,
    save_vrm_upload,
    storage_path,
    validate_vrm_upload,
)


router = APIRouter(tags=["avatars"])


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _voice_options(provider: str) -> list[VoiceOptionOut]:
    if provider == "volcengine":
        return [
            VoiceOptionOut(provider=provider, value=value, label=label)
            for value, label in settings.volcengine_tts_voices
        ]
    if provider == "dashscope":
        return [
            VoiceOptionOut(provider=provider, value=voice, label=voice)
            for voice in settings.guide_tts_voice_values
        ]
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的语音服务商")


def _validate_voice(provider: str, voice: str) -> None:
    if voice not in {option.value for option in _voice_options(provider)}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请选择系统配置中的有效音色")


def _normalize_required_form_text(value: str, field_label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_label}不能为空")
    return normalized


def _normalize_optional_form_text(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def _scenic_avatar_out(config: ScenicAvatarConfig) -> ScenicAvatarOut:
    variant = config.avatar_variant
    human = variant.digital_human
    return ScenicAvatarOut(
        config_id=config.id,
        scenic_area_id=config.scenic_area_id,
        id=variant.id,
        digital_human_id=human.id,
        name=human.name,
        gender=human.gender,
        role_title=human.role_title,
        introduction=human.introduction,
        outfit_name=variant.outfit_name,
        version=variant.version,
        thumbnail_url=variant.thumbnail_url,
        file_size=variant.file_size,
        is_enabled=config.is_enabled,
        is_default=config.is_default,
        sort_order=config.sort_order,
    )


@router.get("/admin/avatars/voices", response_model=list[VoiceOptionOut])
def read_voice_options(
    provider: str = "volcengine",
    _: User = Depends(require_admin),
) -> list[VoiceOptionOut]:
    return _voice_options(provider)


@router.get("/admin/avatars/humans", response_model=list[DigitalHumanOut])
def read_digital_humans(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[DigitalHuman]:
    return list_digital_humans(db)


@router.post("/admin/avatars/humans", response_model=DigitalHumanOut, status_code=status.HTTP_201_CREATED)
def create_digital_human(
    payload: DigitalHumanCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DigitalHuman:
    selected_provider = payload.tts_provider
    if "tts_provider" not in payload.model_fields_set and payload.tts_voice in settings.guide_tts_voice_values:
        selected_provider = "dashscope"
    _validate_voice(selected_provider, payload.tts_voice)
    human = DigitalHuman(**payload.model_dump(exclude={"tts_provider"}), tts_provider=selected_provider)
    db.add(human)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="数字人中文名已存在") from exc
    return get_digital_human(db, human.id) or human


@router.patch("/admin/avatars/humans/{digital_human_id}", response_model=DigitalHumanOut)
def update_digital_human(
    digital_human_id: int,
    payload: DigitalHumanUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DigitalHuman:
    human = get_digital_human(db, digital_human_id)
    if human is None:
        raise _not_found("数字人不存在")
    values = payload.model_dump(exclude_unset=True)
    selected_provider = str(values.get("tts_provider", human.tts_provider))
    selected_voice = str(values.get("tts_voice", human.tts_voice))
    if "tts_voice" in values or "tts_provider" in values:
        _validate_voice(selected_provider, selected_voice)
    for field, value in values.items():
        setattr(human, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="数字人中文名已存在") from exc
    return get_digital_human(db, human.id) or human


@router.delete("/admin/avatars/humans/{digital_human_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_digital_human(digital_human_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    human = get_digital_human(db, digital_human_id)
    if human is None:
        raise _not_found("数字人不存在")
    stored_filenames = [variant.stored_filename for variant in human.variants]
    db.delete(human)
    db.commit()
    for stored_filename in stored_filenames:
        delete_stored_vrm(stored_filename)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/avatars/scenic-configs", response_model=list[ScenicAvatarOut])
def read_scenic_avatar_configs(
    scenic_area_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ScenicAvatarOut]:
    if get_scenic_area_by_id(db, scenic_area_id) is None:
        raise _not_found("景区不存在")
    return [_scenic_avatar_out(config) for config in list_scenic_avatar_configs(db, scenic_area_id)]


@router.post("/admin/avatars/variants", response_model=ScenicAvatarOut, status_code=status.HTTP_201_CREATED)
async def upload_avatar_variant(
    digital_human_id: Annotated[int, Form(gt=0)],
    scenic_area_id: Annotated[int, Form(gt=0)],
    outfit_name: Annotated[str, Form(min_length=1, max_length=120)],
    file: Annotated[UploadFile, File(...)],
    version: Annotated[str, Form(min_length=1, max_length=40)] = "v1",
    thumbnail_url: Annotated[str | None, Form(max_length=500)] = None,
    is_enabled: Annotated[bool, Form()] = True,
    is_default: Annotated[bool, Form()] = False,
    sort_order: Annotated[int, Form(ge=-1000, le=1000)] = 0,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScenicAvatarOut:
    normalized_outfit_name = _normalize_required_form_text(outfit_name, "服装名称")
    normalized_version = _normalize_required_form_text(version, "版本号")
    normalized_thumbnail_url = _normalize_optional_form_text(thumbnail_url)
    human = get_digital_human(db, digital_human_id)
    if human is None:
        raise _not_found("数字人不存在")
    if get_scenic_area_by_id(db, scenic_area_id) is None:
        raise _not_found("景区不存在")
    content = await file.read(settings.avatar_max_upload_bytes + 1)
    original_filename = Path(file.filename or "avatar.vrm").name
    try:
        validate_vrm_upload(content, original_filename)
    except AvatarStorageError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        await file.close()

    try:
        stored_filename = save_vrm_upload(content)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="数字人模型文件保存失败") from exc
    try:
        variant = AvatarVariant(
            digital_human_id=human.id,
            outfit_name=normalized_outfit_name,
            version=normalized_version,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_hash=content_sha256(content),
            file_size=len(content),
            thumbnail_url=normalized_thumbnail_url,
        )
        db.add(variant)
        db.flush()
        config = create_scenic_avatar_config(
            db,
            scenic_area_id=scenic_area_id,
            avatar_variant_id=variant.id,
            is_enabled=is_enabled,
            is_default=is_default,
            sort_order=sort_order,
            commit=False,
        )
        db.commit()
    except (IntegrityError, ValueError) as exc:
        db.rollback()
        delete_stored_vrm(stored_filename)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该人物已存在相同服装和版本") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        delete_stored_vrm(stored_filename)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="数字人外观保存失败") from exc
    refreshed = get_scenic_avatar_config(db, scenic_area_id, config.avatar_variant_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="数字人外观保存失败")
    return _scenic_avatar_out(refreshed)


@router.patch("/admin/avatars/variants/{avatar_variant_id}", response_model=AvatarVariantOut)
def update_avatar_variant(
    avatar_variant_id: int,
    payload: AvatarVariantUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AvatarVariant:
    variant = get_avatar_variant(db, avatar_variant_id)
    if variant is None:
        raise _not_found("数字人外观不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该人物已存在相同服装和版本") from exc
    return variant


@router.delete("/admin/avatars/variants/{avatar_variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar_variant(avatar_variant_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    variant = get_avatar_variant(db, avatar_variant_id)
    if variant is None:
        raise _not_found("数字人外观不存在")
    stored_filename = variant.stored_filename
    db.delete(variant)
    db.commit()
    delete_stored_vrm(stored_filename)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/admin/avatars/scenic-configs/{config_id}", response_model=ScenicAvatarOut)
def update_scenic_avatar_configuration(
    config_id: int,
    payload: ScenicAvatarConfigUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScenicAvatarOut:
    config = db.scalar(
        select(ScenicAvatarConfig)
        .where(ScenicAvatarConfig.id == config_id)
    )
    if config is None:
        raise _not_found("景区数字人配置不存在")
    update_scenic_avatar_config(db, config, **payload.model_dump(exclude_unset=True))
    refreshed = get_scenic_avatar_config(db, config.scenic_area_id, config.avatar_variant_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="数字人配置更新失败")
    return _scenic_avatar_out(refreshed)


@router.get("/avatars/scenic-areas/{scenic_area_code}", response_model=ScenicAvatarListOut)
def read_public_scenic_avatars(
    scenic_area_code: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenicAvatarListOut:
    scenic_area = get_scenic_area_by_code(db, scenic_area_code)
    if scenic_area is None or not scenic_area.is_enabled:
        raise _not_found("景区不存在或未启用")
    configs = list_scenic_avatar_configs(db, scenic_area.id, enabled_only=True)
    default = next((config.avatar_variant_id for config in configs if config.is_default), configs[0].avatar_variant_id if configs else None)
    return ScenicAvatarListOut(
        scenic_area_id=scenic_area.id,
        default_variant_id=default,
        avatars=[_scenic_avatar_out(config) for config in configs],
    )


@router.get("/avatars/scenic-areas/{scenic_area_code}/variants/{avatar_variant_id}/asset")
def download_scenic_avatar_asset(
    scenic_area_code: str,
    avatar_variant_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    scenic_area = get_scenic_area_by_code(db, scenic_area_code)
    if scenic_area is None:
        raise _not_found("景区不存在")
    config = get_scenic_avatar_config(
        db,
        scenic_area.id,
        avatar_variant_id,
        enabled_only=current_user.role != "admin",
    )
    if config is None:
        raise _not_found("数字人外观未在当前景区上架")
    path = storage_path(config.avatar_variant.stored_filename)
    if not path.exists():
        raise _not_found("数字人模型文件不存在")
    cache_headers = {
        "Cache-Control": "private, max-age=31536000, immutable",
        "Vary": "Authorization",
    }
    response = FileResponse(
        path,
        media_type="model/gltf-binary",
        filename=config.avatar_variant.original_filename,
        content_disposition_type="inline",
        headers=cache_headers,
        stat_result=path.stat(),
    )
    if request.headers.get("if-none-match") == response.headers.get("etag"):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                **cache_headers,
                "ETag": response.headers["etag"],
                "Last-Modified": response.headers["last-modified"],
                "Accept-Ranges": "bytes",
            },
        )
    return response
