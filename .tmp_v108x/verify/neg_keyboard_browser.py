# -*- coding: utf-8 -*-
"""负向验证（浏览器层）：把「× 的键盘可达性」打坏，确认 §K 会翻红。

为什么必须做：`browser_e2e_archive_keyboard.py` 的 §K3 是本轮**新增**的断言，
它守护的是 CSS 里三条只对键盘生效的规则。不做负向验证就无法区分
"断言在守护那道闸门" 与 "断言恒真 / 读数写错"（本会话已两次踩到读数假红）。

两次注入（都在沙箱副本里就地改，跑完**还原并逐字节核对**）：
  N1  删掉 `.card-archive:focus-visible` 的显形声明 → §K3#2 该红
  N2  给 × 加 tabindex="-1" → 键盘 Tab 再也走不到 → §K3#1 该红

对照组（两轮都必须**保持绿**，以排除"整体坏了"）：
  §K1#2（× 与卡片一一对应）、§K2#2（未聚焦时 pointer-events: none）

收尾：杀端口、删沙箱。
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
V = os.path.join(ROOT, '.tmp_v108x', 'verify')
BOX = os.path.join(V, 'sandbox_arch')
CSS = os.path.join(BOX, 'app', 'static', 'style.css')
APPJS = os.path.join(BOX, 'app', 'static', 'app.js')
SERVER = os.path.join(BOX, 'app', 'server.py')
KBD = os.path.join(V, 'browser_e2e_archive_keyboard.py')

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


N1_OLD = ('.card-archive:focus-visible { opacity: 1; pointer-events: auto; '
          'outline: none; border-color: var(--accent); }')
N1_NEW = ('.card-archive:focus-visible { outline: none; '
          'border-color: var(--accent); }')
N2_OLD = '<button type="button" class="card-archive" data-archive-id="${s.id}"'
N2_NEW = ('<button type="button" tabindex="-1" class="card-archive" '
          'data-archive-id="${s.id}"')


def wait_ready(timeout=40):
    import http.client
    for _ in range(timeout):
        time.sleep(1)
        try:
            c = http.client.HTTPConnection('127.0.0.1', 8805, timeout=3)
            c.request('GET', '/api/securities')
            if c.getresponse().status == 200:
                return True
        except Exception:
            pass
    return False


def run_kbd():
    r = subprocess.run([PY, KBD], cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith('FAIL')]
    passes = [l.strip() for l in out.splitlines() if l.strip().startswith('PASS')]
    return out, fails, passes


def inject(path, old, new, tag):
    src = open(path, encoding='utf-8', newline='').read()
    if src.count(old) != 1:
        return None, '注入锚点不唯一（%d 处）' % src.count(old)
    open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    return src, None


def restore(path, original):
    open(path, 'w', encoding='utf-8', newline='').write(original)


def main():
    print('=' * 78)
    print('负向验证（浏览器层）：打坏「× 的键盘可达性」→ §K3 必须翻红')
    print('=' * 78)
    if not os.path.exists(CSS):
        print('沙箱不存在（%s）。先跑一次 sandbox_server.py 8805 生成。' % BOX)
        return 1

    results = {}
    for tag, path, old, new, expect in (
            ('N1', CSS, N1_OLD, N1_NEW, '§K3#2'),
            ('N2', APPJS, N2_OLD, N2_NEW, '§K3#1')):
        original, err = inject(path, old, new, tag)
        if err:
            step('%s 注入成功' % tag, False, err)
            continue
        step('%s 注入成功（%s %s）' % (tag, os.path.basename(path), old[:48]),
             True, '')

        proc = subprocess.Popen([PY, '-u', SERVER, '--port', '8805', '--no-browser'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_ready():
            step('%s 负向副本服务就绪' % tag, False, '40 秒内未就绪')
            proc.kill()
            restore(path, original)
            continue
        out, fails, passes = run_kbd()
        open(os.path.join(V, 'neg_kbd_%s.txt' % tag.lower()), 'w',
             encoding='utf-8').write(out)
        print('    %s 负向副本：PASS %d / FAIL %d' % (tag, len(passes), len(fails)))
        for l in fails:
            print('      %s' % l[:140])

        results[tag] = (fails, passes, expect)
        subprocess.run([PY, os.path.join(V, 'kill_port.py'), '8805'],
                       capture_output=True)
        time.sleep(1)
        restore(path, original)
        back = open(path, encoding='utf-8', newline='').read()
        step('%s 跑完已还原原文件且逐字节一致' % tag, back == original)

    for tag, (fails, passes, expect) in results.items():
        step('%s 注入后 %s 确实翻红' % (tag, expect),
             any(expect in l for l in fails), '未翻红；FAIL 共 %d 条' % len(fails))
        step('%s 对照组 §K1#2（× 与卡片一一对应）仍绿（排除"整体坏了"）' % tag,
             any('§K1#2' in l for l in passes))
        step('%s 对照组 §K2#2（未聚焦 pointer-events: none）仍绿' % tag,
             any('§K2#2' in l for l in passes))

    subprocess.run([PY, '-c',
                    'import shutil;shutil.rmtree(r"%s",ignore_errors=True)' % BOX],
                   capture_output=True)
    step('收尾 沙箱已删除、端口已释放', not os.path.exists(BOX))

    print()
    print('=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
