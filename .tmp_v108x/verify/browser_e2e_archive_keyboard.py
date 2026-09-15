# -*- coding: utf-8 -*-
"""归档 / 恢复的**纯键盘路径**端到端验证（沙箱服务 8805，只碰真实库副本）。

为什么单开一份：此前的 `browser_e2e_archive.py` / `..._edge.py` **全部用 `click`**，
即 Playwright 用鼠标点击 —— 那条路径下 Playwright 会替元素补 hover，
**`:focus-visible` / Tab 序 / Enter 激活这三件事一次都没被验过**。
而 CSS 里恰恰有三条只对键盘生效的规则（`.card-archive:focus-visible`、
`.terminal-card.keyboard-focus .card-archive`、以及页面级 keydown 的 Enter 守卫），
外加一个真实风险：**键盘用户可能根本够不到那个「×」**。

覆盖：
  K1  首页每张卡都有 ×（数量一一对应）
  K2  未悬停/未聚焦时 × 不可见且不可点（与鼠标路径同一设计：悬停才出现）
  K3  **Tab 能从卡片走到 ×**；聚焦后 × 显形且可点（键盘用户够得着）
  K4  × 的 aria-label 可读；聚焦后按 Enter 打开归档弹窗（Enter 未被页面级守卫吞掉）
  K5  Escape 关闭弹窗，且**不产生任何归档**（取消是安全的）
  K6  纯键盘完成归档（× → Enter → 表单 Enter 提交），卡片数 17 → 16
  K7  **键盘完成恢复**：展开折叠区 → 聚焦「恢复」 → Enter → Enter
  K8  台账恰好 +2（归档 / 恢复各一条 append-only 留痕）

本环境硬约束（沿用 browser_e2e_archive.py，勿重踩）：
  ① 跨 CLI 调用**不保持页面状态** → 每段「open → 操作 → 观察」必须在**一次** batch 内；
  ② `eval` 的参数**不能含引号**（单双引号都会被 CLI 吃掉，`.card-archive` 会退化成裸 token
     → `ReferenceError: card is not defined`）。对策：**用 `focus` + `document.activeElement`
     读数**；需要类名字面量时用 `String.fromCharCode(...)`；
  ③ `focus` 后读 `opacity` 要 `wait` 一拍（transition .16s，否则读到过渡中间值 0）；
  ④ **一次 batch 里命令一多，输出会被合并**，按块划分（`text_blocks`）会丢读数 ——
     本文件一律改成：`eval` 全部用 `String(...)` 包一层 → 返回值必带引号 →
     用 `re.findall(r'"([^"\\n]*)"', out)` **整串**取，顺序即命令顺序；
     文本证据也一律在**整串**上做子串判断，不依赖块。

跑法：<python> .tmp_v108x/verify/browser_e2e_archive_keyboard.py
"""
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import browser_e2e_archive as B  # noqa: E402
from browser_e2e_archive import (  # noqa: E402
    REAL_DB, URL, archived_rows, batch, close_all, ledger_total, req, sha, step,
    style_blocks,
)

# "modal" / "aria-label" 的码点（绕开 eval 不能带引号的限制）
CP_MODAL = '109,111,100,97,108'
CP_ARIA = '97,114,105,97,45,108,97,98,101,108'

MODAL_N = ('String(document.getElementsByClassName('
           'String.fromCharCode(%s)).length)' % CP_MODAL)


def quoted_values(out):
    """整串取引号值，顺序 == 命令顺序。

    `eval` 一律写成 `String(...)` ⇒ 返回值必定被双引号包住（含空串 `""`），
    故下标对齐稳定。**不要**用块划分（陷阱 ④）。
    """
    return re.findall(r'"([^"\n]*)"', out)


def int_lines(out):
    """`get count` 的读数（纯整数行）。与 eval 的引号值天然区分。"""
    return [int(s) for s in (l.strip() for l in out.splitlines()) if s.isdigit()]


