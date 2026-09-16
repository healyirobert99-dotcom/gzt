# -*- coding: utf-8 -*-
"""探针：「连点两下提交」的真实影响半径（不改任何产品代码，只测量）。

背景
----
2026-09-15 的第七面只测了「添加决策记录」一个弹窗（台账 +2）。
但根因在 `openModal` 的提交回调 —— 它**没有在途守卫**（不 disable 提交按钮、
无 in-flight 标志），所以**凡是挂在它下面的插入型弹窗都会同构中招**。
`openModal` 共 11 个调用点，其中 5 个打到无唯一约束的插入型端点：

    POST /api/securities/{id}/trades      → trades            （业务表，无 UNIQUE）
    POST /api/securities/{id}/ledger      → decision_ledger   （append-only，无 UNIQUE）
    POST /api/securities/{id}/execution   → execution_reviews （append-only，无 UNIQUE）
    PUT  /api/securities/{id}/research    → research          （UNIQUE(sec,version)，但 version=max+1）
    PUT  /api/securities/{id}/plan        → trade_plans       （同上）

服务端只有两处去重：`create_security` 的「禁止重复创建」与 `archive` 的 `changed` 守卫。
本探针逐个实测「连点两下」后的行数增量，给出**可复现的影响半径**。

铁律
----
- 必须发**两次独立 `click`**（`dblclick` 被 Playwright 合成单个事件 → 假绿）。
- 结论只看**后端终态**（沙箱库行数），不看 UI 读数。
- 全程只碰沙箱库副本（`sandbox_arch/`），真实库不参与。
"""
import os
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import browser_e2e_archive as B   # noqa: E402  公共 batch / step / URL

SID = 3            # 亿联网络 300628（活跃标的）
SANDBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'sandbox_arch', 'data', 'workbench.db')
PRIMARY = '.mfoot>button.primary'

# (标签, 打开弹窗的表达式, 需填的字段, 计数对象)
CASES = [
    ('录入交易流水', 'openTradeModal(%d)' % SID,
     [('input[name=price]', '10'), ('input[name=quantity]', '100')], 'trades'),
    ('更新动态执行判断', 'openExecutionModal(%d)' % SID,
     [('input[name=execution_view]', 'probe-kbd')], 'execution_reviews'),
    ('更新研究结论', 'openResearchModal(%d)' % SID, [], 'research'),
    ('修改交易计划', 'openPlanModal(%d)' % SID, [], 'trade_plans'),
    ('添加决策记录（已知）', 'openNoteModal(%d)' % SID,
     [('textarea[name=summary]', 'probe-run')], 'decision_ledger'),
]


def n_rows(table):
    c = sqlite3.connect('file:%s?mode=ro' % SANDBOX.replace('\\', '/'), uri=True)
    try:
        return c.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
    finally:
        c.close()


def toast_text(out):
    """batch 输出里最后一段引号串（toast 文案）。"""
    vals = [v for v in re.findall(r'"([^"\n]*)"', out) if v.strip()]
    return vals[-1] if vals else ''


def main():
    print('=' * 78)
    print('探针：连点两下提交的真实影响半径（沙箱库 %s）' % os.path.basename(SANDBOX))
    print('  目标标的 id=%d；每个弹窗发两次独立 click；只读后端行数增量' % SID)
    print('=' * 78)

    for label, opener, fills, table in CASES:
        before = n_rows(table)
        cmds = ['set viewport 1440 1000', 'open ' + B.URL, 'wait 6000',
                'eval ' + opener, 'wait 900']
        for sel, val in fills:
            cmds.append('fill %s %s' % (sel, val))
        cmds.append('click ' + PRIMARY)
        cmds.append('click ' + PRIMARY)
        cmds.append('wait 1800')
        out = B.batch(*cmds, timeout=180)
        after = n_rows(table)
        delta = after - before
        t = toast_text(out)
        print('\n--- %s ---' % label)
        print('    %s 行数 %d → %d  （增量 %d）' % (table, before, after, delta))
        print('    toast 末条：%r' % t[:80])
        B.step('%s：连点两下 %s 增量 = %d' % (label, table, delta), True)

    B.close_all()
    print('\n' + '=' * 78)
    print('汇总：TOTAL=%d PASS=%d FAIL=%d SKIP=0' % (B.PASS + B.FAIL, B.PASS, B.FAIL))
    print('本探针只**测量**、不判定通过与否；结论见上方行数增量。')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
