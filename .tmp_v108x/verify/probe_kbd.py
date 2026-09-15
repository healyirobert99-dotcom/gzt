# -*- coding: utf-8 -*-
"""一次性探针：摸清 agent-browser 的 focus / press / get styles / eval 输出格式。

只读探索，不改数据。结果用于写 keyboard E2E 脚本的读数函数。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from browser_e2e_archive import BASE, batch, close_all, ab_prefix  # noqa: E402

print('BASE =', BASE)
print('ab   =', ab_prefix())

close_all()
out = batch(
    'set viewport 1280 1200',
    'open %s/#/home' % BASE,
    'wait 6000',
    'eval JSON.stringify({o:getComputedStyle(document.querySelector(".card-archive")).opacity,'
    'p:getComputedStyle(document.querySelector(".card-archive")).pointerEvents})',
    'focus .card-archive',
    'eval JSON.stringify({o:getComputedStyle(document.querySelector(".card-archive")).opacity,'
    'p:getComputedStyle(document.querySelector(".card-archive")).pointerEvents,'
    'a:document.activeElement.className})',
    'get styles .card-archive',
    'press Enter',
    'wait 2500',
    'get text .modal',
    'press Escape',
    'wait 800',
    'eval document.querySelector(".modal") === null ? "NO_MODAL" : "MODAL_OPEN"',
)
print('---- 原始输出 ----')
print(repr(out))
print('---- 逐块可读 ----')
blocks = [b.strip() for b in out.split('\n\n')]
for i, b in enumerate(blocks):
    print('[%d] %s' % (i, b[:400]))
