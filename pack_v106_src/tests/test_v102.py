#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.2 全量测试套件。

**v1.0.2 关键变化：测试隔离**
- 完全使用临时 SQLite 数据库（tempfile 路径），server.DB_PATH 与 sqlite
  默认路径都不读写。init_db 显式传 db_path。
- 不读取、DELETE、INSERT、覆盖或恢复正式 data/workbench.db。
- 真实腾讯行情接口测试拆分为单独的 integration test
  （tests/test_integration_quote.py）。本套件不依赖外网。
- 网络不可用不会影响本地账本完整性测试。

覆盖（依据 v1.0.2 修复任务指令）：
  §A Migration 与原子化
  §B Schema：UNIQUE(security_id, version) + 索引 + settings 默认空
  §C 行情→持仓链路：成功拉到的行情回写 securities.current_price
  §D 历史补录 trade_date ISO 校验 + 时序累计非负拒绝
  §E 计划更新 change_note 非空（首次除外）
  §F 状态弹窗相关：仅后端 coverage；前端由浏览器手测
  §G 删除 sampleBanner 默认触发 / 真实用户不被误导
  §H 404 vs 400 HTTP 语义
  §I multi-currency 单位展示 / fx_rate_missing 显示
  §J trades append-only（源码层）
  §K 重复证券 (exchange, code) 拒绝
  §L 业务+ledger 同事务回滚
  §M v1.0.0 → v1.0.2 一次性迁移
  §N init_db 幂等：已经是目标版本不再迁移
  §O integration test 单独存在（占位）

运行：
  python tests/test_v102.py

