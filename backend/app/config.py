from __future__ import annotations

from pathlib import Path
import re

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_port_override: int | None = None
    secret_key: str
    access_token_expire_minutes: int = 1440
    backend_cors_origins: str = "http://localhost:5173"
    llm_provider: str = "dashscope"
    dashscope_api_key: str = ""
    dashscope_api_host: str = "dashscope.aliyuncs.com"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    llm_chat_model: str = "qwen-plus"
    llm_embedding_model: str = "text-embedding-v4"
    llm_rerank_model: str = "qwen3-rerank"
    asr_model: str = "fun-asr"
    tts_model: str = "cosyvoice-v3.5-plus"

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
