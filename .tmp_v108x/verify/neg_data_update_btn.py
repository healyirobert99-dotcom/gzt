# -*- coding: utf-8 -*-
"""「数据更新」按钮测试的负向验证（meta-test）。

目的
----
证明 tests/test_data_update_btn.py 不是"写完就绿"的空壳：把本次新增能力的每个
关键点逐一**回退**，测试必须逐条报 FAIL。若某个变体回退后测试仍然全绿，说明
那条断言是装饰品。

安全约束
--------
所有替换都在**临时目录的副本**上进行，绝不触碰正式的 app/ 与 tests/。
（v1.0.10 的 neg_desktop_launcher.py 曾因把副本放错位置而真的启动了服务，
这里用独立 tmp 骨架从根上避免同类事故。）

运行：
  python .tmp_v108x/verify/neg_data_update_btn.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable
TEST_REL = 'tests/test_data_update_btn.py'

COPY_FILES = (
    ('app/server.py', 'app/server.py'),
    ('app/static/index.html', 'app/static/index.html'),
    ('app/static/app.js', 'app/static/app.js'),
    ('app/static/style.css', 'app/static/style.css'),
    (TEST_REL, TEST_REL),
)

# 后端 force 分支的原文（用于变体 4 的回退替换）
FORCE_BLOCK = '\n'.join([
    '    if force:',
    '        # 手动「数据更新」：忽略 8 秒缓存窗口，本次请求的全部 symbol 一律重拉。',
    '        need_list = list(need)',
    '    else:',
    '        need_list = [s for s in need if stale_window or s not in cached_snapshot]',
])
NO_FORCE_BLOCK = '    need_list = [s for s in need if stale_window or s not in cached_snapshot]'


def _replace_once(src, old, new):
    if old not in src:
        return None
    return src.replace(old, new, 1)


VARIANTS = [
    (
        '按钮被隐藏（hidden 回归）',
        'app/static/index.html',
        lambda s: _replace_once(s, ' type="button" title=', ' type="button" hidden title='),
        '§C#2',
    ),
    (
        '请求不再带 force=1（按钮退化为普通刷新）',
        'app/static/app.js',
        lambda s: _replace_once(s, "force ? '&force=1'", "''"),
        '§C#7',
    ),
    (
        '点击只传 manual 不传 force',
        'app/static/app.js',
        lambda s: _replace_once(s, 'refreshQuotes(true, true)', 'refreshQuotes(true)'),
        '§C#5',
    ),
    (
        '后端忽略 force（退回旧 8 秒去抖）',
        'app/server.py',
        lambda s: _replace_once(s, FORCE_BLOCK, NO_FORCE_BLOCK),
        '§A#5',
    ),
    (
        '后端 force 只认 "1"（收紧白名单）',
        'app/server.py',
        lambda s: _replace_once(
            s, "in ('1', 'true', 'yes', 'on')", "== '1'"),
        '§B#6',
    ),
]


def build_sandbox():
    tmp = tempfile.mkdtemp(prefix='wb_negbtn_')
    for rel, _ in COPY_FILES:
        dst = os.path.join(tmp, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, *rel.split('/')), dst)
    return tmp


def run_variant(title, rel, mutate, expect_label):
    tmp = build_sandbox()
    try:
        path = os.path.join(tmp, *rel.split('/'))
        with open(path, encoding='utf-8') as f:
            src = f.read()
        new = mutate(src)
        if new is None or new == src:
            print('  [BAD] 变体「%s」：替换未命中 %s（变体本身失效，非测试问题）'
                  % (title, rel))
            return False
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(new)

        r = subprocess.run([PY, os.path.join(tmp, *TEST_REL.split('/'))],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=600)
        out = (r.stdout or '') + (r.stderr or '')
        n_fail = out.count('[FAIL]')
        hit = ('[FAIL] %s' % expect_label) in out
        if hit:
            print('  [OK ] 变体「%s」→ 捕获 %s（该轮 FAIL 共 %d 条）'
                  % (title, expect_label, n_fail))
            return True
        print('  [BAD] 变体「%s」→ 未捕获 %s（FAIL 共 %d 条）'
              % (title, expect_label, n_fail))
        tail = '\n'.join(out.strip().splitlines()[-6:])
        print('       输出尾部：\n%s' % '\n'.join('       ' + l for l in tail.splitlines()))
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print('=== 「数据更新」按钮测试 —— 负向验证（回退必须被抓）===')
    print('正式目录：%s' % ROOT)

    # 先确认基线全绿，否则负向验证无意义
    print('\n--- 基线（未改动副本，应全绿）---')
    tmp = build_sandbox()
    base_ok = False
    try:
        r = subprocess.run([PY, os.path.join(tmp, *TEST_REL.split('/'))],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=600)
        out = (r.stdout or '') + (r.stderr or '')
        base_ok = 'ALL TESTS PASS' in out
        print('  [%s] 基线副本 ALL TESTS PASS' % ('OK ' if base_ok else 'BAD'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not base_ok:
        print('\n基线不绿，负向验证中止。')
        return 1

    print('\n--- 回退变体（每个都必须被某种断言抓住）---')
    ok = all(run_variant(*v) for v in VARIANTS)

    print('\n' + '=' * 60)
    if ok:
        print('负向验证通过：%d/%d 个回退变体全部被测试捕获' % (len(VARIANTS), len(VARIANTS)))
        print('=> test_data_update_btn.py 对本次改动具备真实约束力')
    else:
        print('负向验证失败：存在未被捕获的回退变体，请补齐断言')
    print('=' * 60)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