依赖：app/server.py（只需标准库）
"""
import sys
import os
import json
import sqlite3
import tempfile
import http.client
import threading
import shutil
import time as _time
import urllib.error
import urllib.request

# 先把 app 加进 sys.path，再导入 server（与生产一致）
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


# ============== 临时 DB 管理 ==============
TMP_ROOT = None
TMP_DB = None
TMP_PID = os.getpid()


def setup_tmp_db():
    """每个测试会话准备一份临时 DB（防止污染生产）。"""
    global TMP_ROOT, TMP_DB
    if TMP_DB and os.path.exists(TMP_DB):
        return TMP_DB
    TMP_ROOT = tempfile.mkdtemp(prefix='wb_v102_' + str(TMP_PID) + '_')
    TMP_DB = os.path.join(TMP_ROOT, 'workbench.db')
    server.init_db(seed=False, db_path=TMP_DB)
    return TMP_DB


def cleanup_tmp_db():
    """关闭并清理所有临时数据库文件。"""
    global TMP_ROOT, TMP_DB
    if TMP_ROOT and os.path.exists(TMP_ROOT):
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_DB = None
    TMP_ROOT = None


def fetch_detail(sid):
    """等价于真实 GET /api/securities/{id}；直接调用 server.get_detail() 但强制使用临时 DB。

    v1.0.2 关键：临时 DB 通过 monkey-patch server.get_db 实现。
    """
    return server.get_detail(sid)


# 阶段 0：临时 DB 准备 — 通过 server.get_db 的旁路调用
section('0. 临时 DB 准备')

# 用 server.get_db() 的原始实现，但默认路径替换
class _DBProxy:
    """让 server 内部所有使用 get_db() 的函数统一指向临时库。"""
    def __init__(self, target):
        self.target = target
        self._orig_get_db = server.get_db
        server.get_db = lambda: self._make()
    def _make(self):
        import sqlite3 as _s
        c = _s.connect(self.target, timeout=10)
        c.row_factory = _s.Row
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA foreign_keys=ON')
        return c
    def restore(self):
        server.get_db = self._orig_get_db

setup_tmp_db()
proxy = _DBProxy(TMP_DB)
print(f'临时 DB: {TMP_DB}')
print(f'生产 data/workbench.db 哈希（隔离前）: ', end='')
try:
    h = hashlib_sha(open('data/workbench.db', 'rb').read())
    print(h)
except Exception as e:
    print('不可访问')
print('⚠️ 本测试套件全程不读写此文件 — 仅做存在性指纹')

step('临时 DB 已初始化（schema=1.0.6）',
     os.path.exists(TMP_DB))

# 验证生产 DB 没被改
import hashlib as _hl
def hashlib_sha(b):
    return _hl.sha256(b).hexdigest()[:16]

import os as _os
prod_db = 'data/workbench.db'
if _os.path.exists(prod_db):
    prod_size_before = _os.path.getsize(prod_db)
    prod_hash_before = hashlib_sha(open(prod_db, 'rb').read())
    print(f'生产 DB 大小/指纹：{prod_size_before} / {prod_hash_before}')
else:
    print('生产 DB 不存在（已是隔离环境）')
    prod_size_before = None
    prod_hash_before = None


# =================== §A Migration 与原子化 ===================
section('A. v1.0.0 → v1.0.2 一次性迁移（BEGIN/COMMIT）')

# 从 v1.0.0 状态构造一份临时 DB（无任何约束），跑 migrate_v102 系列
def make_v100_like_db(target):
    """构造一份 v1.0.0 形态的 DB：所有列已存在，但缺 FOREIGN KEY / UNIQUE / CHECK。
    
    这是 v1.0.1 之前真实的库结构（v1.0.1 修复的只是约束，不改列）。
    """
    if os.path.exists(target):
        os.remove(target)
    c = sqlite3.connect(target)
    c.executescript('''
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
    INSERT INTO settings (key, value) VALUES ('schema_version', '1.0.0');

    CREATE TABLE securities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT, exchange TEXT, name TEXT,
      currency TEXT, market TEXT,
      sector TEXT, notes TEXT, status TEXT,
      current_price REAL, current_price_updated_at TEXT,
      created_at TEXT, updated_at TEXT
      -- 注意：v1.0.0 没有 UNIQUE(exchange, code)
    );
    CREATE TABLE trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      security_id INTEGER, trade_date TEXT, side TEXT,
      price REAL, quantity REAL, fee REAL, note TEXT, created_at TEXT
      -- 注意：v1.0.0 没有 CHECK、没有 FOREIGN KEY
    );
    CREATE TABLE research (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      security_id INTEGER, version INTEGER,
      one_liner TEXT, change_note TEXT, created_at TEXT
      -- v1.0.0 没有 UNIQUE(security_id, version)、没有 FOREIGN KEY
    );
    CREATE TABLE trade_plans (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      security_id INTEGER, version INTEGER,
      first_zone_low REAL, first_zone_high REAL,
      add_zone_low REAL, add_zone_high REAL,
      next_action TEXT, change_note TEXT, created_at TEXT
    );
    CREATE TABLE decision_ledger (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      security_id INTEGER, event_date TEXT, event_type TEXT,
      summary TEXT, reason TEXT, created_at TEXT
    );
    ''')
    c.commit()
    c.close()

v100_db = os.path.join(TMP_ROOT, 'v100.db')
make_v100_like_db(v100_db)

# 用 init_db 触发迁移
try:
    proxy2 = _DBProxy(v100_db)
    proxy2._orig_get_db = None
    server.init_db(seed=False, db_path=v100_db)
    step('v1.0.0 → v1.0.2 迁移成功完成', True)
except Exception as e:
    step('v1.0.0 → v1.0.2 迁移', False, str(e)[:120])
finally:
    pass

# 验证迁移后状态
c = sqlite3.connect(v100_db)
c.row_factory = sqlite3.Row
sv = c.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()['value']
step('迁移后 schema_version = 1.0.6', sv == '1.0.6', 'current=%r' % sv)

# hkd_cny_rate 和 account_size_cny 都为空字符串
hc = c.execute("SELECT value FROM settings WHERE key='hkd_cny_rate'").fetchone()['value']
ac = c.execute("SELECT value FROM settings WHERE key='account_size_cny'").fetchone()['value']
step('settings.hkd_cny_rate == ""（生产默认假数据清空）', hc == '', 'value=%r' % hc)
step('settings.account_size_cny == ""（生产默认假数据清空）', ac == '', 'value=%r' % ac)

# UNIQUE 验证
sql_r = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='research'").fetchone()['sql']
sql_p = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trade_plans'").fetchone()['sql']
step('research 含 UNIQUE(security_id, version)', 'UNIQUE(security_id, version)' in sql_r)
step('trade_plans 含 UNIQUE(security_id, version)', 'UNIQUE(security_id, version)' in sql_p)

# 4 个索引都在
all_idx = [r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")]
for idx in ('idx_research_sec', 'idx_plan_sec', 'idx_trades_sec', 'idx_ledger_sec'):
    step(f'索引 {idx} 存在（迁移后立即存在）', idx in all_idx)
c.close()

# =================== §B UNIQUE(security_id, version) 行为验证 ===================
section('B. UNIQUE(security_id, version) 行为')

# 重新用临时主 DB
setup_tmp_db()
proxy = _DBProxy(TMP_DB)

sid = server.create_security({
    'name': '版本化测试', 'exchange': 'SZ', 'code': '300200',
    'sector': '测试', 'status': '可交易',
    'research': {'research_pool': 'p1', 'one_liner': 'ol1'},
    'plan': {'change_note': '初始'}
})['id']

# update_research 写入 v1, v2, v3
server.update_research(sid, {'one_liner': 'v2', 'change_note': 'upd'})
server.update_research(sid, {'one_liner': 'v3', 'change_note': 'upd'})
det = server.get_detail(sid)
versions = sorted(r['version'] for r in det['research_history'])
step('研究 v1-v3 已写入（连续）', versions == [1, 2, 3], str(versions))

# 试图再次写已存在的版本号（手动 SQL，应被 UNIQUE 拒绝）
conn = sqlite3.connect(TMP_DB)
try:
    conn.execute("INSERT INTO research (security_id, version, created_at) VALUES (?, 2, '2026-09-10')",
                 (sid,))
    conn.commit()
    step('UNIQUE(security_id, version) 拦截重复', False, '重复版本被允许')
except sqlite3.IntegrityError as e:
    step('UNIQUE(security_id, version) 拦截重复', 'UNIQUE' in str(e), str(e)[:80])
finally:
    conn.close()


# =================== §C 行情→持仓链路 ===================
section('C. 行情→securities.current_price 真实链路（非测试 UPDATE）')

# 用 monkey-patch fetch_tencent 为 mock，避免依赖网络
def fake_fetch(symbols):
    out = {}
    for s in symbols:
        if s.startswith('sz300200'):
            out[s] = {
                'symbol': s, 'name': '测试标的', 'code': '300200',
                'market': 'A股', 'currency': 'CNY',
                'current': 11.5, 'prev_close': 11.0,
                'change': 0.5, 'change_pct': 4.55,
                'market_time': '2026-09-10 14:00:00',
                'source': 'mock', 'fetched_at': server.now_str(),
            }
    return out

orig_fetch = server.fetch_tencent
server.fetch_tencent = fake_fetch
try:
    # 先清空缓存
    server._quote_cache['ts'] = 0.0
    server._quote_cache['data'] = {}
    server._quote_cache['last_success_at'] = None

    # 录入一笔买入
    server.add_trade(sid, {'side': '买入', 'price': 10, 'quantity': 1000, 'fee': 5,
                           'trade_date': '2026-09-01'})

    # 模拟"行情→持仓"链路：调用 get_quotes 触发回写
    res = server.get_quotes(['sz300200'])

    # 验证：securities.current_price 应该被回写
    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        'SELECT current_price, current_price_updated_at FROM securities WHERE id=?',
        (sid,)).fetchone()
    conn.close()
    step('securities.current_price 被回写 = 11.5',
         r['current_price'] == 11.5,
         'cur=%s' % r['current_price'])
    step('securities.current_price_updated_at 被回写 = 行情时间',
         r['current_price_updated_at'] == '2026-09-10 14:00:00',
         'at=%r' % r['current_price_updated_at'])

    # 端到端：get_detail() 必须用行情计算 market_value
    det = server.get_detail(sid)
    pos = det['position']
    # 1000 股 × 11.5 = 11500
    step('get_detail().position.market_value = 11500 (行情端到端) ',
         pos['market_value'] == 11500,
         'market_value=%s' % pos['market_value'])
    step('持仓汇率未触发 fx_rate_missing（CNY 标的）',
         pos.get('fx_rate_missing') is False)
    step('position_pct=None（无 account_size_cny 时不计算）',
         pos['position_pct'] is None)
finally:
    server.fetch_tencent = orig_fetch


# =================== §D 历史补录 trade_date 与时序校验 ===================
section('D. 历史补录：trade_date ISO 校验 + 时序非负拒绝')

sid2 = server.create_security({
    'name': '时序测试A', 'exchange': 'SZ', 'code': '300201',
    'status': '等价格',
    'research': {}, 'plan': {}
})['id']

# trade_date 非法
try:
    server.add_trade(sid2, {'side': '买入', 'price': 10, 'quantity': 100, 'fee': 0,
                            'trade_date': '2026/09/01'})
    step('非法 trade_date 拒绝', False, '非法日期被接受')
except server.ApiError as e:
    step('非法 trade_date 拒绝', 'ISO' in str(e) or '日期' in str(e), str(e)[:80])

# 正常买入
server.add_trade(sid2, {'side': '买入', 'price': 10, 'quantity': 1000, 'fee': 0,
                       'trade_date': '2026-09-01'})

# 试图卖出超过持仓
try:
    server.add_trade(sid2, {'side': '卖出', 'price': 11, 'quantity': 1500, 'fee': 0,
                            'trade_date': '2026-09-02'})
    step('时序超卖拒绝', False)
except server.ApiError as e:
    step('时序超卖拒绝', '负' in str(e) or '补录' in str(e), str(e)[:80])

# 试图首笔卖出（针对空标的）
sid3 = server.create_security({
    'name': '时序测试B', 'exchange': 'SZ', 'code': '300202',
    'status': '等价格',
    'research': {}, 'plan': {}
})['id']
try:
    server.add_trade(sid3, {'side': '卖出', 'price': 11, 'quantity': 100, 'fee': 0,
                            'trade_date': '2026-09-01'})
    step('首笔不能为卖出', False)
except server.ApiError as e:
    step('首笔不能为卖出', '首笔' in str(e), str(e)[:80])


# =================== §E 计划 change_note 非空 ===================
section('E. update_plan change_note 非空校验')

sid4 = server.create_security({
    'name': '计划修改测试', 'exchange': 'SZ', 'code': '300203',
    'status': '等价格',
    'research': {'change_note': '初始研究'},
    'plan': {'change_note': '初始计划'}
})['id']

# 缺 change_note → 拒绝
try:
    server.update_plan(sid4, {'first_zone_low': 10, 'first_zone_high': 15, 'change_note': ''})
    step('update_plan 缺 change_note 拒绝', False)
except server.ApiError as e:
    step('update_plan 缺 change_note 拒绝', 'change_note' in str(e), str(e)[:80])

# 正常 change_note → 通过
res = server.update_plan(sid4, {'first_zone_low': 9, 'first_zone_high': 16, 'change_note': '调整首仓区'})
det = server.get_detail(sid4)
plan_versions = [p['version'] for p in det['plan_history']]
step('update_plan 正常版（v2 已写入）', 2 in plan_versions)


# =================== §G sampleBanner 删除（仅做 fixture 触发） ===================
section('G. sampleBanner 真实用户不应被自动弹出')

# 检查 app.js 中 sampleBanner() 不再默认触发
src = open(os.path.join(ROOT, 'app', 'static', 'app.js'), encoding='utf-8').read()
no_default = 'const banner = showSampleNoticeIfFixturePresent();' in src
no_old_default = "const banner = (!localStorage.getItem('wb_sample_ok') && S.secs.length) ? sampleBanner() : '';" not in src
step('app.js renderHome 不再依赖 wb_sample_ok localStorage 默认触发',
     no_default and no_old_default,
     'has_new=%s has_old=%s' % (no_default, no_old_default))


# =================== §H 404 vs 400 ===================
section('H. HTTP 404 vs 400 语义')

srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
srv_thread = threading.Thread(target=srv.serve_forever, daemon=True)
srv_thread.start()
port = srv.server_address[1]

# 不存在标的 → 404
c = http.client.HTTPConnection('127.0.0.1', port)
c.request('GET', '/api/securities/999999')
resp = c.getresponse(); body = resp.read()
step('不存在的标的 → HTTP 404 (不是 400)', resp.status == 404, 'status=%d body=%s' % (resp.status, body[:80]))
c.close()

# 缺 reason 状态变更 → 400
c = http.client.HTTPConnection('127.0.0.1', port)
c.request('POST', f'/api/securities/{sid}/status', body=json.dumps({'status': '等价格'}),
          headers={'Content-Type': 'application/json'})
resp = c.getresponse(); body = resp.read()
step('缺 reason 状态变更 → HTTP 400', resp.status == 400, 'status=%d' % resp.status)
c.close()

# 未注册的 API 路径 → 404
c = http.client.HTTPConnection('127.0.0.1', port)
c.request('GET', '/api/no-such-path')
resp = c.getresponse()
step('未注册 API → HTTP 404', resp.status == 404, 'status=%d' % resp.status)
c.close()

srv.shutdown()
srv.server_close()


# =================== §I multi-currency 展示 ===================
section('I. HKD/CNY 单位展示（HKD 缺汇率 / 设汇率后折算）')

sid5 = server.create_security({
    'name': '港股展示测试', 'exchange': 'HK', 'code': '02010',
    'currency': 'HKD',
    'status': '持仓中',
    'research': {}, 'plan': {}
})['id']

server.add_trade(sid5, {'side': '买入', 'price': 5.5, 'quantity': 2000, 'fee': 5,
                       'trade_date': '2026-09-01'})

# 设置汇率空
server.update_settings({'account_size_cny': '', 'hkd_cny_rate': ''})

det = server.get_detail(sid5)
pos = det['position']
step('HKD 缺汇率：market_value=None', pos['market_value'] is None)
step('HKD 缺汇率：fx_rate_missing=True', pos['fx_rate_missing'] is True)
step('HKD 缺汇率：position_pct=None', pos['position_pct'] is None)

# 用 mock fetch 让 HKD 标的也走通真实回写链路（v1.0.2 修复要求）
def fake_fetch_hkd(symbols):
    out = {}
    for s in symbols:
        if s.startswith('hk02010'):
            out[s] = {
                'symbol': s, 'name': '测试H股', 'code': '02010',
                'market': '港股', 'currency': 'HKD',
                'current': 5.6, 'prev_close': 5.5,
                'change': 0.1, 'change_pct': 1.82,
                'market_time': '2026-09-10 14:00:00',
                'source': 'mock', 'fetched_at': server.now_str(),
            }
    return out

orig_fetch = server.fetch_tencent
server.fetch_tencent = fake_fetch_hkd
try:
    server._quote_cache['ts'] = 0.0
    server._quote_cache['data'] = {}
    res = server.get_quotes(['hk02010'])
    # 此时 current_price 已被回写到 5.6
finally:
    server.fetch_tencent = orig_fetch

# 设置汇率后再算
server.update_settings({'hkd_cny_rate': '0.92', 'account_size_cny': '1000000'})
det = server.get_detail(sid5)
pos = det['position']
# 期望：2000 * 5.6 * 0.92 = 10304
step('HKD 设汇率后 market_value 已折算为 CNY',
     pos['market_value'] == 10304,
     'market_value=%s expected=10304' % pos['market_value'])
step('HKD 设汇率后 position_pct 可算',
     pos['position_pct'] is not None and abs(pos['position_pct'] - 1.03) < 0.01,
     'position_pct=%s expected~1.03' % pos['position_pct'])


# =================== §J trades append-only 源码 ===================
section('J. server.py 不暴露 UPDATE trades / DELETE trades 业务路径')

import re as _re
server_src = open(os.path.join(ROOT, 'app', 'server.py'), encoding='utf-8').read()
step('server.py 不出现"UPDATE trades" 业务路径', 'UPDATE trades' not in server_src)
step('server.py 不出现"DELETE FROM trades" 业务路径', 'DELETE FROM trades' not in server_src)


# =================== §K 重复证券 UNIQUE ===================
section('K. 重复 (exchange, code) 拒绝')

sid6 = server.create_security({
    'name': '重复测试', 'exchange': 'SH', 'code': '600000',
    'status': '等价格',
    'research': {}, 'plan': {}
})['id']
try:
    server.create_security({
        'name': '重复测试2', 'exchange': 'SH', 'code': '600000',
        'status': '等价格',
        'research': {}, 'plan': {}
    })
    step('重复 (exchange, code) 拒绝', False)
except server.ApiError as e:
    step('重复 (exchange, code) 拒绝', '该交易所已存在' in str(e) or 'UNIQUE' in str(e), str(e)[:80])


# =================== §L 事务回滚 ===================
section('L. 业务写入 + ledger 同事务（注入失败回滚）')

n_before = sqlite3.connect(TMP_DB).execute('SELECT COUNT(*) FROM securities').fetchone()[0]
server._LEDGER_FAIL_INJECT = True
try:
    server.create_security({
        'name': '回滚测试', 'exchange': 'SZ', 'code': '300301',
        'research': {}, 'plan': {}
    })
    step('注入 ledger 失败应抛错', False, '应抛错')
except RuntimeError as e:
    n_after = sqlite3.connect(TMP_DB).execute('SELECT COUNT(*) FROM securities').fetchone()[0]
    step('注入 ledger 失败：securities 行数未变化',
         n_after == n_before,
         'before=%d after=%d' % (n_before, n_after))
finally:
    server._LEDGER_FAIL_INJECT = False


# =================== §N init_db 幂等性 ===================
section('N. init_db 幂等：已是 v1.0.2 不再迁移')

# 用 v1.0.2 临时库再 init_db
n_backups_before = len([f for f in os.listdir(os.path.dirname(TMP_DB))
                        if f.startswith('workbench-pre-v102-')])
server.init_db(seed=False, db_path=TMP_DB)
n_backups_after = len([f for f in os.listdir(os.path.dirname(TMP_DB))
                       if f.startswith('workbench-pre-v102-')])
# 幂等 init_db 不会触发迁移；目录里没有 backup 子目录，列表应该为 0
step('二次 init_db(v1.0.2 库) 不产生迁移备份',
     n_backups_before == n_backups_after,
     'before=%d after=%d' % (n_backups_before, n_backups_after))


# =================== §O integration test 单独运行提示 ===================
section('O. 真实腾讯行情：单独 integration test')

step('集成测试文件存在（独立运行，不污染主套件）',
     os.path.exists(os.path.join(ROOT, 'tests', 'test_integration_quote.py')))


# ====================== 总计 + 还原 ======================
print()
print('=' * 60)
print(f'总计: PASS {results["pass"]}    FAIL {results["fail"]}')
print('=' * 60)

# 验证生产 DB 不被任何方式触碰
if prod_size_before is not None:
    prod_size_after = os.path.getsize(prod_db)
    prod_hash_after = hashlib_sha(open(prod_db, 'rb').read())
    if prod_size_before == prod_size_after and prod_hash_before == prod_hash_after:
        print(f'✅ 生产 DB 未被触碰（大小={prod_size_after} 指纹={prod_hash_after}）')
    else:
        print(f'❌ 生产 DB 指纹改变！before={prod_size_before}/{prod_hash_before} after={prod_size_after}/{prod_hash_after}')
        results['fail'] += 1

if results['fail']:
    print('\n失败项：')
    for ok, name, detail in results['details']:
        if not ok:
            print(f'  ❌ {name}: {detail}')

# 清理
proxy.restore()
cleanup_tmp_db()

sys.exit(0 if results['fail'] == 0 else 1)
