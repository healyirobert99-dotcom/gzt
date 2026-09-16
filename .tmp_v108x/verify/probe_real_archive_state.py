# -*- coding: utf-8 -*-
"""只读查看真实库：归档态 + 台账里最近的归档/恢复事件。

目的：判断 §6「真实库业务数据变化」是否来自 8765 上用户的实时操作。
全程只读副本，不碰原文件。
"""
import os
import shutil
import sqlite3
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

REAL = r'D:\个股工作台\data\workbench.db'
tmp = os.path.join(tempfile.gettempdir(), 'ro_real.db')
for p in (tmp, tmp + '-wal', tmp + '-shm'):
    if os.path.exists(p):
        os.remove(p)
shutil.copy2(REAL, tmp)

c = sqlite3.connect(tmp)
c.row_factory = sqlite3.Row
try:
    print('== securities 归档态 ==')
    for r in c.execute('SELECT id,code,exchange,name,status,archived_at,'
                       'updated_at,current_price_updated_at FROM securities'
                       ' ORDER BY id'):
        flag = '  <== 已归档' if r['archived_at'] else ''
        print('  %-4s %-6s %-10s %-8s arch=%-20s upd=%s%s'
              % (r['id'], r['code'], r['exchange'], r['status'],
                 r['archived_at'], r['updated_at'], flag))

    print('\n== decision_ledger 列名 ==')
    cols = [d[1] for d in c.execute('PRAGMA table_info(decision_ledger)')]
    print(' ', cols)

    print('\n== 最近 8 条台账（含归档/恢复关键字） ==')
    order = 'id DESC'
    for r in c.execute('SELECT * FROM decision_ledger ORDER BY %s LIMIT 8' % order):
        d = dict(r)
        joined = ' | '.join('%s=%s' % (k, str(v)[:46]) for k, v in d.items())
        print(' ', joined)

    print('\n== 台账中归档/恢复事件总数 ==')
    for r in c.execute("SELECT COUNT(*) FROM decision_ledger"):
        print('  台账总行数 =', r[0])
    try:
        for r in c.execute("SELECT id,created_at FROM decision_ledger"
                           " WHERE CAST(event AS TEXT) LIKE '%归档%'"
                           " OR CAST(event AS TEXT) LIKE '%恢复%'"
                           " ORDER BY id"):
            print('  归档/恢复事件: id=%s at=%s' % (r[0], r[1]))
    except Exception as e:
        print('  （按 event 列过滤失败：%s）' % e)
finally:
    c.close()
    for p in (tmp, tmp + '-wal', tmp + '-shm'):
        if os.path.exists(p):
            os.remove(p)
