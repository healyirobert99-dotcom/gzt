# -*- coding: utf-8 -*-
"""对照实验：证明「真实库被改写」是否来自 8765 上运行中的工作台实例。

做法：在**完全不碰浏览器、不碰沙箱服务**的前提下，隔 80 秒取两次真实库指纹，
并比较 securities 的行情列。若指纹自行变化，则写者只能是外部进程（用户的实例）。
全程只读真实库：先 copy 到临时文件再读，不对真实库加锁/写入。
"""
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding='utf-8')

REAL = r'D:\个股工作台\data\workbench.db'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def snapshot(tag):
    """把真实库复制出来读，避免动到原文件（WAL 库直接开也会生成 -shm/-wal）。"""
    tmp = os.path.join(tempfile.gettempdir(), 'probe_%s.db' % tag)
    if os.path.exists(tmp):
        os.remove(tmp)
    shutil.copy2(REAL, tmp)
    con = sqlite3.connect(tmp)
    try:
        rows = con.execute(
            'SELECT code, exchange, current_price, current_price_updated_at '
            'FROM securities ORDER BY id').fetchall()
        arch = con.execute(
            'SELECT COUNT(*) FROM securities WHERE archived_at IS NOT NULL'
        ).fetchone()[0]
        led = con.execute('SELECT COUNT(*) FROM decision_ledger').fetchone()[0]
        res = con.execute('SELECT COUNT(*) FROM research').fetchone()[0]
    finally:
        con.close()
    os.remove(tmp)
    return rows, arch, led, res


def port_owner(port):
    out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                         encoding='gbk', errors='replace').stdout
    for line in out.splitlines():
        if ':%d ' % port in line and 'LISTENING' in line:
            return line.split()[-1]
    return None


print('=' * 74)
print('8765 端口属主 PID =', port_owner(8765))
print('=' * 74)

h0 = sha(REAL)
rows0, arch0, led0, res0 = snapshot('a')
t0 = time.strftime('%H:%M:%S')
print('[T0 %s] sha256=%s' % (t0, h0[:16]))
print('        securities=%d  archived=%d  ledger=%d  research=%d'
      % (len(rows0), arch0, led0, res0))
print('        样例行情：', rows0[:2])

print('\n等待 80 秒（期间不启动任何浏览器 / 不访问任何端口）...\n')
time.sleep(80)

h1 = sha(REAL)
rows1, arch1, led1, res1 = snapshot('b')
t1 = time.strftime('%H:%M:%S')
print('[T1 %s] sha256=%s' % (t1, h1[:16]))
print('        securities=%d  archived=%d  ledger=%d  research=%d'
      % (len(rows1), arch1, led1, res1))
print('        样例行情：', rows1[:2])

print('\n' + '=' * 74)
print('真实库指纹自行变化      :', h1 != h0)
print('业务行数（securities/research/ledger）变化 :',
      (len(rows1), res1, led1) != (len(rows0), res0, led0))
print('归档标的数变化          :', arch1 != arch0, '(%d → %d)' % (arch0, arch1))

diffs = [(a, b) for a, b in zip(rows0, rows1) if a != b]
print('行情列发生变化的标的数  :', len(diffs), '/', len(rows0))
for a, b in diffs[:5]:
    print('    %s.%s  price %s → %s ; time %s → %s'
          % (a[0], a[1], a[2], b[2], a[3], b[3]))
print('=' * 74)
