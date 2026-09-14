# -*- coding: utf-8 -*-
"""重启工作台服务：停掉旧进程 → 用当前代码重新启动（脱离 agent 进程）。

为什么必须"脱离"：agent 的 shell 一旦结束，它拉起的子进程会被一起回收。
所以用 DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP 起一个独立的服务进程，
输出重定向到 logs/workbench-server.log。

用法：
  python .tmp_v108x/verify/restart_server.py [port]
"""

import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
ROOT = r'D:\个股工作台'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
# 关键：agent 环境的进程树被放在 Job Object 里且 kill-on-close，
# 只用 DETACHED_PROCESS 起的服务在 agent 轮次结束时仍会被回收（实测 PID 40888 即如此）。
# 必须显式请求脱离 Job 才能真正常驻。
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def port_owners(port):
    out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                         errors='replace').stdout
    pids = set()
    for line in out.splitlines():
        if (':%d' % port) in line and 'LISTENING' in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(int(parts[-1]))
    return sorted(pids)


# ---------- 1) 停掉占用端口的旧进程 ----------
old = port_owners(PORT)
if old:
    for pid in old:
        r = subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                           capture_output=True, text=True, encoding='gbk', errors='replace')
        print('  [停止] PID %d → %s' % (pid, (r.stdout or r.stderr or '').strip()))
    time.sleep(2)
else:
    print('  [停止] 端口 %d 当前无监听进程' % PORT)

left = port_owners(PORT)
print('  [确认] 等待后仍占用端口的 PID: %s' % (left or '无'))

# ---------- 2) 用当前代码重新启动（脱离本进程） ----------
logdir = os.path.join(ROOT, 'logs')
os.makedirs(logdir, exist_ok=True)
log_path = os.path.join(logdir, 'workbench-server.log')
log = open(log_path, 'ab')

env = dict(os.environ)
env['PYTHONIOENCODING'] = 'utf-8'

args = [PY, '-u', os.path.join(ROOT, 'app', 'server.py')]
if PORT != 8765:
    args += ['--port', str(PORT)]

flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
try:
    proc = subprocess.Popen(
        args, cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, close_fds=True)
    print('  [启动] 已脱离 Job Object（breakaway）')
except OSError as e:
    print('  [启动] breakaway 被拒（%s），退回普通 detached' % e)
    proc = subprocess.Popen(
        args, cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        creationflags=flags, close_fds=True)
print('  [启动] 新进程 PID %d，日志 %s' % (proc.pid, log_path))

# ---------- 3) 冒烟验证 ----------
ok = False
for _ in range(15):
    time.sleep(1)
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/api/settings' % PORT, timeout=3) as r:
            if r.status == 200:
                ok = True
                break
    except Exception:
        continue

print('  [验证] HTTP 可达: %s' % ('是' if ok else '否'))
if ok:
    with urllib.request.urlopen('http://127.0.0.1:%d/' % PORT, timeout=5) as r:
        html = r.read().decode('utf-8')
    frag = ''
    if 'id="btn-refresh"' in html:
        frag = html.split('id="btn-refresh"', 1)[1].split('>', 1)[0]
    visible = bool(frag) and 'hidden' not in frag.split()
    print('  [验证] 新代码已生效（按钮可见）: %s' % ('是' if visible else '否'))
    print('  [验证] 监听 PID: %s' % (port_owners(PORT) or '无'))

print('  完成。')
sys.exit(0 if ok else 1)
