"""Custom per-page/slide display duration on assets."""

from alembic import op
import sqlalchemy as sa

revision = "0006_asset_display_seconds"
down_revision = "0005_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("display_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "display_seconds")
