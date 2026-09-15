#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""股票信息卡右上角「×」→ 标的归档（软删除，可恢复）+ 影响面确认弹窗。

为什么要"归档"而不是 DELETE
----------------------------
research / trade_plans / execution_reviews / decision_ledger / trades 五张子表
**全部**以 `ON DELETE RESTRICT` 引用 securities(id)，且应用开着
PRAGMA foreign_keys=ON；而 decision_ledger 是 append-only、必须保留"当时的判断"。
任何 DELETE 都会永久抹掉历史，与项目铁律冲突。所以"删除按钮"落地为**归档**：
只给 securities.archived_at 打时间戳 —— 标从工作台消失，历史一行不动、随时可恢复。

被测不变式
----------
  §A  归档/恢复语义（离线）：只改 archived_at；四张子表逐表行数 + 内容摘要不变；
      台账只增不改；幂等；恢复是严格逆操作；不污染 STATUSES
  §B  建表与补列：schema_version **不升**（用户选择只改代码），新增列必须靠
      init_db 的幂等补列落地 —— 这是本改动最容易漏的地方（迁移会被整体跳过）
  §C  HTTP 层（真实 ThreadingHTTPServer）：?archived= 白名单、404/400、影响面接口
  §D  前端静态契约：× 在右上角、默认不可见、悬停显形、阻止冒泡、影响面弹窗、
      键盘守卫（Enter 不得吞掉按钮点击）、**归档不得连带丢掉 A/H 关联**（§D#9）、
      **归档是可见性开关而非只读**（§D#10：操作入口不得静默失效）

