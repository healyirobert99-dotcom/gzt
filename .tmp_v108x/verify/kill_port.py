# -*- coding: utf-8 -*-
"""按端口杀掉监听进程树（含子进程）。本环境 `taskkill` 必须走 Python 调，
且端口属主清理不彻底会让后续实验误判（见 ENV-TRAPS）。"""
import subprocess
import sys

port = sys.argv[1] if len(sys.argv) > 1 else '8805'
out = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True,
                     text=True, errors='replace').stdout
pids = set()
for line in out.splitlines():
    parts = line.split()
    if len(parts) >= 5 and parts[1].endswith(':' + port) and parts[3] == 'LISTENING':
        pids.add(parts[4])
print('port %s owners: %s' % (port, sorted(pids)))
for pid in sorted(pids):
    r = subprocess.run(['taskkill', '/F', '/T', '/PID', pid],
                       capture_output=True, text=True, errors='replace')
    print('kill %s -> rc=%d %s' % (pid, r.returncode,
                                   (r.stdout or r.stderr or '').strip()[:120]))
if not pids:
    print('（端口无监听者）')
