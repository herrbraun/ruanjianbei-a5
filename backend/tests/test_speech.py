from __future__ import annotations

from unittest.mock import patch

import httpx

from app.config import settings
from app.services.speech import recognize_speech, synthesize_speech


def test_recognize_speech_uses_qwen_audio_message_shape() -> None:
    response = httpx.Response(200, json={"choices": [{"message": {"content": "recognized guide question"}}]})

    with (
        patch.object(settings, "dashscope_api_key", "test-key"),
        patch.object(settings, "guide_asr_model", "qwen3-asr-flash-test"),
        patch("app.services.speech._to_pcm_wav", return_value=b"normalized-wav"),
        patch("app.services.speech.httpx.post", return_value=response) as request,
    ):
        result = recognize_speech(b"browser-recording", "audio/webm")

    body = request.call_args.kwargs["json"]
    assert body["model"] == "qwen3-asr-flash-test"
    assert body["messages"][0]["content"][0]["type"] == "input_audio"
    assert body["messages"][0]["content"][0]["input_audio"]["data"].startswith("data:audio/wav;base64,")
    assert result.transcript == "recognized guide question"


def test_synthesize_speech_relays_audio_url_without_exposing_it() -> None:
    requests: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> httpx.Response:
            requests.append(("post", url))
            payload = kwargs["json"]
            assert isinstance(payload, dict)
            assert payload["model"] == "qwen3-tts-instruct-flash-test"
            assert payload["input"]["text"] == "short guide answer"
            return httpx.Response(200, json={"output": {"audio": {"url": "https://audio.example/generated.wav"}}})

        def get(self, url: str) -> httpx.Response:
            requests.append(("get", url))
            return httpx.Response(200, content=b"wav-bytes", headers={"content-type": "audio/wav"})

    with (
        patch.object(settings, "dashscope_api_key", "test-key"),
        patch.object(settings, "guide_tts_model", "qwen3-tts-instruct-flash-test"),
        patch("app.services.speech.httpx.Client", FakeClient),
    ):
        result = synthesize_speech("short guide answer [资料1]")

    assert result.audio == b"wav-bytes"
    assert result.media_type == "audio/wav"
    assert requests == [
        ("post", f"{settings.dashscope_base_url.rstrip('/')}/services/aigc/multimodal-generation/generation"),
        ("get", "https://audio.example/generated.wav"),
    ]
