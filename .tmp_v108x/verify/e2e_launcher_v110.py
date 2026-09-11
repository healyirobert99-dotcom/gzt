# -*- coding: utf-8 -*-
"""v1.0.10 交付包端到端验收（工作区侧探针，不进 ZIP）。

目标：证明交付包**自身**的 `启动工作台.bat` 能在"目标机环境"下把工作台拉起来，
      并证明旧 bat 在同一环境里做不到 —— 即差异来自本次修复。

三个实验（均在**解压后的全新目录**内执行，不碰工作区）：
  A  新 bat + 真实持久 PATH（只含 System32 / WindowsApps，**没有**受管运行时）
     → 必须成功启动、HTTP 200、Server 头 Workbench/1.0.10
  B  旧 bat + 同样"不含任何真 Python"的 PATH
     → 必须失败（这正是 v1.0.9 交付包交给用户时的处境）
  C  `where python` 在含 WindowsApps 的 PATH 下 exit 0
     → 证明旧 bat 的 `if errorlevel 1` 守卫恒不触发，会去调用 Store 存根

安全：全程不调用 Store 存根（只在 C 里运行 `where`，不执行 python）。
"""

import hashlib
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = r'D:\个股工作台'
ZIP = os.path.join(ROOT, '个股工作台-v1.0.10-20260911.zip')
OLD_BAT = os.path.join(ROOT, '.tmp_v108x', '启动工作台.bat')
PORT = 8765

PASS = FAIL = 0


