"""Apply db/schema.sql + db/seed.sql, and optionally seed the first manager
from SEED_MANAGER_EMAIL / SEED_MANAGER_PASSWORD. Run: python migrate.py"""
import os

from dotenv import load_dotenv

load_dotenv()

from db import pool
from security import hash_password


def _run_file(conn, path):
    with open(path, encoding="utf-8") as f:
        conn.execute(f.read())
    print(f"✓ applied {path}")


def main():
    with pool.connection() as conn:
        _run_file(conn, "db/schema.sql")
        _run_file(conn, "db/seed.sql")
        email = os.getenv("SEED_MANAGER_EMAIL")
        password = os.getenv("SEED_MANAGER_PASSWORD")
        if email and password:
            conn.execute(
                """insert into users (email, password_hash, full_name, role)
                   values (%s, %s, 'المدير', 'manager')
                   on conflict (email) do update set role = 'manager', password_hash = excluded.password_hash""",
                [email.lower().strip(), hash_password(password)],
            )
            print(f"✓ manager account ready: {email}")
    print("Migration complete.")


if __name__ == "__main__":
    main()
