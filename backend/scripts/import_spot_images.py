from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models.spot import ScenicSpot, SpotMediaAsset  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
NAME_ALIASES = {"大照壁": "灵山大照壁"}
NUMBERED_SUFFIX = re.compile(r"[\s_-]*(?:\(\d+\)|（\d+）|\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import locally supplied scenic spot images")
    parser.add_argument("source", type=Path, help="Directory containing images named after scenic spots")
    parser.add_argument(
        "--public-base-url",
        default="http://127.0.0.1:8000",
        help="Backend origin used in persisted image URLs",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report matches without copying or writing data")
    return parser.parse_args()


def candidate_names(stem: str) -> list[str]:
    stripped = NUMBERED_SUFFIX.sub("", stem).strip()
    names = [stem.strip()]
    if stripped and stripped not in names:
        names.append(stripped)
    return [NAME_ALIASES.get(name, name) for name in names]


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    if not source.is_dir():
        raise SystemExit(f"Image directory does not exist: {source}")

    image_files = sorted(
        (path for path in source.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda path: path.name,
    )
    destination = Path(__file__).resolve().parents[1] / "static" / "spots"

    with SessionLocal() as db:
        spots = list(db.scalars(select(ScenicSpot).order_by(ScenicSpot.id)).all())
        spots_by_name = {spot.name: spot for spot in spots}
        matched: dict[int, list[Path]] = defaultdict(list)
        unmatched: list[Path] = []

        for image in image_files:
            spot = next((spots_by_name[name] for name in candidate_names(image.stem) if name in spots_by_name), None)
            if spot is None:
                unmatched.append(image)
                continue
            matched[spot.id].append(image)

        missing = [spot for spot in spots if spot.id not in matched]
        print(f"Images found: {len(image_files)}")
        print(f"Spots matched: {len(matched)} / {len(spots)}")
        for spot in spots:
            if spot.id in matched:
                print(f"  MATCH {spot.external_id or spot.id} {spot.name}: {', '.join(path.name for path in matched[spot.id])}")
        print(f"Unmatched images: {len(unmatched)}")
        for image in unmatched:
            print(f"  EXTRA {image.name}")
        print(f"Spots without images: {len(missing)}")
        for spot in missing:
            print(f"  MISSING {spot.external_id or spot.id} {spot.scenic_area} / {spot.name}")

        if args.dry_run:
            return

        destination.mkdir(parents=True, exist_ok=True)
        public_base_url = args.public_base_url.rstrip("/")
        for spot in spots:
            files = matched.get(spot.id)
            if not files:
                continue
            current_urls: set[str] = set()
            file_prefix = spot.external_id or f"spot-{spot.id}"
            for index, source_file in enumerate(files, start=1):
                extension = ".jpg" if source_file.suffix.lower() == ".jpeg" else source_file.suffix.lower()
                filename = f"{file_prefix}-{index:02d}{extension}"
                target = destination / filename
                shutil.copy2(source_file, target)
                url = f"{public_base_url}/static/spots/{filename}"
                current_urls.add(url)
                if index == 1:
                    spot.cover_image_url = url

                asset = db.scalar(
                    select(SpotMediaAsset).where(
                        SpotMediaAsset.spot_id == spot.id,
                        SpotMediaAsset.url == url,
                    )
                )
                if asset is None:
                    asset = SpotMediaAsset(spot_id=spot.id, media_type="image", url=url)
                    db.add(asset)
                asset.description = f"{spot.name}实景图片"
                asset.sort_order = index
                asset.status = "enabled"

            stale_assets = list(
                db.scalars(
                    select(SpotMediaAsset).where(
                        SpotMediaAsset.spot_id == spot.id,
                        SpotMediaAsset.media_type == "image",
                        SpotMediaAsset.url.like("%/static/spots/%"),
                    )
                ).all()
            )
            for asset in stale_assets:
                if asset.url not in current_urls:
                    db.delete(asset)

        db.commit()
        print(f"Imported {sum(len(files) for files in matched.values())} image assets into {destination}")


if __name__ == "__main__":
    main()
