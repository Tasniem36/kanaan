"""PostgreSQL connection pool + small query helpers (psycopg3)."""
import os
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()


def _conninfo() -> str:
    # Cloud Run → Unix socket; otherwise host/port (local proxy or a DB host)
    if os.getenv("INSTANCE_CONNECTION_NAME") and not os.getenv("DB_HOST"):
        host = f"/cloudsql/{os.environ['INSTANCE_CONNECTION_NAME']}"
    else:
        host = os.getenv("DB_HOST", "127.0.0.1")
    return make_conninfo(
        host=host,
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "dukkan"),
    )


pool = ConnectionPool(_conninfo(), min_size=1, max_size=10, open=True,
                      kwargs={"row_factory": dict_row})


def fetch_all(sql, params=None):
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall() if cur.description else []


def fetch_one(sql, params=None):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run a statement that returns nothing (or ignore its result)."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or [])
