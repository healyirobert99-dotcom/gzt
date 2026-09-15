# -*- coding: utf-8 -*-
"""负向验证（浏览器层）：把 `findSec` 回退成修正前的版本，确认 §E7 / §E8 会翻红。

为什么单独做这一条：
  §E7（详情页 4 个操作入口）与 §E8（「··· 更多」菜单里的 4 项，本次新增）都依赖
  `findSec` 覆盖已归档标的。若不做负向验证，无法区分"断言在守护那道闸门"
  与"断言恒真 / 读数写错"。做法：
    1) 把沙箱副本（sandbox_arch）里的 app.js 改成修正前的单级查找；
    2) **直接**用沙箱里那份 server.py 起服务（不经 sandbox_server.py，避免它重建沙箱）；
    3) 跑 browser_e2e_archive_edge.py，要求 §E7#1~#3 与 §E8#1~#4 全部 FAIL，
       而对照组 §E7#4 / §E9#1 仍然 PASS（排除"整体坏了"的误判）；
    4) 收尾杀端口并删掉沙箱。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
BOX = os.path.join(ROOT, '.tmp_v108x', 'verify', 'sandbox_arch')
APP_JS = os.path.join(BOX, 'app', 'static', 'app.js')
SERVER = os.path.join(BOX, 'app', 'server.py')
EDGE = os.path.join(ROOT, '.tmp_v108x', 'verify', 'browser_e2e_archive_edge.py')
OUT = os.path.join(ROOT, '.tmp_v108x', 'verify', 'edge_neg_findsec.txt')

PASS = 0
FAIL = 0


def step(label, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [PASS] %s' % label)
    else:
        FAIL += 1
        print('  [FAIL] %s  ← %s' % (label, detail))


def main():
    print('=' * 78)
    print('负向验证（浏览器层）：findSec 回退 → §E7 / §E8 必须翻红')
    print('=' * 78)
    if not os.path.exists(APP_JS):
        print('沙箱不存在（%s）。先跑一次 sandbox_server.py 8805 生成。' % BOX)
        return 1

    src = open(APP_JS, encoding='utf-8').read()
    fixed = ("const findSec = id => S.secs.find(s => s.id === Number(id))\n"
             "  || (S.archived || []).find(s => s.id === Number(id));")
    broken = "const findSec = id => S.secs.find(s => s.id === Number(id));"
    step('§0 沙箱 app.js 里找到修正后的 findSec（两级查找）', fixed in src)
    if fixed not in src:
        return 1
    open(APP_JS, 'w', encoding='utf-8', newline='').write(src.replace(fixed, broken))
    back = open(APP_JS, encoding='utf-8').read()
    step('§0b 已回退成修正前的单级查找（重复注入防护：不再含 S.archived 兜底）',
         broken in back and fixed not in back)

    proc = subprocess.Popen([PY, '-u', SERVER, '--port', '8805', '--no-browser'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('  沙箱服务已起（PID %d），等待就绪…' % proc.pid)
    import time
    for _ in range(30):
        time.sleep(1)
        try:
            import http.client
            c = http.client.HTTPConnection('127.0.0.1', 8805, timeout=3)
            c.request('GET', '/api/securities')
            if c.getresponse().status == 200:
                print('  服务就绪')
                break
        except Exception:
            pass
    else:
        step('§0c 沙箱服务就绪', False, '30 秒内未就绪')
        proc.kill()
        return 1

    r = subprocess.run([PY, EDGE], cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    open(OUT, 'w', encoding='utf-8').write(out)
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith('FAIL')]
    passes = [l.strip() for l in out.splitlines() if l.strip().startswith('PASS')]
    print('  边缘脚本（负向副本）：PASS %d / FAIL %d' % (len(passes), len(fails)))
    for l in fails:
        print('    %s' % l[:140])

    must_fail = ['§E7#1', '§E7#2', '§E7#3', '§E8#1', '§E8#2', '§E8#3', '§E8#4']
    missing = [m for m in must_fail if not any(m in l for l in fails)]
    step('§1 回退后 §E7#1~#3 + §E8#1~#4 共 7 条全部翻红', not missing,
         '未翻红的=%s' % missing)
    step('§2 对照组 §E7#4（不查 findSec 的入口）回退后仍绿（排除"整体坏了"）',
         any('§E7#4' in l for l in passes))
    step('§3 对照组 §E9#1（活跃标的）回退后仍绿', any('§E9#1' in l for l in passes))

    # 收尾
    subprocess.run([PY, os.path.join(ROOT, '.tmp_v108x', 'verify', 'kill_port.py'), '8805'],
                   capture_output=True)
    subprocess.run([PY, '-c',
                    'import shutil;shutil.rmtree(r"%s",ignore_errors=True)' % BOX],
                   capture_output=True)
    step('§4 沙箱已删除、端口已释放（负向副本不留痕）', not os.path.exists(BOX))

    print()
    print('=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
