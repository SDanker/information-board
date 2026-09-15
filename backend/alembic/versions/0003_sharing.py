"""Share tokens for QR/library downloads."""

from alembic import op
import sqlalchemy as sa

revision = "0003_sharing"
down_revision = "0002_content_and_playlists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_share_tokens_content_id", "share_tokens", ["content_id"])
    op.create_index("ix_share_tokens_token", "share_tokens", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_share_tokens_token", table_name="share_tokens")
    op.drop_index("ix_share_tokens_content_id", table_name="share_tokens")
    op.drop_table("share_tokens")
