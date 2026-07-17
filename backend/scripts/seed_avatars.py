from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

from sqlalchemy import select

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.crud.avatar import create_scenic_avatar_config
from app.crud.knowledge import get_scenic_area_by_code
from app.database import SessionLocal
from app.models.avatar import AvatarVariant, DigitalHuman, ScenicAvatarConfig
from app.services.avatar_storage import (
    AVATAR_UPLOAD_DIRECTORY,
    content_sha256,
    validate_vrm_upload,
)


DEFAULT_MANIFEST = AVATAR_UPLOAD_DIRECTORY / "manifest.json"


@dataclass(frozen=True)
class SeedAvatar:
    name: str
    gender: str
    role_title: str
    introduction: str
    tts_instructions: str
    outfit_name: str
    version: str
    original_filename: str
    stored_filename: str
    sha256: str
    file_size: int
    is_default: bool
    sort_order: int


def load_seed_manifest(manifest_path: Path) -> tuple[str, list[SeedAvatar]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"数字人清单不存在：{manifest_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"数字人清单无法读取：{manifest_path}") from exc
    if payload.get("schema_version") != 1 or not isinstance(payload.get("avatars"), list):
        raise SystemExit("数字人清单格式无效")
    try:
        avatars = [SeedAvatar(**item) for item in payload["avatars"]]
    except (TypeError, KeyError) as exc:
        raise SystemExit("数字人清单缺少必要字段") from exc
    if not avatars or sum(avatar.is_default for avatar in avatars) != 1:
        raise SystemExit("数字人清单必须包含且仅包含一个默认人物")
    if len({(avatar.name, avatar.outfit_name, avatar.version) for avatar in avatars}) != len(avatars):
        raise SystemExit("数字人清单包含重复的人物外观版本")
    scenic_code = str(payload.get("scenic_code") or "").strip()
    if not scenic_code:
        raise SystemExit("数字人清单缺少景区编码")
    return scenic_code, avatars


def verify_manifest_assets(manifest_path: Path, avatars: list[SeedAvatar]) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    root = manifest_path.parent.resolve()
    for avatar in avatars:
        if Path(avatar.stored_filename).name != avatar.stored_filename:
            raise SystemExit(f"模型存储名不安全：{avatar.stored_filename}")
        path = (root / avatar.stored_filename).resolve()
        if path.parent != root or not path.is_file():
            raise SystemExit(f"仓库缺少数字人模型：{path}")
        content = path.read_bytes()
        validate_vrm_upload(content, avatar.original_filename)
        if len(content) != avatar.file_size:
            raise SystemExit(f"模型大小校验失败：{avatar.stored_filename}")
        if content_sha256(content) != avatar.sha256:
            raise SystemExit(f"模型 SHA-256 校验失败：{avatar.stored_filename}")
        assets[avatar.stored_filename] = content
    return assets


def seed(
    manifest_path: Path,
    scenic_code: str | None = None,
    *,
    session_factory=SessionLocal,
) -> None:
    manifest_code, avatars = load_seed_manifest(manifest_path)
    verify_manifest_assets(manifest_path, avatars)
    target_code = scenic_code or manifest_code
    db = session_factory()
    try:
        scenic_area = get_scenic_area_by_code(db, target_code)
        if scenic_area is None:
            raise SystemExit(f"景区不存在：{target_code}，请先导入示范景区资料")
        for item in avatars:
            human = db.scalar(select(DigitalHuman).where(DigitalHuman.name == item.name))
            if human is None:
                human = DigitalHuman(
                    name=item.name,
                    gender=item.gender,
                    role_title=item.role_title,
                    introduction=item.introduction,
                    tts_provider="volcengine",
                    tts_voice=(
                        "zh_male_dayi_uranus_bigtts"
                        if item.gender == "male"
                        else settings.volcengine_tts_default_voice
                    ),
                    tts_instructions=item.tts_instructions,
                )
                db.add(human)
                db.flush()
            variant = db.scalar(
                select(AvatarVariant).where(
                    AvatarVariant.digital_human_id == human.id,
                    AvatarVariant.outfit_name == item.outfit_name,
                    AvatarVariant.version == item.version,
                )
            )
            if variant is None:
                variant = AvatarVariant(
                    digital_human_id=human.id,
                    outfit_name=item.outfit_name,
                    version=item.version,
                    original_filename=item.original_filename,
                    stored_filename=item.stored_filename,
                    content_hash=item.sha256,
                    file_size=item.file_size,
                )
                db.add(variant)
                db.flush()
            existing = db.scalar(
                select(ScenicAvatarConfig)
                .where(
                    ScenicAvatarConfig.scenic_area_id == scenic_area.id,
                    ScenicAvatarConfig.avatar_variant_id == variant.id,
                )
            )
            if existing is None:
                create_scenic_avatar_config(
                    db,
                    scenic_area_id=scenic_area.id,
                    avatar_variant_id=variant.id,
                    is_enabled=True,
                    is_default=item.is_default,
                    sort_order=item.sort_order,
                    commit=False,
                )
        db.commit()
        print(f"已从仓库清单导入 {len(avatars)} 个数字人模型到 {scenic_area.name}")
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从仓库清单导入自制 VRM 数字人")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="数字人 manifest.json 路径")
    parser.add_argument("--scenic-code", help="覆盖清单中的景区编码")
    parser.add_argument("--verify-only", action="store_true", help="仅校验清单和 VRM 文件，不写数据库")
    args = parser.parse_args()
    _, manifest_avatars = load_seed_manifest(args.manifest)
    verify_manifest_assets(args.manifest, manifest_avatars)
    if args.verify_only:
        print(f"数字人素材校验通过：{len(manifest_avatars)} 个 VRM")
    else:
        seed(args.manifest, args.scenic_code)
