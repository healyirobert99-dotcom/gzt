# -*- coding: utf-8 -*-
"""Negative tests for the desktop launcher's guards.

Design notes (learned the hard way):
  * The self-call guard compares "%~f0" with "%WB%\\<launcher name>". A copy
    under a DIFFERENT name therefore does not trigger it - it just delegates
    and really starts the server. So the guard is exercised by placing the
    wrapper under its real name inside a throw-away directory and pointing the
    WB literal at that directory.
  * No probe may touch the project directory, and BROWSER is stubbed so the
    server's webbrowser.open() cannot pop a window.
"""

import hashlib
import os
import shutil
import subprocess
import sys

CJK_DIR = '\u4e2a\u80a1\u5de5\u4f5c\u53f0'          # 个股工作台
CJK_USER = '\u5b9c\u6625\u6cd5\u9662'                # 宜春法院
CJK_BAT = '\u542f\u52a8\u5de5\u4f5c\u53f0.bat'        # 启动工作台.bat

DESKTOP_BAT = 'C:\\Users\\' + CJK_USER + '\\Desktop\\' + CJK_BAT
PROJECT = 'D:\\' + CJK_DIR
SANDBOX = 'D:\\_wbguard_probe'                       # throw-away, ASCII path

raw = open(DESKTOP_BAT, 'rb').read()
print('desktop launcher : %d B' % len(raw))
print('sha256           : %s' % hashlib.sha256(raw).hexdigest())
print()


def run(bat, cwd, timeout=20):
    env = dict(os.environ)
    env['BROWSER'] = 'no-such-browser-stub'          # never open a real tab
    try:
        p = subprocess.run(['cmd.exe', '/c', bat], cwd=cwd,
                           stdin=subprocess.DEVNULL, env=env,
                           capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', ''
    except Exception as e:
        return 'ERROR', str(e)


results = []

# ------------------------------------------------------------------ N1
print('=== N1  self-call guard: wrapper under its real name inside WB ===')
# WB is rewritten to a throw-away dir and the wrapper is placed there under
# its real name, so "%~f0" == "%WB%\<name>" and the guard must fire.
if os.path.isdir(SANDBOX):
    shutil.rmtree(SANDBOX)
os.makedirs(SANDBOX)
cbat = os.path.join(SANDBOX, CJK_BAT)
open(cbat, 'wb').write(raw.replace(PROJECT.encode('utf-8'),
                                   SANDBOX.encode('utf-8')))
rc, out = run(cbat, SANDBOX)
hit = 'running from inside' in out
print('  rc=%s   guard message: %s' % (rc, hit))
print('  runaway recursion : %s' % ('NO' if rc != 'TIMEOUT' else 'YES - BUG'))
for ln in out.splitlines():
    if 'ERROR' in ln:
        print('   ', ln.strip())
ok1 = hit and rc == 1
print('  [%s] N1' % ('PASS' if ok1 else 'FAIL'))
results.append(ok1)
shutil.rmtree(SANDBOX, ignore_errors=True)

# ------------------------------------------------------------------ N2
print()
print('=== N2  missing project path: clear message, non-zero exit ===')
fake = raw.replace(PROJECT.encode('utf-8'), b'D:\\no-such-project-xyz')
tmp = os.path.join(SANDBOX + '_nf', CJK_BAT)
os.makedirs(os.path.dirname(tmp), exist_ok=True)
open(tmp, 'wb').write(fake)
rc, out = run(tmp, os.path.dirname(tmp))
hit = 'Workbench not found' in out
print('  rc=%s   guide message: %s' % (rc, hit))
print('  hung on pause with stdin=NUL : %s' % ('NO' if rc != 'TIMEOUT' else 'YES'))
for ln in out.splitlines():
    if 'ERROR' in ln:
        print('   ', ln.strip())
ok2 = hit and rc == 1
print('  [%s] N2' % ('PASS' if ok2 else 'FAIL'))
results.append(ok2)
shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)

# ------------------------------------------------------------------ N3
print()
print('=== N3  no discovery logic duplicated in the wrapper ===')
txt = raw.decode('utf-8')
bad = {k: (k in txt) for k in ('WindowsApps', ':try', 'sys.version_info')}
print('  must all be False:', bad)
ok3 = not any(bad.values())
print('  [%s] N3' % ('PASS' if ok3 else 'FAIL'))
results.append(ok3)

# ------------------------------------------------------------------ N4
print()
print('=== N4  wrapper delegates to the project launcher, exactly once ===')
calls = txt.count('call "%WB%')
print('  delegate line occurrences: %d (expected 1)' % calls)
ok4 = calls == 1
print('  [%s] N4' % ('PASS' if ok4 else 'FAIL'))
results.append(ok4)

# ------------------------------------------------------------------ N5
print()
print('=== N5  project launcher untouched / no probe leftovers ===')
now = open(DESKTOP_BAT, 'rb').read()
same = now == raw
leftovers = [p for p in (SANDBOX, SANDBOX + '_nf') if os.path.isdir(p)]
print('  desktop launcher sha256 unchanged : %s' % same)
print('  sandbox dirs left behind          : %s' % (leftovers or 'none'))
ok5 = same and not leftovers
print('  [%s] N5' % ('PASS' if ok5 else 'FAIL'))
results.append(ok5)

n_fail = results.count(False)
print()
print('RESULT: PASS %d / FAIL %d' % (len(results) - n_fail, n_fail))
sys.exit(1 if n_fail else 0)
