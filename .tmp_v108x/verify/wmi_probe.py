# -*- coding: utf-8 -*-
"""探测：能否用 WMI 创建一个脱离 agent 进程树的进程。

背景：agent 环境的进程树被放进 Job Object（kill-on-close），
`DETACHED_PROCESS` 和 `CREATE_BREAKAWAY_FROM_JOB` 都留不住后台服务
（前者实测被回收，后者被 WinError 5 拒绝）。

WMI 的 `Win32_Process.Create` 让 WmiPrvSE.exe 当父进程，理论上可脱离。
本脚本先做无害探测：用 WMI 起一个写文件的进程，等几秒后检查文件是否出现。
"""

import os
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = r'D:\个股工作台'
PROBE = os.path.join(ROOT, '.tmp_v108x', 'verify', 'wmi_probe.txt')

if os.path.exists(PROBE):
    os.remove(PROBE)

# wmic 是否还在？（较新 Windows 上可能被移除）
which = subprocess.run(['where', 'wmic'], capture_output=True, text=True,
                       errors='replace').stdout.strip()
print('[1] wmic 路径: %s' % (which or '未找到'))

# 用 WMI 起一个进程：写个文件并停留 2 秒，便于观察存活
inner = 'cmd.exe /c echo wmi-ok-%s > "%s" & timeout /t 6 >nul' % (int(time.time()), PROBE)
r = subprocess.run(['wmic', 'process', 'call', 'create', inner],
                   capture_output=True, text=True, errors='replace')
out = ((r.stdout or '') + (r.stderr or '')).strip()
print('[2] wmic rc=%d' % r.returncode)
for line in out.splitlines()[:12]:
    print('    ' + line.strip())

time.sleep(3)
print('[3] 探测文件已生成: %s' % os.path.exists(PROBE))
if os.path.exists(PROBE):
    with open(PROBE, encoding='utf-8', errors='replace') as f:
        print('    内容: %s' % f.read().strip())
