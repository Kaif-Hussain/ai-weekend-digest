import os
import sqlite3
import json
from typing import Optional, List, Dict
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "subscribers.db"
ENCRYPTION_KEY = os.environ.get("DB_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise RuntimeError("DB_ENCRYPTION_KEY is missing in .env file!")

cipher = Fernet(ENCRYPTION_KEY.encode())


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                email TEXT PRIMARY KEY,
                encrypted_api_key TEXT NOT NULL,
                cached_sunday_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def upsert_subscriber(email: str, raw_api_key: str):
    encrypted_key = cipher.encrypt(raw_api_key.encode()).decode()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO subscribers (email, encrypted_api_key)
            VALUES (?, ?)
            ON CONFLICT(email) DO UPDATE SET encrypted_api_key=excluded.encrypted_api_key
        """, (email.lower().strip(), encrypted_key))
        conn.commit()


def delete_subscriber(email: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("DELETE FROM subscribers WHERE email = ?", (email.lower().strip(),))
        conn.commit()
        return cursor.rowcount > 0


def get_all_subscribers() -> List[Dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT email, encrypted_api_key, cached_sunday_json FROM subscribers").fetchall()
        results = []
        for row in rows:
            decrypted_key = cipher.decrypt(row["encrypted_api_key"].encode()).decode()
            results.append({
                "email": row["email"],
                "api_key": decrypted_key,
                "cached_sunday": json.loads(row["cached_sunday_json"]) if row["cached_sunday_json"] else None
            })
        return results


def save_sunday_cache(email: str, sunday_payload: Dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE subscribers SET cached_sunday_json = ? WHERE email = ?",
            (json.dumps(sunday_payload), email.lower().strip())
        )
        conn.commit()


def clear_sunday_cache(email: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE subscribers SET cached_sunday_json = NULL WHERE email = ?",
            (email.lower().strip(),)
        )
        conn.commit()