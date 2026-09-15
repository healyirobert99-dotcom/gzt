# -*- coding: utf-8 -*-
"""原样打印 batch C 的输出，确认 Tab 到底落在哪个元素上（不解析、不猜）。"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from browser_e2e_archive import URL, batch, close_all  # noqa: E402

CP_MODAL = '109,111,100,97,108'
CP_ARIA = '97,114,105,97,45,108,97,98,101,108'

close_all()
out = batch(
    'set viewport 1280 4000', 'open ' + URL, 'wait 7000',
    'focus .terminal-card',
    'eval String(document.activeElement.className)',
    'eval String(document.activeElement.dataset.secId)',
    'press Tab', 'wait 600',
    'eval String(document.activeElement.className)',
    'eval String(document.activeElement.tagName)',
    'eval String(document.activeElement.getAttribute(String.fromCharCode(%s)))' % CP_ARIA,
    'wait 800',
    'eval String(getComputedStyle(document.activeElement).opacity)',
    'eval String(getComputedStyle(document.activeElement).pointerEvents)',
    'eval String(document.getElementsByClassName(String.fromCharCode(%s)).length)' % CP_MODAL,
)
print('==== 整串输出 ====')
print(out)
print('==== 引号值（整串正则） ====')
print(re.findall(r'"([^"\n]*)"', out))
