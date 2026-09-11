# -*- coding: utf-8 -*-
"""v1.0.10 「启动脚本交付修复」交付契约测试。

背景（v1.0.9 交付后用户实测发现）
--------------------------------
v1.0.9 及更早交付包内的 `启动工作台.bat`（388 B）用

    set "PY=python"
    where python >nul 2>nul
    if errorlevel 1 ( echo [ERROR] Python not found. ... )

判定解释器。本机**持久 PATH** 上与 python 相关的项只有
`%LOCALAPPDATA%\\Microsoft\\WindowsApps`，该目录下的 python.exe 是
**Microsoft Store 执行别名存根**，不是解释器：

  · `where python` 命中存根 → 守卫恒为"通过"，"Python not found" 分支从不触发
  · `python app\\server.py` 实际拉起的是商店存根
  · 用户现象：双击窗口一闪而过 / 弹出应用商店

诊断陷阱：在 agent 的 shell 里 `where python` 与 `python --version` 都正常
（受管运行时被注入到**进程** PATH 且排在 WindowsApps 之前），
只在本机 shell 验证会得出"bat 没问题"的错误结论；必须看持久 PATH。

本测试把「启动脚本必须长什么样」固化为可执行契约，防止再次回退
（旧 bat 会直接踩中 §B#2 / §B#4 / §B#5 / §B#6）。

  §A  版本同步契约：服务端 4 处版本号 + 前端版本头必须同为 1.0.10
  §B  启动脚本契约：ASCII-only / 全 CRLF / 真执行探测 / 显式拒绝 Store 存根 /
      不含旧判定 / 端口与 server.py 默认端口一致

不依赖数据库、不联网、不启动服务。
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

TARGET = '1.0.10'
BAT_REL = '启动工作台.bat'

FAIL_COUNT = 0
TOTAL = 0


def step(name, ok, detail=''):
    global FAIL_COUNT, TOTAL
    TOTAL += 1
    flag = 'PASS' if ok else 'FAIL'
    print('  [%s] %s %s' % (flag, name, detail))
    if not ok:
        FAIL_COUNT += 1


def _read_text(rel):
    with open(os.path.join(ROOT, *rel.split('/')), encoding='utf-8') as f:
        return f.read()


def _read_bytes(rel):
    with open(os.path.join(ROOT, *rel.split('/')), 'rb') as f:
        return f.read()


# ==================== §A 版本同步契约 ====================

# 版本号必须同步的 4 处（服务端）—— 每项给出"抽取用正则"。
# 正则只匹配到版本号本身，因此可以直接断言"4 处抽取值完全一致"。
SERVER_SLOTS = (
    ('TARGET_SCHEMA_VERSION', r"TARGET_SCHEMA_VERSION\s*=\s*'([^']+)'"),
    ('server_version',        r"server_version\s*=\s*'Workbench/([^']+)'"),
    ('argparse description',  r"description='A/H 投研交易工作台 v([^']+)'"),
    ('启动 print 文案',        r"A/H 投研交易工作台 v([^']+) 已启动"),
)


def test_a_version_sync():
    print('\n=== §A 版本同步契约（v%s）===' % TARGET)
    src = _read_text('app/server.py')
    js = _read_text('app/static/app.js')

    step('§A#1 TARGET_SCHEMA_VERSION=%s' % TARGET,
         "TARGET_SCHEMA_VERSION = '%s'" % TARGET in src)
    step('§A#2 server_version=Workbench/%s' % TARGET,
         "server_version = 'Workbench/%s'" % TARGET in src)
    step('§A#3 argparse 描述为 v%s' % TARGET,
         "description='A/H 投研交易工作台 v%s'" % TARGET in src)
    step('§A#4 启动文案为 v%s' % TARGET,
         'A/H 投研交易工作台 v%s 已启动' % TARGET in src)

    # 版本契约的**唯一性**：4 处必须都能抽到，且值必须完全一致。
    # 这条是"版本号同步 4 处"约定的机器化表达 —— v1.0.10 就曾在
    # 移植过程中只改了 3 处而让启动文案留在 1.0.9。
    vals = []
    for label, pat in SERVER_SLOTS:
        m = re.search(pat, src)
        vals.append(m.group(1) if m else None)
    step('§A#5 服务端 4 处版本号齐全且完全一致',
         vals == [TARGET] * len(SERVER_SLOTS),
         '%s' % dict(zip([s[0] for s in SERVER_SLOTS], vals)))

    step('§A#6 前端版本头 v%s' % TARGET,
         '前端  v%s' % TARGET in js,
         '实际头部: %r' % (re.search(r'前端\s+v[\d.]+', js) or {}))


# ==================== §B 启动脚本契约 ====================

def test_b_launcher_contract():
    print('\n=== §B 交付启动脚本契约 ===')
    path = os.path.join(ROOT, BAT_REL)

    if not os.path.exists(path):
        step('§B#1 交付包内 `%s` 存在' % BAT_REL, False, '文件缺失')
        for i in range(2, 9):
            step('§B#%d （因缺文件而跳过）' % i, False)
        return

    raw = _read_bytes(BAT_REL)
    text = raw.decode('utf-8', 'replace')
    server_src = _read_text('app/server.py')

    step('§B#1 交付包内 `%s` 存在' % BAT_REL, True,
         '%d B / %d 行' % (len(raw), raw.count(b'\r\n')))

    # 非 ASCII 字节会被 cmd.exe 按控制台代码页（936 / 65001）逐字节解释而错位，
    # 污染最终交给 shell 的路径。用户名含中文，所以脚本统一用 %USERPROFILE% 展开。
    nonascii = [b for b in raw if b >= 128]
    step('§B#2 纯 ASCII（无 ≥0x80 字节）', not nonascii,
         '非 ASCII 字节数 = %d' % len(nonascii))

    step('§B#3 全 CRLF 行尾（无裸 LF）',
         raw.count(b'\n') > 0 and raw.count(b'\n') == raw.count(b'\r\n'),
         'LF=%d CRLF=%d' % (raw.count(b'\n'), raw.count(b'\r\n')))

    # 核心修复点 1：候选必须**真跑一次**才算通过。
    # 旧版只看 `where python` 是否存在，无法区分真解释器与 Store 存根。
    probe = text.replace(' ', '')
    step('§B#4 真执行探测解释器版本（非仅检查命令存在）',
         'sys.version_info>=(3,8)' in probe,
         '命中 `sys.version_info>=(3,8)`' if 'sys.version_info>=(3,8)' in probe
         else '未找到真执行探测')

    # 核心修复点 2：显式拒绝路径含 WindowsApps 的候选（即使它能"跑起来"）。
    step('§B#5 显式拒绝 Microsoft Store 执行别名存根',
         '%T:WindowsApps=%' in text,
         '路径守卫存在' if '%T:WindowsApps=%' in text else '缺少 WindowsApps 路径守卫')

    step('§B#6 不含旧的 `set "PY=python"` + `where python` 判定',
         'where python' not in text and 'set "PY=python"' not in text,
         '旧判定残留')

    step('§B#7 启动前后置守卫：校验 app\\server.py 存在',
         'app\\server.py' in text)

    # 端口一致性：脚本里印出的地址必须与 server.py 的 --port 默认值相同，
    # 否则用户按脚本提示访问会 404/连不上。
    m = re.search(r"add_argument\('--port',\s*type=int,\s*default=(\d+)\)", server_src)
    default_port = m.group(1) if m else None
    step('§B#8 提示端口与 server.py 默认端口一致',
         default_port is not None and (':%s' % default_port) in text,
         'server.py default=%s, bat 正文含 `:%s`=%s'
         % (default_port, default_port, (':%s' % default_port) in text))


# ==================== 入口 ====================

def main():
    print('=== v1.0.10 启动脚本交付修复 —— 交付契约测试 ===')
    test_a_version_sync()
    test_b_launcher_contract()
    print('\n' + '=' * 60)
    print('v1.0.10 测试: PASS %d / FAIL %d  (共 %d 断言)'
          % (TOTAL - FAIL_COUNT, FAIL_COUNT, TOTAL))
    print('=' * 60)
    if FAIL_COUNT:
        print('FAIL_COUNT = %d' % FAIL_COUNT)
        return 1
    print('FAIL_COUNT = 0')
    print('ALL TESTS PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
