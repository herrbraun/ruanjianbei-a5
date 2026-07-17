from __future__ import annotations

from pathlib import Path
import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_port_override: int | None = None
    secret_key: str
    access_token_expire_minutes: int = 1440
    backend_cors_origins: str = "http://localhost:5173"
    initial_admin_username: str = "admin"
    initial_admin_password: str = ""
    llm_provider: str = "dashscope"
    dashscope_api_key: str = ""
    dashscope_api_host: str = "dashscope.aliyuncs.com"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    llm_chat_model: str = "qwen-plus"
    llm_embedding_model: str = "text-embedding-v4"
    llm_rerank_model: str = "qwen3-rerank"
    insight_analysis_model: str = "qwen-plus"
    insight_report_model: str = "qwen-plus"
    rag_vector_backend: str = "pgvector"
    rag_json_candidate_limit: int = Field(default=2000, ge=1, le=10000)
    asr_model: str = "qwen3-asr-flash"
    tts_model: str = "qwen3-tts-instruct-flash"
    guide_asr_model: str = "qwen3-asr-flash"
    guide_tts_model: str = "qwen3-tts-instruct-flash"
    tts_voice: str = "Cherry"
    guide_tts_voice_options: str = "Cherry"
    volcengine_tts_api_key: str = ""
    doubao_tts_api_key: str = ""
    volcengine_tts_endpoint: str = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    volcengine_tts_resource_id: str = "seed-tts-2.0"
    volcengine_tts_model: str = "seed-tts-2.0"
    volcengine_tts_default_voice: str = "zh_female_vv_uranus_bigtts"
    volcengine_tts_voice_options: str = (
        "zh_female_vv_uranus_bigtts|Vivi 2.0（女声）,"
        "zh_male_dayi_uranus_bigtts|大壹（男声）"
    )
    tts_first_chunk_timeout_ms: int = Field(default=4500, ge=500, le=10000)
    tts_instructions: str = "以亲切、清晰、自然的中文景区讲解员语气播报，语速适中。"
    guide_max_audio_bytes: int = 6 * 1024 * 1024
    guide_max_normalized_audio_bytes: int = 7 * 1024 * 1024
    guide_audio_transcode_timeout_seconds: int = 30
    guide_tts_max_characters: int = 600
    avatar_max_upload_bytes: int = 80 * 1024 * 1024
    media_ffmpeg_binary: str = "ffmpeg"

    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parents[1] / ".env",
            Path(__file__).resolve().parents[1] / ".env.docker",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def guide_tts_voice_values(self) -> list[str]:
        configured = [voice.strip() for voice in self.guide_tts_voice_options.split(",") if voice.strip()]
        return configured or [self.tts_voice]

    @property
    def volcengine_tts_voices(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for item in self.volcengine_tts_voice_options.split(","):
            value, separator, label = item.strip().partition("|")
            if value:
                options.append((value, label.strip() if separator and label.strip() else value))
        return options or [(self.volcengine_tts_default_voice, self.volcengine_tts_default_voice)]

    @property
    def resolved_volcengine_tts_api_key(self) -> str:
        return self.volcengine_tts_api_key or self.doubao_tts_api_key

    @property
    def uses_json_vector_backend(self) -> bool:
        return self.rag_vector_backend.strip().lower() == "json" or self.resolved_database_url.startswith("sqlite")

    @property
    def resolved_database_url(self) -> str:
        if self.database_port_override is None:
            return self.database_url
        return re.sub(
            r"(@[^:/]+:)\d+(/)",
            rf"\g<1>{self.database_port_override}\g<2>",
            self.database_url,
            count=1,
        )


settings = Settings()
