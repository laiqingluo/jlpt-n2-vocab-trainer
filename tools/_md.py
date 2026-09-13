import sys, sqlite3
sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("data/n2.db")
rows = conn.execute("SELECT word, meaning_detail FROM words WHERE meaning_detail IS NOT NULL AND meaning_detail != '' LIMIT 8").fetchall()
for w, md in rows:
    print(repr(w), "=>", repr(md[:300]))
    print()
