import sys, sqlite3
sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("data/n2.db")
rows = conn.execute("SELECT word, examples FROM words WHERE examples IS NOT NULL AND examples != '' LIMIT 20").fetchall()
for w, ex in rows:
    print(repr(w), "=>", repr(ex[:150]))
