from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import httpx

from app.config import settings
from app.services.guide_answer import strip_source_markers


class SpeechError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecognizedSpeech:
    transcript: str
    model: str
    duration_ms: int


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    media_type: str


_INPUT_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
}


def _require_api_key() -> str:
    key = settings.dashscope_api_key
    if not key or key == "your_dashscope_api_key":
        raise SpeechError("未配置 DASHSCOPE_API_KEY，无法使用语音服务")
    return key


def _ffmpeg_binary() -> str:
    binary = settings.media_ffmpeg_binary
    if Path(binary).is_file() or shutil.which(binary):
        return binary
    raise SpeechError("未找到 ffmpeg，无法处理录音。请安装 ffmpeg 或设置 MEDIA_FFMPEG_BINARY")


def _to_pcm_wav(audio: bytes, content_type: str | None) -> bytes:
    if not audio:
        raise SpeechError("录音文件为空")
    if len(audio) > settings.guide_max_audio_bytes:
        raise SpeechError("录音文件过大，请控制在 6 MB 以内")

    extension = _INPUT_EXTENSIONS.get((content_type or "").lower(), ".webm")
    with tempfile.TemporaryDirectory(prefix="ai-tour-guide-asr-") as directory:
        directory_path = Path(directory)
        source_path = directory_path / f"input{extension}"
        output_path = directory_path / "normalized.wav"
        source_path.write_bytes(audio)
        try:
            subprocess.run(
                [
                    _ffmpeg_binary(),
                    "-nostdin",
                    "-y",
                    "-i",
                    str(source_path),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    str(output_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=settings.guide_audio_transcode_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpeechError("录音转码超时，请缩短录音后重试") from exc
        except OSError as exc:
            raise SpeechError("无法启动 ffmpeg 处理录音") from exc

        if not output_path.exists() or not output_path.stat().st_size:
            raise SpeechError("无法识别该录音格式，请使用浏览器重新录音")
        normalized = output_path.read_bytes()

    if len(normalized) > settings.guide_max_normalized_audio_bytes:
        raise SpeechError("录音时长过长，请控制在 90 秒以内")
    return normalized


def recognize_speech(audio: bytes, content_type: str | None) -> RecognizedSpeech:
    api_key = _require_api_key()
    normalized = _to_pcm_wav(audio, content_type)
    encoded_audio = base64.b64encode(normalized).decode("ascii")
    started = perf_counter()
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.guide_asr_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": f"data:audio/wav;base64,{encoded_audio}"},
                            }
                        ],
                    }
                ],
                "stream": False,
                "asr_options": {"language": "zh", "enable_itn": True},
            },
            timeout=90.0,
        )
    except httpx.HTTPError as exc:
        raise SpeechError("语音识别服务连接失败") from exc

    if response.is_error:
        raise SpeechError(f"语音识别失败（HTTP {response.status_code}）：{response.text[:240]}")
    try:
        payload = response.json()
        choices = payload.get("choices")
        transcript = choices[0]["message"]["content"] if isinstance(choices, list) and choices else ""
    except (KeyError, TypeError, ValueError) as exc:
        raise SpeechError("语音识别返回格式异常") from exc
    if not isinstance(transcript, str) or not transcript.strip():
        raise SpeechError("没有识别到清晰语音，请靠近麦克风后重试")
    return RecognizedSpeech(
        transcript=transcript.strip(),
        model=settings.guide_asr_model,
        duration_ms=round((perf_counter() - started) * 1000),
    )


def synthesize_speech(
    text: str,
    *,
    model: str | None = None,
    voice: str | None = None,
    instructions: str | None = None,
) -> SynthesizedSpeech:
    text = strip_source_markers(text)
    if not text.strip():
        raise SpeechError("没有可播报的文本")
    if len(text) > settings.guide_tts_max_characters:
        raise SpeechError("回答内容过长，暂时无法播报")

    api_key = _require_api_key()
    try:
        with httpx.Client(timeout=90.0, follow_redirects=True) as client:
            response = client.post(
                f"{settings.dashscope_base_url.rstrip('/')}/services/aigc/multimodal-generation/generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model or settings.guide_tts_model,
                    "input": {"text": text, "voice": voice or settings.tts_voice, "language_type": "Chinese"},
                    "parameters": {
                        "instructions": instructions or settings.tts_instructions,
                        "optimize_instructions": True,
                    },
                },
            )
            if response.is_error:
                raise SpeechError(f"语音合成失败（HTTP {response.status_code}）：{response.text[:240]}")
            try:
                audio_url = response.json()["output"]["audio"]["url"]
            except (KeyError, TypeError, ValueError) as exc:
                raise SpeechError("语音合成没有返回音频") from exc
            if not isinstance(audio_url, str) or not audio_url.startswith(("https://", "http://")):
                raise SpeechError("语音合成返回了无效音频地址")
            audio_response = client.get(audio_url)
            if audio_response.is_error or not audio_response.content:
                raise SpeechError("无法获取生成的语音文件")
            content_type = audio_response.headers.get("content-type", "audio/wav").split(";", 1)[0]
            if not content_type.startswith("audio/"):
                content_type = "audio/wav"
            return SynthesizedSpeech(audio=audio_response.content, media_type=content_type)
    except httpx.HTTPError as exc:
        raise SpeechError("语音合成服务连接失败") from exc
