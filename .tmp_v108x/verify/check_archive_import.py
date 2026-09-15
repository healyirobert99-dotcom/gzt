# -*- coding: utf-8 -*-
"""归档 × 导入流程 的交叉核查（「被过滤集合」检查线的第三个同型面）。

背景：2026-09-15 归档功能上线后查明两处真缺陷，都源于「把 S.secs 当全部标的用」。
该检查法要求：凡有一个**被过滤过的集合**，就问三件事 ——
  ① 表单/下拉/多选   → 静默改值（已修：A/H 下拉）
  ② 操作入口的查找   → 静默失效（已修：findSec）
  ③ 展示/统计        → 通常正确（已确认：行情/标的库计数）

本脚本处理**服务端**的同类面：导入流程按 `exchange+code` 匹配标的。
做法：把真实库复制一份到临时目录，monkeypatch server.DB_PATH，**在进程内**直接调用
server.py 的公开函数（不起服务、不碰真实库）。

待证命题（分两类）：
  A. 数据完整性 —— 导入**不得**复活已归档标的、不得清掉 archived_at、不得伪造归档事件。
  B. 交互缺口   —— 预览/报错文案**看不出**标的是"已归档"而非"已删除"。这是缺口，
     按项目约定**只记录、不擅自改**（改文案属于功能改动，需用户批准）。

预期：A 全绿（设计正确）；B 全绿（缺口被如实记录，作为开放项）。
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\个股工作台'
sys.path.insert(0, os.path.join(ROOT, 'app'))

REAL_DB = os.path.join(ROOT, 'data', 'workbench.db')

PASS = 0
FAIL = 0


def step(label, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  [PASS] %s' % label)
    else:
        FAIL += 1
        print('  [FAIL] %s%s' % (label, ('  ← ' + str(detail)) if detail else ''))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def counts(conn, sid):
    t = {}
    for table in ('research', 'trade_plans', 'execution_reviews', 'decision_ledger', 'trades'):
        t[table] = conn.execute(
            'SELECT COUNT(*) c FROM %s WHERE security_id=?' % table, (sid,)).fetchone()[0]
    return t


def main():
    # ---------- 0. 准备隔离沙箱 ----------
    print('=' * 78)
    print('[0] 隔离沙箱（真实库只读复制，绝不改写）')
    print('=' * 78)
    real_sha_before = sha256(REAL_DB)
    box = tempfile.mkdtemp(prefix='arch_import_')
    tmp_db = os.path.join(box, 'workbench.db')
    shutil.copy2(REAL_DB, tmp_db)
    shutil.copy2(REAL_DB + '-wal', tmp_db + '-wal') if os.path.exists(REAL_DB + '-wal') else None

    import server
    server.DB_PATH = tmp_db
    server.DATA_DIR = box
    print('  沙箱 = %s' % box)

    # —— 仓库里的 DB 快照曾经**还没有** archived_at 列（快照早于归档功能）。
    # 这正是"用户拉下仓库直接启动"的路径：必须靠 init_db 里的**无条件幂等补列**
    # 把列加上，而不能指望 schema_version 迁移（用户库版本已等于 TARGET）。
    conn = sqlite3.connect(tmp_db)
    cols_before = [r[1] for r in conn.execute('PRAGMA table_info(securities)')]
    n_before_init = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()[0]
    conn.close()
    # 这条只记录事实、**不作断言**（一旦用户跑过工作台，快照就会带上该列）：
    print('  信息：仓库版 DB 快照 %s archived_at 列'
          % ('已含' if 'archived_at' in cols_before else '尚无（快照早于归档功能）'))
    print('        不论哪种起点，下面的 §0#2 都必须成立 —— 补列靠 init_db 的无条件'
          '幂等 ALTER，而不是靠 schema_version 迁移。')

    migrated = []
    real_do_migration = server.do_migration
    server.do_migration = lambda *a, **k: migrated.append(a)

    server.init_db(seed=False)

    server.do_migration = real_do_migration
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    cols_after = [r[1] for r in conn.execute('PRAGMA table_info(securities)')]
    n_sec_before_total = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c']
    n_archived_before = conn.execute(
        'SELECT COUNT(*) c FROM securities WHERE archived_at IS NOT NULL').fetchone()['c']
    conn.close()
    step('§0#2 init_db 后 archived_at 列已补上（幂等补列，不依赖 schema_version）',
         'archived_at' in cols_after)
    step('§0#3 init_db 期间**未**触发 do_migration（版本已达目标 → 整体跳过）',
         len(migrated) == 0, migrated)
    step('§0#4 补列不丢数据（行数不变）', n_sec_before_total == n_before_init,
         '%d vs %d' % (n_sec_before_total, n_before_init))
    print('  沙箱库：标的 %d 只，其中已归档 %d 只' % (n_sec_before_total, n_archived_before))

    # ---------- 1. 造一只"已归档"标的 ----------
    print()
    print('=' * 78)
    print('[1] 造样本：新建 → 归档（全程只用沙箱库）')
    print('=' * 78)
    EX, CD = 'SZ', '399901'   # 明显虚构的代码，避免与真实标的撞车
    created = server.create_security_tx({
        'name': '核查用虚构标的（归档×导入）',
        'exchange': EX, 'code': CD, 'sector': '核查',
        'status': '等价格',
        'research': {
            'research_pool': '', 'one_liner': '核查用（虚构）',
            'positive_changes': '', 'core_validations': [], 'wall_conditions': [],
            'report_link': '', 'research_date': '2026-09-15', 'change_note': '核查创建',
        },
        'plan': {},
    })
    SID = created['id']
    step('§1#1 样本标的已创建 (id=%d)' % SID, SID > 0)

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    count_pre_archive = counts(conn, SID)
    conn.close()

    ares = server.archive_security(SID, {'reason': '核查：模拟用户归档'})
    step('§1#2 归档成功 changed=True', ares.get('changed') is True, ares)

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM securities WHERE id=?', (SID,)).fetchone()
    arch_at = row['archived_at']
    count_arch_before = counts(conn, SID)
    n_arch_ev_0 = conn.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=? AND event_type='标的归档'",
        (SID,)).fetchone()['c']
    conn.close()
    step('§1#3 归档后 archived_at 非空', bool(arch_at), arch_at)
    step('§1#4 归档后标的仍在库里（是软删除，不是删除）', row is not None)
    step('§1#5 归档后台账恰好追加 1 条（%d → %d）'
         % (count_pre_archive['decision_ledger'], count_arch_before['decision_ledger']),
         count_arch_before['decision_ledger'] == count_pre_archive['decision_ledger'] + 1,
         count_arch_before['decision_ledger'])
    step('§1#6 该条事件类型为「标的归档」', n_arch_ev_0 == 1, n_arch_ev_0)
    step('§1#7 归档不动五张子表的业务行（research/plans/executions/trades 逐表不变）',
         all(count_arch_before[k] == count_pre_archive[k]
             for k in ('research', 'trade_plans', 'execution_reviews', 'trades')),
         {'before': count_pre_archive, 'after': count_arch_before})

    # ---------- 2. 格式 A（导入研究结果）：匹配、预览、提交 ----------
    print()
    print('=' * 78)
    print('[2] 格式 A 全量导入 × 已归档标的')
    print('=' * 78)

    payload = {
        'format': 'ah-workbench-import', 'format_version': '1.0',
        'securities': [{
            'identity': {'exchange': EX, 'code': CD, 'name': '核查用虚构标的（归档×导入）',
                         'sector': '核查'},
            # 与库内 status 一致 → 不需要 confirmed_status_changes
            'status': '等价格',
            'research': {
                'research_pool': '', 'one_liner': '核查用第二版（虚构）',
                'positive_changes': '', 'core_validations': [], 'wall_conditions': [],
                'report_link': '', 'research_date': '2026-09-15', 'change_note': '核查导入第二版',
            },
            'trade_plan': {
                'first_zone_low': 10.0, 'first_zone_high': 11.0,
                'add_zone_low': 9.0, 'add_zone_high': 9.5,
                'odds_zone_low': 8.0, 'odds_zone_high': 8.5,
                'no_chase_price': 12.0, 'target_position_pct': 5.0,
                'next_action': '核查用（虚构）', 'change_note': '核查计划',
            },
            'execution': {
                'execution_date': '2026-09-15', 'price_snapshot': 11.2,
                'support_zone': '10.8-11.0', 'resistance_zone': '11.8-12.0',
                'technical_structure': '核查用（虚构）', 'execution_condition': '核查用（虚构）',
                'execution_view': '等待技术确认', 'reason': '核查用（虚构）',
            },
        }],
    }

    prev = server.preview_import_full(payload)
    sv = prev['securities'][0]
    step('§2#1 已归档标的被识别为「已存在」而非新标的（匹配不按归档过滤 —— 正确：'
         '身份只认 exchange+code）', sv['exists'] is True, sv.get('exists'))
    step('§2#2 预览用的是库里真实的 security_id', sv['security_id'] == SID, sv.get('security_id'))
    step('§2#3 预览正确读到库内当前 status', sv['status_change']['current'] == '等价格',
         sv.get('status_change'))

    # —— 交互缺口（记录，不修）：预览载荷里没有任何"已归档"标识
    pj = json.dumps(prev, ensure_ascii=False)
    step('§2#4 【缺口】预览载荷未提示"该标的已归档，导入后仍隐藏"（无 is_archived / 已归档字样）',
         ('is_archived' not in pj) and ('已归档' not in pj))

    token = prev['token']
    summ = server.commit_import_full(token, [])

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    row_after = conn.execute('SELECT * FROM securities WHERE id=?', (SID,)).fetchone()
    n_sec_after = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c']
    r_ver = conn.execute(
        'SELECT MAX(version) v FROM research WHERE security_id=?', (SID,)).fetchone()['v']
    p_ver = conn.execute(
        'SELECT MAX(version) v FROM trade_plans WHERE security_id=?', (SID,)).fetchone()['v']
    n_arch_ev = conn.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=? AND event_type='标的归档'",
        (SID,)).fetchone()['c']
    n_unarch_ev = conn.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=? AND event_type='标的恢复'",
        (SID,)).fetchone()['c']
    count_after = counts(conn, SID)
    active_ids = [r['id'] for r in conn.execute(
        'SELECT id FROM securities WHERE archived_at IS NULL').fetchall()]
    only_ids = [r['id'] for r in conn.execute(
        'SELECT id FROM securities WHERE archived_at IS NOT NULL').fetchall()]
    conn.close()
    print('  commit 摘要 = %s' % json.dumps(summ, ensure_ascii=False))

    step('§2#5 【关键】导入没有复活归档 —— archived_at 仍非空', bool(row_after['archived_at']),
         row_after['archived_at'])
    step('§2#6 归档时间戳未被改写（仍是归档那一刻）', row_after['archived_at'] == arch_at,
         '%s vs %s' % (row_after['archived_at'], arch_at))
    step('§2#7 导入没有新增 securities 行（走的是 UPDATE 路径）', n_sec_after == n_sec_before_total + 1,
         '%d vs %d' % (n_sec_after, n_sec_before_total + 1))
    step('§2#8 导入确实生效：research 升到 v2', r_ver == 2, r_ver)
    step('§2#9 导入确实生效：trade_plans 升到 v2', p_ver == 2, p_ver)
    step('§2#10 execution 追加 1 行',
         count_after['execution_reviews'] == count_arch_before['execution_reviews'] + 1,
         count_after['execution_reviews'])
    step('§2#11 trades 一行未动（导入路径不触碰 trades）',
         count_after['trades'] == count_arch_before['trades'], count_after['trades'])
    step('§2#12 导入没有伪造「标的归档」事件（仍恰好 1 条）', n_arch_ev == 1, n_arch_ev)
    step('§2#13 导入没有伪造「标的恢复」事件（0 条）', n_unarch_ev == 0, n_unarch_ev)
    step('§2#14 导入后台账只增不减', count_after['decision_ledger'] > count_arch_before['decision_ledger'])
    step('§2#15 归档标的仍不出现在活跃列表（导入后依然隐藏）', SID not in active_ids)
    step('§2#16 归档标的出现在「仅已归档」列表（可恢复）', SID in only_ids)

    # ---------- 3. 归档 vs 漂移检测 ----------
    print()
    print('=' * 78)
    print('[3] 归档会不会被误判成"预览后数据漂移"而阻断导入？')
    print('=' * 78)
    payload2 = json.loads(json.dumps(payload))
    payload2['securities'][0]['research']['one_liner'] = '核查用第三版（虚构）'
    payload2['securities'][0]['research']['change_note'] = '核查导入第三版'
    payload2['securities'][0]['execution']['execution_view'] = '等待技术确认（第三版）'
    prev2 = server.preview_import_full(payload2)
    # 预览之后紧接一次"再归档"（幂等：changed 应为 False，且这不改变任何被导入的字段）
    r2 = server.archive_security(SID, {'reason': '核查：预览后再归档一次'})
    step('§3#1 预览后重复归档是幂等的（changed=False，不重复写台账）', r2.get('changed') is False, r2)
    try:
        s2 = server.commit_import_full(prev2['token'], [])
        drift_blocked = False
    except Exception as e:
        drift_blocked = True
        s2 = str(e)
    step('§3#2 归档状态不参与漂移指纹（status/研究版本/计划版本/执行 id 未变 → 不阻断导入）',
         drift_blocked is False, s2)

    # ---------- 4. 格式 B（导入动态执行） × 已归档标的 ----------
    print()
    print('=' * 78)
    print('[4] 格式 B 执行导入 × 已归档标的')
    print('=' * 78)
    pv_b = server.preview_import_execution({
        'format': 'ah-workbench-execution', 'format_version': '1.0',
        'identity': {'exchange': EX, 'code': CD},
        'execution': {
            'execution_date': '2026-09-15', 'price_snapshot': 11.5,
            'support_zone': '10.9-11.1', 'resistance_zone': '11.9-12.1',
            'technical_structure': '核查用（虚构）', 'execution_condition': '核查用（虚构）',
            'execution_view': '等待技术确认', 'reason': '核查用（虚构）',
        },
    })
    step('§4#1 已归档标的仍能被格式 B 定位（不报"尚未进入工作台"）',
         pv_b['security']['id'] == SID, pv_b.get('security'))
    conn = sqlite3.connect(tmp_db)
    n_exec_before_b = conn.execute(
        'SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?', (SID,)).fetchone()[0]
    conn.close()
    server.commit_import_execution(pv_b['token'])
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    n_exec_after_b = conn.execute(
        'SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?', (SID,)).fetchone()[0]
    a2 = conn.execute('SELECT archived_at FROM securities WHERE id=?', (SID,)).fetchone()['archived_at']
    conn.close()
    step('§4#2 格式 B 追加了 execution 行', n_exec_after_b == n_exec_before_b + 1,
         '%d → %d' % (n_exec_before_b, n_exec_after_b))
    step('§4#3 【关键】格式 B 也没有复活归档', bool(a2), a2)

    # ---------- 5. 重复创建提示（交互缺口，记录不修） ----------
    print()
    print('=' * 78)
    print('[5] 对已归档标的再次「创建」会得到什么提示？')
    print('=' * 78)
    err = ''
    try:
        server.create_security_tx({'name': '核查用（重复）', 'exchange': EX, 'code': CD,
                                   'status': '等价格', 'research': {}, 'plan': {}})
        created_again = True
    except Exception as e:
        created_again = False
        err = str(e)
    print('  文案 = %s' % err)
    step('§5#1 重复创建被拒绝（唯一性约束仍生效 —— 正确）', created_again is False)
    step('§5#2 【缺口】文案只说"禁止重复创建"，未提示"该标的处于已归档状态，'
         '可到首页「已归档」区恢复"', ('归档' not in err) and ('恢复' not in err), err)

    # ---------- 6. 隔离性 & 真实库 ----------
    print()
    print('=' * 78)
    print('[6] 隔离性与真实库')
    print('=' * 78)
    conn = sqlite3.connect(tmp_db)
    n_arch_now = conn.execute(
        'SELECT COUNT(*) c FROM securities WHERE archived_at IS NOT NULL').fetchone()[0]
    n_total_now = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()[0]
    sec_row = conn.execute('SELECT status, name FROM securities WHERE id=?', (SID,)).fetchone()
    conn.close()
    step('§6#1 沙箱内只有 1 只归档标的（本次操作未波及任何其他标的）',
         n_arch_now == n_archived_before + 1, '%d vs %d' % (n_arch_now, n_archived_before + 1))
    step('§6#2 沙箱内标的总数只多了本次新建的 1 只', n_total_now == n_sec_before_total + 1,
         '%d vs %d' % (n_total_now, n_sec_before_total + 1))
    step('§6#3 归档不改变 status（"归档"是可见性，不是第六种交易状态）',
         sec_row[0] == '等价格', sec_row[0])

    real_sha_after = sha256(REAL_DB)
    step('§6#4 真实库 data/workbench.db 全程未被触碰（SHA-256 前后一致）',
         real_sha_before == real_sha_after,
         '%s vs %s' % (real_sha_before[:16], real_sha_after[:16]))

    shutil.rmtree(box, ignore_errors=True)
    step('§6#5 沙箱已清理', not os.path.exists(box))

    print()
    print('=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('真实库 SHA-256 = %s' % real_sha_after)
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
