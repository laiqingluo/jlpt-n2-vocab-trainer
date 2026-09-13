import sys, sqlite3
sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("data/n2.db")
rows = conn.execute("SELECT word, examples FROM words WHERE examples LIKE '%pdf%' OR examples LIKE '%真题%' LIMIT 10").fetchall()
for w, ex in rows:
    print(repr(w), "=>", repr(ex[:200]))
