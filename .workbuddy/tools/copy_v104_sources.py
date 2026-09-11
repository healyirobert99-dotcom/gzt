"""v1.0.4 审计打包：复制源到 audit_pack_src，生成清单 + 日志，打 ZIP"""
import os, shutil, sys, sqlite3, hashlib

ROOT = r'D:\个股工作台'
DST = r'D:\个股工作台\audit_pack_src'

if os.path.exists(DST):
    shutil.rmtree(DST)
os.makedirs(DST)

# 选定清单（v1.0.4）
include = [
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_integration_quote.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'tests/fixtures/sample_seed.py',
    # data/workbench.db 单独处理（升级后保留，不要 backup/ 子目录）
    '启动工作台.bat',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.4.docx',
    'output/20260910-audit/build_docx_v104.py',
    'output/20260910-audit/pipeline-state.yaml',
]

for rel in include:
    s = os.path.join(ROOT, rel)
    d = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(s, d)

# 单独复制生产 DB（不复制 backup/ 子目录）
db_src = os.path.join(ROOT, 'data', 'workbench.db')
db_dst = os.path.join(DST, 'data', 'workbench.db')
os.makedirs(os.path.dirname(db_dst), exist_ok=True)
shutil.copy2(db_src, db_dst)

print(f'复制 {len(include) + 1} 个文件')

# 升级 audit_pack_src 内 DB 到 v1.0.4
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server

# Monkey-patch do_migration 使其不写 backup 到 audit_pack_src/data/backup/
import os as _os
real_do_migration = server.do_migration
def _silent_do_migration(conn, db_path):
    # 备份写到临时目录
    import tempfile
    tmp_bak = _os.path.join(tempfile.gettempdir(), 'wb_v104_migration_backup.db')
    if _os.path.exists(tmp_bak):
        _os.remove(tmp_bak)
    # 临时把 db_path 改成临时路径做备份，但实际写入目标不变
    # 简化：直接调 do_migration 然后清理 audit_pack_src/data/backup/
    real_do_migration(conn, db_path)
    bak_dir = _os.path.join(_os.path.dirname(db_path), 'backup')
    if _os.path.exists(bak_dir):
        shutil.rmtree(bak_dir, ignore_errors=True)
server.do_migration = _silent_do_migration

server.init_db(seed=False, db_path=db_dst)

co = sqlite3.connect(db_dst)
co.row_factory = sqlite3.Row
sv = co.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
print(f'升级后 schema_version: {sv["value"]}')
co.close()

# 双重保险：再次清理 backup
bak_dir = os.path.join(os.path.dirname(db_dst), 'backup')
if os.path.exists(bak_dir):
    shutil.rmtree(bak_dir, ignore_errors=True)
    print(f'清理 backup 目录: {bak_dir}')