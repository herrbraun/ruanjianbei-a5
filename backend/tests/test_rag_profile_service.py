from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.crud.knowledge import activate_profile, create_profile
from app.database import Base
from app.models.knowledge import KnowledgeBase, RagProfile, RagProfileKnowledgeBase, ScenicArea


def test_activating_profile_archives_previous_active_profile() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db: Session = session_factory()
    try:
        scenic = ScenicArea(code="test-scenic", name="测试景区")
        base = KnowledgeBase(code="test-base", name="测试资料库")
        db.add_all([scenic, base])
        db.commit()
        db.refresh(scenic)
        db.refresh(base)
        first = create_profile(db, RagProfile(scenic_area_id=scenic.id, name="正式版", status="active"), [RagProfileKnowledgeBase(knowledge_base_id=base.id)])
        second = create_profile(db, RagProfile(scenic_area_id=scenic.id, name="候选版", status="draft"), [RagProfileKnowledgeBase(knowledge_base_id=base.id)])
        activate_profile(db, second)
        statuses = dict(db.execute(select(RagProfile.name, RagProfile.status)).all())
        assert statuses[first.name] == "archived"
        assert statuses[second.name] == "active"
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
