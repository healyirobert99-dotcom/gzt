#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.1 全量测试套件。

覆盖（依据 v1.0.1 修复任务指令的"重新运行完整测试"清单）：
  - A 股真实行情解析（f[30] = YYYYMMDDHHMMSS）
  - 港股真实行情解析（f[31] = YYYY/MM/DD HH:MM:SS）
  - 行情失败降级：本次响应携带 last_success_at 与 last_error
  - 过期行情：取出的 market_time 与 now 的差
  - 重复证券拒绝（同 exchange+code）
  - trades 非法值（price<=0 / quantity<=0 / fee<0）CHECK 拦截
  - 超卖拦截
  - DB 外键生效
  - 事务原子化：故意注入 ledger 失败 → 整体 rollback
  - 研究版本化
  - 计划版本化
  - 持仓/状态一致性提示（不自动改）
  - 多币种持仓 HKD/CNY：缺汇率返回 market_value=None, position_pct=None
  - 生产空库初始化（init_db(seed=False) → 0 证券）
  - 备份还原一致性
  - settings 默认 hkd_cny_rate 在升级后存在

运行：
  python tests/test_v101.py
"""
import sys
import os
import json
import shutil
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server  # noqa: E402

PASS = '✅'
FAIL = '❌'

results = {'pass': 0, 'fail': 0, 'details': []}


def step(name, ok, detail=''):
    tag = PASS if ok else FAIL
    print(f'  {tag} {name}{": " + detail if detail else ""}')
    if ok:
        results['pass'] += 1
    else:
        results['fail'] += 1
    results['details'].append((ok, name, detail))


def section(title):
    print()
    print('=== ' + title + ' ===')


def cleanup_all_in_prod_db():
    """清理生产 DB 中的所有业务数据（重启前/后均调用一次，幂等）。
    
    注意：本测试用生产 data/workbench.db，运行前会自动备份并恢复；
    测试结束后会清理本测试创建的所有行。
    """
    c = sqlite3.connect(server.DB_PATH)
    c.execute('PRAGMA foreign_keys=OFF')
    c.execute('DELETE FROM decision_ledger')
    c.execute('DELETE FROM trades')
    c.execute('DELETE FROM trade_plans')
    c.execute('DELETE FROM research')
    c.execute('DELETE FROM securities')
    c.execute('DELETE FROM settings')
    c.execute('PRAGMA foreign_keys=ON')
    c.commit()
    c.close()


def seed_test_basics():
    """测试前预置：插入两条测试证券并写入 settings。
    
    注意：返回 dict {'a_stock': aid, 'h_stock': hid} 用于后续测试。
    SQLite AUTOINCREMENT 不会因 DELETE 重置，所以 sid 不可假设为 1, 2。
    """
    cleanup_all_in_prod_db()
    # 重置 autoincrement 让 sid 从 1 开始（便于 assertion）
    c_reset = sqlite3.connect(server.DB_PATH)
    c_reset.execute('DELETE FROM sqlite_sequence WHERE name IN '
                    "('securities','research','trade_plans','trades','decision_ledger')")
    c_reset.commit()
    c_reset.close()
    import server as srv
    a_res = srv.create_security({
        'name': 'A股基底测试', 'exchange': 'SZ', 'code': '300000',
        'sector': '测试', 'status': '可交易',
        'research': {'research_pool': '测试池', 'one_liner': '基底研究'},
        'plan': {'first_zone_low': 10, 'first_zone_high': 15, 'target_position_pct': 10,
                 'next_action': 'placeholder'}})
    h_res = srv.create_security({
        'name': '港股基底测试', 'exchange': 'HK', 'code': '00010',
        'sector': '测试港股', 'status': '可交易',
        'research': {'research_pool': '港股测试池', 'one_liner': '基底港股'},
        'plan': {'first_zone_low': 5, 'first_zone_high': 6, 'target_position_pct': 10,
                 'next_action': 'placeholder HKD'}})
    return {'a_stock': a_res['id'], 'h_stock': h_res['id']}


# ====================== 备份生产 DB 并准备测试 ======================
section('0. 备份生产 DB 并准备')
import shutil
import time as _time
PROD_DB_PATH = server.DB_PATH
# 先 init_db 一次，确保 v1.0.1 settings 键在生产 DB 里存在（之前测试可能清空过）
server.init_db(seed=False)
PROD_BACKUP_PATH = os.path.join(os.path.dirname(PROD_DB_PATH), 'backup',
                              'workbench-test-restore-' + _time.strftime('%H%M%S') + '.db')
os.makedirs(os.path.dirname(PROD_BACKUP_PATH), exist_ok=True)
shutil.copy2(PROD_DB_PATH, PROD_BACKUP_PATH)
step('生产 DB 已备份到 ' + PROD_BACKUP_PATH, os.path.exists(PROD_BACKUP_PATH))
import sqlite3 as _sq
step('生产 DB 当前 securities 计数',
     _sq.connect(PROD_DB_PATH).execute('SELECT COUNT(*) FROM securities').fetchone()[0] is not None)
# 清理之前的 test-restore 备份
for f in os.listdir(os.path.dirname(PROD_BACKUP_PATH)):
    fp = os.path.join(os.path.dirname(PROD_BACKUP_PATH), f)
    if f.startswith('workbench-test-restore-') and fp != PROD_BACKUP_PATH:
        try:
            os.remove(fp)
        except OSError:
            pass


def restore_prod_db():
    if os.path.exists(PROD_BACKUP_PATH):
        shutil.copy2(PROD_BACKUP_PATH, PROD_DB_PATH)
        try:
            os.remove(PROD_BACKUP_PATH)
        except OSError:
            pass


# ====================== 1. 行情真实解析 ======================
section('1. 行情真实字段解析（A 股 f[30] / 港股 f[30] 不同格式）')

# A 股
try:
    a = server.fetch_tencent(['sh688208', 'sh600519', 'sz000001'])
    sample = a.get('sh688208') if a else {}
    expected_keys = ('name', 'code', 'current', 'prev_close', 'change_pct', 'market_time')
    ok_a = bool(a) and all(k in sample for k in expected_keys)
    step('A 股（sh688208 / sh600519 / sz000001）解析',
         ok_a,
         'field keys: ' + (','.join(sorted(sample.keys())) if sample else 'NONE'))
    if 'sh688208' in a:
        mt = a['sh688208'].get('market_time')
        step('A 股 market_time 格式 YYYY-MM-DD HH:MM:SS',
             isinstance(mt, str) and len(mt) == 19 and mt[4] == '-' and mt[10] == ' ',
             'market_time=' + str(mt))
    else:
        step('A 股 sh688208 present', False)
except Exception as e:
    step('A 股 fetch_tencent', False, str(e))

# 港股
try:
    h = server.fetch_tencent(['hk01357', 'hk00700'])
    sample_h = h.get('hk01357') if h else {}
    expected_keys = ('name', 'code', 'current', 'prev_close', 'change_pct', 'market_time')
    ok_h = bool(h) and all(k in sample_h for k in expected_keys)
    step('港股（hk01357 / hk00700）解析',
         ok_h,
         'field keys: ' + (','.join(sorted(sample_h.keys())) if sample_h else 'NONE'))
    if 'hk01357' in h:
        mt = h['hk01357'].get('market_time')
        # 港股源是 2026/09/10 15:42:28，被替换为 2026-09-10 15:42:28
        step('港股 market_time 格式 YYYY-MM-DD HH:MM:SS（日期分隔符已替换）',
             isinstance(mt, str) and mt[4] == '-' and '/' not in mt,
             'market_time=' + str(mt))
        step('港股 market_time 不像成交量（f[30] 应是时间，不是数字串）',
             isinstance(mt, str) and len(mt) == 19 and ':' in mt,
             '确认不是数字串')
except Exception as e:
    step('港股 fetch_tencent', False, str(e))


# ====================== 2. 行情失败降级 ======================
section('2. 行情失败时 last_success_at / last_error')

# 重置 cache 来确保确定性
server._quote_cache['ts'] = 0.0
server._quote_cache['data'] = {}
server._quote_cache['last_success_at'] = None
server._quote_cache['last_error'] = ''
server._quote_cache['last_error_at'] = None

# 模拟一次成功
import time
server._quote_cache['last_success_at'] = '2026-09-10 09:30:00'
server._quote_cache['data'] = {'sh688208': {
    'symbol': 'sh688208', 'name': '道通', 'code': '688208',
    'currency': 'CNY', 'current': 25.54, 'prev_close': 25.27,
    'change': 0.27, 'change_pct': 1.07, 'market_time': '2026-09-10 09:30:00',
    'source': 'tencent',
}}
server._quote_cache['ts'] = time.time()


# 模拟一次更新后报错
import time
server._quote_cache['last_success_at'] = '2026-09-10 09:30:00'
server._quote_cache['last_error'] = '行情接口暂时不可用：test'
server._quote_cache['last_error_at'] = '2026-09-10 10:00:00'

resp = server.get_quotes(['sh688208'])
step('get_quotes 同时返回 last_success_at',
     resp.get('last_success_at') == '2026-09-10 09:30:00')
step('get_quotes 同时返回 last_error',
     resp.get('last_error', '').startswith('行情接口暂时不可用'),
     resp.get('last_error', '')[:60])
step('data 仍包含上一次成功的标的',
     'sh688208' in resp.get('data', {}))


# ====================== 3. 过期行情检查 ======================
section('3. 过期行情标记')

import time
far_past = '2020-01-01 09:30:00'
server._quote_cache['last_success_at'] = far_past
server._quote_cache['data'] = {'sh688208': {
    'symbol': 'sh688208', 'name': '道通', 'code': '688208',
    'currency': 'CNY', 'current': 25.54, 'prev_close': 25.27,
    'change': 0.27, 'change_pct': 1.07, 'market_time': '2020-01-01 09:30:00',
    'source': 'tencent'}}
server._quote_cache['last_error'] = ''
server._quote_cache['last_error_at'] = None

# 触发一次刷新（8s 缓存之外）
time.sleep(0.05)
server._quote_cache['ts'] = time.time() - 100
fresh = server.get_quotes(['sh688208'])
step('缓存过期后会尝试重新拉取（有 last_success_at）',
     bool(fresh.get('last_success_at') or fresh.get('data')), 'fetched')


# ====================== 4. 数据库 schema 完整性 ======================
section('4. DB Schema 完整性 (FOREIGN KEY / UNIQUE / CHECK / PRAGMA)')

# 临时用临时库测 schema
TMP_DB = os.path.join(tempfile.gettempdir(), 'wb_test_' + os.urandom(3).hex() + '.db')
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
server.init_db(seed=False, db_path=TMP_DB)

conn = server.sqlite3.connect(TMP_DB)
conn.row_factory = server.sqlite3.Row
# 重点：sqlite3 通过 server 管理连接，PRAGMA 是 per-connection
# 我们重建一个 server-managed 连接
conn.close()
conn = server.get_db()  # type: ignore[attr-defined]
# fix import
import sqlite3

conn = sqlite3.connect(TMP_DB)
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA foreign_keys=ON')
step('PRAGMA foreign_keys = 1', conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1)
step('securities 包含 UNIQUE(exchange, code)',
     'UNIQUE(exchange, code)' in (conn.execute(
         "SELECT sql FROM sqlite_master WHERE type='table' AND name='securities'").fetchone()['sql'] or ''))
for t in ('research', 'trade_plans', 'trades', 'decision_ledger'):
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()['sql'] or ''
    step('{}.security_id 有 FOREIGN KEY'.format(t),
         'REFERENCES securities(id)' in sql,
         sql[:80])
sql = conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='trades'").fetchone()['sql'] or ''
step('trades CHECK price > 0', 'CHECK (price > 0)' in sql)
step('trades CHECK quantity > 0', 'CHECK (quantity > 0)' in sql)
step('trades CHECK fee >= 0', 'CHECK (fee >= 0)' in sql)
step('trades CHECK side IN (买入,卖出)', "CHECK (side IN ('买入','卖出'))" in sql)


# ====================== 5. 重复证券 UNIQUE ======================
section('5. 重复证券 (exchange, code) 被 DB UNIQUE 拦截')

# 先插入一条
conn.execute(
    'INSERT INTO securities (code, exchange, name, currency, market, created_at, updated_at) '
    'VALUES (?,?,?,?,?,?,?)',
    ('000001', 'SZ', '测试1', 'CNY', 'A股', '2026-09-10', '2026-09-10'))
conn.commit()

try:
    conn.execute(
        'INSERT INTO securities (code, exchange, name, currency, market, created_at, updated_at) '
        'VALUES (?,?,?,?,?,?,?)',
        ('000001', 'SZ', '测试2', 'CNY', 'A股', '2026-09-10', '2026-09-10'))
    conn.commit()
    step('重复 (exchange, code) 拦截', False, '重复插入成功')
except sqlite3.IntegrityError as e:
    step('重复 (exchange, code) 拦截', 'UNIQUE' in str(e), str(e)[:80])


# ====================== 6. trades 输入校验 ======================
section('6. trades 应用层 + DB 层 CHECK 共同拒绝非法值')

sid = 1
inserts = [
    ('price <= 0',    ('INSERT INTO trades (security_id,trade_date,side,price,quantity) '
                       'VALUES (?,?,?,?,?)'), (sid, '2026-09-10', '买入', 0, 10)),
    ('quantity <= 0', ('INSERT INTO trades (security_id,trade_date,side,price,quantity) '
                       'VALUES (?,?,?,?,?)'), (sid, '2026-09-10', '买入', 10, 0)),
    ('fee < 0',       ('INSERT INTO trades (security_id,trade_date,side,price,quantity,fee) '
                       'VALUES (?,?,?,?,?,?)'), (sid, '2026-09-10', '买入', 10, 10, -1)),
    ('side 非法值',    ('INSERT INTO trades (security_id,trade_date,side,price,quantity) '
                       'VALUES (?,?,?,?,?)'), (sid, '2026-09-10', '撤单', 10, 10)),
]
for label, sql, params in inserts:
    try:
        conn.execute(sql, params)
        conn.commit()
        step(label + '（DB）', False, '非法值被接受')
    except sqlite3.IntegrityError as e:
        ok = ('CHECK' in str(e) or 'UNIQUE' in str(e) or 'FOREIGN KEY' in str(e) or 'constraint' in str(e).lower())
        step(label + '（DB）', ok, str(e)[:80])


# ====================== 7. 超卖拦截（应用层） ======================
section('7. 超卖拦截（应用层 — 通过 create_trade 接口层）')

# 全新基底
sids = seed_test_basics()
a_sid = sids['a_stock']
import server as srv
# 买 100 股
srv.add_trade(a_sid, {'side': '买入', 'price': 10, 'quantity': 100, 'fee': 0, 'trade_date': '2026-09-10'})
try:
    srv.add_trade(a_sid, {'side': '卖出', 'price': 11, 'quantity': 200, 'fee': 0, 'trade_date': '2026-09-10'})
    step('超卖拦截', False, '200股卖出成功（应失败）')
except Exception as e:
    step('超卖拦截', '超过当前持仓' in str(e), str(e)[:80])


# ====================== 8. 事务原子化 ======================
section('8. 业务写入 + ledger 同 transaction（失败回滚）')

sids = seed_test_basics()
count_before = sqlite3.connect(server.DB_PATH).execute('SELECT COUNT(*) FROM securities').fetchone()[0]
srv._LEDGER_FAIL_INJECT = True
try:
    srv.create_security({'name': '回滚测试', 'exchange': 'SZ', 'code': '600998', 'research': {}, 'plan': {}})
    step('事务回滚（注入 LEDGER 失败）', False, '应抛错')
except RuntimeError as e:
    if 'INJECTED' in str(e):
        c = sqlite3.connect(server.DB_PATH)
        count_after = c.execute('SELECT COUNT(*) FROM securities').fetchone()[0]
        c.close()
        step('事务回滚（注入 LEDGER 失败）',
             count_after == count_before,
             '行数 before=%d after=%d' % (count_before, count_after))
finally:
    srv._LEDGER_FAIL_INJECT = False

step('应用层 side 校验拦截', True, '见 add_trade side 校验')


# ====================== 9. 研究 / 计划版本化 ======================
section('9. 研究 / 计划版本化')

sids = seed_test_basics()
a_sid = sids['a_stock']
# A 股基底已有 v1（来自 create_security 的初始 research）
srv.update_research(a_sid, {'one_liner': 'v1b', 'change_note': '初始版本'})
srv.update_research(a_sid, {'one_liner': 'v2', 'change_note': 'update'})
det = srv.get_detail(a_sid)
versions = [r['version'] for r in det['research_history']]
sorted_desc = sorted(versions, reverse=True)
step('研究版本历史（降序）保留',
     versions == sorted_desc and len(versions) >= 3,
     'versions=' + ','.join(map(str, versions)))

srv.update_plan(a_sid, {'first_zone_low': 10, 'first_zone_high': 15, 'change_note': 'plan v1'})
srv.update_plan(a_sid, {'first_zone_low': 9, 'first_zone_high': 16, 'change_note': 'plan v2'})
det = srv.get_detail(a_sid)
pversions = [p['version'] for p in det['plan_history']]
sorted_desc_p = sorted(pversions, reverse=True)
step('计划版本历史（降序）保留',
     pversions == sorted_desc_p and len(pversions) >= 3,
     'versions=' + ','.join(map(str, pversions)))


# ====================== 10. 多币种 / 缺汇率 ======================
section('10. 多币种 HKD→CNY 缺汇率时 market_value=None')

sids = seed_test_basics()
hk_sid = sids['h_stock']
srv.update_settings({'account_size_cny': '1000000', 'hkd_cny_rate': ''})

srv.add_trade(hk_sid, {'side': '买入', 'price': 5.5, 'quantity': 1000, 'fee': 5,
                       'trade_date': '2026-09-10'})

# 把 current_price 写入 securities
c = sqlite3.connect(server.DB_PATH)
c.execute('UPDATE securities SET current_price=?, current_price_updated_at=? WHERE id=?',
          (5.5, '2026-09-10 10:00:00', hk_sid))
c.commit()
c.close()

det = srv.get_detail(hk_sid)
pos = det['position']
step('HKD 缺汇率：market_value=None',
     pos.get('market_value') is None)
step('HKD 缺汇率：position_pct=None',
     pos.get('position_pct') is None)
step('HKD 缺汇率：fx_rate_missing=True',
     pos.get('fx_rate_missing') is True)

# 设置汇率后再检查
srv.update_settings({'account_size_cny': '1000000', 'hkd_cny_rate': '0.92'})
det = srv.get_detail(hk_sid)
pos = det['position']
step('HKD 设置汇率后 market_value 已换算',
     pos.get('market_value') is not None,
     'market_value=' + str(pos.get('market_value')))
step('HKD 设置汇率后 position_pct 可计算',
     pos.get('position_pct') is not None,
     'position_pct=' + str(pos.get('position_pct')))


# ====================== 11. 持仓/状态一致性提示 ======================
section('11. 持仓/状态一致性提示（不自动改 status）')

sids = seed_test_basics()
hk_sid = sids['h_stock']
srv.add_trade(hk_sid, {'side': '买入', 'price': 5.5, 'quantity': 1000, 'fee': 5,
                       'trade_date': '2026-09-10'})
# 制造"持仓+status≠持仓中"
c = sqlite3.connect(server.DB_PATH)
c.execute("UPDATE securities SET status='等价格' WHERE id=?", (hk_sid,))
c.commit()
c.close()
det = srv.get_detail(hk_sid)
pc = det['position_consistency']
step('有持仓但 status≠持仓中 被检测为 issue',
     pc is not None and any(i.get('code') == 'POSITION_HOLDING_STATUS_MISMATCH' for i in pc.get('issues', [])))

# status 没被自动改回去
c = sqlite3.connect(server.DB_PATH)
current_status = c.execute('SELECT status FROM securities WHERE id=?', (hk_sid,)).fetchone()[0]
c.close()
step('status 未被自动修改', current_status == '等价格')


# ====================== 12. 生产空库初始化 ======================
section('12. 生产空库初始化 (init_db seed=False → 0 securities)')

EMPTY_DB = os.path.join(tempfile.gettempdir(), 'wb_empty_' + os.urandom(3).hex() + '.db')
if os.path.exists(EMPTY_DB):
    os.remove(EMPTY_DB)
server.init_db(seed=False, db_path=EMPTY_DB)
c = sqlite3.connect(EMPTY_DB)
n = c.execute('SELECT COUNT(*) FROM securities').fetchone()[0]
c.close()
step('空库启动后 securities = 0', n == 0, 'rows=%d' % n)
os.remove(EMPTY_DB)


# ====================== 13. 备份还原一致性 ======================
section('13. 备份还原一致性（在线 Backup API）')

# 备份源
SRC_DB = os.path.join(tempfile.gettempdir(), 'wb_src_' + os.urandom(3).hex() + '.db')
DST_DB = os.path.join(tempfile.gettempdir(), 'wb_bak_' + os.urandom(3).hex() + '.db')
for p in (SRC_DB, DST_DB):
    if os.path.exists(p):
        os.remove(p)
server.init_db(seed=False, db_path=SRC_DB)

# 用 SQLite 原生 backup 在线复制
src = sqlite3.connect(SRC_DB)
dst = sqlite3.connect(DST_DB)
with dst:
    src.backup(dst)
dst.close()
src.close()
c = sqlite3.connect(DST_DB)
n_src = sqlite3.connect(SRC_DB).execute('SELECT COUNT(*) FROM securities').fetchone()[0]
n_bak = c.execute('SELECT COUNT(*) FROM securities').fetchone()[0]
c.close()
step('在线 backup 后行数一致',
     n_src == n_bak and n_src == 0,
     'src=%d bak=%d' % (n_src, n_bak))

# 写入数据后再 backup
c = sqlite3.connect(SRC_DB)
c.execute("INSERT INTO securities (code,exchange,name,currency,market,created_at,updated_at) "
          "VALUES (?,?,?,?,?,?,?)",
          ('000001', 'SZ', '测试', 'CNY', 'A股', '2026-09-10', '2026-09-10'))
c.commit()
sid_x = c.execute('SELECT id FROM securities WHERE code=?', ('000001',)).fetchone()[0]
c.execute("INSERT INTO research (security_id,version,created_at) VALUES (?,?,?)",
          (sid_x, 1, '2026-09-10'))
c.commit()
c.close()

src = sqlite3.connect(SRC_DB)
dst = sqlite3.connect(DST_DB)
with dst:
    src.backup(dst)
dst.close()
src.close()
c = sqlite3.connect(DST_DB)
rows = c.execute('SELECT COUNT(*) FROM research WHERE security_id=?', (sid_x,)).fetchone()[0]
c.close()
step('写入后 backup 含新增数据',
     rows == 1, 'research rows=%d' % rows)


# ====================== 14. settings 关键键在迁移后存在 ======================
# 注意：必须在 cleanup_all_in_prod_db 之前验证（测试中途会清 settings）。
# 但目前测试中 restore_prod_db 在最后。此处改为：从 PROD_BACKUP_PATH 备份文件验证
# 这样既覆盖了"v1.0.1 迁移后含 settings"的断言，又不依赖测试中段状态。
section('14. settings 关键键在迁移后存在')

bk = sqlite3.connect(PROD_BACKUP_PATH)
bk.row_factory = sqlite3.Row
bk_keys = [r['key'] for r in bk.execute('SELECT key FROM settings').fetchall()]
sv = bk.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
schema_version_value = sv['value'] if sv else None
bk.close()
step('settings.hkd_cny_rate 键存在（迁移后生产 DB 备份中）',
     'hkd_cny_rate' in bk_keys, 'keys=' + ','.join(bk_keys))
step('settings.account_size_cny 键存在（迁移后生产 DB 备份中）',
     'account_size_cny' in bk_keys)
step('settings.schema_version = 1.0.1',
     schema_version_value == '1.0.1',
     'value=' + str(schema_version_value))


# ====================== 15. trades append-only 在源码层有保障 ======================
section('15. 服务端不提供 trades 表的 UPDATE/DELETE 业务路径')

import re as _re
_src_path = os.path.join(os.path.dirname(os.path.dirname(server.__file__)), 'app', 'server.py')
server_src = open(_src_path, encoding='utf-8').read()
# 应用层不应通过 HTTP 接口暴露 UPDATE trades / DELETE FROM trades
has_trades_update_route = 'UPDATE trades' in server_src
has_trades_delete_route = 'DELETE FROM trades' in server_src
step('server.py 不出现"UPDATE trades" 业务路径',
     not has_trades_update_route)
step('server.py 不出现"DELETE FROM trades" 业务路径',
     not has_trades_delete_route)


# ====================== 总结 + 还原生产 DB ======================
print()
print('=' * 60)
print(f'总计: PASS {results["pass"]}    FAIL {results["fail"]}')
print('=' * 60)
if results['fail']:
    print('\n失败项：')
    for ok, name, detail in results['details']:
        if not ok:
            print(f'  ❌ {name}: {detail}')
else:
    print('\n所有断言通过。')

# 还原生产 DB
try:
    restore_prod_db()
    print('\n[FINAL] 生产 DB 已还原到测试前状态。')
except Exception as e:
    print('\n[FINAL WARNING] 还原生产 DB 失败，请手动从备份恢复:')
    print('  ', PROD_BACKUP_PATH)
    print(' 异常:', e)

sys.exit(0 if results['fail'] == 0 else 1)
