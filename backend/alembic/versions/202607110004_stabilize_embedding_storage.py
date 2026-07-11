"""stabilize embedding storage across vector backends

Revision ID: 202607110004
Revises: 202607110003
Create Date: 2026-07-11 20:20:00
"""

from alembic import op


revision = "202607110004"
down_revision = "202607110003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert legacy JSON/vector columns into the config-independent array type."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        DO $$
        DECLARE current_udt_name text;
        BEGIN
            SELECT udt_name INTO current_udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'knowledge_embeddings'
              AND column_name = 'embedding';

            IF current_udt_name IN ('json', 'jsonb', 'vector') THEN
                EXECUTE '
                    ALTER TABLE knowledge_embeddings
                    ALTER COLUMN embedding TYPE double precision[]
                    USING translate(embedding::text, ''[]'', ''{}'')::double precision[]
                ';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # The old migration selected a physical type from runtime configuration.
    # Keeping the portable array representation prevents reintroducing that
    # mismatch during a code-only rollback.
    pass
