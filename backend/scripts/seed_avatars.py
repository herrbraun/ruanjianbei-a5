from __future__ import annotations

import argparse
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
    save_vrm_upload,
    validate_vrm_upload,
)


SEED_AVATARS = (
    ("沈清莲", "female", "灵山文化讲解员", "以温和、沉静的文化讲解员语气，清晰介绍灵山历史与佛教艺术。", "Lingshan Cultural Guide.vrm", "浅青新中式"),
    ("顾听雪", "female", "四季风物讲解员", "以温柔、清爽的语气介绍灵山四季景观与出行建议。", "Lingshan Winter Guide.vrm", "冬日国风"),
    ("林青岚", "female", "山林生态讲解员", "以亲切、自然的语气介绍山林生态、徒步礼仪与安全提醒。", "Lingshan Forest Guide.vrm", "山林轻装"),
    ("苏澜", "female", "湖畔休闲讲解员", "以轻松、明快的语气介绍湖畔景致与休闲路线。", "Lingshan Lakeside Guide.vrm", "湖畔休闲装"),
    ("周知微", "female", "游客服务讲解员", "以专业、耐心的前台服务语气回答游客服务与动线问题。", "Lingshan Reception Guide.vrm", "正式接待装"),
    ("陆远峰", "male", "山地路线讲解员", "以稳重、可靠的语气介绍登山路线、观景点与安全事项。", "Lingshan Mountain Guide.vrm", "山地风衣"),
    ("程叙川", "male", "城市文化讲解员", "以友好、简洁的语气介绍城市文化与交通服务。", "Lingshan City Guide.vrm", "城市轻运动装"),
    ("谢文博", "male", "艺术展馆讲解员", "以文雅、清晰的语气介绍展馆艺术、参观秩序与文化背景。", "Lingshan Gallery Guide.vrm", "展馆简约装"),
    ("陈乐川", "male", "亲子互动讲解员", "以活泼、耐心的语气面向亲子游客说明互动体验。", "Lingshan Family Guide.vrm", "亲子活力装"),
    ("顾承文", "male", "遗产文化讲解员", "以庄重、平和的语气讲解文化遗产与参观礼仪。", "Lingshan Heritage Guide.vrm", "遗产正式装"),
)


def find_existing_upload(content: bytes) -> str | None:
    """Reuse a tracked VRM with identical content instead of duplicating it."""
    if not AVATAR_UPLOAD_DIRECTORY.exists():
        return None
    expected_hash = content_sha256(content)
    for candidate in AVATAR_UPLOAD_DIRECTORY.glob("*.vrm"):
        if candidate.stat().st_size != len(content):
            continue
        if content_sha256(candidate.read_bytes()) == expected_hash:
            return candidate.name
    return None


def seed(source: Path, scenic_code: str) -> None:
    db = SessionLocal()
    try:
        scenic_area = get_scenic_area_by_code(db, scenic_code)
        if scenic_area is None:
            raise SystemExit(f"景区不存在：{scenic_code}")
        for order, (name, gender, role_title, instructions, filename, outfit_name) in enumerate(SEED_AVATARS):
            human = db.scalar(select(DigitalHuman).where(DigitalHuman.name == name))
            if human is None:
                human = DigitalHuman(
                    name=name,
                    gender=gender,
                    role_title=role_title,
                    introduction=f"{role_title}，服务于灵山景区数字导览。",
                    tts_voice=settings.tts_voice,
                    tts_instructions=instructions,
                )
                db.add(human)
                db.flush()
            variant = db.scalar(
                select(AvatarVariant).where(
                    AvatarVariant.digital_human_id == human.id,
                    AvatarVariant.outfit_name == outfit_name,
                    AvatarVariant.version == "v1",
                )
            )
            if variant is None:
                source_path = source / filename
                if not source_path.exists():
                    raise SystemExit(f"缺少模型文件：{source_path}")
                content = source_path.read_bytes()
                validate_vrm_upload(content, filename)
                stored_filename = find_existing_upload(content) or save_vrm_upload(content)
                variant = AvatarVariant(
                    digital_human_id=human.id,
                    outfit_name=outfit_name,
                    version="v1",
                    original_filename=filename,
                    stored_filename=stored_filename,
                    content_hash=content_sha256(content),
                    file_size=len(content),
                )
                db.add(variant)
                db.flush()
            existing = db.scalar(
                select(AvatarVariant.id)
                .join_from(AvatarVariant, ScenicAvatarConfig)
                .where(
                    AvatarVariant.id == variant.id,
                    ScenicAvatarConfig.scenic_area_id == scenic_area.id,
                )
            )
            if existing is None:
                create_scenic_avatar_config(
                    db,
                    scenic_area_id=scenic_area.id,
                    avatar_variant_id=variant.id,
                    is_enabled=True,
                    is_default=order == 0,
                    sort_order=order,
                )
        db.commit()
        print(f"已导入 {len(SEED_AVATARS)} 个数字人模型到 {scenic_area.name}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入灵山自制 VRM 数字人")
    parser.add_argument("--source", type=Path, default=Path.home() / "Documents", help="VRM 所在目录")
    parser.add_argument("--scenic-code", default="lingshan")
    args = parser.parse_args()
    seed(args.source, args.scenic_code)
