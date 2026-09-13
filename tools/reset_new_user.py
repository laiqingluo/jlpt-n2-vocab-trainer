"""Simulate a brand-new user: clear settings and progress for 'default' user."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from db import get_conn

conn = get_conn()
conn.execute("DELETE FROM user_sessions WHERE user_id='default' AND key='user_settings'")
conn.execute("DELETE FROM user_word_status WHERE user_id='default'")
conn.commit()
print("Cleared: user_settings and user_word_status for default user")

settings = conn.execute("SELECT COUNT(*) FROM user_sessions WHERE user_id='default' AND key='user_settings'").fetchone()[0]
status   = conn.execute("SELECT COUNT(*) FROM user_word_status WHERE user_id='default'").fetchone()[0]
print(f"Remaining: user_settings={settings}, user_word_status={status}")
