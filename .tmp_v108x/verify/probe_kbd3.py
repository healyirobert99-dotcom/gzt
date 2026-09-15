# -*- coding: utf-8 -*-
"""探针 3：用 focus + document.activeElement 实现"无引号 eval"。"""
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
    'get count .card-archive',
    'get count .terminal-card',
    # 聚焦前：用 hover 之外的方式读不到，改由 activeElement 路径统一处理
    'focus .card-archive',
    'eval document.activeElement.className',
    'eval getComputedStyle(document.activeElement).opacity',
    'wait 600',
    'eval getComputedStyle(document.activeElement).opacity',
    'eval getComputedStyle(document.activeElement).pointerEvents',
    # 卡片自身 focus 后 Tab 能否走到 ×
    'focus .terminal-card',
    'eval document.activeElement.className',
    'press Tab',
    'wait 400',
    'eval document.activeElement.className',
    'eval document.activeElement.getAttribute(String.fromCharCode(97,114,105,97,45,108,97,98,101,108))',
    # 键盘 Enter 打开归档弹窗
    'press Enter',
    'wait 2500',
    'get count .modal',
    'get text .modal',
    # Escape 关闭
    'press Escape',
    'wait 800',
    'get count .modal',
)
for i, b in enumerate([x.strip() for x in out.split('\n\n')]):
    print('[%d] %s' % (i, b[:220].replace('\n', ' | ')))
