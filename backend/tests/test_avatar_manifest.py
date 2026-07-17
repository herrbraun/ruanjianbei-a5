from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.avatar import AvatarVariant, DigitalHuman, ScenicAvatarConfig
from app.models.knowledge import ScenicArea
from app.services.avatar_storage import content_sha256
import scripts.seed_avatars as seed_module
from scripts.seed_avatars import load_seed_manifest, seed, verify_manifest_assets


def _valid_glb() -> bytes:
    payload = b"glTF" + struct.pack("<II", 2, 20) + b"\x00" * 8
    assert len(payload) == 20
    return payload


def _manifest(path: Path, *, digest: str, size: int) -> Path:
    payload = {
        "schema_version": 1,
        "scenic_code": "lingshan",
        "avatars": [
            {
                "name": "测试讲解员",
                "gender": "female",
                "role_title": "测试",
                "introduction": "测试人物",
                "tts_instructions": "自然讲解",
                "outfit_name": "测试服装",
                "version": "v1",
                "original_filename": "guide.vrm",
                "stored_filename": "guide.vrm",
                "sha256": digest,
                "file_size": size,
                "is_default": True,
                "sort_order": 0,
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_avatar_manifest_validates_repository_asset(tmp_path: Path) -> None:
    content = _valid_glb()
    (tmp_path / "guide.vrm").write_bytes(content)
    manifest = _manifest(tmp_path / "manifest.json", digest=content_sha256(content), size=len(content))
    scenic_code, avatars = load_seed_manifest(manifest)
    assets = verify_manifest_assets(manifest, avatars)
    assert scenic_code == "lingshan"
    assert assets == {"guide.vrm": content}


def test_avatar_manifest_rejects_tampered_asset(tmp_path: Path) -> None:
    content = _valid_glb()
    (tmp_path / "guide.vrm").write_bytes(content)
    manifest = _manifest(tmp_path / "manifest.json", digest="0" * 64, size=len(content))
    _, avatars = load_seed_manifest(manifest)
    with pytest.raises(SystemExit, match="SHA-256"):
        verify_manifest_assets(manifest, avatars)


def test_avatar_seed_rolls_back_everything_on_database_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _valid_glb()
    avatars = []
    for index in range(2):
        stored_filename = f"guide-{index}.vrm"
        (tmp_path / stored_filename).write_bytes(content)
        avatars.append(
            {
                "name": f"测试讲解员{index}",
                "gender": "female" if index == 0 else "male",
                "role_title": "测试",
                "introduction": "测试人物",
                "tts_instructions": "自然讲解",
                "outfit_name": f"测试服装{index}",
                "version": "v1",
                "original_filename": stored_filename,
                "stored_filename": stored_filename,
                "sha256": content_sha256(content),
                "file_size": len(content),
                "is_default": index == 0,
                "sort_order": index,
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"schema_version": 1, "scenic_code": "lingshan", "avatars": avatars},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        db.add(ScenicArea(code="lingshan", name="灵山胜境", is_enabled=True))
        db.commit()

    original_create = seed_module.create_scenic_avatar_config
    call_count = 0

    def fail_on_second_config(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("模拟配置写入失败")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(seed_module, "create_scenic_avatar_config", fail_on_second_config)
    with pytest.raises(RuntimeError, match="模拟配置写入失败"):
        seed(manifest, session_factory=testing_session)

    with testing_session() as db:
        assert db.scalar(select(func.count(DigitalHuman.id))) == 0
        assert db.scalar(select(func.count(AvatarVariant.id))) == 0
        assert db.scalar(select(func.count(ScenicAvatarConfig.id))) == 0
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
