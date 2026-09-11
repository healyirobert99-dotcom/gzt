# -*- coding: utf-8 -*-
"""
A/H 投研交易工作台 —— 本地服务（仅 Python 标准库，零第三方依赖）

v1.0.1 关键修复（与 v1.0.0 相比）：
- SQLite 加 FOREIGN KEY（research / trade_plans / trades / decision_ledger.security_id → securities.id）
- SQLite 加 UNIQUE (exchange, code) 防止重复证券
- trades 加 CHECK：price>0 / quantity>0 / fee>=0（应用层 + DB 层双重防护）
- PRAGMA foreign_keys=ON 默认启用
- 多币种仓位计算：HKD 必须经汇率换算；缺汇率时 position_pct 显式返回 None
- 行情解析按市场区分字段：A 股时间 f[30] (YYYYMMDDHHMMSS)，港股时间 f[31] (YYYY/MM/DD HH:MM:SS)
- 业务写入 + ledger 写入在同一 BEGIN/COMMIT/ROLLBACK，失败整体回滚
- /api/quotes 同时返回 last_success_at 与 error；前端据此展示「最后成功行情时间」与失败提示
- 数据库迁移函数 migrate_v101()：保留原数据
- 在线备份 make_backup()：使用 SQLite 官方 Backup API

边界（与需求文档一致）：
  - 标的库 / 研究结论（版本化）/ 交易计划（版本化）/ 真实持仓（由流水推导）/ 交易流水（append-only）
  - 决策台账 decision_ledger（append-only）
  - 行情代理：只提供客观价格事实，不生成任何建议
  - 不重做研究、不改投资口径、不自动判断买卖

数据：../data/workbench.db (SQLite, WAL)
启动：python server.py [--port 8765] [--no-browser] [--seed] [--backup [path]]
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'workbench.db')

STATUSES = ['可交易', '等价格', '等证据', '持仓中', '暂不参与']
EXCHANGES = ['SH', 'SZ', 'HK']

# ================ Schema（含 v1.0.1 修复） ================
# 注意：所有使用 security_id 关联 securities 的业务表都加 FOREIGN KEY ... ON DELETE RESTRICT
# securities 加 UNIQUE(exchange, code) 防止重复证券
# trades 表加 CHECK: price>0 / quantity>0 / fee>=0
SCHEMA = '''
CREATE TABLE IF NOT EXISTS securities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  exchange TEXT NOT NULL CHECK (exchange IN ('SH','SZ','HK')),
  name TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'CNY',
  market TEXT NOT NULL DEFAULT 'A股',
  sector TEXT DEFAULT '',
  ah_link_id INTEGER,
  notes TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT '等价格',
  research_pool TEXT DEFAULT '',
  current_price REAL,
  current_price_updated_at TEXT,
  created_at TEXT,
  updated_at TEXT,
  UNIQUE(exchange, code)
);
CREATE TABLE IF NOT EXISTS research (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL DEFAULT 1,
  research_pool TEXT DEFAULT '',
  one_liner TEXT DEFAULT '',
  positive_changes TEXT DEFAULT '',
  core_validations TEXT DEFAULT '[]',
  wall_conditions TEXT DEFAULT '[]',
  report_link TEXT DEFAULT '',
  research_date TEXT DEFAULT '',
  change_note TEXT DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS trade_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL DEFAULT 1,
  first_zone_low REAL, first_zone_high REAL,
  add_zone_low REAL, add_zone_high REAL,
  odds_zone_low REAL, odds_zone_high REAL,
  no_chase_price REAL,
  target_position_pct REAL,
  next_action TEXT DEFAULT '',
  change_note TEXT DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
  trade_date TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('买入','卖出')),
  price REAL NOT NULL CHECK (price > 0),
  quantity REAL NOT NULL CHECK (quantity > 0),
  fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
  note TEXT DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS decision_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
  event_date TEXT NOT NULL,
  event_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  reason TEXT DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE INDEX IF NOT EXISTS idx_research_sec ON research(security_id, version);
CREATE INDEX IF NOT EXISTS idx_plan_sec ON trade_plans(security_id, version);
CREATE INDEX IF NOT EXISTS idx_trades_sec ON trades(security_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_ledger_sec ON decision_ledger(security_id, event_date);
'''


class ApiError(Exception):
    """业务校验错误 → HTTP 400"""


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def today_str():
    return datetime.now().strftime('%Y-%m-%d')


def get_db():
    """获取 SQLite 连接。
    
    关键：每个连接都要启用 PRAGMA foreign_keys=ON，并按 schema_version 当前版本做迁移。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


# ================ 迁移 v0.x / v1.0.0 → v1.0.1 ================
# 检测缺哪些约束，并做不丢数据的兼容升级。

MIGRATIONS = []


def _column_exists(conn, table, column):
    return any(r['name'] == column
               for r in conn.execute(f'PRAGMA table_info({table})').fetchall())


def _indexed_constraint_check(conn, sql):
    """返回 SQL 创建的 index/table 名"""
    pass


