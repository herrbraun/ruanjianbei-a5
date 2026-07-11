from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.knowledge import KnowledgeBase, KnowledgeDocument, RagProfile, RagProfileKnowledgeBase, ScenicArea


def list_scenic_areas(db: Session, enabled_only: bool = False) -> list[ScenicArea]:
    statement = select(ScenicArea).order_by(ScenicArea.name)
    if enabled_only:
        statement = statement.where(ScenicArea.is_enabled.is_(True))
    return list(db.scalars(statement))


def get_scenic_area_by_id(db: Session, scenic_area_id: int) -> ScenicArea | None:
    return db.get(ScenicArea, scenic_area_id)


def get_scenic_area_by_code(db: Session, code: str) -> ScenicArea | None:
    return db.scalar(select(ScenicArea).where(ScenicArea.code == code))


def create_scenic_area(db: Session, **values: object) -> ScenicArea:
    scenic_area = ScenicArea(**values)
    db.add(scenic_area)
    db.commit()
    db.refresh(scenic_area)
    return scenic_area


def list_knowledge_bases(db: Session) -> list[KnowledgeBase]:
    return list(db.scalars(select(KnowledgeBase).order_by(KnowledgeBase.name)))


def get_knowledge_base(db: Session, knowledge_base_id: int) -> KnowledgeBase | None:
    return db.get(KnowledgeBase, knowledge_base_id)


def create_knowledge_base(db: Session, **values: object) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(**values)
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


def list_profiles(db: Session, scenic_area_id: int | None = None) -> list[RagProfile]:
    statement = select(RagProfile).options(selectinload(RagProfile.knowledge_base_bindings).selectinload(RagProfileKnowledgeBase.knowledge_base))
    if scenic_area_id is not None:
        statement = statement.where(RagProfile.scenic_area_id == scenic_area_id)
    return list(db.scalars(statement.order_by(RagProfile.updated_at.desc())))


def get_profile(db: Session, profile_id: int) -> RagProfile | None:
    return db.scalar(
        select(RagProfile)
        .options(selectinload(RagProfile.knowledge_base_bindings).selectinload(RagProfileKnowledgeBase.knowledge_base))
        .where(RagProfile.id == profile_id)
    )


def get_active_profile(db: Session, scenic_area_id: int) -> RagProfile | None:
    return db.scalar(
        select(RagProfile)
        .options(selectinload(RagProfile.knowledge_base_bindings).selectinload(RagProfileKnowledgeBase.knowledge_base))
        .where(RagProfile.scenic_area_id == scenic_area_id, RagProfile.status == "active")
    )


def create_profile(db: Session, profile: RagProfile, bindings: list[RagProfileKnowledgeBase]) -> RagProfile:
    if profile.status == "active":
        db.execute(
            update(RagProfile)
            .where(RagProfile.scenic_area_id == profile.scenic_area_id, RagProfile.status == "active")
            .values(status="archived")
        )
    db.add(profile)
    db.flush()
    for binding in bindings:
        binding.rag_profile_id = profile.id
        db.add(binding)
    db.commit()
    return get_profile(db, profile.id)  # type: ignore[return-value]


def activate_profile(db: Session, profile: RagProfile) -> RagProfile:
    db.execute(
        update(RagProfile)
        .where(RagProfile.scenic_area_id == profile.scenic_area_id, RagProfile.id != profile.id, RagProfile.status == "active")
        .values(status="archived")
    )
    profile.status = "active"
    db.commit()
    return get_profile(db, profile.id)  # type: ignore[return-value]


def list_documents(db: Session, knowledge_base_id: int | None = None) -> list[KnowledgeDocument]:
    statement = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    if knowledge_base_id is not None:
        statement = statement.where(KnowledgeDocument.knowledge_base_id == knowledge_base_id)
    return list(db.scalars(statement))


def get_document(db: Session, document_id: int) -> KnowledgeDocument | None:
    return db.get(KnowledgeDocument, document_id)


def delete_document(db: Session, document: KnowledgeDocument) -> None:
    db.delete(document)
    db.commit()
