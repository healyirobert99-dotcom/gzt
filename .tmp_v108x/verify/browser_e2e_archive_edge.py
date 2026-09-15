# -*- coding: utf-8 -*-
"""归档功能的**边界检查**（在沙箱服务 8805 上运行，只碰真实库的副本）。

补做「归档按钮」交付后未完成的两条路径，以及由它们衍生的三条不变式：

  E1. 归档到只剩 0 张卡 —— 首页是否仍**完整可用**
      （不抛错、五个分组空态、已归档区正常渲染并列出全部）
  E2. 后退进入被归档标的的 #/s/{id} —— 详情抽屉能否正常打开
      （后端 GET /api/securities/{id} 不按 archived 过滤；抽屉不依赖 S.secs）
  E3. 已归档标的对「默认列表 / 标的库页」彻底不可见（接口与 UI 一致）
  E4. 全归档仍可逆 —— 从「已归档」区点恢复，首页卡片由 0 回到 1，再全量恢复回原值
  E5. 隔离性 —— 全程只操作副本，真实库逐字节未变

跑法：
    1) 后台任务起沙箱服务（真实库副本 + 端口 8805）：
       <python> .tmp_v108x/verify/sandbox_server.py 8805
    2) python .tmp_v108x/verify/browser_e2e_archive_edge.py

本脚本**复用** browser_e2e_archive.py 里已固化的 agent-browser 硬约束实现
（单批次保状态 / 无空格子选择器 / 落盘不接管道 / 超时按进程树杀 / 按内容特征读数），
不再复制粘贴，避免两份漂移。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from browser_e2e_archive import (  # noqa: E402
    BASE, URL, REAL_DB, REAL_PREFIX, SANDBOX_DB,
    batch, close_all, req, sha, archived_rows, sec_row, ledger_total,
    last_text, count_values, text_blocks, text_with,
)

# 读数一律用公共实现（都在 browser_e2e_archive 里，三份脚本共用一份，避免漂移）：
#   count_values(out)     —— 按行取纯整数行；get count 命令须**独占批次**
#   text_with(out, *keys) —— 按关键词取文本块，不依赖块序号

PASS = FAIL = 0


def step(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %s' % name)
    else:
        FAIL += 1
        print('  FAIL  %s   %s' % (name, detail))


def archive_all(ids):
    ok = 0
    for i in ids:
        st, _ = req('/api/securities/%d/archive' % i, 'POST', {})
        ok += (st == 200)
    return ok


def unarchive_all(ids):
    ok = 0
    for i in ids:
        st, _ = req('/api/securities/%d/unarchive' % i, 'POST', {})
        ok += (st == 200)
    return ok


def main():
    print('=' * 78)
    print('真实服务 8805 + 真实 Chromium —— 归档功能**边界检查**')
    print('=' * 78)

    real_hash0 = sha(REAL_DB)
    st, active0 = req('/api/securities')
    st2, only0 = req('/api/securities?archived=only')
    if st != 200 or st2 != 200:
        print('沙箱服务不在线（st=%s/%s）。' % (st, st2))
        return 1
    n_all = len(active0) + len(only0)
    ids = [s['id'] for s in active0]
    base_ledger = ledger_total()
    print('\n真实库 sha256 = %s' % real_hash0)
    print('沙箱库 = %s' % SANDBOX_DB)
    print('标的 %d 只；台账 %d 条' % (n_all, base_ledger))
    step('§E0#1 起测为干净态（无归档标的、全部可见）',
         len(only0) == 0 and len(active0) == n_all,
         'active=%d only=%d' % (len(active0), len(only0)))
    if len(only0) != 0 or not ids:
        print('\n沙箱不干净，终止。')
        return 1

    # ---------- 把全部标的归档（走真实写入口 POST /archive） ----------
    n_ok = archive_all(ids)
    close_all()
    _, active_z = req('/api/securities')
    _, only_z = req('/api/securities?archived=only')
    step('§E0#2 全部 %d 只经真实接口归档成功' % n_all, n_ok == n_all,
         '%d/%d' % (n_ok, n_all))
    step('§E0#3 归档后默认列表为空、归档列表为全部',
         len(active_z) == 0 and len(only_z) == n_all,
         'active=%d only=%d' % (len(active_z), len(only_z)))

    # ---------- §E1 首页在 0 张卡时完整可用 ----------
    print('\n§E1 归档到只剩 0 张卡 —— 首页仍完整可用')
    close_all()
    # (a) 文本证据：一个批次只做 get text，避免与 count 的输出互相污染
    out = batch('set viewport 1280 2000', 'open ' + URL, 'wait 6000',
                'get text #app', 'get text .archive-section')
    app_txt = text_with(out, '暂无')
    arch_txt = text_with(out, '已归档', '个标的')
    # (b) count 证据：**必须独占批次**（见 count_values 注释）
    cv = count_values(batch('set viewport 1280 2000', 'open ' + URL, 'wait 6000',
                            'get count .terminal-card',
                            'get count .card-archive'))
    card_z = cv[0] if len(cv) >= 1 else None
    btn_z = cv[1] if len(cv) >= 2 else None
    # (c) 展开后逐行数
    cv_row = count_values(batch('set viewport 1280 2000', 'open ' + URL, 'wait 6000',
                                'click .archive-section>details>summary',
                                'wait 1200', 'get count .archive-row'))
    row_z = cv_row[-1] if cv_row else None

    step('§E1#1 首页渲染未走进 catch 分支（无「页面加载失败」）',
         bool(app_txt) and '页面加载失败' not in app_txt,
         repr(app_txt[:80]))
    step('§E1#2 五个分组全部落到空态（「暂无…」>= 5 处）',
         app_txt.count('暂无') >= 5, 'count=%d' % app_txt.count('暂无'))
    step('§E1#3 各分组计数归零（「0 个标的」>= 5 处）',
         app_txt.count('0 个标的') >= 5, 'count=%d' % app_txt.count('0 个标的'))
    step('§E1#4 页面上不再有任何标的卡片', card_z == 0, 'card=%r' % card_z)
    step('§E1#5 页面上不再有任何「×」按钮', btn_z == 0, 'btn=%r' % btn_z)
    step('§E1#6 已归档区仍正常渲染', '已归档' in arch_txt and 'ARCHIVED' in arch_txt,
         repr(arch_txt[:60]))
    step('§E1#7 已归档区标出 %d 个标的' % n_all,
         ('%d 个标的' % n_all) in arch_txt, repr(arch_txt[:120]))
    step('§E1#8 已归档区明说历史完整保留、可恢复',
         '历史完整保留' in arch_txt and '可恢复' in arch_txt, '')
    step('§E1#9 展开后逐行列出全部 %d 只被归档标的' % n_all, row_z == n_all,
         'rows=%r expect=%d' % (row_z, n_all))

    # ---------- §E2 后退进入被归档标的的详情页 ----------
    print('\n§E2 后退进入被归档标的 #/s/{id} —— 详情抽屉仍能打开')
    tgt = only_z[0]
    sid, nm, cd = tgt['id'], tgt['name'], tgt['code']
    st_detail, detail = req('/api/securities/%d' % sid)
    close_all()
    # 抽屉是异步渲染（openDetailDrawer 里 await 了接口），wait 放长；文本与 count 分批次
    out = batch('set viewport 1280 1200', 'open %s/#/s/%d' % (BASE, sid),
                'wait 7000', 'get text .detail-drawer')
    drawer_txt = text_with(out, nm)
    cv2 = count_values(batch('set viewport 1280 1200',
                             'open %s/#/s/%d' % (BASE, sid), 'wait 7000',
                             'get count .detail-drawer',
                             'get count .terminal-card'))
    drawer_cnt = cv2[0] if len(cv2) >= 1 else None
    card_cnt2 = cv2[1] if len(cv2) >= 2 else None

    step('§E2#1 后端 GET /api/securities/{id} 对已归档标的不设过滤',
         st_detail == 200 and detail.get('security', {}).get('name') == nm,
         'st=%s name=%s' % (st_detail, detail.get('security', {}).get('name')
                            if isinstance(detail, dict) else detail))
    step('§E2#2 详情抽屉成功打开（.detail-drawer 恰好 1 个）',
         drawer_cnt == 1, 'drawer=%r' % drawer_cnt)
    step('§E2#3 抽屉内容含该标的名称与代码', nm in drawer_txt and cd in drawer_txt,
         repr(drawer_txt[:80]))
    step('§E2#4 抽屉未退化为空壳（仍渲染「更新动态执行」入口）',
         '更新动态执行' in drawer_txt, repr(drawer_txt[-120:]))
    step('§E2#5 详情页背后的首页确实不含该卡片（详情走独立接口）',
         card_cnt2 == 0, 'card=%r' % card_cnt2)

    # ---------- §E3 已归档标的的不可见性 ----------
    print('\n§E3 已归档标的对默认列表 / 标的库页彻底不可见')
    _, active_now = req('/api/securities')
    step('§E3#1 默认接口 /api/securities 不含已归档标的',
         all(s['id'] != sid for s in active_now) and len(active_now) == 0,
         'n=%d' % len(active_now))
    close_all()
    out = batch('set viewport 1280 1200', 'open %s/#/list' % BASE, 'wait 5000',
                'get text #app')
    list_txt = last_text(out)
    step('§E3#2 标的库页计数为 0', '共 0 个标的' in list_txt, repr(list_txt[:60]))
    step('§E3#3 标的库页给出空态指引（前往「导入与更新」）',
         '暂无标的' in list_txt and '导入与更新' in list_txt, repr(list_txt[:120]))

    # ---------- §E4 全归档仍可逆 ----------
    print('\n§E4 全归档仍可逆 —— 从「已归档」区点恢复')
    recovered = False
    out = ''
    for attempt in (1, 2, 3):
        close_all()
        out = batch('set viewport 1280 4000', 'open ' + URL, 'wait 5000',
                    'click .archive-section>details>summary', 'wait 1200',
                    'click .archive-row>button', 'wait 2000',
                    'click .mfoot>button.primary', 'wait 3000',
                    'get count .terminal-card')
        _, act = req('/api/securities')
        if len(act) == 1:
            recovered = True
            print('        （第 %d 次尝试恢复成功）' % attempt)
            break
        print('        （第 %d 次尝试未生效，重试）' % attempt)
    cv3 = count_values(out)
    card_one = cv3[-1] if cv3 else None
    _, act1 = req('/api/securities')
    _, only1 = req('/api/securities?archived=only')
    step('§E4#1 从已归档区点「恢复」确认后默认列表回到 1 只', len(act1) == 1,
         'n=%d' % len(act1))
    step('§E4#2 首页重新渲染出恰好 1 张标的卡', card_one == 1,
         'card=%r' % card_one)
    step('§E4#3 已归档区相应减到 %d 只' % (n_all - 1), len(only1) == n_all - 1,
         'only=%d' % len(only1))

    # 其余用接口恢复（浏览器点击已覆盖真实路径）
    rest = [s['id'] for s in only1]
    n_ok2 = unarchive_all(rest)
    _, act_final = req('/api/securities')
    _, only_final = req('/api/securities?archived=only')
    step('§E4#4 存量全部恢复成功', n_ok2 == len(rest) and len(act_final) == n_all
         and len(only_final) == 0,
         'ok=%d/%d active=%d only=%d' % (n_ok2, len(rest), len(act_final),
                                         len(only_final)))
    step('§E4#5 台账恰为 归档+恢复 各一次 × %d 只（append-only）' % n_all,
         ledger_total() == base_ledger + 2 * n_all,
         '%d → %d（期望 %d）' % (base_ledger, ledger_total(),
                                 base_ledger + 2 * n_all))

    # ---------- §E5 隔离性 ----------
    print('\n§E5 隔离性：全程只操作副本')
    real_hash1 = sha(REAL_DB)
    step('§E5#1 真实库 data/workbench.db 逐字节未变', real_hash1 == real_hash0,
         '%s → %s' % (real_hash0[:16], real_hash1[:16]))
    step('§E5#2 真实库仍等于本次会话开始时的内容',
         real_hash1.startswith(REAL_PREFIX), real_hash1[:16])
    step('§E5#3 沙箱库确已演进（证明操作真的落到副本上）',
         sha(SANDBOX_DB) != real_hash1, sha(SANDBOX_DB)[:16])
    print('        真实库 sha256 = %s' % real_hash1)
    print('        沙箱库 sha256 = %s' % sha(SANDBOX_DB))

    print('\n' + '=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
