from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from uuid import uuid4

from app.config import settings


AVATAR_UPLOAD_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads" / "avatars"
AVATAR_MANIFEST_PATH = AVATAR_UPLOAD_DIRECTORY / "manifest.json"


class AvatarStorageError(ValueError):
    pass


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_vrm_upload(content: bytes, original_filename: str) -> None:
    if not original_filename.lower().endswith(".vrm"):
        raise AvatarStorageError("仅支持上传 .vrm 数字人模型文件")
    if not content:
        raise AvatarStorageError("上传的 VRM 文件为空")
    if len(content) > settings.avatar_max_upload_bytes:
        raise AvatarStorageError("VRM 文件超过 80MB 限制")
    if len(content) < 20 or content[:4] != b"glTF":
        raise AvatarStorageError("文件不是有效的 GLB/VRM 模型")
    version, declared_length = struct.unpack_from("<II", content, 4)
    if version != 2 or declared_length != len(content):
        raise AvatarStorageError("VRM 文件的 GLB 头信息不完整或无效")


def save_vrm_upload(content: bytes) -> str:
    AVATAR_UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}.vrm"
    (AVATAR_UPLOAD_DIRECTORY / stored_filename).write_bytes(content)
    return stored_filename


def storage_path(stored_filename: str) -> Path:
    root = AVATAR_UPLOAD_DIRECTORY.resolve()
    path = (root / Path(stored_filename).name).resolve()
    if path.parent != root:
        raise AvatarStorageError("模型存储路径不安全")
    return path


def delete_stored_vrm(stored_filename: str) -> None:
    try:
        payload = json.loads(AVATAR_MANIFEST_PATH.read_text(encoding="utf-8"))
        packaged = {
            str(item.get("stored_filename"))
            for item in payload.get("avatars", [])
            if isinstance(item, dict)
        }
    except (OSError, json.JSONDecodeError):
        packaged = set()
    if Path(stored_filename).name in packaged:
        return
    storage_path(stored_filename).unlink(missing_ok=True)
