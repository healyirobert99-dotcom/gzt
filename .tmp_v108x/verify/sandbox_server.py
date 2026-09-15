# -*- coding: utf-8 -*-
"""沙箱服务启动器：把 app 与**数据库副本**放进沙箱，然后前台跑 server.py。

为什么要独立成脚本并由后台任务启动：
本环境 agent 起不了"能活下去"的服务进程（进程树被 Job Object 托管），
但**后台任务**里的进程会在任务存活期间一直活着。故：
  1) 用后台任务跑本脚本（= 拿到一个持续可用的沙箱服务）
  2) 再用普通 Bash 调用跑 agent-browser / HTTP 断言
  3) 最后杀掉端口属主并删沙箱

绝不触碰 D:\\个股工作台\\data\\workbench.db —— 只用它的副本。
"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8805
BOX = os.path.join(ROOT, '.tmp_v108x', 'verify', 'sandbox_arch')

REAL_DB = os.path.join(ROOT, 'data', 'workbench.db')

shutil.rmtree(BOX, ignore_errors=True)
os.makedirs(BOX)
shutil.copytree(os.path.join(ROOT, 'app'), os.path.join(BOX, 'app'))
os.makedirs(os.path.join(BOX, 'data'), exist_ok=True)
shutil.copy2(REAL_DB, os.path.join(BOX, 'data', 'workbench.db'))

print('沙箱 = %s' % BOX)
print('沙箱库 = %s（真实库副本，真实库不会被碰）' % os.path.join(BOX, 'data', 'workbench.db'))
print('端口 = %d' % PORT, flush=True)

os.chdir(BOX)
os.execv(PY, [PY, '-u', os.path.join(BOX, 'app', 'server.py'),
              '--port', str(PORT), '--no-browser'])
