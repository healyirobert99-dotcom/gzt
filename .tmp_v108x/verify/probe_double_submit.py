# -*- coding: utf-8 -*-
"""只读探针：弹窗「提交按钮连点两下」会发生什么？

背景：`openModal()` 的提交回调**没有任何在途守卫** ——
    $('#mform').addEventListener('submit', async e => {
      e.preventDefault();
      try { await onSubmit(new FormData(e.target), e.target); closeModal(); }
      catch (err) { }
    });
按钮既不 disable，也没有 in-flight 标志。于是「双击提交」会派发**两次**请求。

归档功能**不受影响**：后端 `_set_archived_at` 有幂等守卫（第二次 changed=false），
已由 §C#15 与并发探针锁定。但**其它 append-only 弹窗**（添加决策记录 / 录入交易 /
更新动态执行）没有任何幂等机制 —— 本探针要测出真实后果。

两个被测弹窗（都在沙箱副本上，真实库不碰）：
  ① 添加决策记录 → POST /api/securities/{id}/ledger （append-only）
  ② 归档        → POST /api/securities/{id}/archive（**幂等**，对照组）

跑法：<python> .tmp_v108x/verify/probe_double_submit.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from browser_e2e_archive import URL, batch, close_all, req  # noqa: E402

SANDBOX_DB = os.path.join(HERE, 'sandbox_arch', 'data', 'workbench.db')


def ledger_n(sid):
    c = sqlite3.connect(SANDBOX_DB)
    try:
        return c.execute('SELECT COUNT(*) FROM decision_ledger WHERE security_id=?',
                         (sid,)).fetchone()[0]
    finally:
        c.close()


def main():
    if not os.path.exists(SANDBOX_DB):
        print('沙箱不存在。先起 sandbox_server.py 8805。')
        return 1
    st, secs = req('/api/securities')
    if st != 200 or not secs:
        print('沙箱服务不可用')
        return 1
    sid = secs[-1]['id']
    name = secs[-1]['name']
    print('受测标的 id=%d %s' % (sid, name))

    # ---------- ① 添加决策记录：连点两下提交 ----------
    # 注意：不能用 `dblclick` —— Playwright 会把它合成为**单个** click 事件
    # （实测只派发 1 次提交，台账 +1），测不出"连点两下"的真实情形。
    # 必须发**两次独立的 click**。
    n0 = ledger_n(sid)
    close_all()
    out = batch(
        'set viewport 1280 1400', 'open ' + URL, 'wait 7000',
        'eval openNoteModal(%d)' % sid, 'wait 1600',
        'fill textarea[name=summary] 连点两下探针',
        'wait 500',
        'click .mfoot>button.primary',
        'click .mfoot>button.primary',
        'wait 1100',
        'get text #toast-root',
    )
    n1 = ledger_n(sid)
    print('\n① 添加决策记录（append-only）—— 连点两下提交')
    print('   台账 %d → %d（增量 %d）' % (n0, n1, n1 - n0))
    print('   toast 全文 = %r' % out[-320:])

    # ---------- ② 归档：双击提交（对照组，后端幂等） ----------
    ledger_all0 = None
    c = sqlite3.connect(SANDBOX_DB)
    ledger_all0 = c.execute('SELECT COUNT(*) FROM decision_ledger').fetchone()[0]
    c.close()
    close_all()
    out2 = batch(
        'set viewport 1280 1400', 'open ' + URL, 'wait 7000',
        'eval openArchiveModal(%d)' % sid, 'wait 2000',
        'click .mfoot>button.primary',
        'click .mfoot>button.primary',
        'wait 1100',
        'get text #toast-root',
    )
    c = sqlite3.connect(SANDBOX_DB)
    ledger_all1 = c.execute('SELECT COUNT(*) FROM decision_ledger').fetchone()[0]
    arch = c.execute('SELECT archived_at FROM securities WHERE id=?', (sid,)).fetchone()[0]
    c.close()
    print('\n② 归档（幂等，对照组）—— 连点两下提交')
    print('   台账 %d → %d（增量 %d）' % (ledger_all0, ledger_all1, ledger_all1 - ledger_all0))
    print('   archived_at = %r' % arch)
    print('   toast 全文 = %r' % out2[-320:])
    return 0


if __name__ == '__main__':
    sys.exit(main())
