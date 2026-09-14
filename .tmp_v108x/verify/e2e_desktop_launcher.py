# -*- coding: utf-8 -*-
"""Acceptance test for the DESKTOP launcher.

Runs it exactly the way a double-click would:
  * PATH      = the machine's REAL persistent PATH (registry), i.e. WITHOUT
                the managed-runtime injection this dev shell has. This is the
                whole point: the earlier launcher bug only appeared there.
  * cwd       = the desktop, not the project
  * stdin     = NUL (no interactive help)
  * BROWSER   = a stub, so the automatic webbrowser.open() does not pop a tab
                during the test run

Then it verifies over HTTP, not by reading console text (the console stream
mixes code pages and is unreliable to parse).
"""

import ctypes
import os
import re
import subprocess
import sys
import time
import urllib.request
import winreg

PORT = 8765
DESKTOP_BAT = 'C:\\Users\\' + '\u5b9c\u6625\u6cd5\u9662' + '\\Desktop\\' + \
              '\u542f\u52a8\u5de5\u4f5c\u53f0.bat'
DESKTOP = os.path.dirname(DESKTOP_BAT)

passes, failures = [], []


def step(label, ok, detail=''):
    (passes if ok else failures).append(label)
    print('  [%s] %-52s %s' % ('PASS' if ok else 'FAIL', label, detail))


def port_open():
    import socket
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(('127.0.0.1', PORT))
        return True
    except Exception:
        return False
    finally:
        s.close()


def persistent_path():
    """Rebuild the real PATH the way Windows does: machine + user, expanded."""
    def read(root, sub):
        try:
            k = winreg.OpenKey(root, sub)
            v, _ = winreg.QueryValueEx(k, 'Path')
            return v
        except Exception:
            return ''
    machine = read(winreg.HKEY_LOCAL_MACHINE,
                   r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
    user = read(winreg.HKEY_CURRENT_USER, r'Environment')
    combined = ';'.join(p for p in (machine, user) if p)
    # expand %VAR% references using the current process env as the base
    os.environ.setdefault('SystemRoot', r'C:\Windows')
    return os.path.expandvars(combined)


def taskkill_tree(pid):
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                   capture_output=True, shell=False)


def port_owner_pid():
    r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                       errors='replace')
    for ln in r.stdout.splitlines():
        if 'LISTENING' in ln and (':%d' % PORT) in ln:
            return ln.split()[-1]
    return None


print('=== setup ===')
step('port %d free before test' % PORT, not port_open(),
     'already listening - aborting' if port_open() else 'free')
if port_open():
    sys.exit(1)

real_path = persistent_path()
has_managed = r'.workbuddy\binaries' in real_path
step('persistent PATH has NO managed runtime (the real double-click case)',
     not has_managed,
     'managed runtime present in PATH!' if has_managed else 'clean')
step('desktop launcher exists', os.path.exists(DESKTOP_BAT), DESKTOP_BAT)

env = dict(os.environ)
env['PATH'] = real_path
env['BROWSER'] = 'no-such-browser-stub'      # keep the test from opening a tab

print()
print('=== run: exactly like a double-click ===')
print('  cwd : %s' % DESKTOP)
p = subprocess.Popen(['cmd.exe', '/c', DESKTOP_BAT], cwd=DESKTOP,
                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, env=env)

code, header, up = None, '', False
deadline = time.time() + 25
while time.time() < deadline:
    if port_open():
        up = True
        break
    if p.poll() is not None:
        break
    time.sleep(0.3)

step('launcher brought the workbench up (port %d listening)' % PORT, up)

if up:
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/' % PORT, timeout=8) as r:
            code = r.status
            header = r.headers.get('Server') or ''
    except Exception as e:
        header = 'ERR %s' % e
    step('GET / returns 200', code == 200, 'status=%s' % code)
    step('Server header carries v1.0.10', 'Workbench/1.0.10' in header, header)
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/api/securities' % PORT,
                                    timeout=8) as r:
            body = r.read().decode('utf-8', 'replace')
        n = len(re.findall(r'"code"', body))
        step('/api/securities responds with data', r.status == 200 and n > 0,
             'status=%s securities=%d' % (r.status, n))
    except Exception as e:
        step('/api/securities responds with data', False, 'ERR %s' % e)

print()
print('=== teardown ===')
# kill the WHOLE tree: the wrapper's cmd -> called bat's cmd -> python.exe
# Popen.kill() alone would leave python holding the port (known trap).
owner = port_owner_pid()
if owner:
    taskkill_tree(owner)
if p.poll() is None:
    taskkill_tree(p.pid)
for _ in range(30):
    if not port_open():
        break
    time.sleep(0.3)
step('port %d released after teardown' % PORT, not port_open())

print()
print('RESULT: PASS %d / FAIL %d' % (len(passes), len(failures)))
for f in failures:
    print('  FAILED: %s' % f)
sys.exit(1 if failures else 0)
