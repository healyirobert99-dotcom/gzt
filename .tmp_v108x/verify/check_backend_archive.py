import os
import subprocess
import sys

os.chdir(r'D:\个股工作台')
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'

r = subprocess.run([PY, '-m', 'py_compile', 'app/server.py'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print('py_compile rc =', r.returncode)
print((r.stdout or '') + (r.stderr or ''))

src = open('app/server.py', encoding='utf-8').read()
keys = [
    ('SCHEMA 加列', 'archived_at TEXT,\n  UNIQUE(exchange, code)'),
    ('迁移期望列', "('archived_at', 'TEXT'),\n    ]"),
    ('重建复制列', "'archived_at')"),
    ('幂等补列函数', 'def _ensure_security_columns(conn):'),
    ('init_db 调用', '_ensure_security_columns(conn)'),
    ('模式白名单', '_ARCHIVED_MODES = {'),
    ('归档影响面', 'def archive_impact(conn, sid):'),
    ('唯一写入口', 'def _set_archived_at(conn, sid, value, event_type, summary, reason='),
    ('归档事务', 'def archive_security_tx(conn, sid, body):'),
    ('恢复事务', 'def unarchive_security_tx(conn, sid, body):'),
    ('列表过滤', "def list_securities(mode='active'):"),
    ('路由 archived', "seg[2] == 'archived'"),
    ('路由 impact', "seg[3] == 'archive-impact'"),
    ('路由 post archive', "sub == 'archive'"),
    ('路由 post unarchive', "sub == 'unarchive'"),
]
for name, k in keys:
    print(('  OK   ' if k in src else '  缺失 ') + name)

print('--- 语法告警检查 ---')
r2 = subprocess.run([PY, '-W', 'error::SyntaxWarning', '-c',
                     'import ast,sys; ast.parse(open(sys.argv[1],encoding="utf-8").read())',
                     'app/server.py'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace')
print('rc =', r2.returncode, (r2.stderr or '').strip()[:300] or '(无告警)')
