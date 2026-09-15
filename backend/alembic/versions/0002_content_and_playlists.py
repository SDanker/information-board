"""Content platform (contents/versions/assets/jobs) and playlists."""

from alembic import op
import sqlalchemy as sa

revision = "0002_content_and_playlists"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("library_visibility", sa.String(length=20), nullable=False),
        sa.Column("qr_overlay", sa.JSON(), nullable=True),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_contents_kind", "contents", ["kind"])

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_content_versions_content_id", "content_versions", ["content_id"])

    with op.batch_alter_table("contents") as batch_op:
        batch_op.create_foreign_key(
            "fk_contents_published_version", "content_versions", ["published_version_id"], ["id"], ondelete="SET NULL"
        )

    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_assets_content_version_id", "assets", ["content_version_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_processing_jobs_content_version_id", "processing_jobs", ["content_version_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])

    op.create_table(
        "playlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "playlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("playlist_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("days_of_week", sa.JSON(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_playlist_items_playlist_id", "playlist_items", ["playlist_id"])
    op.create_index("ix_playlist_items_content_id", "playlist_items", ["content_id"])

    with op.batch_alter_table("screens") as batch_op:
        batch_op.create_foreign_key(
            "fk_screens_playlist", "playlists", ["playlist_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("screens") as batch_op:
        batch_op.drop_constraint("fk_screens_playlist", type_="foreignkey")
    op.drop_index("ix_playlist_items_content_id", table_name="playlist_items")
    op.drop_index("ix_playlist_items_playlist_id", table_name="playlist_items")
    op.drop_table("playlist_items")
    op.drop_table("playlists")
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_content_version_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_assets_content_version_id", table_name="assets")
    op.drop_table("assets")
    with op.batch_alter_table("contents") as batch_op:
        batch_op.drop_constraint("fk_contents_published_version", type_="foreignkey")
    op.drop_index("ix_content_versions_content_id", table_name="content_versions")
    op.drop_table("content_versions")
    op.drop_index("ix_contents_kind", table_name="contents")
    op.drop_table("contents")
