
import sys
from pathlib import Path

# Ensure project root is in sys.path when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from app.core.auth import generate_api_token, hash_token
from app.core.config import DATABASE_URL


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python -m scripts.create_dev_user <principal_id>"
        )
        raise SystemExit(1)

    principal_id = sys.argv[1].strip()

    if not principal_id:
        print("Principal ID cannot be empty.")
        raise SystemExit(1)

    token = generate_api_token()
    token_digest = hash_token(token)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_users (principal_id, token_hash)
                VALUES (%s, %s)
                ON CONFLICT (principal_id)
                DO UPDATE SET
                    token_hash = EXCLUDED.token_hash,
                    is_active = TRUE
                """,
                (principal_id, token_digest),
            )

    print("Development user created.")
    print("Principal:", principal_id)
    print("API token (save it now; it will not be stored in plaintext):")
    print(token)


if __name__ == "__main__":
    main()
