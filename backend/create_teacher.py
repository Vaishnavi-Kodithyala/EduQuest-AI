"""
Create a teacher account, or turn an existing account into one.

    python -m backend.create_teacher <username>              asks for a password
    python -m backend.create_teacher <username> --password <password>

Teachers sign in on the normal login page and are taken to the class
dashboard. They cannot sign up from the app: anyone could otherwise register
as a teacher and see every student's results.
"""

import argparse
import getpass
import sys

from .database import ensure_indexes, users
from .routes.auth import hash_password

MIN_PASSWORD = 6


def ask_password() -> str:
    while True:
        first = getpass.getpass("Password for the teacher: ")
        if len(first) < MIN_PASSWORD:
            print(f"Use at least {MIN_PASSWORD} characters.")
            continue
        if getpass.getpass("Type it again: ") != first:
            print("The two passwords did not match. Try again.")
            continue
        return first


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote a teacher account.")
    parser.add_argument("username")
    parser.add_argument("--password", help="Leave out to be asked (the password is then not shown).")
    parser.add_argument("--grade", type=int, default=6)
    args = parser.parse_args()

    if args.password is not None and len(args.password) < MIN_PASSWORD:
        sys.exit(f"The password must be at least {MIN_PASSWORD} characters.")

    ensure_indexes()
    existing = users.find_one({"username": args.username})

    if existing:
        changes = {"role": "teacher", "grade": args.grade}
        if args.password:
            changes["password_hash"] = hash_password(args.password)
        users.update_one({"_id": existing["_id"]}, {"$set": changes})
        note = " and the password was changed" if args.password else " (password unchanged)"
        print(f"'{args.username}' is now a teacher{note}.")
        return

    password = args.password or ask_password()
    users.insert_one({
        "username": args.username,
        "password_hash": hash_password(password),
        "grade": args.grade,
        "language": "en",
        "points": 0,
        "role": "teacher",
        "avatar": "🧑‍🏫",
    })
    print(f"Teacher account '{args.username}' created. Sign in with it on the normal login page.")


if __name__ == "__main__":
    main()
