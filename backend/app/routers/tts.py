from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.tts import ensure_tts_provider_settings, set_default_provider, set_fallback_provider
from app.database import get_db
from app.models.avatar import TtsProviderSetting
from app.models.user import User
from app.routers.auth import require_admin
from app.schemas.avatar import TtsProviderSettingOut, TtsProviderSettingUpdate, TtsProviderTestRequest
from app.services.speech import SpeechError
from app.services.streaming_speech import TtsRuntimeConfig, prepare_speech_stream


router = APIRouter(prefix="/admin/tts", tags=["tts"])


def _voice_values(provider: str) -> set[str]:
    if provider == "volcengine":
        return {value for value, _ in settings.volcengine_tts_voices}
    if provider == "dashscope":
        return set(settings.guide_tts_voice_values)
    return set()


def _validate_voice(provider: str, voice: str) -> None:
    if voice not in _voice_values(provider):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请选择该服务商配置中的有效音色")


def _configured(provider: str) -> bool:
    if provider == "volcengine":
        return bool(
            settings.resolved_volcengine_tts_api_key
            and settings.resolved_volcengine_tts_api_key not in {"your_volcengine_tts_api_key", "your_doubao_api_key"}
        )
    return bool(settings.dashscope_api_key and settings.dashscope_api_key != "your_dashscope_api_key")


def _out(item: TtsProviderSetting) -> TtsProviderSettingOut:
    return TtsProviderSettingOut(
        provider=item.provider,
        display_name=item.display_name,
        is_enabled=item.is_enabled,
        is_default=item.is_default,
        is_fallback=item.is_fallback,
        model=item.model,
        default_voice=item.default_voice,
        first_chunk_timeout_ms=item.first_chunk_timeout_ms,
        configured=_configured(item.provider),
    )


@router.get("/providers", response_model=list[TtsProviderSettingOut])
def list_tts_providers(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[TtsProviderSettingOut]:
    return [_out(item) for item in ensure_tts_provider_settings(db)]


@router.patch("/providers/{provider}", response_model=TtsProviderSettingOut)
def update_tts_provider(
    provider: str,
    payload: TtsProviderSettingUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TtsProviderSettingOut:
    ensure_tts_provider_settings(db)
    item = db.scalar(select(TtsProviderSetting).where(TtsProviderSetting.provider == provider))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="语音服务商不存在")
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_default") is True and values.get("is_fallback") is True:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="同一服务不能同时设为默认和备用")
    if "default_voice" in values:
        _validate_voice(provider, str(values["default_voice"]))
    if values.get("is_enabled") is False and (item.is_default or item.is_fallback):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="默认或备用服务不能直接停用，请先调整服务角色")
    make_default = values.pop("is_default", False)
    make_fallback = values.pop("is_fallback", False)
    current_default = next((setting for setting in ensure_tts_provider_settings(db) if setting.is_default), None)
    current_fallback = next((setting for setting in ensure_tts_provider_settings(db) if setting.is_fallback), None)
    if make_default:
        set_default_provider(db, provider)
        if item.is_fallback and current_default is not None and current_default.provider != provider:
            set_fallback_provider(db, current_default.provider)
    if make_fallback:
        if item.is_default and current_fallback is not None and current_fallback.provider != provider:
            set_default_provider(db, current_fallback.provider)
        set_fallback_provider(db, provider)
    for field, value in values.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _out(item)


@router.post("/providers/{provider}/test")
async def test_tts_provider(
    provider: str,
    payload: TtsProviderTestRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    ensure_tts_provider_settings(db)
    item = db.scalar(select(TtsProviderSetting).where(TtsProviderSetting.provider == provider))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="语音服务商不存在")
    if not item.is_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="请先启用该语音服务")
    if payload.voice is not None:
        _validate_voice(provider, payload.voice)
    runtime = TtsRuntimeConfig(
        provider=item.provider,
        model=item.model,
        default_voice=item.default_voice,
        first_chunk_timeout_ms=item.first_chunk_timeout_ms,
    )
    try:
        prepared = await prepare_speech_stream(
            payload.text,
            primary=runtime,
            voice=payload.voice,
        )
    except SpeechError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StreamingResponse(
        prepared.chunks,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Audio-Format": "pcm_s16le",
            "X-Audio-Sample-Rate": str(prepared.sample_rate),
            "X-TTS-Provider": prepared.provider,
        },
    )
