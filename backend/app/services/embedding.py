from __future__ import annotations

from collections.abc import Callable, Iterable

import httpx

from app.config import settings


EMBEDDING_DIMENSIONS = 1024
EMBEDDING_BATCH_SIZE = 10
EMBEDDING_MODEL = "text-embedding-v4"


class EmbeddingError(RuntimeError):
    pass


def _endpoint() -> str:
    return f"{settings.dashscope_base_url.rstrip('/')}/services/embeddings/text-embedding/text-embedding"


def _read_embeddings(payload: dict[object, object]) -> list[list[float]]:
    output = payload.get("output")
    if not isinstance(output, dict):
        raise EmbeddingError("Embedding 服务返回缺少 output")
    rows = output.get("embeddings")
    if not isinstance(rows, list):
        raise EmbeddingError("Embedding 服务返回缺少 embeddings")
    vectors: list[list[float]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("embedding"), list):
            raise EmbeddingError("Embedding 服务返回向量格式异常")
        vector = row["embedding"]
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(f"Embedding 维度异常：期望 {EMBEDDING_DIMENSIONS}，实际 {len(vector)}")
        vectors.append([float(value) for value in vector])
    return vectors


ProgressCallback = Callable[[int, int], None]


def embed_texts(
    texts: Iterable[str],
    text_type: str,
    on_progress: ProgressCallback | None = None,
) -> list[list[float]]:
    items = list(texts)
    if not items:
        return []
    if not settings.dashscope_api_key or settings.dashscope_api_key == "your_dashscope_api_key":
        raise EmbeddingError("未配置 DASHSCOPE_API_KEY，无法生成向量")
    vectors: list[list[float]] = []
    headers = {"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=60.0) as client:
            for offset in range(0, len(items), EMBEDDING_BATCH_SIZE):
                batch = items[offset : offset + EMBEDDING_BATCH_SIZE]
                response = client.post(
                    _endpoint(),
                    headers=headers,
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": {"texts": batch},
                        "parameters": {"text_type": text_type, "dimension": EMBEDDING_DIMENSIONS},
                    },
                )
                if response.is_error:
                    raise EmbeddingError(f"Embedding 服务调用失败（HTTP {response.status_code}）：{response.text[:300]}")
                batch_vectors = _read_embeddings(response.json())
                if len(batch_vectors) != len(batch):
                    raise EmbeddingError("Embedding 服务返回的向量数与输入不一致")
                vectors.extend(batch_vectors)
                if on_progress is not None:
                    on_progress(len(vectors), len(items))
    except httpx.HTTPError as exc:
        raise EmbeddingError("Embedding 服务连接失败") from exc
    return vectors


def embed_documents(
    texts: Iterable[str],
    on_progress: ProgressCallback | None = None,
) -> list[list[float]]:
    return embed_texts(texts, text_type="document", on_progress=on_progress)


def embed_query(text: str) -> list[float]:
    return embed_texts([text], text_type="query")[0]
