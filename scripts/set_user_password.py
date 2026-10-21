
import getpass
import sys
from pathlib import Path

# Ensure project root is in sys.path when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from app.core.config import DATABASE_URL
from app.core.passwords import hash_password


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python -m scripts.set_user_password <principal_id>"
        )
        raise SystemExit(1)

    principal_id = sys.argv[1].strip()

    if not principal_id:
        print("Principal ID cannot be empty.")
        raise SystemExit(1)

    password = getpass.getpass("New password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        print("Passwords do not match.")
        raise SystemExit(1)

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1) from exc

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE app_users
                SET password_hash = %s
                WHERE principal_id = %s
                  AND is_active = TRUE
                RETURNING principal_id;
                """,
                (password_hash, principal_id),
            )

            row = cur.fetchone()

            if row is None:
                print(
                    "No active account found. "
                    "No account was created or changed."
                )
                raise SystemExit(1)

    print("Password configured successfully for:", principal_id)


if __name__ == "__main__":
    main()
