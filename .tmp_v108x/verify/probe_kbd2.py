# -*- coding: utf-8 -*-
"""探针 2：确定 eval 的引号存活情况 + 过渡等待，再写 keyboard E2E。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from browser_e2e_archive import BASE, batch, close_all  # noqa: E402

close_all()
out = batch(
    'set viewport 1280 1200',
    'open %s/#/home' % BASE,
    'wait 6000',
    # A. 纯表达式，无引号
    'eval document.title',
    # B. 单引号
    "eval document.getElementsByClassName('card-archive')[0].className",
    # C. 双引号
    'eval document.getElementsByClassName("card-archive")[0].className',
    # D. 无引号取元素：用 CSS.escape 不行，改用 tagName + 数组
    'eval Array.prototype.filter.call(document.querySelectorAll("*"),function(e){return e.className==="card-archive"})[0].tagName',
    # E. opacity 时机：先取值 -> 聚焦 -> 立刻取值 -> 等 500ms -> 再取值
    'eval getComputedStyle(document.getElementsByClassName("card-archive")[0]).opacity',
    'focus .card-archive',
    'eval getComputedStyle(document.getElementsByClassName("card-archive")[0]).opacity',
    'wait 500',
    'eval getComputedStyle(document.getElementsByClassName("card-archive")[0]).opacity',
    'eval getComputedStyle(document.getElementsByClassName("card-archive")[0]).pointerEvents',
    'eval document.activeElement.className',
)
print('---- 逐块 ----')
for i, b in enumerate([x.strip() for x in out.split('\n\n')]):
    print('[%d] %s' % (i, b[:200].replace('\n', ' | ')))
