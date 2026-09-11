# -*- coding: utf-8 -*-
"""试跑工作台启动脚本，捕获前若干秒的输出，判断能否正常拉起服务。

放在 .tmp_v108x/verify/ 下（工作区侧探针，不进交付包）。
"""
import os
import subprocess
import sys
import time

ROOT = r'D:\个股工作台'
BAT = os.path.join(ROOT, os.environ.get('BAT_NAME', '\u542f\u52a8\u5de5\u4f5c\u53f0.bat'))
WAIT = float(os.environ.get('WAIT', '8'))
PORT = int(os.environ.get('PORT', '8765'))

print('bat   :', BAT)
print('exists:', os.path.exists(BAT))
print('size  :', os.path.getsize(BAT) if os.path.exists(BAT) else '-')
print('-' * 60)

p = subprocess.Popen(
    ['cmd.exe', '/c', BAT],
    cwd=ROOT,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
print('pid   :', p.pid)

# 给服务一点启动时间，同时探测端口
deadline = time.time() + WAIT
port_up = False
import socket
while time.time() < deadline:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(('127.0.0.1', PORT))
        port_up = True
        s.close()
        break
    except Exception:
        s.close()
    if p.poll() is not None:
        break
    time.sleep(0.3)

print('port %d up: %s' % (PORT, port_up))
print('proc alive:', p.poll() is None, 'rc=', p.poll())
print('-' * 60)

try:
    p.kill()
except Exception:
    pass
try:
    out, _ = p.communicate(timeout=5)
except Exception:
    out = b''

text = (out or b'').decode('gbk', 'replace')
print('--- launcher output ---')
print(text)
print('--- end ---')

# 收尾：确认端口已释放
time.sleep(1.0)
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', PORT))
    print('WARN: port still up after kill')
except Exception:
    print('port released: OK')
finally:
    s.close()