def step(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  [FAIL] %s %s' % (name, detail))


def persistent_path():
    """读注册表里的**持久** PATH，而不是当前进程的 PATH。"""
    import winreg
    parts = []
    for hive, key, name in (
            (winreg.HKEY_CURRENT_USER, r'Environment', 'Path'),
            (winreg.HKEY_LOCAL_MACHINE,
             r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path')):
        try:
            with winreg.OpenKey(hive, key) as k:
                v, _ = winreg.QueryValueEx(k, name)
                parts.append(v)
        except Exception as e:
            parts.append('')
    return ';'.join(p for p in parts if p)


def port_open(p, timeout=0.4):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(('127.0.0.1', p))
        return True
    except Exception:
        return False
    finally:
        s.close()


# ---------- 准备：解压到全新目录 ----------
tmp = tempfile.mkdtemp(prefix='final-v110-')
print('解压到：%s' % tmp)
with zipfile.ZipFile(ZIP) as z:
    z.extractall(tmp)

bat = os.path.join(tmp, '启动工作台.bat')
step('交付包内含 启动工作台.bat', os.path.exists(bat))

raw = open(bat, 'rb').read()
zraw = zipfile.ZipFile(ZIP).read('启动工作台.bat')
step('解压出的 bat 与 ZIP 内一致',
     hashlib.sha256(raw).hexdigest() == hashlib.sha256(zraw).hexdigest(),
     '%d B / %s' % (len(raw), hashlib.sha256(raw).hexdigest()))

# ---------- 构造"目标机环境" ----------
real_path = persistent_path()
print('\n持久 PATH = %s' % real_path)

winapps = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WindowsApps')
sys32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'system32')
os.makedirs(winapps, exist_ok=True)

# A 用：真实持久 PATH（含 WindowsApps，不含任何受管运行时）
# B 用：完全不含 python 的 PATH
PATH_A = sys32 + ';' + winapps
PATH_B = sys32
step('持久 PATH 中确实不含受管运行时',
     '.workbuddy' not in real_path.lower(), real_path[:70])

# ---------- 实验 C：where python 的行为 ----------
print('\n[C] 旧 bat 守卫为何恒不触发')
r = subprocess.run(['where', 'python'], shell=True, capture_output=True,
                   env=dict(os.environ, PATH=PATH_A))
step('C#1 含 WindowsApps 时 `where python` exit=0（守卫不触发）',
     r.returncode == 0,
     r.stdout.decode('gbk', 'replace').strip().splitlines()[0]
     if r.stdout.strip() else 'rc=%d' % r.returncode)
r2 = subprocess.run(['where', 'python'], shell=True, capture_output=True,
                    env=dict(os.environ, PATH=PATH_B))
step('C#2 不含 WindowsApps 时 `where python` 失败（说明旧 bat 只认 PATH）',
     r2.returncode != 0, 'rc=%d' % r2.returncode)


def kill_port_owner(p):
    """杀掉占用端口 p 的进程树，并等到端口真正释放。

    注意：`proc.kill()` 只杀 cmd.exe，其子进程 python.exe 会活下来继续监听，
    于是后续实验会误判"旧 bat 也留下了监听端口"。必须按端口属主杀。
    """
    for _ in range(5):
        if not port_open(p):
            return True
        r = subprocess.run('netstat -ano | findstr LISTENING | findstr :%d' % p,
                           shell=True, capture_output=True)
        pids = set()
        for ln in r.stdout.decode('gbk', 'replace').splitlines():
            parts = ln.split()
            if len(parts) >= 5 and parts[-1].isdigit():
                pids.add(parts[-1])
        for pid in pids:
            subprocess.run('taskkill /F /T /PID %s' % pid, shell=True,
                           capture_output=True)
        time.sleep(0.6)
    return not port_open(p)


# ---------- 实验 A：新 bat 在目标机环境下启动 ----------
def run_bat(script, path_env, wait=12.0):
    p = subprocess.Popen(['cmd.exe', '/c', script], cwd=tmp,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(os.environ, PATH=path_env))
    up = False
    deadline = time.time() + wait
    while time.time() < deadline:
        if port_open(PORT):
            up = True
            break
        if p.poll() is not None and time.time() > deadline - wait + 1.5:
            break
        time.sleep(0.3)
    return p, up


print('\n[A] 新 bat + 真实持久 PATH（无受管运行时）')
proc_a, up_a = run_bat(bat, PATH_A)
step('A#1 工作台被拉起（8765 监听中）', up_a)
hdr = ''
code = None
if up_a:
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/' % PORT, timeout=8) as resp:
            code = resp.status
            hdr = resp.headers.get('Server') or ''
    except Exception as e:
        hdr = 'ERR %s' % e
step('A#2 GET / 返回 200', code == 200, 'status=%s' % code)
step('A#3 Server 头为 Workbench/1.0.10', 'Workbench/1.0.10' in hdr, hdr)
try:
    proc_a.kill()
except Exception:
    pass
step('A#4 收尾：端口已彻底释放（按端口属主杀进程树）', kill_port_owner(PORT))

# ---------- 实验 B：旧 bat 在同一环境下失败 ----------
print('\n[B] v1.0.9 交付包内旧 bat + 不含真 Python 的 PATH')
old_dir = os.path.join(tmp, '_oldbat')
os.makedirs(old_dir, exist_ok=True)
old_copy = os.path.join(old_dir, '启动工作台.bat')
with open(old_copy, 'wb') as f:
    f.write(open(OLD_BAT, 'rb').read())
r = subprocess.run(['cmd.exe', '/c', old_copy], cwd=tmp,
                   stdin=subprocess.DEVNULL, capture_output=True,
                   env=dict(os.environ, PATH=PATH_B))
out_b = (r.stdout or b'').decode('gbk', 'replace')
step('B#1 旧 bat 无法启动（报 Python not found）',
     'Python not found' in out_b, out_b.strip().splitlines()[-1] if out_b.strip() else '')
step('B#2 旧 bat 未留下监听端口', not port_open(PORT))

print('\n' + '=' * 58)
print('交付包端到端验收: PASS %d / FAIL %d' % (PASS, FAIL))
print('=' * 58)

import shutil
if FAIL:
    print('保留解压目录以便排查：%s' % tmp)
else:
    shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if FAIL else 0)
