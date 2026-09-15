# -*- coding: utf-8 -*-
"""探针：`get count` 的读数行为。

目的：解释边界脚本里 4 条 FAIL —— 到底是产品问题还是**读数问题**。
要回答两件事：
  A) count 为 0（元素不存在）时，输出块长什么样、能否被 ints() 解析？
  B) 同一条命令放在批次**中间** vs **末尾**，输出是否都能被解析？

当前沙箱库 = 已全部恢复（17 张卡）：`.terminal-card` = 17，`.zzz-none-a` = 0。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from browser_e2e_archive import batch, close_all, URL, ints  # noqa: E402

close_all()
out = batch('set viewport 1280 900', 'open ' + URL, 'wait 5000',
            'get count .terminal-card',      # 中间位置，值 17
            'get count .zzz-none-a',         # 中间位置，值 0
            'get text #top-clock',           # 中间位置，短文本（干扰项）
            'get count .terminal-card')      # 末尾位置，值 17

print('===== ints() 解析结果 =====')
print(ints(out))
print('===== 逐块原文 =====')
blocks = out.split('\u2713 Done')
for i, b in enumerate(blocks):
    print('--- block %d (len=%d) ---' % (i, len(b)))
    print(repr(b[:260]))
