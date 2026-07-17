from __future__ import annotations

import asyncio
import base64
import io
import json
import wave
from dataclasses import dataclass
from typing import AsyncIterator
from uuid import uuid4

import httpx

from app.config import settings
from app.services.guide_answer import strip_source_markers
from app.services.speech import SpeechError, synthesize_speech


@dataclass(frozen=True)
class TtsRuntimeConfig:
    provider: str
    model: str
    default_voice: str
    first_chunk_timeout_ms: int


@dataclass(frozen=True)
class PreparedSpeechStream:
    chunks: AsyncIterator[bytes]
    provider: str
    sample_rate: int = 24000


def _require_volcengine_api_key() -> str:
    key = settings.resolved_volcengine_tts_api_key
    if not key or key in {"your_volcengine_tts_api_key", "your_doubao_api_key"}:
        raise SpeechError("未配置 VOLCENGINE_TTS_API_KEY，无法使用火山引擎语音服务")
    return key


async def _iter_volcengine_pcm(
    text: str,
    *,
    voice: str,
    model: str,
    instructions: str | None,
) -> AsyncIterator[bytes]:
    request_params: dict[str, object] = {
        "text": text,
        "speaker": voice,
        "audio_params": {"format": "pcm", "sample_rate": 24000},
    }
    if instructions:
        request_params["additions"] = json.dumps(
            {"explicit_language": "zh", "context_texts": [instructions]},
            ensure_ascii=False,
        )
    decoder = json.JSONDecoder()
    buffer = ""
    completed = False
    resource_id = model if model.startswith("seed-tts-") else settings.volcengine_tts_resource_id
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=8.0)) as client:
            async with client.stream(
                "POST",
                settings.volcengine_tts_endpoint,
                headers={
                    "X-Api-Key": _require_volcengine_api_key(),
                    "X-Api-Resource-Id": resource_id,
                    "X-Api-Request-Id": str(uuid4()),
                    "Content-Type": "application/json",
                },
                json={"req_params": request_params},
            ) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="replace")
                    raise SpeechError(f"火山引擎语音合成失败（HTTP {response.status_code}）：{detail[:240]}")
                async for raw in response.aiter_text():
                    buffer += raw
                    offset = 0
                    while True:
                        while offset < len(buffer) and buffer[offset].isspace():
                            offset += 1
                        if offset >= len(buffer):
                            buffer = ""
                            break
                        try:
                            event, end = decoder.raw_decode(buffer, offset)
                        except json.JSONDecodeError:
                            buffer = buffer[offset:]
                            break
                        offset = end
                        code = event.get("code")
                        if code == 0 and event.get("data"):
                            try:
                                chunk = base64.b64decode(event["data"], validate=True)
                            except (ValueError, TypeError) as exc:
                                raise SpeechError("火山引擎返回了无效的音频分片") from exc
                            if chunk:
                                yield chunk
                        elif code == 20000000:
                            completed = True
                        elif code != 0:
                            raise SpeechError(f"火山引擎语音合成失败：{event.get('message') or code}")
                if not completed:
                    raise SpeechError("火山引擎语音流提前结束")
    except httpx.HTTPError as exc:
        raise SpeechError("火山引擎实时语音服务连接失败") from exc


def _wav_to_pcm(audio: bytes) -> bytes:
    try:
        with wave.open(io.BytesIO(audio), "rb") as stream:
            if stream.getnchannels() != 1 or stream.getsampwidth() != 2 or stream.getframerate() != 24000:
                raise SpeechError("千问语音返回格式不是 24kHz 单声道 PCM")
            return stream.readframes(stream.getnframes())
    except (wave.Error, EOFError) as exc:
        raise SpeechError("千问语音返回了无法解析的音频") from exc


async def _iter_dashscope_pcm(
    text: str,
    *,
    model: str,
    voice: str,
    instructions: str | None,
) -> AsyncIterator[bytes]:
    synthesized = await asyncio.to_thread(
        synthesize_speech,
        text,
        model=model,
        voice=voice,
        instructions=instructions,
    )
    pcm = _wav_to_pcm(synthesized.audio)
    chunk_size = 24000
    for offset in range(0, len(pcm), chunk_size):
        yield pcm[offset : offset + chunk_size]


def _provider_stream(
    config: TtsRuntimeConfig,
    text: str,
    *,
    voice: str | None,
    instructions: str | None,
) -> AsyncIterator[bytes]:
    selected_voice = voice or config.default_voice
    if config.provider == "volcengine":
        return _iter_volcengine_pcm(
            text,
            voice=selected_voice,
            model=config.model,
            instructions=instructions,
        )
    if config.provider == "dashscope":
        return _iter_dashscope_pcm(text, model=config.model, voice=selected_voice, instructions=instructions)
    raise SpeechError("不支持的语音服务商")


async def prepare_speech_stream(
    text: str,
    *,
    primary: TtsRuntimeConfig,
    fallback: TtsRuntimeConfig | None = None,
    voice: str | None = None,
    instructions: str | None = None,
) -> PreparedSpeechStream:
    normalized = strip_source_markers(text).strip()
    if not normalized:
        raise SpeechError("没有可播报的文本")
    if len(normalized) > settings.guide_tts_max_characters:
        raise SpeechError("回答内容过长，暂时无法播报")

    async def prime(config: TtsRuntimeConfig, selected_voice: str | None) -> tuple[bytes, AsyncIterator[bytes]]:
        stream = _provider_stream(
            config,
            normalized,
            voice=selected_voice,
            instructions=instructions,
        )
        try:
            first = await asyncio.wait_for(anext(stream), timeout=config.first_chunk_timeout_ms / 1000)
        except StopAsyncIteration as exc:
            raise SpeechError("语音服务没有返回音频") from exc
        return first, stream

    selected = primary
    try:
        first_chunk, remaining = await prime(primary, voice)
    except (SpeechError, asyncio.TimeoutError) as primary_error:
        if fallback is None or fallback.provider == primary.provider:
            if isinstance(primary_error, asyncio.TimeoutError):
                raise SpeechError("语音服务首包超时") from primary_error
            raise
        selected = fallback
        try:
            first_chunk, remaining = await prime(fallback, None)
        except asyncio.TimeoutError as exc:
            raise SpeechError("主语音与备用语音服务均未能在时限内返回首包") from exc

    async def chunks() -> AsyncIterator[bytes]:
        yield first_chunk
        async for chunk in remaining:
            yield chunk

    return PreparedSpeechStream(chunks=chunks(), provider=selected.provider)
