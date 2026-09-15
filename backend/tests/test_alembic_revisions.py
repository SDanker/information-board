"""SQLite does not enforce varchar(32) on alembic_version.version_num, but PostgreSQL does:
a revision id that is too long passes local tests and only fails on a real server. This
test prevents that mistake from happening again.
"""

from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
MAX_LENGTH = 32  # width of alembic_version.version_num created by Alembic


def test_all_revision_ids_fit_in_postgres_column():
    offenders = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("revision = "):
                revision = line.split("=", 1)[1].strip().strip('"').strip("'")
                if len(revision) > MAX_LENGTH:
                    offenders.append((path.name, revision, len(revision)))
    assert not offenders, f"Revision ids longer than {MAX_LENGTH} characters: {offenders}"
