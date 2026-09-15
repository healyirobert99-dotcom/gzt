# -*- coding: utf-8 -*-
"""核对：真实库 data/workbench.db 相对仓库版本到底变了哪些列。
预期只有 securities 的 current_price / current_price_updated_at
（运行工作台触发的正常行情刷新），不应出现 archived_at / 台账行数变化。"""
import os
import sqlite3
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'D:\个股工作台')
subprocess.run(['git', 'show', 'HEAD:data/workbench.db'],
               stdout=open('.tmp_v108x/verify/head.db', 'wb'), check=True)


def dump(p):
    c = sqlite3.connect('file:%s?mode=ro' % p.replace('\\', '/'), uri=True)
    c.row_factory = sqlite3.Row
    out = {}
    for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        out[n] = [dict(r) for r in c.execute('SELECT * FROM "%s"' % n)]
    c.close()
    return out


a = dump('.tmp_v108x/verify/head.db')
b = dump('data/workbench.db')
for t in sorted(set(a) | set(b)):
    ra, rb = a.get(t, []), b.get(t, [])
    if len(ra) != len(rb):
        print('%-20s 行数 %d -> %d  <<< 行数变化！' % (t, len(ra), len(rb)))
        continue
    cols = set()
    for x, y in zip(ra, rb):
        for k in set(x) | set(y):
            if x.get(k) != y.get(k):
                cols.add(k)
    print('%-20s 行数 %-4d 变化列=%s' % (t, len(ra), sorted(cols) or '无'))

print('\n结论：若只有 securities 的 current_price* 两列变化，即为正常的行情刷新。')
os.remove('.tmp_v108x/verify/head.db')
