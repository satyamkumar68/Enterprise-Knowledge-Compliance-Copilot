"""
Seed the evaluation corpus into PostgreSQL and configure RBAC permissions.

Public compliance documents are accessible to both 'employee-001' and 'executive-001'.
Confidential documents (executive compensation) are strictly restricted to 'executive-001'.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg

from app.core.auth import generate_api_token, hash_token
from app.core.config import DATABASE_URL
from app.core.passwords import hash_password
from app.ingestion.pipeline import ingest_document


EVAL_CORPUS_DIR = PROJECT_ROOT / "eval" / "corpus"

DOCUMENTS = [
    {
        "filename": "access_control_soc2.md",
        "owner": "employee-001",
        "read_principals": ["employee-001", "executive-001"],
    },
    {
        "filename": "incident_response_playbook.md",
        "owner": "employee-001",
        "read_principals": ["employee-001", "executive-001"],
    },
    {
        "filename": "data_retention_and_privacy.md",
        "owner": "employee-001",
        "read_principals": ["employee-001", "executive-001"],
    },
    {
        "filename": "confidential_executive_compensation.md",
        "owner": "executive-001",
        "read_principals": ["executive-001"],  # STRICTLY executive only!
    },
]


def ensure_users_exist():
    """Ensure test principals employee-001 and executive-001 exist in app_users with web login password."""
    principals = ["employee-001", "executive-001"]
    pwd_hash = hash_password("password123456")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for p in principals:
                token = generate_api_token()
                token_hash = hash_token(token)
                cur.execute(
                    """
                    INSERT INTO app_users (principal_id, token_hash, password_hash, is_active)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (principal_id) DO UPDATE
                    SET password_hash = COALESCE(app_users.password_hash, EXCLUDED.password_hash);
                    """,
                    (p, token_hash, pwd_hash),
                )
    print("Test users verified: employee-001, executive-001 (Default password: password123456)")


def seed_corpus():
    ensure_users_exist()

    doc_id_map = {}

    for doc_config in DOCUMENTS:
        file_path = EVAL_CORPUS_DIR / doc_config["filename"]
        if not file_path.exists():
            print(f"Error: {file_path} not found!")
            continue

        print(f"Ingesting {doc_config['filename']} for owner {doc_config['owner']}...")
        doc_id = ingest_document(str(file_path), principal_id=doc_config["owner"])
        doc_id_map[doc_config["filename"]] = doc_id

        # Update additional permissions
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                for principal in doc_config["read_principals"]:
                    cur.execute(
                        """
                        INSERT INTO document_permissions (document_id, principal_id, permission)
                        VALUES (%s, %s, 'read')
                        ON CONFLICT (document_id, principal_id) DO NOTHING;
                        """,
                        (doc_id, principal),
                    )

        print(
            f"  -> Ingested doc_id={doc_id}. Granted read access to: {doc_config['read_principals']}"
        )

    print("\nCorpus seeding complete.")
    return doc_id_map


if __name__ == "__main__":
    seed_corpus()
