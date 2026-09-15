# -*- coding: utf-8 -*-
"""A/H 关联 × 归档 的交互边界 —— 归档功能引入的回归验证。

命题：若 A 标的关联 B 标的，B 被归档后，用户在 A 的「编辑基本信息」里
**只改别的字段并保存**，A→B 的关联会不会被**静默清空**？

静态根因（已确认）：
  `openBasicModal` 里 A/H 下拉的候选项来自 `S.secs.filter(x => x.id !== s.id)`，
  而 `S.secs` **不含已归档标的** → 下拉里没有 B → 浏览器默认选中首项「— 无 —」
  → 提交时 `ah_link_id=""` → 后端 `ah in (None,'') → None` 写回 NULL。
  且 toast 只说「基本信息已更新」，用户无从察觉。

本脚本断言的是**期望行为**（关联必须保留、下拉必须仍含被归档的关联项）。
**修正前必须红（证明缺陷真实存在）；修正后必须绿。**

跑法：先起沙箱（8805），再 `python .tmp_v108x/verify/check_ah_link_archive.py`。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from browser_e2e_archive import (  # noqa: E402
    BASE, SANDBOX_DB, REAL_DB, REAL_PREFIX,
    batch, close_all, req, sha, count_values, text_blocks,
)

import sqlite3  # noqa: E402

PASS = FAIL = 0


def step(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %s' % name)
    else:
        FAIL += 1
        print('  FAIL  %s   %s' % (name, detail))


def ah_of(sid):
    c = sqlite3.connect(SANDBOX_DB)
    try:
        r = c.execute('SELECT ah_link_id FROM securities WHERE id=?', (sid,)).fetchone()
        return r[0] if r else 'NO-ROW'
    finally:
        c.close()


def put_sec(sid, body):
    return req('/api/securities/%d' % sid, 'PUT', body)


def modal_open_batch(extra=()):
    """详情抽屉 → ··· 更多 → 编辑基本信息，然后在末尾追加额外读数命令。

    每次调用先 `close_all()` 重开会话：上一批次若把弹窗留在打开状态，
    本批次的 `open` 之后抽屉会被弹窗遮罩挡住，点击链静默落空，
    读 `.modal` 就变成「Element not found」—— 一次纯粹由**测试装置**造成的误报。
    """
    close_all()
    return batch('set viewport 1280 1600',
                 'open %s/#/s/%d' % (BASE, A_ID), 'wait 6500',
                 'click .drawer-actions>button:nth-child(4)', 'wait 1300',
                 'click .more-actions>button:nth-child(3)', 'wait 1300',
                 *extra)


A_ID = B_ID = None
N_ACTIVE = None

print('=' * 78)
print('A/H 关联 × 归档 —— 交互边界验证（沙箱 8805）')
print('=' * 78)

real_hash0 = sha(REAL_DB)
st, secs = req('/api/securities')
st2, arch0 = req('/api/securities?archived=only')
if st != 200 or st2 != 200 or len(secs) < 2 or arch0:
    print('沙箱不干净或标的不足，终止。（active=%s archived=%s）'
          % (len(secs) if st == 200 else '?', len(arch0) if st2 == 200 else '?'))
    sys.exit(1)

N_ACTIVE = len(secs)
A, B = secs[0], secs[1]
A_ID, B_ID = A['id'], B['id']
print('\nA = %s(%s.%s)   B = %s(%s.%s)   活跃标的 %d 只'
      % (A['name'], A['code'], A['exchange'], B['name'], B['code'], B['exchange'], N_ACTIVE))

# ---------- §1 建立 A → B 的 A/H 关联 ----------
st, _ = put_sec(A_ID, {'name': A['name'], 'sector': A.get('sector') or '',
                       'notes': A.get('notes') or '', 'ah_link_id': B_ID})
step('§1#1 通过 PUT 建立 A → B 关联（接口 200）', st == 200, 'st=%s' % st)
step('§1#2 库里 A.ah_link_id == B', ah_of(A_ID) == B_ID,
     'ah=%r expect=%r' % (ah_of(A_ID), B_ID))

# ---------- §2 归档 B ----------
st, _ = req('/api/securities/%d/archive' % B_ID, 'POST', {})
step('§2#1 归档 B 成功（接口 200）', st == 200, 'st=%s' % st)
step('§2#2 归档 B 后 A 的关联在库中仍然保留', ah_of(A_ID) == B_ID,
     'ah=%r' % ah_of(A_ID))
close_all()

# ---------- §3 打开 A 的「编辑基本信息」，A/H 下拉是否仍含被归档的 B ----------
close_all()
# 期望选项数 = 「— 无 —」1 个 + 其余活跃标的 (N_ACTIVE-2) 个 + 被归档的关联项 B 1 个
#   = N_ACTIVE。若为 N_ACTIVE-1，则说明下拉里**没有**已归档的 B（即缺陷态）。
N_OPT = 1 + (N_ACTIVE - 2) + 1
out = modal_open_batch(['get count select[name=ah_link_id]>option'])
cv = count_values(out)
n_opt = cv[-1] if cv else None
step('§3#1 编辑框打开且 A/H 下拉选项数 == %d（含被归档的关联项 B）' % N_OPT,
     n_opt == N_OPT,
     'options=%r expect=%d（若为 %d 则说明下拉里没有已归档的 B）'
     % (n_opt, N_OPT, N_OPT - 1))

out_t = modal_open_batch(['get text .modal'])
modal_txt = '\n'.join(text_blocks(out_t))
step('§3#2 弹窗标题为「编辑基本信息」', '编辑基本信息' in modal_txt,
     repr(modal_txt[:60]))
step('§3#3 下拉文本里能看到 B（或被归档标记）',
     B['name'] in modal_txt or '已归档' in modal_txt,
     repr(modal_txt[:200]))

# ---------- §4 只点「保存」（不改任何字段），关联是否被静默清空 ----------
close_all()
modal_open_batch(['click .mfoot>button.primary', 'wait 3000'])
ah_after = ah_of(A_ID)
step('§4#1 保存后 A.ah_link_id 仍 == B（关联未被静默清空）',
     ah_after == B_ID,
     'ah=%r（被清成空说明缺陷存在：下拉缺项 → 默认「— 无 —」→ 写回 NULL）'
     % (ah_after,))

# ---------- §5 对照：未建立关联的标的，下拉本就不该多出选项 ----------
st, _ = req('/api/securities/%d/unarchive' % B_ID, 'POST', {})
step('§5#1 归档 A/H 关联标的可恢复（不影响关联字段）',
     st == 200 and ah_of(A_ID) == B_ID, 'ah=%r' % ah_of(A_ID))

# ---------- §6 隔离性 ----------
real_hash1 = sha(REAL_DB)
step('§6#1 真实库逐字节未变', real_hash1 == real_hash0,
     '%s → %s' % (real_hash0[:16], real_hash1[:16]))
step('§6#2 真实库仍等于会话开始时的内容',
     real_hash1.startswith(REAL_PREFIX), real_hash1[:16])

print('\n' + '=' * 78)
print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
print('=' * 78)
sys.exit(0 if FAIL == 0 else 1)
