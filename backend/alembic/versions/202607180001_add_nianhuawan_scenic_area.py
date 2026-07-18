"""add Nianhuawan scenic area

Revision ID: 202607180001
Revises: 202607170004
Create Date: 2026-07-18
"""

from alembic import op


revision = "202607180001"
down_revision = "202607170004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO scenic_areas (code, name, description, is_enabled)
        VALUES ('nianhuawan', '拈花湾禅意小镇', '拈花湾禅意小镇景区', true)
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name,
            description = EXCLUDED.description,
            is_enabled = true
        """
    )
    op.execute(
        """
        INSERT INTO insight_report_schedules (scenic_area_id)
        SELECT id FROM scenic_areas WHERE code = 'nianhuawan'
        ON CONFLICT (scenic_area_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO knowledge_bases (code, name, description)
        VALUES
            ('nianhuawan-structured', '拈花湾结构化景点资料库', '景点基础信息、开放时间与演艺安排'),
            ('nianhuawan-culture', '拈花湾历史文化资料库', '历史、文化和导览叙述资料')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO rag_profiles (scenic_area_id, name, status)
        SELECT id, '拈花湾正式版 RAG', 'active'
        FROM scenic_areas
        WHERE code = 'nianhuawan'
          AND NOT EXISTS (
              SELECT 1 FROM rag_profiles profile
              WHERE profile.scenic_area_id = scenic_areas.id
                AND profile.status = 'active'
          )
        """
    )
    op.execute(
        """
        INSERT INTO rag_profile_knowledge_bases (rag_profile_id, knowledge_base_id, retrieval_priority)
        SELECT profile.id, base.id,
               CASE WHEN base.code = 'nianhuawan-structured' THEN 100 ELSE 10 END
        FROM rag_profiles profile
        JOIN scenic_areas scenic ON scenic.id = profile.scenic_area_id
        JOIN knowledge_bases base ON base.code IN ('nianhuawan-structured', 'nianhuawan-culture')
        WHERE scenic.code = 'nianhuawan' AND profile.status = 'active'
        ON CONFLICT (rag_profile_id, knowledge_base_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM scenic_areas WHERE code = 'nianhuawan'")
    op.execute("DELETE FROM knowledge_bases WHERE code IN ('nianhuawan-structured', 'nianhuawan-culture')")