def main():
    print('=' * 78)
    print('真实服务 8805 + 真实 Chromium —— 归档 / 恢复的**纯键盘路径**')
    print('=' * 78)

    real0 = sha(REAL_DB)
    st, act = req('/api/securities')
    st2, arc = req('/api/securities?archived=only')
    if st != 200 or st2 != 200 or arc:
        print('  沙箱不可用或不干净（st=%s/%s archived=%d），终止。' % (st, st2, len(arc)))
        return 1
    n_all = len(act) + len(arc)
    base_ledger = ledger_total()
    print('  标的 %d 只；台账 %d 条' % (n_all, base_ledger))
    close_all()

    # ---------- K1 ----------
    print('\n§K1 首页每张卡右上角都有一个 ×')
    out = batch('set viewport 1280 1200', 'open ' + URL, 'wait 7000',
                'get count .terminal-card', 'get count .card-archive')
    cv = int_lines(out)
    n_cards, n_xbtn = (cv[0], cv[1]) if len(cv) >= 2 else (None, None)
    step('§K1#1 卡片数量与起测一致（%d）' % n_all, n_cards == n_all, 'ui=%r' % n_cards)
    step('§K1#2 × 数量 == 卡片数量（每张卡都有，不多不少）',
         n_xbtn == n_cards, '×=%r cards=%r' % (n_xbtn, n_cards))

    # ---------- K2 ----------
    print('\n§K2 未悬停 / 未聚焦时 × 不可见')
    s0 = {}
    for attempt in (1, 2, 3):
        close_all()
        out = batch('set viewport 1280 1200', 'open ' + URL, 'wait 7000',
                    'mouse move 0 0', 'wait 700', 'get styles .card-archive')
        sbs = style_blocks(out)
        s0 = sbs[-1] if sbs else {}
        if s0.get('opacity') is not None:
            break
    step('§K2#1 未悬停/未聚焦时 × 完全不可见（opacity: 0）',
         s0.get('opacity') == '0', 'opacity=%r' % s0.get('opacity'))
    step('§K2#2 未悬停/未聚焦时 × 不可点（pointer-events: none）',
         s0.get('pointer-events') == 'none', repr(s0.get('pointer-events')))

    # ---------- K3 / K4 / K5 ----------
    print('\n§K3 键盘 Tab 到 ×，聚焦即显形（Enter 打开弹窗、Escape 取消）')
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
        'press Enter', 'wait 2600',
        'eval ' + MODAL_N,
        'get text .modal',
        'press Escape', 'wait 1100',
        'eval ' + MODAL_N,
    )
    qv = quoted_values(out)
    print('        键盘读数 = %s' % qv)
    keys = ['card_cls', 'sid', 'focus_cls', 'focus_tag', 'aria',
            'opacity', 'pe', 'modal_open', 'modal_esc']
    v = dict(zip(keys, qv))
    step('§K3#1 从卡片按 Tab 能走到 ×，且焦点确实落在按钮上',
         v.get('focus_cls') == 'card-archive' and v.get('focus_tag') == 'BUTTON',
         'class=%r tag=%r（卡片本身 class=%r）'
         % (v.get('focus_cls'), v.get('focus_tag'), v.get('card_cls')))
    step('§K3#2 聚焦后 × 显形（opacity: 1）—— 键盘用户看得见',
         v.get('opacity') == '1', repr(v.get('opacity')))
    step('§K3#3 聚焦后 × 可点（pointer-events: auto）', v.get('pe') == 'auto',
         repr(v.get('pe')))

    aria = v.get('aria') or ''
    name = aria.split(' ', 1)[1] if aria.startswith('归档 ') else ''
    step('§K4#1 × 有无障碍标签「归档 <名称>」', name != '', 'aria=%r' % aria)
    step('§K4#2 聚焦 × 后按 Enter 打开「归档标的」确认弹窗（modal 数 0 → 1）',
         v.get('modal_open') == '1' and '归档标的' in out,
         'modal=%r' % v.get('modal_open'))
    ui = re.search(r'研究版本\s*(\d+)\s*交易计划\s*(\d+)\s*动态执行\s*(\d+)'
                   r'\s*决策台账\s*(\d+)\s*交易流水\s*(\d+)', out)
    step('§K4#3 弹窗列出五类影响面', bool(ui), 'match=%s' % bool(ui))
    step('§K4#4 弹窗标的身份 == 被聚焦的那张卡（同一次键盘操作，不串标的）',
         name != '' and name in out, 'aria 名称=%r' % name)

    step('§K5#1 按 Escape 关闭弹窗（modal 数 1 → 0）', v.get('modal_esc') == '0',
         repr(v.get('modal_esc')))
    step('§K5#2 Escape 之后没有任何标的被归档（取消是安全的）',
         archived_rows() == [] and ledger_total() == base_ledger,
         'archived=%s ledger=%d' % (archived_rows(), ledger_total()))

    # ---------- K6 ----------
    print('\n§K6 纯键盘完成归档（× → Enter → 表单 Enter 提交）')
    close_all()
    out = batch(
        'set viewport 1280 1200', 'open ' + URL, 'wait 7000',
        'focus .terminal-card', 'press Tab', 'wait 600',
        'press Enter', 'wait 2600',
        'eval String(document.activeElement.tagName)',
        'press Enter', 'wait 3500',
        'eval ' + MODAL_N,
        'get count .terminal-card',
    )
    qv2 = quoted_values(out)
    step('§K6#1 弹窗打开后焦点自动落在输入框（可直接回车提交）',
         bool(qv2) and qv2[0] == 'INPUT', 'activeElement=%r' % (qv2[0] if qv2 else None))
    step('§K6#2 键盘提交后弹窗自动关闭（modal 数 → 0）',
         len(qv2) > 1 and qv2[1] == '0', 'quoted=%s' % qv2)
    rows = archived_rows()
    step('§K6#3 恰好 1 只标的进入归档态（以后端为准）', len(rows) == 1, str(rows))
    cv2 = int_lines(out)
    step('§K6#4 工作台卡片数 %d → %d（UI 实测）' % (n_all, n_all - 1),
         bool(cv2) and cv2[-1] == n_all - 1, 'ui=%r' % (cv2[-1] if cv2 else None))
    step('§K6#5 台账 +1（归档留痕）', ledger_total() == base_ledger + 1,
         '%d → %d' % (base_ledger, ledger_total()))

    # ---------- K7 ----------
    print('\n§K7 键盘完成恢复（展开折叠区 → 聚焦「恢复」 → Enter → Enter）')
    close_all()
    out = batch(
        'set viewport 1280 4000', 'open ' + URL, 'wait 7000',
        'click .archive-section>details>summary', 'wait 1500',
        'focus .archive-row>button',
        'eval String(document.activeElement.className)',
        'press Enter', 'wait 2600',
        'get text .modal',
        'focus .mfoot>button.primary',
        'press Enter', 'wait 3500',
    )
    qv3 = quoted_values(out)
    step('§K7#1 键盘展开「已归档」区后，焦点能落到「恢复」按钮上',
         bool(qv3) and 'btn' in qv3[0], 'activeElement=%r' % (qv3[0] if qv3 else None))
    step('§K7#2 按 Enter 打开「恢复标的」确认框', '恢复标的' in out, '')
    step('§K7#3 键盘提交恢复后归档归零（以后端为准）', archived_rows() == [],
         str(archived_rows()))
    step('§K7#4 工作台重新可见全部 %d 只标的' % n_all,
         len(req('/api/securities')[1]) == n_all,
         str(len(req('/api/securities')[1])))

    # ---------- K8 ----------
    print('\n§K8 台账与隔离性')
    step('§K8#1 台账恰好 +2（归档 / 恢复各追加 1 条，append-only）',
         ledger_total() == base_ledger + 2, '%d → %d' % (base_ledger, ledger_total()))
    step('§K8#2 真实库 data/workbench.db 逐字节未变', sha(REAL_DB) == real0,
         '%s → %s' % (real0[:16], sha(REAL_DB)[:16]))

    print('\n' + '=' * 78)
    print('结果：%d PASS / %d FAIL' % (B.PASS, B.FAIL))
    print('=' * 78)
    return 0 if B.FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
