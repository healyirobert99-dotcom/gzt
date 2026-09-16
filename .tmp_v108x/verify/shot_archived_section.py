# -*- coding: utf-8 -*-
"""补拍「已归档」区：把一只标的归档后，拍下首页底部的已归档区块。

1000px 宽下整页高度 > 4000px（前一次 03-1.png 因此把已归档区截在画外），
故这次把视口放大到 1000x6000，并用 `get box .archive-section` 拿到精确坐标，
再按坐标裁剪 + 放大，保证交付的图里「已归档」区一定完整且可读。
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'browser_e2e_archive.py')
SHOT_DIR = os.path.join(os.path.expanduser('~'), '.agent-browser', 'tmp',
                        'screenshots')
OUT = r'D:\个股工作台\output\20260916-卡片删除按钮确认'


def load():
    spec = importlib.util.spec_from_file_location('e2e_mod', TARGET)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def box_of(raw, label):
    """抠出某个 `get box` 输出块的坐标：从 label 之后开始找 x/y/width/height。"""
    i = raw.find(label)
    seg = raw[i:] if i >= 0 else raw
    d = {}
    for k in ('x', 'y', 'width', 'height'):
        mm = re.search(r'(?m)^%s:\s*(-?[\d.]+)' % k, seg)
        if mm:
            d[k] = float(mm.group(1))
    return d


def main():
    m = load()
    before = set(os.listdir(SHOT_DIR))
    m.close_all()

    raw = m.batch(
        'set viewport 1000 6000', 'open ' + m.URL, 'wait 9000',
        'hover .terminal-card', 'wait 900',
        'click .card-archive', 'wait 2800',
        'click .mfoot>button.primary', 'wait 4000',
        'get box .archive-section',
        'click .archive-section>details>summary', 'wait 1600',
        'screenshot',
    )
    with open(os.path.join(HERE, 'shot_raw_4.txt'), 'w', encoding='utf-8') as f:
        f.write(raw)

    time.sleep(0.6)
    new = sorted(set(os.listdir(SHOT_DIR)) - before,
                 key=lambda n: os.path.getmtime(os.path.join(SHOT_DIR, n)))
    if not new:
        print('[FAIL] 没拿到新截图'); return 1
    src = os.path.join(SHOT_DIR, new[-1])
    dst = os.path.join(OUT, '04-整页-归档后.png')
    shutil.copy2(src, dst)
    print('  [shot] →', os.path.basename(dst))

    b = box_of(raw, 'x:')
    print('  archive-section box =', b)
    print('  归档态 =', m.archived_rows())
    return 0


if __name__ == '__main__':
    sys.exit(main())
