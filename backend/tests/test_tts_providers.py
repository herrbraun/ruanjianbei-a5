from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.services import streaming_speech
from app.services.speech import SpeechError
from app.services.streaming_speech import TtsRuntimeConfig, prepare_speech_stream


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_switch_default_tts_provider(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/admin/tts/providers", headers=headers)
    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()}
    assert providers["volcengine"]["is_default"] is True
    assert providers["dashscope"]["is_fallback"] is True
    assert "api_key" not in response.text

    switched = client.patch(
        "/api/admin/tts/providers/dashscope",
        headers=headers,
        json={"is_default": True},
    )
    assert switched.status_code == 200
    providers = {
        item["provider"]: item
        for item in client.get("/api/admin/tts/providers", headers=headers).json()
    }
    assert providers["dashscope"]["is_default"] is True
    assert providers["volcengine"]["is_fallback"] is True


def test_provider_rejects_conflicting_roles_and_unknown_voice(client: TestClient) -> None:
    headers = _admin_headers(client)
    conflict = client.patch(
        "/api/admin/tts/providers/volcengine",
        headers=headers,
        json={"is_default": True, "is_fallback": True},
    )
    assert conflict.status_code == 422
    invalid_voice = client.patch(
        "/api/admin/tts/providers/volcengine",
        headers=headers,
        json={"default_voice": "Cherry"},
    )
    assert invalid_voice.status_code == 422


def test_stream_falls_back_only_before_first_audio(monkeypatch) -> None:
    primary = TtsRuntimeConfig("volcengine", "seed-tts-2.0", "voice-a", 500)
    fallback = TtsRuntimeConfig("dashscope", "qwen", "voice-b", 500)

    def fake_provider(config, text, *, voice, instructions):
        async def chunks():
            if config.provider == "volcengine":
                raise SpeechError("primary unavailable")
            yield b"\x01\x00"
            yield b"\x02\x00"
        return chunks()

    monkeypatch.setattr(streaming_speech, "_provider_stream", fake_provider)
    async def exercise() -> None:
        prepared = await prepare_speech_stream("测试讲解", primary=primary, fallback=fallback)
        assert prepared.provider == "dashscope"
        assert b"".join([chunk async for chunk in prepared.chunks]) == b"\x01\x00\x02\x00"

    asyncio.run(exercise())


def test_stream_does_not_change_voice_after_first_audio(monkeypatch) -> None:
    primary = TtsRuntimeConfig("volcengine", "seed-tts-2.0", "voice-a", 500)
    fallback = TtsRuntimeConfig("dashscope", "qwen", "voice-b", 500)

    def fake_provider(config, text, *, voice, instructions):
        async def chunks():
            if config.provider == "dashscope":
                yield b"\x09\x00"
                return
            yield b"\x01\x00"
            raise SpeechError("connection dropped")
        return chunks()

    monkeypatch.setattr(streaming_speech, "_provider_stream", fake_provider)
    async def exercise() -> None:
        prepared = await prepare_speech_stream("测试讲解", primary=primary, fallback=fallback)
        assert prepared.provider == "volcengine"
        iterator = prepared.chunks.__aiter__()
        assert await anext(iterator) == b"\x01\x00"
        with pytest.raises(SpeechError, match="connection dropped"):
            await anext(iterator)

    asyncio.run(exercise())