def migrate_v101(conn):
    """对 v1.0.0 数据库做兼容升级。

    升级要点：
    1. securities.research_pool、current_price、current_price_updated_at 加列（如缺）
    2. 通过重建表方式加 FOREIGN KEY 与 UNIQUE(exchange, code)
    3. trades 加 CHECK（重建表）
    4. PRAGMA foreign_keys=ON
    """
    # Step 0：清理上一次中断可能留下的 __new 残表
    for t in ('securities', 'research', 'trade_plans', 'trades', 'decision_ledger'):
        conn.execute(f'DROP TABLE IF EXISTS {t}__new')

    # Step 1：缺列补齐（securities 加 research_pool / current_price）
    if not _column_exists(conn, 'securities', 'research_pool'):
        conn.execute('ALTER TABLE securities ADD COLUMN research_pool TEXT DEFAULT ""')
    if not _column_exists(conn, 'securities', 'current_price'):
        conn.execute('ALTER TABLE securities ADD COLUMN current_price REAL')
    if not _column_exists(conn, 'securities', 'current_price_updated_at'):
        conn.execute('ALTER TABLE securities ADD COLUMN current_price_updated_at TEXT')

    # 重建表时临时关闭外键（SQLite 不支持 ALTER TABLE ADD CONSTRAINT 的标准做法）
    conn.execute('PRAGMA foreign_keys=OFF')

    # Step 2：检查 securities 是否已有 UNIQUE(exchange, code)
    idx_list = list(conn.execute('PRAGMA index_list(securities)').fetchall())
    has_uniq_ec = any('UNIQUE' in ((i['sql'] or '') if 'sql' in i.keys() else '')
                      for i in conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='securities'").fetchall())
    if not has_uniq_ec:
        # 检查现有数据是否有重复
        dups = conn.execute(
            "SELECT exchange, code, COUNT(*) c FROM securities GROUP BY exchange, code HAVING c>1"
        ).fetchall()
        if dups:
            conn.execute('PRAGMA foreign_keys=ON')
            raise RuntimeError(
                'securities 存在重复 (exchange, code)，请先手工去重: '
                + ', '.join('%s/%s x%d' % (d['exchange'], d['code'], d['c']) for d in dups)
            )
        # 通过重建表加 UNIQUE
        conn.executescript('''
        CREATE TABLE securities__new (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL,
          exchange TEXT NOT NULL CHECK (exchange IN ('SH','SZ','HK')),
          name TEXT NOT NULL,
          currency TEXT NOT NULL DEFAULT 'CNY',
          market TEXT NOT NULL DEFAULT 'A股',
          sector TEXT DEFAULT '',
          ah_link_id INTEGER,
          notes TEXT DEFAULT '',
          status TEXT NOT NULL DEFAULT '等价格',
          research_pool TEXT DEFAULT '',
          current_price REAL,
          current_price_updated_at TEXT,
          created_at TEXT,
          updated_at TEXT,
          UNIQUE(exchange, code)
        );
        INSERT INTO securities__new
          (id, code, exchange, name, currency, market, sector, ah_link_id, notes,
           status, research_pool, current_price, current_price_updated_at, created_at, updated_at)
          SELECT id, code, exchange, name, currency, market, sector, ah_link_id, notes,
                 status, research_pool, current_price, current_price_updated_at, created_at, updated_at
            FROM securities;
        DROP TABLE securities;
        ALTER TABLE securities__new RENAME TO securities;
        ''')

    # Step 3：业务表加 FOREIGN KEY
    # 先校验当前数据完整性（外键关闭时不会自动校验）
    bad = []
    for table in ('research', 'trade_plans', 'trades', 'decision_ledger'):
        bad.extend('{}:sid={}'.format(table, r['security_id'])
                   for r in conn.execute(
                       "SELECT security_id FROM {} WHERE security_id NOT IN (SELECT id FROM securities)".format(table)
                   ).fetchall())
    if bad:
        conn.execute('PRAGMA foreign_keys=ON')
        raise RuntimeError(
            '发现孤儿业务记录，无法加 FOREIGN KEY: ' + ', '.join(bad[:10])
            + ('... (%d 条)' % len(bad) if len(bad) > 10 else '')
        )

    def rebuild_table(src_table, create_sql, columns):
        """重建表以应用新 schema。columns 为 INSERT 列顺序。"""
        conn.executescript(
            'CREATE TABLE {new} ({create});\n'
            'INSERT INTO {new} ({cols}) SELECT {cols} FROM {src};\n'
            'DROP TABLE {src};\n'
            'ALTER TABLE {new} RENAME TO {src};'.format(
                src=src_table, new=src_table + '__new', create=create_sql, cols=','.join(columns))
        )

    # research 表
    r_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='research'"
    ).fetchone()['sql'] or ''
    if 'REFERENCES securities' not in r_sql:
        rebuild_table('research', '''
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL DEFAULT 1,
          research_pool TEXT DEFAULT '',
          one_liner TEXT DEFAULT '',
          positive_changes TEXT DEFAULT '',
          core_validations TEXT DEFAULT '[]',
          wall_conditions TEXT DEFAULT '[]',
          report_link TEXT DEFAULT '',
          research_date TEXT DEFAULT '',
          change_note TEXT DEFAULT '',
          created_at TEXT
        ''', ['id', 'security_id', 'version', 'research_pool', 'one_liner', 'positive_changes',
             'core_validations', 'wall_conditions', 'report_link', 'research_date',
             'change_note', 'created_at'])

    p_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='trade_plans'"
    ).fetchone()['sql'] or ''
    if 'REFERENCES securities' not in p_sql:
        rebuild_table('trade_plans', '''
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL DEFAULT 1,
          first_zone_low REAL, first_zone_high REAL,
          add_zone_low REAL, add_zone_high REAL,
          odds_zone_low REAL, odds_zone_high REAL,
          no_chase_price REAL,
          target_position_pct REAL,
          next_action TEXT DEFAULT '',
          change_note TEXT DEFAULT '',
          created_at TEXT
        ''', ['id', 'security_id', 'version', 'first_zone_low', 'first_zone_high',
             'add_zone_low', 'add_zone_high', 'odds_zone_low', 'odds_zone_high',
             'no_chase_price', 'target_position_pct', 'next_action', 'change_note',
             'created_at'])

    t_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='trades'"
    ).fetchone()['sql'] or ''
    if 'CHECK' not in t_sql or 'REFERENCES securities' not in t_sql:
        rebuild_table('trades', '''
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          trade_date TEXT NOT NULL,
          side TEXT NOT NULL CHECK (side IN ('买入','卖出')),
          price REAL NOT NULL CHECK (price > 0),
          quantity REAL NOT NULL CHECK (quantity > 0),
          fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
          note TEXT DEFAULT '',
          created_at TEXT
        ''', ['id', 'security_id', 'trade_date', 'side', 'price', 'quantity', 'fee',
             'note', 'created_at'])

    l_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='decision_ledger'"
    ).fetchone()['sql'] or ''
    if 'REFERENCES securities' not in l_sql:
        rebuild_table('decision_ledger', '''
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          event_date TEXT NOT NULL,
          event_type TEXT NOT NULL,
          summary TEXT NOT NULL,
          reason TEXT DEFAULT '',
          created_at TEXT
        ''', ['id', 'security_id', 'event_date', 'event_type', 'summary', 'reason',
             'created_at'])

    # 重建表完成，重新启用外键
    conn.execute('PRAGMA foreign_keys=ON')

    # Step 4：删除已废弃的 settings 默认值（仅补 hkd_cny_rate 缺省）
    if not conn.execute(
        "SELECT 1 FROM settings WHERE key='hkd_cny_rate'"
    ).fetchone():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('hkd_cny_rate', '')"
        )
    if not conn.execute(
        "SELECT 1 FROM settings WHERE key='account_size_cny'"
    ).fetchone():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('account_size_cny', '')"
        )

    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', '1.0.1')")