本文件是功能测试，不写真实 data/workbench.db。
"""

import hashlib
import http.client
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server  # noqa: E402

FAIL = 0
TOTAL = 0
SKIPPED = 0

CHILD_TABLES = ('research', 'trade_plans', 'execution_reviews', 'trades')


def step(name, ok, detail='', skip=False):
    global FAIL, TOTAL, SKIPPED
    if skip:
        SKIPPED += 1
        print('  [SKIP] %s %s' % (name, detail))
        return
    TOTAL += 1
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAIL += 1


def section(title):
    print('\n=== %s ===' % title)


def read_text(rel):
    with open(os.path.join(ROOT, *rel.split('/')), encoding='utf-8') as f:
        return f.read()


# ==================== 隔离环境：临时 DB ====================

TMP_ROOT = tempfile.mkdtemp(prefix='wb_archive_')
TMP_DB = os.path.join(TMP_ROOT, 'workbench.db')
server.init_db(seed=False, db_path=TMP_DB)


def _tmp_db():
    c = sqlite3.connect(TMP_DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
    return c


server.get_db = _tmp_db


def raw(sql, args=()):
    c = sqlite3.connect(TMP_DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def count_of(table, sid=None):
    if sid is None:
        return raw('SELECT COUNT(*) c FROM %s' % table)[0]['c']
    return raw('SELECT COUNT(*) c FROM %s WHERE security_id=?' % table, (sid,))[0]['c']


def digest(table, where='', args=()):
    """整表内容摘要：行序按 id，逐列取值。用于证明"一行都没被改过"。"""
    rows = raw('SELECT * FROM %s %s ORDER BY id' % (table, where), args)
    payload = json.dumps([dict(r) for r in rows], ensure_ascii=False,
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def sec_row(sid):
    rows = raw('SELECT * FROM securities WHERE id=?', (sid,))
    return dict(rows[0]) if rows else None


def make_security(code, name='归档测试标的'):
    return server.create_security({
        'name': name, 'exchange': 'SH', 'code': code, 'sector': '测试',
        'status': '等价格', 'research': {}, 'plan': {},
    })['id']


SID = make_security('600001')

# 造齐五类历史：研究 1 版、计划 1 版、执行 1 条、交易 1 笔、台账 1 条
server.update_research(SID, {'one_liner': '一句话结论', 'core_validations': [],
                             'wall_conditions': [], 'positive_changes': ''})
server.update_plan(SID, {'first_zone_low': 8.0, 'first_zone_high': 9.0,
                         'next_action': '等首仓区', 'change_note': '初始计划'})
server.add_execution_tx(SID, {'execution_view': '等待技术确认',
                              'execution_date': '2026-09-15'})
server.add_trade(SID, {'trade_date': '2026-09-10', 'side': '买入',
                       'price': 8.5, 'quantity': 1000, 'fee': 5})
server.add_note(SID, {'summary': '建仓前记录', 'reason': '等待条件成熟'})


# ==================== §A 归档 / 恢复语义 ====================

def test_a_semantics():
    section('§A 归档 / 恢复语义（离线）')

    before_sec = sec_row(SID)
    before_counts = {t: count_of(t, SID) for t in CHILD_TABLES}
    before_digests = {t: digest(t, 'WHERE security_id=?', (SID,)) for t in CHILD_TABLES}
    ledger_max_id = raw('SELECT MAX(id) m FROM decision_ledger')[0]['m'] or 0
    ledger_prefix = digest('decision_ledger', 'WHERE id<=?', (ledger_max_id,))
    ledger_n0 = count_of('decision_ledger')

    step('§A#0 前置：五类历史齐备（研究/计划/执行/交易/台账各 ≥1 行）',
         all(before_counts[t] >= 1 for t in CHILD_TABLES) and ledger_n0 >= 1,
         'counts=%s ledger=%d' % (before_counts, ledger_n0))

    # A1 未归档时出现在工作台
    active_ids = [s['id'] for s in server.list_securities()]
    step('§A#1 未归档 → 出现在 /api/securities 列表',
         SID in active_ids, 'active=%d 只' % len(active_ids))
    step('§A#1b 未归档 → archived_at 为 NULL',
         before_sec['archived_at'] is None, 'archived_at=%r' % before_sec['archived_at'])

    # A2 影响面
    conn = _tmp_db()
    try:
        im = server.archive_impact(conn, SID)
    finally:
        conn.close()
    step('§A#2 影响面五类计数与直接 COUNT 一致',
         im['research'] == before_counts['research']
         and im['plans'] == before_counts['trade_plans']
         and im['executions'] == before_counts['execution_reviews']
         and im['trades'] == before_counts['trades']
         and im['ledger'] == ledger_n0,
         'impact=%s' % {k: im[k] for k in
                        ('research', 'plans', 'executions', 'ledger', 'trades')})
    step('§A#2b 影响面 total = 五项之和',
         im['total'] == sum(im[k] for k in
                            ('research', 'plans', 'executions', 'ledger', 'trades')),
         'total=%d' % im['total'])
    step('§A#2c 影响面带出身份信息（弹窗标题要用）',
         im['name'] and im['code'] and im['exchange'] and im['is_archived'] is False,
         'name=%s code=%s.%s is_archived=%s'
         % (im['name'], im['code'], im['exchange'], im['is_archived']))

    # A3 归档
    res = server.archive_security(SID, {'reason': '测试归档原因'})
    step('§A#3 归档返回 changed=True', res.get('changed') is True, 'res=%s' % res.get('changed'))

    after_sec = sec_row(SID)
    step('§A#3b 归档后 archived_at 已打时间戳',
         bool(after_sec['archived_at']), 'archived_at=%s' % after_sec['archived_at'])

    # A4 归档即从工作台消失
    active_ids2 = [s['id'] for s in server.list_securities()]
    step('§A#4 归档后不再出现在 /api/securities（工作台消失）',
         SID not in active_ids2, 'active=%d 只' % len(active_ids2))
    archived_ids = [s['id'] for s in server.list_archived_securities()]
    step('§A#4b 归档后出现在 /api/securities/archived（可恢复入口的数据源）',
         SID in archived_ids, 'archived=%d 只' % len(archived_ids))

    # A5 子表行数逐表不变 —— 这是"可恢复"的硬前提
    after_counts = {t: count_of(t, SID) for t in CHILD_TABLES}
    step('§A#5 归档不减少任何子表行数（逐表不变）',
         after_counts == before_counts,
         'before=%s after=%s' % (before_counts, after_counts))

    # A6 子表内容逐行不变（不只是行数）
    after_digests = {t: digest(t, 'WHERE security_id=?', (SID,)) for t in CHILD_TABLES}
    same = [t for t in CHILD_TABLES if after_digests[t] == before_digests[t]]
    step('§A#6 归档不修改任何既有子表行（四表内容摘要全等）',
         len(same) == len(CHILD_TABLES),
         '相同=%s 不同=%s' % (same, [t for t in CHILD_TABLES if t not in same]))

    # A7 台账只增不改
    ledger_n1 = count_of('decision_ledger')
    step('§A#7 归档使 decision_ledger 恰好 +1（留痕，非静默状态变化）',
         ledger_n1 == ledger_n0 + 1, 'ledger %d -> %d' % (ledger_n0, ledger_n1))
    step('§A#7b 既有台账行逐字段未变（append-only 未被破坏）',
         digest('decision_ledger', 'WHERE id<=?', (ledger_max_id,)) == ledger_prefix)
    new_row = raw('SELECT * FROM decision_ledger WHERE id>? ORDER BY id', (ledger_max_id,))
    # 断言取不到行时也必须给出结论，不能直接下标崩溃 ——
    # 测试崩溃会掩盖它后面的所有断言（负向验证 V02 就是这么暴露出来的）。
    step('§A#7c 新增台账 event_type=标的归档 且摘要含名称与代码',
         len(new_row) == 1 and new_row[0]['event_type'] == server.ARCHIVE_EVENT
         and '600001' in new_row[0]['summary'],
         'event_type=%s summary=%s' % (
             new_row[0]['event_type'] if new_row else '(无新增台账行)',
             new_row[0]['summary'] if new_row else '—'))
    step('§A#7d 弹窗里填的原因写入台账 reason',
         bool(new_row) and (new_row[0]['reason'] or '') == '测试归档原因',
         'reason=%r' % (new_row[0]['reason'] if new_row else None))

    # A8 只改两列
    # 注意：now_str() 是秒级精度，同一秒内归档时 updated_at 可能与归档前相同，
    # 故这里断言的是"变化集合 ⊆ {archived_at, updated_at} 且 archived_at 必变"，
    # 而不是"恰好两列都变"——后者会因运行速度产生假红。
    changed = sorted(k for k in before_sec if before_sec[k] != after_sec[k])
    step('§A#8 归档只改 archived_at / updated_at，且 archived_at 必定变化',
         set(changed) <= {'archived_at', 'updated_at'} and 'archived_at' in changed,
         'changed=%s' % changed)
    step('§A#8b 归档不触碰业务字段（name/code/exchange/currency/sector/notes/'
         'ah_link_id/status/research_pool/current_price 全等）',
         all(before_sec[k] == after_sec[k] for k in
             ('name', 'code', 'exchange', 'currency', 'sector', 'notes',
              'ah_link_id', 'status', 'research_pool', 'current_price')),
         '差异=%s' % [k for k in
                     ('name', 'code', 'exchange', 'currency', 'sector', 'notes',
                      'ah_link_id', 'status', 'research_pool', 'current_price')
                     if before_sec[k] != after_sec[k]])

    # A9 归档不是第六种状态
    step('§A#9 归档不改变 status（可见性开关，与交易状态正交）',
         after_sec['status'] == before_sec['status'],
         'status %r -> %r' % (before_sec['status'], after_sec['status']))
    step('§A#9b STATUSES 白名单未被污染（仍 5 项，不含"已归档"）',
         len(server.STATUSES) == 5 and '已归档' not in server.STATUSES,
         'STATUSES=%s' % server.STATUSES)

    # A10 幂等
    res2 = server.archive_security(SID, {'reason': '重复归档'})
    step('§A#10 重复归档 changed=False（幂等，不报错）',
         res2.get('changed') is False, 'changed=%s' % res2.get('changed'))
    step('§A#10b 重复归档不再追写台账',
         count_of('decision_ledger') == ledger_n1,
         'ledger=%d 期望 %d' % (count_of('decision_ledger'), ledger_n1))
    step('§A#10c 重复归档不改动 archived_at（保留首次归档时间）',
         sec_row(SID)['archived_at'] == after_sec['archived_at'],
         'archived_at=%s' % sec_row(SID)['archived_at'])

    # A11 恢复
    res3 = server.unarchive_security(SID, {'reason': '恢复原因'})
    step('§A#11 恢复返回 changed=True', res3.get('changed') is True)
    step('§A#11b 恢复后 archived_at 归 NULL',
         sec_row(SID)['archived_at'] is None, 'archived_at=%r' % sec_row(SID)['archived_at'])
    step('§A#11c 恢复后重新出现在 /api/securities',
         SID in [s['id'] for s in server.list_securities()])
    step('§A#11d 恢复后从 /api/securities/archived 消失',
         SID not in [s['id'] for s in server.list_archived_securities()])
    step('§A#11e 恢复追加 1 条 event_type=标的恢复 的台账',
         count_of('decision_ledger') == ledger_n1 + 1
         and raw('SELECT event_type e FROM decision_ledger ORDER BY id DESC LIMIT 1')[0]['e']
         == server.UNARCHIVE_EVENT,
         'ledger=%d' % count_of('decision_ledger'))

    # A12 恢复幂等
    res4 = server.unarchive_security(SID, {})
    step('§A#12 重复恢复 changed=False（幂等）',
         res4.get('changed') is False, 'changed=%s' % res4.get('changed'))
    step('§A#12b 重复恢复不再追写台账',
         count_of('decision_ledger') == ledger_n1 + 1,
         'ledger=%d' % count_of('decision_ledger'))

    # A13 往返后历史净零变化
    final_counts = {t: count_of(t, SID) for t in CHILD_TABLES}
    final_digests = {t: digest(t, 'WHERE security_id=?', (SID,)) for t in CHILD_TABLES}
    step('§A#13 归档→恢复往返后子表行数与初始完全一致',
         final_counts == before_counts, 'counts=%s' % final_counts)
    step('§A#13b 归档→恢复往返后子表内容与初始完全一致',
         final_digests == before_digests, '四表摘要全等=%s' % (final_digests == before_digests))
    fin_sec = sec_row(SID)
    fin_changed = sorted(k for k in before_sec if before_sec[k] != fin_sec[k])
    step('§A#13c 往返后 securities 除 updated_at 外无任何残留变化',
         set(fin_changed) <= {'updated_at'}, 'changed=%s' % fin_changed)

    # A14 不存在的标的
    try:
        server.archive_security(999999, {})
        step('§A#14 归档不存在的标的 → NotFoundError', False, '未抛异常')
    except server.NotFoundError as e:
        step('§A#14 归档不存在的标的 → NotFoundError', True, str(e))
    except Exception as e:
        step('§A#14 归档不存在的标的 → NotFoundError', False,
             '抛了 %s: %s' % (type(e).__name__, e))

    # A15 list_securities 三种模式
    two = make_security('600002', '归档模式测试')
    server.archive_security(two, {})
    act = {s['id'] for s in server.list_securities()}
    only = {s['id'] for s in server.list_securities(mode='only')}
    allm = {s['id'] for s in server.list_securities(mode='all')}
    step('§A#15 mode=active 不含归档 / mode=only 只含归档 / mode=all 含全部',
         two not in act and two in only and two in allm and SID in act,
         'active=%d only=%d all=%d' % (len(act), len(only), len(allm)))
    step('§A#15b active ∪ only == all（三种模式自洽，不重不漏）',
         act | only == allm and not (act & only),
         'active∩only=%s' % (act & only))
    try:
        server.list_securities(mode='bogus')
        step('§A#15c mode 非法 → ApiError（不静默兜底）', False, '未抛异常')
    except server.ApiError as e:
        step('§A#15c mode 非法 → ApiError（不静默兜底）', True, str(e))

    # A16 归档标的不影响其它未归档标的
    step('§A#16 归档 A 不影响 B 的可见性',
         SID in act and two not in act, 'act=%s' % sorted(act))

    # A17 归档不写 trades / 不动 execution append-only 语义
    step('§A#17 全程未新增任何 trades 行',
         count_of('trades') == 1, 'trades=%d' % count_of('trades'))
    step('§A#17b 全程未新增任何 execution_reviews 行',
         count_of('execution_reviews') == 1,
         'execution_reviews=%d' % count_of('execution_reviews'))


# ==================== §B 建表与幂等补列 ====================

def test_b_schema_and_migration():
    section('§B 建表与幂等补列（schema_version 不升，靠 init_db 补列）')

    # B1 全新空库自带 archived_at
    fresh = os.path.join(TMP_ROOT, 'fresh.db')
    server.init_db(seed=False, db_path=fresh)
    c = sqlite3.connect(fresh)
    cols = [r[1] for r in c.execute('PRAGMA table_info(securities)')]
    c.close()
    step('§B#1 全新空库 securities 自带 archived_at',
         'archived_at' in cols, 'cols=%s' % cols)

    # B2 关键路径：已存在、且 schema_version == TARGET 的库（用户的真实情形）
    #    迁移会被整体跳过，只能靠幂等补列落地
    legacy = os.path.join(TMP_ROOT, 'legacy_samever.db')
    old_schema = server.SCHEMA.replace('  archived_at TEXT,\n', '')
    assert 'archived_at' not in old_schema
    c = sqlite3.connect(legacy)
    c.executescript(old_schema)
    c.execute("INSERT INTO settings (key,value) VALUES ('schema_version', ?)",
              (server.TARGET_SCHEMA_VERSION,))
    c.execute("INSERT INTO securities (code, exchange, name, status) "
              "VALUES ('600900','SH','存量标的一','等价格')")
    c.execute("INSERT INTO securities (code, exchange, name, status) "
              "VALUES ('000001','SZ','存量标的二','持仓中')")
    c.commit()
    before_rows = c.execute('SELECT id, code, name, status FROM securities ORDER BY id').fetchall()
    c.close()

    sv = sqlite3.connect(legacy)
    sv.execute("UPDATE settings SET value=? WHERE key='schema_version'",
               (server.TARGET_SCHEMA_VERSION,))
    sv.commit()
    sv.close()

    server.init_db(seed=False, db_path=legacy)
    c = sqlite3.connect(legacy)
    c.row_factory = sqlite3.Row
    cols2 = [r['name'] for r in c.execute('PRAGMA table_info(securities)')]
    rows2, err2 = [], ''
    try:
        rows2 = c.execute(
            'SELECT id, code, name, status, archived_at FROM securities ORDER BY id').fetchall()
    except sqlite3.OperationalError as e:
        # 补列没生效时这里会 no such column —— 必须被记录成断言失败，
        # 而不是让测试崩掉、掩盖后面的断言。
        err2 = str(e)
    c.close()
    step('§B#2 schema_version 已等于目标（迁移被跳过）时 archived_at 仍被补上',
         'archived_at' in cols2, 'cols=%s' % cols2)
    step('§B#2b 补列后存量行数与内容不变（补列不得吞数据）',
         len(rows2) == 2 and [tuple(r)[:4] for r in rows2] == before_rows,
         'rows=%s err=%s' % ([tuple(r)[:4] for r in rows2], err2 or '无'))
    step('§B#2c 补列后存量行 archived_at 全为 NULL（不猜测历史）',
         bool(rows2) and all(r['archived_at'] is None for r in rows2),
         'rows=%d' % len(rows2))

    # B3 幂等：再跑一次不得报 duplicate column name
    #    另：故意用**没设 row_factory** 的连接跑一遍，验证补列路径不会因为
    #    PRAGMA 行被当 tuple 而抛 TypeError（那等于"启动即失败"）。
    try:
        c = sqlite3.connect(legacy)
        added = server._ensure_security_columns(c)
        c.close()
        step('§B#3 _ensure_security_columns 幂等（第二次 added=[]）',
             added == [], 'added=%s' % added)
    except Exception as e:
        step('§B#3 _ensure_security_columns 幂等（第二次 added=[]）', False,
             '%s: %s' % (type(e).__name__, e))

    try:
        c = sqlite3.connect(legacy)
        c.row_factory = sqlite3.Row
        step('§B#3b 连接设了 row_factory 时同样 no-op',
             server._ensure_security_columns(c) == [])
        c.close()
    except Exception as e:
        step('§B#3b 连接设了 row_factory 时同样 no-op', False,
             '%s: %s' % (type(e).__name__, e))

    # 反向验证兼容分支真的必要：未设 row_factory 的连接若走 r['name'] 会抛 TypeError
    try:
        c = sqlite3.connect(legacy)
        c.execute('PRAGMA table_info(securities)').fetchall()[0]['name']
        step('§B#3c （反向）未设 row_factory 的连接确实不能按列名取值', False,
             '居然没抛异常，兼容分支可能已无必要')
        c.close()
    except TypeError:
        step('§B#3c （反向）未设 row_factory 的连接确实不能按列名取值 —— '
             '证明 §B#3 的兼容分支不是多余的', True)
    except Exception as e:
        step('§B#3c （反向）未设 row_factory 的连接确实不能按列名取值', False,
             '抛了 %s: %s' % (type(e).__name__, e))

    # B4 真跑一次完整迁移（老库无 UNIQUE → 触发 securities 重建路径）
    #    重建路径若漏了 archived_at，数据会在重建时被静默丢弃
    old_v1 = os.path.join(TMP_ROOT, 'legacy_v100.db')
    c = sqlite3.connect(old_v1)
    c.executescript('''
    CREATE TABLE securities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT NOT NULL, exchange TEXT NOT NULL, name TEXT NOT NULL,
      currency TEXT NOT NULL DEFAULT 'CNY', market TEXT NOT NULL DEFAULT 'A股',
      sector TEXT DEFAULT '', ah_link_id INTEGER, notes TEXT DEFAULT '',
      status TEXT NOT NULL DEFAULT '等价格', created_at TEXT, updated_at TEXT
    );
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
    INSERT INTO settings (key, value) VALUES ('schema_version', '1.0.0');
    INSERT INTO securities (code, exchange, name, status)
      VALUES ('600519','SH','老库标的甲','持仓中');
    INSERT INTO securities (code, exchange, name, status)
      VALUES ('000002','SZ','老库标的乙','等价格');
    ''')
    c.commit()
    c.close()
    try:
        server.init_db(seed=False, db_path=old_v1)
        c = sqlite3.connect(old_v1)
        c.row_factory = sqlite3.Row
        cols3 = [r['name'] for r in c.execute('PRAGMA table_info(securities)')]
        rows3 = c.execute('SELECT code, exchange, name, status FROM securities ORDER BY id').fetchall()
        sv3 = c.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        c.close()
        ok = ('archived_at' in cols3 and len(rows3) == 2
              and rows3[0]['name'] == '老库标的甲')
        step('§B#4 老库完整迁移后 archived_at 存在且存量行未丢', ok,
             'cols=%s rows=%s schema_version=%s'
             % (cols3, [tuple(r) for r in rows3], sv3['value'] if sv3 else None))
    except Exception as e:
        step('§B#4 老库完整迁移后 archived_at 存在且存量行未丢', False,
             '%s: %s' % (type(e).__name__, e))

    # B5 期望列清单与 SCHEMA 双源一致性
    expect = dict(server.EXPECTED_SECURITY_COLUMNS)
    step('§B#5 EXPECTED_SECURITY_COLUMNS 含 archived_at',
         expect.get('archived_at') == 'TEXT', 'expect=%s' % expect)
    src = read_text('app/server.py')
    sec_ddl = src.split('CREATE TABLE IF NOT EXISTS securities (', 1)[1].split(');', 1)[0]
    step('§B#5b SCHEMA 的 securities 建表语句确实含 archived_at',
         'archived_at TEXT' in sec_ddl)
    step('§B#5c 重建路径的复制列清单含 archived_at（否则重建丢列）',
         "'archived_at')" in src)

    # B5d 更硬：重建时 securities__new 的建表列 与 INSERT 复制列 必须**完全一致**。
    #     只要有一列只出现在 DDL 而没进复制列，迁移就会把该列的数据静默清空
    #     （SQLite 的 INSERT ... SELECT 不会报错，只是那列变成 DEFAULT）。
    rebuild = src.split('def _create_securities_uniqueness_if_missing', 1)[1]
    ddl = rebuild.split('CREATE TABLE securities__new (', 1)[1].split(")''')", 1)[0]
    ddl_cols = [m.group(1) for m in re.finditer(r'^\s*(\w+)\s+(?:INTEGER|TEXT|REAL)', ddl, re.M)]
    copy_block = rebuild.split('cols = (', 1)[1].split(')', 1)[0]
    copy_cols = [c.strip().strip("'\"") for c in copy_block.replace('\n', '').split(',')]
    copy_cols = [c for c in copy_cols if c]
    step('§B#5d 重建 DDL 列集合 == INSERT 复制列集合（漏一列就静默清空一列）',
         sorted(ddl_cols) == sorted(copy_cols),
         'DDL 独有=%s / 复制列独有=%s'
         % (sorted(set(ddl_cols) - set(copy_cols)),
            sorted(set(copy_cols) - set(ddl_cols))))


# ==================== §C HTTP 层 ====================

def test_c_http():
    section('§C HTTP 层（真实 ThreadingHTTPServer + 临时 DB）')

    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    srv.daemon_threads = True
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def req(method, path, payload=None):
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        hdr = {'Content-Type': 'application/json'} if body else {}
        c.request(method, path, body=body, headers=hdr)
        r = c.getresponse()
        txt = r.read().decode('utf-8')
        c.close()
        try:
            return r.status, json.loads(txt)
        except Exception:
            return r.status, txt

    target = make_security('600003', 'HTTP 测试标的')

    try:
        st, act = req('GET', '/api/securities')
        step('§C#1 GET /api/securities → 200', st == 200, 'status=%d' % st)

        st2, arc = req('GET', '/api/securities?archived=only')
        act_ids = {s['id'] for s in act}
        arc_ids = {s['id'] for s in arc}
        step('§C#1b 默认列表与归档列表严格互斥、并集为全部，且新标的在默认列表',
             st2 == 200 and not (act_ids & arc_ids)
             and arc_ids and target in act_ids,
             'active=%s archived=%s' % (sorted(act_ids), sorted(arc_ids)))
        step('§C#1c 默认列表每行 archived_at 均为空',
             all(not s['archived_at'] for s in act))

        st, im = req('GET', '/api/securities/%d/archive-impact' % target)
        step('§C#2 GET .../archive-impact → 200 且字段齐全',
             st == 200 and all(k in im for k in
                               ('security_id', 'name', 'code', 'exchange', 'status',
                                'archived_at', 'is_archived',
                                'research', 'plans', 'executions', 'ledger',
                                'trades', 'total')),
             'status=%d keys=%s' % (st, sorted(im.keys()) if isinstance(im, dict) else im))
        step('§C#2b is_archived=False（未归档）', im.get('is_archived') is False)

        st, res = req('POST', '/api/securities/%d/archive' % target,
                      {'reason': 'http 测试'})
        step('§C#3 POST .../archive → 200 且 changed=True',
             st == 200 and res.get('changed') is True,
             'status=%d body=%s' % (st, res))
        step('§C#3b archive 响应内嵌 impact（前端无需二次请求即可提示）',
             isinstance(res.get('impact'), dict)
             and res['impact'].get('is_archived') is True)

        st, body = req('GET', '/api/securities')
        step('§C#4 归档后默认列表不再含它',
             all(s['id'] != target for s in body))
        st, body = req('GET', '/api/securities?archived=only')
        step('§C#5 ?archived=only 只含归档标的',
             st == 200 and any(s['id'] == target for s in body)
             and all(s['archived_at'] for s in body),
             'status=%d ids=%s' % (st, [s['id'] for s in body]))
        st, body = req('GET', '/api/securities?archived=all')
        step('§C#6 ?archived=all 含全部',
             st == 200 and any(s['id'] == target for s in body)
             and any(not s['archived_at'] for s in body))
        st, body = req('GET', '/api/securities/archived')
        step('§C#7 GET /api/securities/archived → 已归档列表',
             st == 200 and isinstance(body, list)
             and any(s['id'] == target for s in body),
             'ids=%s' % ([s['id'] for s in body] if isinstance(body, list) else body))

        for raw_v, code in (('bogus', 400), ('2', 400), ('maybe', 400)):
            st, _ = req('GET', '/api/securities?archived=' + raw_v)
            step('§C#8 ?archived=%s → %d（白名单，不静默兜底）' % (raw_v, code),
                 st == code, 'status=%d' % st)
        for raw_v in ('1', 'only', 'true', 'yes'):
            st, _ = req('GET', '/api/securities?archived=' + raw_v)
            step('§C#9 ?archived=%s → 200（等价 only）' % raw_v, st == 200,
                 'status=%d' % st)

        st, res = req('POST', '/api/securities/%d/unarchive' % target, {})
        step('§C#10 POST .../unarchive → 200 且 changed=True',
             st == 200 and res.get('changed') is True, 'status=%d body=%s' % (st, res))
        st, body = req('GET', '/api/securities')
        step('§C#10b 恢复后重回默认列表',
             any(s['id'] == target for s in body))

        st, body = req('POST', '/api/securities/999999/archive', {})
        step('§C#11 归档不存在的标的 → 404',
             st == 404, 'status=%d body=%s' % (st, body))
        st, body = req('POST', '/api/securities/999999/unarchive', {})
        step('§C#12 恢复不存在的标的 → 404', st == 404, 'status=%d' % st)
        st, _ = req('GET', '/api/securities/999999/archive-impact')
        step('§C#13 影响面查不存在的标的 → 404', st == 404, 'status=%d' % st)

        st, _ = req('GET', '/api/securities/%d/archive-impact' % target)
        step('§C#14 影响面接口是只读的（连查两次不改变状态）',
             st == 200 and any(s['id'] == target for s in
                               req('GET', '/api/securities')[1]))
    finally:
        srv.shutdown()
        srv.server_close()


# ==================== §D 前端静态契约 ====================

def test_d_frontend_contract():
    section('§D 前端静态契约')

    js = read_text('app/static/app.js')
    css = read_text('app/static/style.css')
    html = read_text('app/static/index.html')

    # D1 按钮存在于卡片模板
    step('§D#1 uiCardHtml 内渲染 .card-archive 按钮',
         'class="card-archive" data-archive-id="${s.id}"' in js)
    step('§D#1b 按钮用 × 字符作图标',
         re.search(r'openArchiveModal\(\$\{s\.id\}\)">×</button>', js) is not None)
    step('§D#1c 按钮带 title / aria-label（可访问性 + 悬停说明）',
         'title="归档该标的' in js and 'aria-label="归档 ' in js)

    # D2 阻止冒泡：卡片整块是 <a>/onclick 跳详情，不阻止就会"点 × 却跳走"
    m = re.search(r'onclick="([^"]*openArchiveModal\(\$\{s\.id\}\)[^"]*)"', js)
    step('§D#2 × 的 onclick 在 openArchiveModal 之前含 stopPropagation + preventDefault',
         bool(m) and 'stopPropagation' in m.group(1) and 'preventDefault' in m.group(1),
         'onclick=%s' % (m.group(1) if m else None))
    step('§D#2b 卡片本体仍是点击跳详情（未因加按钮而破坏原交互）',
         "onclick=\"location.hash='#/s/${s.id}'\"" in js)

    # D3 右上角定位 + 默认不可见
    step('§D#3 CSS 把 .card-archive 绝对定位在右上角',
         re.search(r'\.card-archive\s*\{[^}]*position:\s*absolute[^}]*top:\s*\d+px[^}]*right:\s*\d+px',
                   css) is not None)
    step('§D#3b 默认 opacity:0 且不可点击（未悬停时不可见）',
         re.search(r'\.card-archive\s*\{[^}]*opacity:\s*0[^}]*pointer-events:\s*none', css)
         is not None)
    step('§D#3c 悬停卡片时显形（opacity:1 + 可点击）—— 用户要求的"悬停后出现"',
         re.search(r'\.terminal-card:hover\s+\.card-archive[^{]*\{[^}]*opacity:\s*1[^}]*pointer-events:\s*auto',
                   css) is not None)
    step('§D#3d 键盘聚焦 / 抽屉选中态也能显形（键盘与触屏用户可达）',
         '.terminal-card.keyboard-focus .card-archive' in css
         and '.terminal-card.selected-card .card-archive' in css)
    step('§D#3e 预留 head 右侧槽位，避免悬停时徽章位移抖动',
         '.terminal-card-head { padding-right: 24px; }' in css)
    step('§D#3f × 的红色只用于破坏性操作，未挪用 --up 表达上涨',
         'border-color: var(--up)' in css and '--up:' in css and '涨 = 红' in css)

    # D4 影响面确认弹窗
    step('§D#4 openArchiveModal 先拉 /archive-impact（影响面来自后端，前端不自己算）',
         "api('/api/securities/' + id + '/archive-impact')" in js)
    step('§D#4b 弹窗列出五类历史计数',
         'ARCHIVE_IMPACT_FIELDS' in js
         and all(k in js for k in ("'研究版本'", "'交易计划'", "'动态执行'",
                                   "'决策台账'", "'交易流水'")))
    step('§D#4c 弹窗明说"记录不会被删除"（避免用户误以为彻底删除）',
         '不会被删除' in js)
    step('§D#4d 持仓中标的额外提示：不改状态、不删持仓记录',
         '不会改变状态' in js and '持仓中' in js)
    step('§D#4e 归档原因可选，写入决策台账',
         'name="reason"' in js and '写入决策台账' in js)
    step('§D#4f 确认按钮文案为「确认归档」而非「保存」',
         "'确认归档'" in js)

    # D5 归档后刷新
    # 注意：这里必须**只取 openArchiveModal 的函数体**再断言。
    # 若写成 re.search(..., js, re.S) 跨全文匹配，.*? 会一路吃到
    # openRestoreModal 里的 `await loadAll(); await render();`，
    # 于是"归档后忘了重绘"这种回退也照样通过 —— 断言恒真，等于没有。
    # （这条恒真断言最初就是这么写出来的，是负向验证 V13 把它揪出来的。）
    arch_body = js.split('async function openArchiveModal', 1)[1] \
                  .split('async function openRestoreModal', 1)[0]
    step('§D#5 归档成功后在该函数体内重新 loadAll + render（卡片立即消失）',
         "/archive'" in arch_body and 'await loadAll();' in arch_body
         and 'await render();' in arch_body,
         'body 长度=%d' % len(arch_body))
    step('§D#5b loadAll 同时拉取已归档列表（S.archived）',
         '/api/securities/archived' in js and 'S.archived = archived' in js)
    step('§D#5c S 初始状态含 archived: []', 'archived: [],' in js)

    # D6 恢复入口
    step('§D#6 首页渲染「已归档」区', '${uiArchivedSection()}' in js)
    step('§D#6b 无归档标的时不渲染该区块（不产生空区块）',
         'if (!list.length) return \'\';' in js)
    step('§D#6c 每行有「恢复」按钮，走 unarchive 接口',
         'openRestoreModal(${s.id})' in js and "/unarchive', { method: 'POST'" in js)
    step('§D#6d 已归档区默认折叠（与候补研究区一致的 details 模式）',
         'ARCHIVED / RESTORE' in js and 'candidate-disclosure' in js)

    # D7 键盘守卫
    step('§D#7 键盘快捷键守卫覆盖 button（否则 Enter 会吞掉 × 的点击）',
         re.search(r"active\.matches\('a\[href\], button,", js) is not None)
    step('§D#7b 守卫变量已改名，无遗留 editing 引用',
         'editing' not in js and 'onControl' in js)

    # D8 不污染既有语义
    step('§D#8 前端 STATUSES 仍 5 项，未新增"已归档"状态',
         "const STATUSES = ['可交易', '等价格', '等证据', '持仓中', '暂不参与'];" in js)
    step('§D#8b 未引入 confirm() 原生弹窗（与工作台弹窗风格统一）',
         'confirm(' not in js)
    step('§D#8c 未新增文件拖拽 / Markdown 解析等被明令不实现的能力',
         'drop(' not in js and 'marked' not in js)

    # D9 归档 × A/H 关联：不得连带把关联丢掉
    # 根因：S.secs 不含已归档标的。若 A/H 下拉只照 S.secs 生成，被归档的关联标的
    # 就不在选项里，浏览器会回落到首项「— 无 —」，用户只改行业/备注再保存
    # 就会把 ah_link_id 静默写成 NULL（实测见 .tmp_v108x/verify/check_ah_link_archive.py，
    # 修正前 11 断言里 4 条红、其中 3 条是决定性证据）。
    m_basic = re.search(r'function openBasicModal\(id\) \{(.*?)\nfunction ', js, re.S)
    basic = m_basic.group(1) if m_basic else ''
    step('§D#9 A/H 下拉的候选项回退到「已归档」列表（不再只有 S.secs）',
         len(basic) > 0 and 'S.archived' in basic and 'ahOptions' in basic,
         'body 长度=%d' % len(basic))
    step('§D#9b 被归档的关联项明确标注「· 已归档」',
         '· 已归档' in basic)
    step('§D#9c 兜底仅在「当前已关联、且该关联不在活跃列表」时生效（不无条件塞入已归档标的）',
         '!others.some(o => o.id === s.ah_link_id)' in basic)
    step('§D#9d 下拉选项统一由 ahOptions 生成',
         "${ahOptions.join('')}" in basic)
    step('§D#9e 标的库的 A/H 关联显示同样回退到已归档列表并标注',
         re.search(r'const o = inActive \|\| \(S\.archived \|\| \[\]\)\.find', js)
         is not None and '（已归档）' in js)

    # D10 归档是**可见性开关**，不是只读开关
    # 根因：findSec 只查 S.secs（活跃列表），而已归档标的的详情页从 #/s/{id} 仍能打开
    #（书签 / 浏览器后退 / 标的库的 A/H 关联链接）→ 抽屉上「更新动态执行 / 录入交易 /
    # 查看研究 / ··· 更多」4 个操作入口全部**点了毫无反应**（静默失效）。
    # 后端没有任何 mutation 端点校验 archived_at，即后端本就允许编辑。
    # 实测：修正前 §E7#1~#3 三条红、对照组 §E7#4（不走 findSec 的「更多操作」）绿。
    m_find = re.search(r'const findSec = ([^;]+);', js, re.S)
    find_body = m_find.group(1) if m_find else ''
    step('§D#10 findSec 同时覆盖活跃与已归档列表（归档 = 可见性开关，非只读）',
         'S.secs.find' in find_body and 'S.archived' in find_body,
         'body=%r' % find_body[:120])
    step('§D#10b findSec 优先活跃列表（同一 id 同时存在时以活跃为准）',
         find_body.find('S.secs.find') < find_body.find('S.archived'),
         'body=%r' % find_body[:120])
    step('§D#10c 各操作入口统一走 findSec，无一处绕过它直接查活跃列表',
         len(re.findall(r'const s = S\.secs\.find', js)) == 0
         and js.count('const s = findSec(id); if (!s) return;') >= 7,
         '直接查活跃列表=%d 处；走 findSec 的入口=%d 个'
         % (len(re.findall(r'const s = S\.secs\.find', js)),
            js.count('const s = findSec(id); if (!s) return;')))


if __name__ == '__main__':
    test_a_semantics()
    test_b_schema_and_migration()
    test_c_http()
    test_d_frontend_contract()
    print('\n' + '=' * 62)
    print('汇总：TOTAL=%d  PASS=%d  FAIL=%d  SKIP=%d'
          % (TOTAL, TOTAL - FAIL, FAIL, SKIPPED))
    print('=' * 62)
    sys.exit(1 if FAIL else 0)
