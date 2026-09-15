"""Publication period on content: start, end and weekdays."""

from alembic import op
import sqlalchemy as sa

revision = "0007_content_publication"
down_revision = "0006_asset_display_seconds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing content keeps no limits, so nothing already on screen disappears after upgrading.
    op.add_column("contents", sa.Column("publish_start_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("contents", sa.Column("publish_end_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("contents", sa.Column("publish_days", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "publish_days")
    op.drop_column("contents", "publish_end_at")
    op.drop_column("contents", "publish_start_at")
