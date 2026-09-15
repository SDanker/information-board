"""Administrative command-line tasks, run inside the backend container.

Examples::

    docker compose exec backend python -m app.cli list-users
    docker compose exec backend python -m app.cli create-admin --username maria
    docker compose exec backend python -m app.cli reset-password --username admin

When ``--password`` is omitted the password is asked interactively and not echoed,
which also keeps it out of the shell history.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password

MIN_PASSWORD_LENGTH = 8


def _read_password(provided: str | None) -> str:
    if provided is None:
        provided = getpass.getpass("New password: ")
        if getpass.getpass("Repeat the password: ") != provided:
            raise SystemExit("The passwords do not match.")
    if len(provided) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"The password must have at least {MIN_PASSWORD_LENGTH} characters.")
    return provided


def create_admin(username: str, password: str | None) -> int:
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)) is not None:
            print(f"A user named {username!r} already exists. Use reset-password instead.", file=sys.stderr)
            return 1
        db.add(User(username=username, password_hash=hash_password(_read_password(password)), role="ADMIN"))
        db.commit()
    print(f"Administrator {username!r} created.")
    return 0


def reset_password(username: str, password: str | None, activate: bool) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            print(f"There is no user named {username!r}.", file=sys.stderr)
            return 1
        user.password_hash = hash_password(_read_password(password))
        if activate:
            user.is_active = True
        db.commit()
    print(f"Password for {username!r} updated.")
    return 0


def list_users() -> int:
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.username)).all()
    for user in users:
        state = "active" if user.is_active else "inactive"
        print(f"{user.username}\t{user.role}\t{state}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Information Board administration tasks")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-admin", help="create a new administrator account")
    create.add_argument("--username", required=True)
    create.add_argument("--password", help="omit to type it without echo")

    reset = commands.add_parser("reset-password", help="set a new password for an existing account")
    reset.add_argument("--username", required=True)
    reset.add_argument("--password", help="omit to type it without echo")
    reset.add_argument("--activate", action="store_true", help="also re-enable the account if it was deactivated")

    commands.add_parser("list-users", help="list accounts with their role and state")

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return create_admin(args.username, args.password)
    if args.command == "reset-password":
        return reset_password(args.username, args.password, args.activate)
    return list_users()


if __name__ == "__main__":
    sys.exit(main())
