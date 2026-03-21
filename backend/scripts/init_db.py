import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("SUPABASE_DB_URL", "")
if not db_url:
    raise SystemExit("SUPABASE_DB_URL is not set")

sql_dir = Path(__file__).resolve().parent.parent / "migrations"
sql_files = sorted(sql_dir.glob("*.sql"))

if not sql_files:
    raise SystemExit("No migration files found")

with psycopg2.connect(db_url) as conn:
    with conn.cursor() as cur:
        for sql_path in sql_files:
            with sql_path.open("r", encoding="utf-8") as handle:
                sql = handle.read()
            cur.execute(sql)
    conn.commit()

print(f"Applied {len(sql_files)} migrations.")