# ================ 备份（SQLite 在线 Backup API） ================


def init_db(seed=False, db_path=None):
    """初始化数据库（v1.0.1）。

    - seed=True：仅在显式 CLI（--seed）或测试调用时，从 tests/fixtures/sample_seed.py
      写入示例数据。生产 init_db 默认 seed=False，保持空库。
    - 已有数据库：自动 migrate_v101 升级。
    """
    target = db_path or DB_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    is_new = not os.path.exists(target)

    conn = sqlite3.connect(target, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        conn.executescript(SCHEMA)
        if not is_new:
            migrate_v101(conn)
        if seed:
            if conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c'] == 0:
                sys.path.insert(0, os.path.join(ROOT_DIR, 'tests', 'fixtures'))
                from sample_seed import seed_sample as _seed_fixture
                _seed_fixture(conn)
                print('[INIT] 示例数据已写入（来源：tests/fixtures/sample_seed.py）')
            else:
                print('[INIT] 数据库已非空，跳过示例 seed')
        conn.commit()
    finally:
        conn.close()


# ================ 备份（SQLite 在线 Backup API） ================

def make_backup(dst_path=None):
    """在线一致性备份。无需停服。
    
    使用 sqlite3.Connection.backup()（PEP 248 / sqlite3 自带，3.7+）。
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(DB_PATH)
    if dst_path is None:
        ts = now_str().replace(' ', '_').replace(':', '')
        dst_path = os.path.join(DATA_DIR, 'backup', f'workbench-{ts}.db')
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dst_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dst_path


# ================ 基础读写 + 业务校验 ================

def current_row(conn, table, sid):
    r = conn.execute(
        'SELECT * FROM %s WHERE security_id=? ORDER BY version DESC, id DESC LIMIT 1' % table,
        (sid,)).fetchone()
    return dict(r) if r else None


def ledger_add(conn, sid, event_date, event_type, summary, reason=''):
    """写入台账。注意：调用方必须保证 conn 在同一事务内。"""
    conn.execute(
        'INSERT INTO decision_ledger (security_id, event_date, event_type, summary, reason, created_at) '
        'VALUES (?,?,?,?,?,?)',
        (sid, event_date or today_str(), event_type, summary, reason or '', now_str()))


# 测试钩子：可注入强制 ledger_add 失败以验证事务回滚
_LEDGER_FAIL_INJECT = False


def compute_position(conn, sid, account_size_cny=None, hkd_cny_rate=None):
    """持仓完全由流水推导，不单独存储。
    
    v1.0.1 多币种处理：
    - market_value 以 CNY 为统一计价
    - HKD 必须乘以 hkd_cny_rate；缺汇率时返回 None，不输出错误比例
    - position_pct 需要 account_size_cny；缺则 None
    """
    sec = conn.execute(
        'SELECT currency, current_price FROM securities WHERE id=?', (sid,)).fetchone()
    if not sec:
        return {'quantity': 0, 'avg_cost': 0.0, 'realized_pnl': 0.0,
                'currency': 'CNY', 'current_price': None, 'market_value': None,
                'market_value_currency': None, 'position_pct': None}
    currency = sec['currency'] or 'CNY'
    cur_price = sec['current_price']

    rows = conn.execute(
        'SELECT * FROM trades WHERE security_id=? ORDER BY trade_date, id', (sid,)).fetchall()
    qty, cost, realized = 0.0, 0.0, 0.0
    for t in rows:
        q = float(t['quantity'] or 0)
        p = float(t['price'] or 0)
        fee = float(t['fee'] or 0)
        if q <= 0:
            continue
        if t['side'] == '买入':
            new_qty = qty + q
            cost = (cost * qty + p * q + fee) / new_qty if new_qty > 0 else 0.0
            qty = new_qty
        else:
            q = min(q, qty)
            realized += (p - cost) * q - fee
            qty -= q
            if qty <= 1e-9:
                qty, cost = 0.0, 0.0
    pos = {
        'quantity': round(qty, 6),
        'avg_cost': round(cost, 6) if qty > 0 else 0.0,
        'realized_pnl': round(realized, 2),
        'currency': currency,
        'current_price': cur_price,
        'market_value': None,
        'market_value_currency': None,
        'position_pct': None,
        'fx_rate_used': None,
        'fx_rate_missing': False,
    }

    if qty > 0 and cur_price and cur_price > 0:
        if currency == 'CNY':
            mv = round(qty * cur_price, 2)
            pos['market_value'] = mv
            pos['market_value_currency'] = 'CNY'
        elif currency == 'HKD':
            if hkd_cny_rate and float(hkd_cny_rate) > 0:
                rate = float(hkd_cny_rate)
                mv = round(qty * cur_price * rate, 2)
                pos['market_value'] = mv
                pos['market_value_currency'] = 'CNY (after HKD→CNY @ %.4f)' % rate
                pos['fx_rate_used'] = rate
            else:
                pos['market_value'] = None
                pos['market_value_currency'] = None
                pos['fx_rate_missing'] = True

    if pos['market_value'] is not None and account_size_cny:
        try:
            a = float(account_size_cny)
            if a > 0:
                pos['position_pct'] = round(pos['market_value'] / a * 100, 2)
        except (TypeError, ValueError):
            pass

    return pos


def consistency_check(sec, pos):
    """持仓/状态一致性提示。**不自动改 status**，只回报问题。"""
    issues = []
    has_pos = pos['quantity'] > 1e-9
    status = sec['status']
    if has_pos and status != '持仓中':
        issues.append({
            'code': 'POSITION_HOLDING_STATUS_MISMATCH',
            'level': 'warn',
            'message': f'当前持仓 {pos["quantity"]} {pos["currency"]}，但 status={status}（≠持仓中）。'
                       '本系统不自动调整 status，请人工复核"下一动作"。'
        })
    if not has_pos and status == '持仓中':
        issues.append({
            'code': 'STATUS_HOLDING_NO_POSITION',
            'level': 'warn',
            'message': 'status=持仓中 但当前无持仓，请确认是否漏录交易流水，或误置状态。'
        })
    return {
        'has_position': has_pos,
        'issues': issues,
        'checked': True,
    }


def tencent_symbol(sec):
    if sec['exchange'] == 'HK':
        return 'hk' + str(sec['code']).zfill(5)
    return ('sh' if sec['exchange'] == 'SH' else 'sz') + str(sec['code'])


def enrich(conn, sec, account_size_cny=None, hkd_cny_rate=None):
    s = dict(sec)
    s['tencent_symbol'] = tencent_symbol(s)
    r = current_row(conn, 'research', s['id'])
    if r:
        r['core_validations'] = json.loads(r.get('core_validations') or '[]')
        r['wall_conditions'] = json.loads(r.get('wall_conditions') or '[]')
    s['research'] = r
    s['plan'] = current_row(conn, 'trade_plans', s['id'])
    s['position'] = compute_position(conn, s['id'], account_size_cny, hkd_cny_rate)
    s['position_consistency'] = consistency_check(s, s['position'])
    return s


def get_security_or_404(conn, sid):
    r = conn.execute('SELECT * FROM securities WHERE id=?', (sid,)).fetchone()
    if not r:
        raise ApiError('标的不存在: %s' % sid)
    return dict(r)


def get_settings_cached(conn):
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows}


# ================ 查询接口 ================

def list_securities():
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM securities ORDER BY id').fetchall()
        s = get_settings_cached(conn)
        a = s.get('account_size_cny') or None
        h = s.get('hkd_cny_rate') or None
        return [enrich(conn, r, a, h) for r in rows]
    finally:
        conn.close()


def get_detail(sid):
    conn = get_db()
    try:
        sec = get_security_or_404(conn, sid)
        s = get_settings_cached(conn)
        a = s.get('account_size_cny') or None
        h = s.get('hkd_cny_rate') or None
        out = enrich(conn, sec, a, h)
        research_history = [dict(r) for r in conn.execute(
            'SELECT * FROM research WHERE security_id=? ORDER BY version DESC', (sid,)).fetchall()]
        for r in research_history:
            r['core_validations'] = json.loads(r.get('core_validations') or '[]')
            r['wall_conditions'] = json.loads(r.get('wall_conditions') or '[]')
        plan_history = [dict(r) for r in conn.execute(
            'SELECT * FROM trade_plans WHERE security_id=? ORDER BY version DESC', (sid,)).fetchall()]
        trades = [dict(r) for r in conn.execute(
            'SELECT * FROM trades WHERE security_id=? ORDER BY trade_date, id', (sid,)).fetchall()]
        ledger = [dict(r) for r in conn.execute(
            'SELECT * FROM decision_ledger WHERE security_id=? ORDER BY event_date DESC, id DESC',
            (sid,)).fetchall()]
        return {
            'security': out,
            'research': out['research'],
            'plan': out['plan'],
            'position': out['position'],
            'position_consistency': out['position_consistency'],
            'research_history': research_history,
            'plan_history': plan_history,
            'trades': trades,
            'ledger': ledger,
        }
    finally:
        conn.close()


def get_settings():
    conn = get_db()
    try:
        d = get_settings_cached(conn)
        return {
            'account_size_cny': d.get('account_size_cny', ''),
            'hkd_cny_rate': d.get('hkd_cny_rate', ''),
        }
    finally:
        conn.close()


def update_settings(body):
    conn = get_db()
    try:
        for key in ('account_size_cny', 'hkd_cny_rate'):
            if key in body:
                v = body.get(key)
                if v in (None, ''):
                    v = ''
                else:
                    try:
                        fv = float(v)
                        if key == 'account_size_cny' and fv < 0:
                            raise ApiError('账户规模不能为负')
                        if key == 'hkd_cny_rate' and fv <= 0:
                            raise ApiError('汇率必须大于 0')
                        v = str(fv)
                    except (TypeError, ValueError):
                        raise ApiError('%s 必须是数字' % key)
                conn.execute(
                    'INSERT INTO settings (key, value) VALUES (?,?) '
                    'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, v))
        conn.commit()
        return get_settings()
    finally:
        conn.close()


# ================ 行情代理（仅客观事实） ================

_quote_lock = threading.Lock()
_quote_cache = {'ts': 0.0, 'data': {}, 'last_success_at': None, 'last_error': '', 'last_error_at': None}


def fetch_tencent(symbols):
    """调用腾讯免费行情接口。
    
    通用字段（f 索引位置经真实响应实测）：
      f[0]=市场标识(A=1 / 港=100), f[1]=名称, f[2]=代码, f[3]=当前价, f[4]=昨收, f[5]=今开
      f[30]=行情时间（A 股 YYYYMMDDHHMMSS 紧凑；港股 YYYY/MM/DD HH:MM:SS）
      f[31]=涨跌额; f[32]=涨跌幅
    港股来源下 f[0]=100，货币标记改为 HKD。
    """
    url = 'https://qt.gtimg.cn/q=' + ','.join(symbols)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://gu.qq.com/'})
    raw = urllib.request.urlopen(req, timeout=8).read().decode('gbk', 'ignore')
    out = {}
    for m in re.finditer(r'v_([A-Za-z0-9_]+)="([^"]*)"', raw):
        sym = m.group(1)
        f = m.group(2).split('~')
        if len(f) < 33:  # 至少需要 f[32]
            continue
        try:
            cur = float(f[3])
            prev = float(f[4])
        except (ValueError, IndexError):
            continue
        if cur <= 0 or prev <= 0:
            continue  # 停牌 / 字段无效
        market = sym[:2].lower()  # 'sh', 'sz', 'hk'

        # 行情时间字段都在 f[30]，但格式按市场不同
        mt_raw = f[30]
        if market == 'hk':
            # YYYY/MM/DD HH:MM:SS → YYYY-MM-DD HH:MM:SS
            if re.fullmatch(r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}', mt_raw or ''):
                mt = mt_raw.replace('/', '-')
            else:
                mt = ''
        else:
            # YYYYMMDDHHMMSS → YYYY-MM-DD HH:MM:SS
            if re.fullmatch(r'\d{14}', mt_raw or ''):
                mt = f'{mt_raw[0:4]}-{mt_raw[4:6]}-{mt_raw[6:8]} {mt_raw[8:10]}:{mt_raw[10:12]}:{mt_raw[12:14]}'
            else:
                mt = ''
        try:
            change = float(f[31])
        except (ValueError, IndexError):
            change = round(cur - prev, 4)
        try:
            change_pct = float(f[32])
        except (ValueError, IndexError):
            change_pct = round((cur - prev) / prev * 100, 2) if prev else 0.0
        out[sym] = {
            'symbol': sym,
            'name': f[1] if len(f) > 1 else '',
            'code': f[2] if len(f) > 2 else '',
            'market': '港股' if market == 'hk' else 'A股',
            'currency': 'HKD' if market == 'hk' else 'CNY',
            'current': cur,
            'prev_close': prev,
            'change': round(change, 4),
            'change_pct': round(change_pct, 2),
            'market_time': mt or None,
            'source': 'tencent',
            'fetched_at': now_str(),
        }
    return out


def get_quotes(symbols):
    result = {}
    with _quote_lock:
        cached = dict(_quote_cache['data'])
        last_success_at = _quote_cache.get('last_success_at')
        last_error = _quote_cache.get('last_error')
        last_error_at = _quote_cache.get('last_error_at')
        stale = time.time() - _quote_cache['ts'] > 8 if _quote_cache['ts'] else True
    need = [s for s in symbols if stale or s not in cached]
    if need:
        try:
            fetched = fetch_tencent(need)
            with _quote_lock:
                _quote_cache['data'].update(fetched)
                _quote_cache['ts'] = time.time()
                if fetched:
                    _quote_cache['last_success_at'] = now_str()
        except Exception as e:
            with _quote_lock:
                _quote_cache['last_error'] = '行情接口暂时不可用：%s' % e
                _quote_cache['last_error_at'] = now_str()
    with _quote_lock:
        for s in symbols:
            if s in _quote_cache['data']:
                result[s] = _quote_cache['data'][s]
        last_success_at = _quote_cache.get('last_success_at')
        last_error = _quote_cache.get('last_error')
        last_error_at = _quote_cache.get('last_error_at')
    # 上次成功后是否曾报错？
    error = last_error if (last_error_at and last_success_at and last_error_at > last_success_at) else ''
    return {
        'fetched_at': last_success_at,            # 本次响应使用最近一次成功时间
        'data': result,
        'error': error,
        'last_success_at': last_success_at,
        'last_error': last_error,
        'last_error_at': last_error_at,
    }


# ================ 写入接口（事务原子化） ================

def _to_f(v):
    if v in (None, ''):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ApiError('数值字段格式不正确: %r' % v)


def _norm_code(code, exchange):
    code = re.sub(r'\D', '', str(code))
    if not code:
        raise ApiError('证券代码不能为空')
    if exchange == 'HK':
        if len(code) > 5:
            raise ApiError('港股代码应为 5 位数字')
        return code.zfill(5)
    if len(code) != 6:
        raise ApiError('A 股代码应为 6 位数字')
    return code


def _research_fields(body):
    vals = body.get('core_validations') or []
    walls = body.get('wall_conditions') or []
    if not isinstance(vals, list) or not isinstance(walls, list):
        raise ApiError('核心验证项 / 危墙条件格式不正确')
    return {
        'research_pool': str(body.get('research_pool') or '').strip(),
        'one_liner': str(body.get('one_liner') or '').strip(),
        'positive_changes': str(body.get('positive_changes') or '').strip(),
        'core_validations': json.dumps(vals, ensure_ascii=False),
        'wall_conditions': json.dumps(walls, ensure_ascii=False),
        'report_link': str(body.get('report_link') or '').strip(),
        'research_date': str(body.get('research_date') or '').strip(),
        'change_note': str(body.get('change_note') or '').strip(),
    }


def _plan_fields(body):
    f = {k: _to_f(body.get(k)) for k in (
        'first_zone_low', 'first_zone_high', 'add_zone_low', 'add_zone_high',
        'odds_zone_low', 'odds_zone_high', 'no_chase_price', 'target_position_pct')}
    for zone in (('first_zone_low', 'first_zone_high'),
                 ('add_zone_low', 'add_zone_high'),
                 ('odds_zone_low', 'odds_zone_high')):
        lo, hi = f[zone[0]], f[zone[1]]
        if lo is not None and hi is not None and lo > hi:
            raise ApiError('价格区间下限不能大于上限')
    t = f['target_position_pct']
    if t is not None and not (0 <= t <= 100):
        raise ApiError('目标仓位应在 0-100 之间')
    f['next_action'] = str(body.get('next_action') or '').strip()
    f['change_note'] = str(body.get('change_note') or '').strip()
    return f


def _run_in_transaction(func):
    """装饰器：保证 func(conn) 内整体事务化。
    
    业务写入 + ledger_add 任意一处失败，整体 ROLLBACK。
    """
    def wrapper(*args, **kwargs):
        conn = get_db()
        try:
            conn.execute('BEGIN')
            res = func(conn, *args, **kwargs)
            conn.execute('COMMIT')
            return res
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            raise
        finally:
            conn.close()
    return wrapper


@_run_in_transaction
def create_security_tx(conn, body):
    name = str(body.get('name') or '').strip()
    exchange = str(body.get('exchange') or '').strip()
    if not name:
        raise ApiError('公司名称不能为空')
    if exchange not in EXCHANGES:
        raise ApiError('交易所必须为 SH / SZ / HK')
    code = _norm_code(body.get('code'), exchange)
    status = body.get('status') or '等价格'
    if status not in STATUSES:
        raise ApiError('状态不合法')
    currency = 'HKD' if exchange == 'HK' else 'CNY'
    market = '港股' if exchange == 'HK' else 'A股'

    r = _research_fields(body.get('research') or {})
    p = _plan_fields(body.get('plan') or {})

    # 唯一性 (exchange, code) 校验（DB 层 UNIQUE 也会兜底）
    dup = conn.execute(
        'SELECT id FROM securities WHERE exchange=? AND code=?', (exchange, code)).fetchone()
    if dup:
        raise ApiError(f'该交易所已存在相同代码：{exchange} {code}（id={dup["id"]}）。禁止重复创建。')

    cur = conn.execute(
        'INSERT INTO securities (code, exchange, name, currency, market, sector, notes, status, created_at, updated_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?)',
        (code, exchange, name, currency, market,
         str(body.get('sector') or '').strip(), str(body.get('notes') or '').strip(),
         status, now_str(), now_str()))
    sid = cur.lastrowid
    conn.execute(
        'INSERT INTO research (security_id, version, research_pool, one_liner, positive_changes, '
        'core_validations, wall_conditions, report_link, research_date, change_note, created_at) '
        'VALUES (?,1,?,?,?,?,?,?,?,?,?)',
        (sid, r['research_pool'], r['one_liner'], r['positive_changes'],
         r['core_validations'], r['wall_conditions'], r['report_link'],
         r['research_date'], r['change_note'], now_str()))
    conn.execute(
        'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, add_zone_low, '
        'add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, target_position_pct, '
        'next_action, change_note, created_at) VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?)',
        (sid, p['first_zone_low'], p['first_zone_high'], p['add_zone_low'], p['add_zone_high'],
         p['odds_zone_low'], p['odds_zone_high'], p['no_chase_price'], p['target_position_pct'],
         p['next_action'], p['change_note'], now_str()))
    if _LEDGER_FAIL_INJECT:
        raise RuntimeError('INJECTED LEDGER FAIL')
    ledger_add(conn, sid, today_str(), '标的创建',
               '新建标的 %s（%s.%s），初始交易状态：%s' % (name, code, exchange, status))
    return {'id': sid}


def create_security(body):
    return create_security_tx(body)


@_run_in_transaction
def update_security_tx(conn, sid, body):
    sec = get_security_or_404(conn, sid)
    name = str(body.get('name') or sec['name']).strip()
    if not name:
        raise ApiError('公司名称不能为空')
    ah = body.get('ah_link_id')
    if ah in (None, ''):
        ah = None
    else:
        try:
            ah = int(ah)
        except (TypeError, ValueError):
            raise ApiError('A/H 关联标的不合法')
        if ah == sid:
            raise ApiError('不能关联标的自身')
        if not conn.execute('SELECT 1 FROM securities WHERE id=?', (ah,)).fetchone():
            raise ApiError('A/H 关联标的不存在')
    conn.execute(
        'UPDATE securities SET name=?, sector=?, notes=?, ah_link_id=?, updated_at=? WHERE id=?',
        (name, str(body.get('sector') or '').strip(),
         str(body.get('notes') or '').strip(), ah, now_str(), sid))
    ledger_add(conn, sid, today_str(), '信息更新',
               '更新标的基础信息（名称/行业/AH 关联/备注）')


def update_security(sid, body):
    update_security_tx(sid, body)
    return get_detail(sid)


@_run_in_transaction
def change_status_tx(conn, sid, body):
    status = body.get('status')
    reason = str(body.get('reason') or '').strip()
    event_date = str(body.get('event_date') or '').strip() or today_str()
    if status not in STATUSES:
        raise ApiError('状态不合法')
    if not reason:
        raise ApiError('变更原因必填——决策台账需要保留当时的判断依据')
    sec = get_security_or_404(conn, sid)
    old = sec['status']
    if old == status:
        raise ApiError('新状态与当前状态相同')
    conn.execute('UPDATE securities SET status=?, updated_at=? WHERE id=?',
                 (status, now_str(), sid))
    ledger_add(conn, sid, event_date, '状态变更',
               '状态变更：%s → %s' % (old, status), reason)


def change_status(sid, body):
    change_status_tx(sid, body)
    return get_detail(sid)


@_run_in_transaction
def update_research_tx(conn, sid, body):
    r = _research_fields(body)
    get_security_or_404(conn, sid)
    old = current_row(conn, 'research', sid)
    v = (old['version'] + 1) if old else 1
    conn.execute(
        'INSERT INTO research (security_id, version, research_pool, one_liner, positive_changes, '
        'core_validations, wall_conditions, report_link, research_date, change_note, created_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (sid, v, r['research_pool'], r['one_liner'], r['positive_changes'],
         r['core_validations'], r['wall_conditions'], r['report_link'],
         r['research_date'], r['change_note'], now_str()))
    ledger_add(conn, sid, today_str(), '研究更新',
               '研究结论更新至 v%d%s' % (v, ('：' + r['change_note']) if r['change_note'] else ''))


def update_research(sid, body):
    update_research_tx(sid, body)
    return get_detail(sid)


@_run_in_transaction
def update_plan_tx(conn, sid, body):
    p = _plan_fields(body)
    get_security_or_404(conn, sid)
    old = current_row(conn, 'trade_plans', sid)
    v = (old['version'] + 1) if old else 1
    conn.execute(
        'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, add_zone_low, '
        'add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, target_position_pct, '
        'next_action, change_note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (sid, v, p['first_zone_low'], p['first_zone_high'], p['add_zone_low'], p['add_zone_high'],
         p['odds_zone_low'], p['odds_zone_high'], p['no_chase_price'], p['target_position_pct'],
         p['next_action'], p['change_note'], now_str()))
    ledger_add(conn, sid, today_str(), '计划修改',
               '交易计划更新至 v%d%s' % (v, ('：' + p['change_note']) if p['change_note'] else ''))


def update_plan(sid, body):
    update_plan_tx(sid, body)
    return get_detail(sid)


@_run_in_transaction
def add_trade_tx(conn, sid, body):
    side = body.get('side')
    if side not in ('买入', '卖出'):
        raise ApiError('交易方向必须为 买入 / 卖出')
    try:
        price = float(body.get('price'))
        quantity = float(body.get('quantity'))
    except (TypeError, ValueError):
        raise ApiError('价格 / 数量必须是数字')
    if price <= 0 or quantity <= 0:
        raise ApiError('价格 / 数量必须大于 0')
    try:
        fee = float(body.get('fee') or 0)
    except (TypeError, ValueError):
        raise ApiError('费用必须是数字')
    if fee < 0:
        raise ApiError('费用不能为负')
    trade_date = str(body.get('trade_date') or '').strip() or today_str()
    note = str(body.get('note') or '').strip()

    get_security_or_404(conn, sid)
    if side == '卖出':
        # 注意：这是同一事务里的预读，跨事务需要 SELECT 锁（SQLite 默认 deferred）
        # 如需更强一致性可执行 BEGIN IMMEDIATE；此处保留 Postgres / SQLite 通用做法
        pos = compute_position(conn, sid)
        if quantity > pos['quantity'] + 1e-9:
            raise ApiError('卖出数量（%g）超过当前持仓（%g）' % (quantity, pos['quantity']))
    conn.execute(
        'INSERT INTO trades (security_id, trade_date, side, price, quantity, fee, note, created_at) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (sid, trade_date, side, price, quantity, fee, note, now_str()))
    ledger_add(conn, sid, trade_date, side,
               '%s %g 股 @ %g' % (side, quantity, price) + (('，' + note) if note else ''))


def add_trade(sid, body):
    add_trade_tx(sid, body)
    return get_detail(sid)


@_run_in_transaction
def add_note_tx(conn, sid, body):
    summary = str(body.get('summary') or '').strip()
    if not summary:
        raise ApiError('记录内容不能为空')
    event_date = str(body.get('event_date') or '').strip() or today_str()
    reason = str(body.get('reason') or '').strip()
    get_security_or_404(conn, sid)
    ledger_add(conn, sid, event_date, '备注', summary, reason)


def add_note(sid, body):
    add_note_tx(sid, body)
    return get_detail(sid)


# ================ HTTP 服务 ================

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
}


class Handler(BaseHTTPRequestHandler):
    server_version = 'Workbench/1.0.1'

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, obj)

    def _err(self, msg, code=400):
        self._json({'error': msg}, code)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            raise ApiError('请求体不是有效的 JSON')

    def _static(self, rel):
        path = os.path.realpath(os.path.join(STATIC_DIR, rel))
        if not path.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(path):
            return self._err('not found', 404)
        ext = os.path.splitext(path)[1].lower()
        with open(path, 'rb') as f:
            self._send(200, f.read(), MIME.get(ext, 'application/octet-stream'))

    def do_GET(self):
        try:
            u = urlparse(self.path)
            p = unquote(u.path)
            if p == '/':
                return self._static('index.html')
            if p.startswith('/api/'):
                return self.api(u, None, None)
            if p.startswith('/static/'):
                return self._static(p[len('/static/'):])
            return self._err('not found', 404)
        except ApiError as e:
            self._err(str(e), 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._err('服务器错误: %s' % e, 500)
            except Exception:
                pass

    def _mut(self, method):
        try:
            u = urlparse(self.path)
            if not u.path.startswith('/api/'):
                return self._err('not found', 404)
            self.api(u, method, self._body())
        except ApiError as e:
            try:
                self._err(str(e), 400)
            except Exception:
                pass
        except sqlite3.IntegrityError as e:
            # DB CHECK / UNIQUE / NOT NULL / FOREIGN KEY 失败 → 应用层错
            try:
                self._err('数据库完整性约束失败: %s' % e, 400)
            except Exception:
                pass
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._err('服务器错误: %s' % e, 500)
            except Exception:
                pass

    def do_POST(self):
        self._mut('POST')

    def do_PUT(self):
        self._mut('PUT')

    def api(self, u, method, body):
        seg = [s for s in unquote(u.path).split('/') if s]
        qs = parse_qs(u.query)

        # ---- GET
        if method is None:
            if seg == ['api', 'securities']:
                return self._json(list_securities())
            if len(seg) == 3 and seg[1] == 'securities' and seg[2].isdigit():
                return self._json(get_detail(int(seg[2])))
            if seg[:2] == ['api', 'quotes']:
                syms = [s for s in qs.get('symbols', [''])[0].split(',') if s]
                return self._json(get_quotes(syms))
            if seg == ['api', 'settings']:
                return self._json(get_settings())
            return self._err('not found', 404)

        # ---- POST /api/securities
        if method == 'POST' and seg == ['api', 'securities']:
            return self._json(create_security(body), 201)
        if method == 'PUT' and seg == ['api', 'settings']:
            return self._json(update_settings(body))
        if len(seg) >= 3 and seg[1] == 'securities' and seg[2].isdigit():
            sid = int(seg[2])
            if len(seg) == 3 and method == 'PUT':
                return self._json(update_security(sid, body))
            if len(seg) == 4:
                sub = seg[3]
                if method == 'POST' and sub == 'status':
                    return self._json(change_status(sid, body))
                if method == 'POST' and sub == 'trades':
                    return self._json(add_trade(sid, body))
                if method == 'POST' and sub == 'ledger':
                    return self._json(add_note(sid, body))
                if method == 'PUT' and sub == 'research':
                    return self._json(update_research(sid, body))
                if method == 'PUT' and sub == 'plan':
                    return self._json(update_plan(sid, body))
        return self._err('not found', 404)


def main():
    ap = argparse.ArgumentParser(description='A/H 投研交易工作台 v1.0.1')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    ap.add_argument('--seed', action='store_true',
                    help='初始化时写入示例数据（仅显式调用, 默认空库）')
    ap.add_argument('--backup', nargs='?', default=None, const='__DEFAULT__',
                    help='执行在线一致性备份；不传值时备份到 data/backup/workbench-<时间>.db')
    args = ap.parse_args()

    # 1) 备份模式：不启动服务，直接备份并退出
    if args.backup is not None:
        dst = None if args.backup == '__DEFAULT__' else args.backup
        path = make_backup(dst)
        size = os.path.getsize(path)
        print('[备份] %s (%d bytes)' % (path, size))
        # 简单一致性自检：能否以 SQLite 打开并读到 securities 表行数
        c = sqlite3.connect(path)
        n = c.execute('SELECT COUNT(*) FROM securities').fetchone()[0]
        c.close()
        print('[备份验证] %d 行 securities,可读取' % n)
        return

    # 2) 启动服务
    init_db(seed=args.seed)
    url = 'http://127.0.0.1:%d' % args.port
    try:
        ThreadingHTTPServer.daemon_threads = True
        srv = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        print('[提示] 端口 %d 已被占用，工作台可能已在运行：%s' % (args.port, url))
        webbrowser.open(url)
        return
    print('A/H 投研交易工作台 v1.0.1 已启动: %s' % url)
    print('数据文件: %s' % DB_PATH)
    print('按 Ctrl+C 停止服务。')
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止。')


if __name__ == '__main__':
    main()
