# -*- coding: utf-8 -*-
"""诊断：沙箱里的 server.py 为什么起不来。"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import http.client

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
PORT = 8801

BOX = tempfile.mkdtemp(prefix='wb_diag_')
shutil.copytree(os.path.join(ROOT, 'app'), os.path.join(BOX, 'app'))
os.makedirs(os.path.join(BOX, 'data'), exist_ok=True)
shutil.copy2(os.path.join(ROOT, 'data', 'workbench.db'),
             os.path.join(BOX, 'data', 'workbench.db'))
print('BOX =', BOX)
print('app 内容 =', sorted(os.listdir(os.path.join(BOX, 'app'))))
print('data 内容 =', sorted(os.listdir(os.path.join(BOX, 'data'))))

out = open(os.path.join(BOX, 'o.txt'), 'w', encoding='utf-8')
err = open(os.path.join(BOX, 'e.txt'), 'w', encoding='utf-8')
p = subprocess.Popen([PY, '-u', os.path.join(BOX, 'app', 'server.py'),
                      '--port', str(PORT), '--no-browser'],
                     cwd=BOX, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
print('PID =', p.pid)

ok = False
for i in range(20):
    time.sleep(0.5)
    try:
        c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=3)
        c.request('GET', '/api/settings')
        r = c.getresponse()
        r.read()
        c.close()
        if r.status == 200:
            ok = True
            print('第 %.1fs /api/settings -> %d  OK' % ((i + 1) * 0.5, r.status))
            break
    except Exception as e:
        if i in (0, 5, 19):
            print('第 %.1fs 探测异常: %s: %s' % ((i + 1) * 0.5, type(e).__name__, e))

print('poll rc =', p.poll())
out.close()
err.close()
print('--- stdout ---')
print(open(os.path.join(BOX, 'o.txt'), encoding='utf-8', errors='replace').read()[-2000:])
print('--- stderr ---')
print(open(os.path.join(BOX, 'e.txt'), encoding='utf-8', errors='replace').read()[-3000:])

if p.poll() is None:
    r = subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)],
                       capture_output=True, text=True, encoding='gbk', errors='replace')
    print('taskkill rc =', r.returncode)
print('结论:', 'OK' if ok else '起不来')
shutil.rmtree(BOX, ignore_errors=True)
