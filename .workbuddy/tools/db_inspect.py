import sqlite3
co = sqlite3.connect(r'D:\个股工作台\data\workbench.db')
co.row_factory = sqlite3.Row
print('=== settings 表 ===')
rows = co.execute('SELECT key,value FROM settings ORDER BY key').fetchall()
if not rows:
    print('  (空)')
for r in rows:
    print(f'  {r["key"]!r} = {r["value"]!r}')
print()
print('=== securities 表 ===')
rows = co.execute('SELECT id, code, exchange, name FROM securities').fetchall()
if not rows:
    print('  (空)')
for r in rows:
    print(f'  id={r["id"]} code={r["code"]} exchange={r["exchange"]} name={r["name"]}')
print()
print('schema_version:', co.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()['value'])
print('integrity_check:', co.execute('PRAGMA integrity_check').fetchone()[0])
print('fk_violations:', list(co.execute('PRAGMA foreign_key_check').fetchall()))
co.close()
