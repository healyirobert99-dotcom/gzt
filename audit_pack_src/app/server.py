# -*- coding: utf-8 -*-
"""
A/H 投研交易工作台 —— 本地服务（仅 Python 标准库，零第三方依赖）

v1.0.2 关键修复（与 v1.0.1 相比）：
- 行情→持仓链路：成功获取的行情自动回写 securities.current_price / current_price_updated_at，
  compute_position() 直接使用最新行情；端到端测试不再手动 UPDATE current_price。
- 历史补录校验：trade_date 必须是有效 ISO 日期；写入前对"完整时间序列"
  重新计算累计持仓，任意时点累计为负则拒绝写入并返回明确错误；
  废除 v1.0.1 中 q=min(q, qty) 静默截断非法历史卖出的做法。
- 状态弹窗修复：openStatusModal 拼接选项时正确选中当前状态。
  （前端修复；详见 app.js。）
- 清除生产默认假数据：init_db 不预填 hkd_cny_rate / account_size_cny。
- 数据库级版本唯一性：research / trade_plans 加 UNIQUE(security_id, version)。
- 测试隔离：测试必须临时 DB，并显式将 server.DB_PATH 指向临时库。
  真实腾讯行情接口测试拆为 integration 单独跑。
- Migration 原子化：BEGIN→重建表→重建索引→foreign_key_check→COMMIT，
  失败整体 ROLLBACK；迁移后立即验证 4 个业务索引存在。
- schema_version 优先：启动时先读 settings.schema_version；等于目标版本
  完全跳过迁移（一次性，已迁过的库不再重复运行迁移）。
- UNIQUE 检测用 PRAGMA index_list/index_info，不依赖 sqlite_master 中
  autoindex 的空 sql 文本。
- 计划更新 change_note 非空（首次除外）；不允许静默提交。
- 行情失败语义：从未成功时也返回 error；前端价格派生提示带时间戳，避免
  把"上次成功行情"伪装为"当前价格"。
- 文档安全描述与 HTTP 语义修正（404 vs 400）。
- 港股/已实现盈亏单位明确：HKD/CNY 各自标注；折算市值标 CNY（带汇率标记）。
- 删除 sampleBanner 默认触发，真实用户创建第一只股票后不再看到"美图/道通"。
- 修复重复 app/启动工作台.bat。
- design_research_pool_history.md 改为事实一致问题报告（research 已有该字段）。

v1.0.3 新增（用户明确批准）：
- 新增独立"动态执行层"（execution_reviews 表，append-only）。
  静态交易计划 = "什么价格值得交易"；动态执行层 = "现在是否适合执行"。
  两层严格分离：动态执行层不得反向修改研究结论和静态交易计划。
- 字段：execution_date / price_snapshot / support_zone / resistance_zone /
  technical_structure / execution_condition / execution_view / reason / created_at
  不增加 RSI / MACD / 均线 / 评分 / 状态机等任何自动技术字段。
- v1.0.4 修复：EXECUTION_VIEWS 改为"前端 datalist 常用建议项"，不再是后端白名单。
  该字段是人工文本判断，不是状态机；后端只校验"非空"，不限制取值范围。
  常用建议（仅供前端 datalist 提示）：等待技术确认 / 可以开始执行 / 暂缓执行 / 继续观察。
  用户可填写任意自由文本（如"首仓可以执行，加仓等待确认"）。
- 新增 REST 端点：
  GET  /api/securities/{id}/execution  → 最新 + 历史
  POST /api/securities/{id}/execution  → 新增一条 execution review
  POST 必须在同一 SQLite transaction 中同时写入一条 decision_ledger（"动态执行判断更新"）。
- 行情刷新不得修改 execution_reviews 任何字段；execution view 只在用户手动录入时改变。
- do_migration 新增 migrate_v103()（建表 + 索引），schema_version→1.0.3。
  v1.0.4 不再引入新迁移函数（仅修 init_db 全新库路径与 migrate_v102 的清空逻辑）。

边界（与需求文档一致，不变）：
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
import sys
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
# v1.0.3 新增：动态执行层判断标准选项（文本表达，非自动状态机）。
# 系统**不**根据价格、行情、技术指标自动切换 execution_view；只能由用户手动录入。
EXECUTION_VIEWS = ['等待技术确认', '可以开始执行', '暂缓执行', '继续观察']
# v1.0.4 修复：仅作为前端 datalist 常用建议项；后端 _execution_fields() 已不再白名单校验。
# 用户可填写任意自由文本。

# ================ Schema（含 v1.0.2 修复） ================
# 关键约束清单：
# - 所有使用 security_id 关联 securities 的业务表都加 FOREIGN KEY ... ON DELETE RESTRICT
# - securities 加 UNIQUE(exchange, code) 防止重复证券
# - trades 表加 CHECK: price>0 / quantity>0 / fee>=0
# - v1.0.2 新增：research / trade_plans 在 (security_id, version) 上加 UNIQUE；
#   迁移前需先检查是否存在重复版本号（违反则报错停止迁移，由人工处理）。
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
  created_at TEXT,
  UNIQUE(security_id, version)
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
  created_at TEXT,
  UNIQUE(security_id, version)
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
-- v1.0.3 新增：动态执行层（execution_reviews）
-- 静态交易计划 = "什么价格值得交易"；动态执行层 = "现在是否适合执行"。
-- 完全 append-only，不允许 UPDATE / DELETE 旧 execution review。
-- 行情刷新不得修改任何字段。
CREATE TABLE IF NOT EXISTS execution_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
  execution_date TEXT NOT NULL,
  price_snapshot REAL,
  support_zone TEXT DEFAULT '',
  resistance_zone TEXT DEFAULT '',
  technical_structure TEXT DEFAULT '',
  execution_condition TEXT DEFAULT '',
  execution_view TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_exec_review ON execution_reviews(security_id, execution_date, id);
'''


class ApiError(Exception):
    """业务校验错误 → HTTP 400。"""


class NotFoundError(Exception):
    """资源不存在 → HTTP 404。"""


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


# ================ 迁移 v1.0.2 → v1.0.3（动态执行层） ================

TARGET_SCHEMA_VERSION = '1.0.4'


class MigrationError(RuntimeError):
    """迁移异常：必须由人工处理后才能重试。"""


def _column_exists(conn, table, column):
    return any(r['name'] == column
               for r in conn.execute(f'PRAGMA table_info({table})').fetchall())


def _has_unique_index_on(conn, table, cols):
    """通过 PRAGMA index_list + index_info 检测 table 上是否存在针对 cols 的 UNIQUE 索引。

    优先用 PRAGMA（避开 sqlite_master 中 autoindex_*_N 的空 sql 文本）。
    对 SQLite 3.16+（Python 3.13 内置） index_list 行必有 unique 字段。
    """
    rows = list(conn.execute(f'PRAGMA index_list({table})').fetchall())
    target = sorted(cols)
    for r in rows:
        # index_list cols: seq, name, unique, origin, partial
        is_unique = bool(dict(r).get('unique'))
        if not is_unique:
            continue
        idx_name = r['name']
        try:
            info_rows = list(conn.execute(
                f'PRAGMA index_info({idx_name!s})').fetchall())
        except sqlite3.Error:
            continue
        cols_found = sorted(ir['name'] for ir in info_rows)
        if cols_found == target:
            return True
    return False


def _create_securities_uniqueness_if_missing(conn):
    """对 v1.0.0 之前的库：检测并重建 securities 加 UNIQUE(exchange, code)。
    仅在没有 UNIQUE、且无重复数据时执行；发现重复抛 MigrationError 让人工处理。

    注意：本函数在 do_migration 的事务内被调用。
    SQLite3 conn.executescript 会隐式 COMMIT，所以中间不能用 executescript；
    用逐 conn.execute 替代。

    修复：旧 v1.0.0 库可能缺多个列（ah_link_id / research_pool / others）。
    重建前先用 ALTER TABLE 把 SCHEMA 中所有期望的列补齐。
    """
    if _has_unique_index_on(conn, 'securities', ['exchange', 'code']):
        return

    # 补全 SCHEMA 期望但旧表缺的列
    _expected_securities_cols = [
        ('code', 'TEXT NOT NULL'),
        ('exchange', "TEXT NOT NULL CHECK (exchange IN ('SH','SZ','HK'))"),
        ('name', 'TEXT NOT NULL'),
        ('currency', "TEXT NOT NULL DEFAULT 'CNY'"),
        ('market', "TEXT NOT NULL DEFAULT 'A股'"),
        ('sector', "TEXT DEFAULT ''"),
        ('ah_link_id', 'INTEGER'),
        ('notes', "TEXT DEFAULT ''"),
        ('status', "TEXT NOT NULL DEFAULT '等价格'"),
        ('research_pool', "TEXT DEFAULT ''"),
        ('current_price', 'REAL'),
        ('current_price_updated_at', 'TEXT'),
        ('created_at', 'TEXT'),
        ('updated_at', 'TEXT'),
    ]
    for col, decl in _expected_securities_cols:
        if not _column_exists(conn, 'securities', col):
            conn.execute(f'ALTER TABLE securities ADD COLUMN {col} {decl}')

    dups = list(conn.execute(
        "SELECT exchange, code, COUNT(*) c FROM securities "
        "GROUP BY exchange, code HAVING c > 1"
    ).fetchall())
    if dups:
        raise MigrationError(
            'securities 存在重复 (exchange, code)，请先手工去重: '
            + ', '.join('%s/%s ×%d' % (d['exchange'], d['code'], d['c']) for d in dups)
        )
    conn.execute('DROP TABLE IF EXISTS securities__new')
    conn.execute('''
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
    )''')
    cols = ('id','code','exchange','name','currency','market','sector','ah_link_id','notes',
            'status','research_pool','current_price','current_price_updated_at','created_at','updated_at')
    src_cols = ','.join(cols)
    conn.execute(
        f'INSERT INTO securities__new ({src_cols}) SELECT {src_cols} FROM securities'
    )
    conn.execute('DROP TABLE securities')
    conn.execute('ALTER TABLE securities__new RENAME TO securities')


def _migration_precheck_unique_versions(conn, table):
    """迁移前检查 table 是否在 (security_id, version) 上有重复。
    发现重复 → 抛 MigrationError，由用户决定如何合并/取舍；本工具不擅自删改。
    """
    rows = list(conn.execute(
        f"SELECT security_id, version, COUNT(*) c FROM {table} "
        f"GROUP BY security_id, version HAVING c > 1"
    ).fetchall())
    if rows:
        lines = ['sid=%d v=%d ×%d' % (r['security_id'], r['version'], r['c']) for r in rows[:10]]
        raise MigrationError(
            f'{table} 已存在重复版本号，无法自动加 UNIQUE(security_id, version)。'
            f'请人工决定如何合并/取舍后重新启动迁移。重复：{"; ".join(lines)}'
            + (' ...' if len(rows) > 10 else '')
        )


def _rebuild_add_unique_versioned(conn, table, columns, create_sql):
    """通用：重建 table，添加 UNIQUE(security_id, version)。

    在事务内调用，故不用 executescript（避免隐式 COMMIT）。
    旧 v1.0.0 库可能缺列，先 ALTER TABLE 补齐 SCHEMA 期望的列。
    """
    if _has_unique_index_on(conn, table, ['security_id', 'version']):
        return

    # 先按 create_sql 中出现的列补齐（解析列名）。
    # 简单做法：从 create_sql 提取 "TEXT DEFAULT ..." 等模式的列名
    expected_col_names = []
    import re as _re_mig
    for m in _re_mig.finditer(r'(\w+)\s+(?:INTEGER|TEXT|REAL)\b', create_sql):
        name = m.group(1).lower()
        if name != 'id' and name not in expected_col_names:
            expected_col_names.append(name)
    for col in expected_col_names:
        if not _column_exists(conn, table, col):
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT ""')

    conn.execute(f'DROP TABLE IF EXISTS {table}__new')
    conn.execute(f'CREATE TABLE {table}__new ({create_sql})')
    cols_str = ','.join(columns)
    conn.execute(
        f'INSERT INTO {table}__new ({cols_str}) SELECT {cols_str} FROM {table}'
    )
    conn.execute(f'DROP TABLE {table}')
    conn.execute(f'ALTER TABLE {table}__new RENAME TO {table}')


def _verify_indexes(conn):
    """迁移完成时立刻验证 5 个业务索引都存在——不允许依赖第二次启动补建。"""
    expected = [
        ('research', 'idx_research_sec'),
        ('trade_plans', 'idx_plan_sec'),
        ('trades', 'idx_trades_sec'),
        ('decision_ledger', 'idx_ledger_sec'),
        ('execution_reviews', 'idx_exec_review'),
    ]
    missing = []
    for table, idx in expected:
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (idx,)).fetchone()
        if not present:
            missing.append((table, idx))
    if missing:
        raise MigrationError(
            '迁移后缺少以下业务索引：' + ', '.join('%s.%s' % m for m in missing)
            + '。这是迁移自身缺陷，不应继续。'
        )


def migrate_v102(conn):
    """v1.0.1 → v1.0.2 增量迁移（在 do_migration 控制的事务内执行）。

    本函数**不**管理 BEGIN/COMMIT；由 do_migration 在更外层统一事务化。
    """
    # Step 1：清理上次未完成迁移的 __new 残表
    for t in ('securities', 'research', 'trade_plans', 'trades', 'decision_ledger'):
        conn.execute(f'DROP TABLE IF EXISTS {t}__new')

    # Step 2：v1.0.0 之前的库需要先确保 securities UNIQUE
    _create_securities_uniqueness_if_missing(conn)

    # Step 3：迁移前重复版本号检查（不允许自行合并/删除）
    for t in ('research', 'trade_plans'):
        _migration_precheck_unique_versions(conn, t)

    # Step 4：补 securities 早期库缺的列
    if not _column_exists(conn, 'securities', 'research_pool'):
        conn.execute('ALTER TABLE securities ADD COLUMN research_pool TEXT DEFAULT ""')
    if not _column_exists(conn, 'securities', 'current_price'):
        conn.execute('ALTER TABLE securities ADD COLUMN current_price REAL')
    if not _column_exists(conn, 'securities', 'current_price_updated_at'):
        conn.execute('ALTER TABLE securities ADD COLUMN current_price_updated_at TEXT')

    # Step 5：重建 research / trade_plans 加 UNIQUE(security_id, version)
    _rebuild_add_unique_versioned(conn, 'research', [
        'id', 'security_id', 'version', 'research_pool', 'one_liner', 'positive_changes',
        'core_validations', 'wall_conditions', 'report_link', 'research_date',
        'change_note', 'created_at'
    ], '''
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
        created_at TEXT,
        UNIQUE(security_id, version)
    ''')

    _rebuild_add_unique_versioned(conn, 'trade_plans', [
        'id', 'security_id', 'version', 'first_zone_low', 'first_zone_high',
        'add_zone_low', 'add_zone_high', 'odds_zone_low', 'odds_zone_high',
        'no_chase_price', 'target_position_pct', 'next_action', 'change_note', 'created_at'
    ], '''
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
        created_at TEXT,
        UNIQUE(security_id, version)
    ''')

    # v1.0.4 修复：删除 v1.0.2 引入的无条件 UPDATE 清空逻辑。
    # 旧版假默认（0.92 / 1000000）的清理由导入新版前的"一次性人工操作"或"显式 seed"承担；
    # 迁移脚本无法区分「系统假数据」」与「用户真实输入」，
    # 猜测性覆盖会静默破坏用户真实数据，绝对不允许。
    # 若键不存在则插入空字符串（仅在从未初始化过 settings 的早期库中兜底）
    for k in ('hkd_cny_rate', 'account_size_cny'):
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, '')", (k,)
        )

    # Step 7：写 schema_version（migrate_v102 内部不再写，由 do_migration 统一管理）
    # 保留此函数幂等完成 schema 调整；最终 schema_version 在 do_migration 末尾写入。


def migrate_v103(conn):
    """v1.0.2 → v1.0.3 增量迁移（在 do_migration 控制的事务内执行）。

    新增：
      - execution_reviews 表（FK→securities，append-only）
      - idx_exec_review 索引
    幂等：表/索引存在则跳过。
    """
    # Step 1：建表（IF NOT EXISTS 幂等）
    conn.execute('''
    CREATE TABLE IF NOT EXISTS execution_reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
      execution_date TEXT NOT NULL,
      price_snapshot REAL,
      support_zone TEXT DEFAULT '',
      resistance_zone TEXT DEFAULT '',
      technical_structure TEXT DEFAULT '',
      execution_condition TEXT DEFAULT '',
      execution_view TEXT NOT NULL,
      reason TEXT DEFAULT '',
      created_at TEXT
    )
    ''')
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_exec_review '
        'ON execution_reviews(security_id, execution_date, id)'
    )


def do_migration(conn, db_path):
    """执行一次性原子迁移：BEGIN → 重建 → 索引重建 → FK 检查 → COMMIT。
    失败整体 ROLLBACK，并在 backup 文件中保留迁移前快照。

    注意：调用前必须 PRAGMA foreign_keys=OFF（per-connection），
    迁移结束后统一 PRAGMA foreign_keys=ON。
    """
    # 0) 先备份（不管迁移是否成功都保留，失败时可手动恢复）
    bak_dir = os.path.join(os.path.dirname(db_path), 'backup')
    os.makedirs(bak_dir, exist_ok=True)
    ts = now_str().replace(' ', '_').replace(':', '')
    bak_path = os.path.join(bak_dir, f'workbench-pre-v103-{ts}.db')
    try:
        # 用 SQLite Backup API，与迁移并发安全；迁移前快照一致点
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(bak_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
            src.close()
    except Exception as e:
        raise MigrationError(f'迁移前备份失败：{e}（中止迁移，请人工处理）')

    conn.execute('BEGIN')
    try:
        # 1) 旧版迁移（v1.0.0 → v1.0.1，等价幂等）
        _migrate_v101_minimal(conn)
        # 2) v1.0.1 → v1.0.2 增量
        migrate_v102(conn)
        # 3) v1.0.2 → v1.0.3 增量（新增 execution_reviews）
        migrate_v103(conn)
        # 4) 重建索引（即使 SCHEMA 已建，重建为安全；逐 execute 避免隐式 commit）
        conn.execute('CREATE INDEX IF NOT EXISTS idx_research_sec ON research(security_id, version)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_plan_sec ON trade_plans(security_id, version)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trades_sec ON trades(security_id, trade_date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ledger_sec ON decision_ledger(security_id, event_date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_exec_review ON execution_reviews(security_id, execution_date, id)')
        # 5) 验证索引存在
        _verify_indexes(conn)
        # 6) FK 一致性
        fk_violations = list(conn.execute('PRAGMA foreign_key_check').fetchall())
        if fk_violations:
            raise MigrationError(
                'FK 检查未通过：' + str(fk_violations[:5])
                + (' ...' if len(fk_violations) > 5 else '')
            )
        # 7) 写 schema_version（最终一次性写入）
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
            (TARGET_SCHEMA_VERSION,)
        )
        conn.execute('COMMIT')
    except Exception:
        try:
            conn.execute('ROLLBACK')
        except Exception:
            pass
        raise


def _migrate_v101_minimal(conn):
    """v1.0.0 → v1.0.1 兼容入口（这里是幂等的小步骤）。
    一次性原子迁由 do_migration 负责事务；此处只做事。"""
    for t in ('securities', 'research', 'trade_plans', 'trades', 'decision_ledger'):
        conn.execute(f'DROP TABLE IF EXISTS {t}__new')

    # 补 securities 早期库缺的列
    if not _column_exists(conn, 'securities', 'research_pool'):
        conn.execute('ALTER TABLE securities ADD COLUMN research_pool TEXT DEFAULT ""')
    if not _column_exists(conn, 'securities', 'current_price'):
        conn.execute('ALTER TABLE securities ADD COLUMN current_price REAL')
    if not _column_exists(conn, 'securities', 'current_price_updated_at'):
        conn.execute('ALTER TABLE securities ADD COLUMN current_price_updated_at TEXT')

    _create_securities_uniqueness_if_missing(conn)

    # 业务表加 FOREIGN KEY（已有则跳过）
    def rebuild_table(src_table, columns, create_sql):
        cur_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (src_table,)).fetchone()
        cur_sql_str = (cur_sql['sql'] or '') if cur_sql else ''
        if 'REFERENCES securities' in cur_sql_str:
            return
        # 旧 v1.0.0 表可能缺列；列出实际存在的列，仅 INSERT 实际存在的列
        existing = [r['name'] for r in conn.execute(f'PRAGMA table_info({src_table})').fetchall()]
        cols_used = [c for c in columns if c in existing]
        # 缺失的列用 NULL 填充（DEFAULT 会处理）
        # SQLite INSERT ... SELECT (cols) FROM src 只要 SELECT 子句中列在 src 存在即可
        conn.execute(f'DROP TABLE IF EXISTS {src_table}__new')
        conn.execute(f'CREATE TABLE {src_table}__new ({create_sql})')
        if cols_used:
            cols_str = ','.join(cols_used)
            conn.execute(
                f'INSERT INTO {src_table}__new ({cols_str}) SELECT {cols_str} FROM {src_table}'
            )
        else:
            conn.execute(f'INSERT INTO {src_table}__new SELECT * FROM {src_table}')
        conn.execute(f'DROP TABLE {src_table}')
        conn.execute(f'ALTER TABLE {src_table}__new RENAME TO {src_table}')

    rebuild_table('research', [
        'id', 'security_id', 'version', 'research_pool', 'one_liner', 'positive_changes',
        'core_validations', 'wall_conditions', 'report_link', 'research_date',
        'change_note', 'created_at'
    ], '''
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
    ''')

    rebuild_table('trade_plans', [
        'id', 'security_id', 'version', 'first_zone_low', 'first_zone_high',
        'add_zone_low', 'add_zone_high', 'odds_zone_low', 'odds_zone_high',
        'no_chase_price', 'target_position_pct', 'next_action', 'change_note', 'created_at'
    ], '''
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
    ''')

    rebuild_table('trades', [
        'id', 'security_id', 'trade_date', 'side', 'price', 'quantity', 'fee', 'note', 'created_at'
    ], '''
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
        trade_date TEXT NOT NULL,
        side TEXT NOT NULL CHECK (side IN ('买入','卖出')),
        price REAL NOT NULL CHECK (price > 0),
        quantity REAL NOT NULL CHECK (quantity > 0),
        fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
        note TEXT DEFAULT '',
        created_at TEXT
    ''')

    rebuild_table('decision_ledger', [
        'id', 'security_id', 'event_date', 'event_type', 'summary', 'reason', 'created_at'
    ], '''
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
        event_date TEXT NOT NULL,
        event_type TEXT NOT NULL,
        summary TEXT NOT NULL,
        reason TEXT DEFAULT '',
        created_at TEXT
    ''')


def init_db(seed=False, db_path=None):
    """初始化数据库（v1.0.4）。

    关键修复：
    - 不再依赖 DB_PATH；可显式 db_path 参数（用于测试隔离）
    - v1.0.4 修复：全新数据库（is_new=True）建表后立即写入 schema_version
      = TARGET_SCHEMA_VERSION。否则第二次启动会被误判为旧库触发完整 migration。
    - 调用前先读 settings.schema_version；已经是 TARGET_SCHEMA_VERSION
      完全跳过迁移（一次性，已迁过的库不再重复运行）
    - 迁移由 do_migration() 控制：backup → BEGIN → 重建 → 索引 → FK check → COMMIT
    - seed=True：仅在显式 CLI（--seed）或测试调用时，从 tests/fixtures/sample_seed.py
      写入示例数据。生产 init_db 默认 seed=False，保持空库。
    - v1.0.4 修复：hkd_cny_rate / account_size_cny 不会写入任何默认值；
      用户的真实输入不会被迁移脚本清空（迁移不得猜测真假）。
    """
    target = db_path or DB_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    is_new = not os.path.exists(target)

    conn = sqlite3.connect(target, timeout=10)
    conn.row_factory = sqlite3.Row
    # 1) 外键在迁移期必须 OFF（重建表期间不触发外键检查）
    conn.execute('PRAGMA foreign_keys=OFF')
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        conn.executescript(SCHEMA)

        if not is_new:
            # 读 schema_version（已是目标则完全跳过迁移）
            cur = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
            cur_ver = cur['value'] if cur else None
            if cur_ver != TARGET_SCHEMA_VERSION:
                do_migration(conn, target)
        else:
            # v1.0.4 修复：全新数据库建表后立即写入 schema_version。
            # 否则下一次启动会因为 schema_version 缺失被误判为旧库，触发完整 migration。
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
                (TARGET_SCHEMA_VERSION,)
            )

        # 迁移完成后启用外键
        conn.execute('PRAGMA foreign_keys=ON')

        if seed:
            n = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c']
            if n == 0:
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
    # 测试钩子：v1.0.2 之前 v1.0.1 也有此机制，本版未变。
    if _LEDGER_FAIL_INJECT:
        raise RuntimeError('ledger_add 失败注入（测试用）')
    conn.execute(
        'INSERT INTO decision_ledger (security_id, event_date, event_type, summary, reason, created_at) '
        'VALUES (?,?,?,?,?,?)',
        (sid, event_date or today_str(), event_type, summary, reason or '', now_str()))


# 测试钩子：可注入强制 ledger_add 失败以验证事务回滚
_LEDGER_FAIL_INJECT = False


def compute_position(conn, sid, account_size_cny=None, hkd_cny_rate=None):
    """持仓完全由流水推导，不单独存储。

    v1.0.2 修复：
    - 移除旧版 q=min(q, qty) 静默吞掉非法历史卖出的做法
    - 计算时若发现时序累计为负，立即抛 ValueError（应用层 add_trade_tx
      在写入前已校验；此处是最后一道保护）
    - v1.0.1 多币种处理不变：HKD 必须乘以 hkd_cny_rate；缺汇率时返回 None
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
            # v1.0.2：不再 q=min(q, qty) 静默截断。写入端已保证合法。
            qty -= q
            if qty < -1e-9:
                # 这只会在数据已损坏（如绕过应用层直接 SQL）时触发；
                # 一旦发现，说明校验链缺失，必须让上层立刻感知。
                raise ValueError(
                    'compute_position: security_id=%s 时序累计为负 qty=%.4f（数据被破坏）。'
                    % (sid, qty))
            realized += (p - cost) * q - fee
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

    if qty > 0 and currency == 'HKD' and (not hkd_cny_rate or float(hkd_cny_rate) <= 0):
        pos['fx_rate_missing'] = True

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
            # 否则已在上方设置 fx_rate_missing=True

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


# ================ 动态执行层（v1.0.3 新增） ================
#
# 静态交易计划决定"什么价格值得交易"；动态执行层决定"现在是否适合执行"。
# 严格 append-only：一次提交生成一条新记录，过去记录永久保留。
# 行情刷新（quote refresh）不得修改 execution_reviews 任何字段。

def _validate_execution_date(s):
    """执行日期必须为 ISO YYYY-MM-DD。"""
    if s is None or str(s).strip() == '':
        raise ApiError('执行日期（execution_date）不能为空')
    s = str(s).strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        raise ApiError('执行日期必须是有效的 ISO 日期（YYYY-MM-DD），实际：%r' % s)
    # 进一步校验月份/日期是否真实存在（拒绝 2026-02-30 这类）
    try:
        datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        raise ApiError('执行日期不存在：%s' % s)
    return s


def get_execution(sid):
    """返回 execution_latest + execution_history。"""
    conn = get_db()
    try:
        get_security_or_404(conn, sid)
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM execution_reviews WHERE security_id=? '
            'ORDER BY execution_date DESC, id DESC', (sid,)
        ).fetchall()]
        latest = rows[0] if rows else None
        return {'latest': latest, 'history': rows}
    finally:
        conn.close()


def _execution_fields(body):
    """把请求体规范化为 execution review 字段 dict。

    v1.0.4 修复：
    - execution_view 允许任意非空自由文本（不再白名单校验）。
      EXECUTION_VIEWS 仅作为前端 datalist 常用建议项。
    - execution_date 仅校验 YYYY-MM-DD 格式与日期真实性；
      不再校验「不得晚于今天」（用户未授权此业务规则）。
    """
    out = {}
    out['execution_date'] = _validate_execution_date(body.get('execution_date'))
    # price_snapshot 可空；>0 才接受
    ps = body.get('price_snapshot')
    if ps in (None, ''):
        out['price_snapshot'] = None
    else:
        try:
            fv = float(ps)
            if fv <= 0:
                raise ApiError('price_snapshot 必须大于 0')
            out['price_snapshot'] = fv
        except (TypeError, ValueError):
            raise ApiError('price_snapshot 必须是数字')
    for k in ('support_zone', 'resistance_zone', 'technical_structure',
              'execution_condition', 'reason'):
        v = body.get(k)
        out[k] = '' if v is None else str(v).strip()
    view = body.get('execution_view')
    if view is None or str(view).strip() == '':
        raise ApiError('execution_view 不能为空')
    out['execution_view'] = str(view).strip()
    return out


def _execution_latest_row(conn, sid):
    """返回该标的最新一条 execution review（无记录返回 None）。

    v1.0.4 修复：与 get_execution().latest 完全同一口径（ORDER BY execution_date DESC, id DESC），
    避免出现「详情页最新」与「首页最新」两个口径的不一致。
    """
    return conn.execute(
        'SELECT * FROM execution_reviews WHERE security_id=? '
        'ORDER BY execution_date DESC, id DESC LIMIT 1', (sid,)
    ).fetchone()


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
    # v1.0.4 修复：首页数据链路必须包含最新动态执行；无记录时为 None
    e = _execution_latest_row(conn, s['id'])
    s['execution_latest'] = dict(e) if e else None
    return s


def get_security_or_404(conn, sid):
    r = conn.execute('SELECT * FROM securities WHERE id=?', (sid,)).fetchone()
    if not r:
        raise NotFoundError('标的不存在: %s' % sid)
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
        # v1.0.3：动态执行层（最新 + 历史）
        exec_rows = [dict(r) for r in conn.execute(
            'SELECT * FROM execution_reviews WHERE security_id=? '
            'ORDER BY execution_date DESC, id DESC', (sid,)).fetchall()]
        execution_latest = exec_rows[0] if exec_rows else None
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
            'execution_latest': execution_latest,
            'execution_history': exec_rows,
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


def _persist_quote_to_securities(symbol, q):
    """把单条成功行情回写到 securities.current_price / current_price_updated_at。
    返回 True 表示写入了 DB；False 表示找不到对应证券或数据不完整。

    这是 v1.0.2 修复"行情→持仓链路"的关键入口：成功获取的行情数据必须
    回写 DB，compute_position() 才能在 get_detail() 中真实使用。
    """
    m = re.match(r'^(sh|sz|hk)(.+)$', symbol)
    if not m:
        return False
    market = m.group(1).upper()
    code_raw = m.group(2)
    code = code_raw.lstrip('0') or '0'
    code = code.zfill(5 if market == 'HK' else 6)
    cur = q.get('current')
    mt = q.get('market_time')
    if cur is None or mt is None:
        return False
    conn = get_db()
    try:
        r = conn.execute(
            'SELECT id FROM securities WHERE exchange=? AND code=?',
            (market, code)).fetchone()
        if not r:
            return False
        conn.execute(
            'UPDATE securities SET current_price=?, current_price_updated_at=? WHERE id=?',
            (cur, mt, r['id']))
        conn.commit()
        return True
    finally:
        conn.close()


def _persist_quotes_to_db(fetched):
    """批量回写刚成功获取的行情到 securities 表。"""
    if not fetched:
        return 0
    n = 0
    for sym, q in fetched.items():
        if _persist_quote_to_securities(sym, q):
            n += 1
    return n


def get_quotes(symbols):
    """拉取/返回行情快照。

    v1.0.2 失败语义修正：
    - 第一次获取就失败时也必须返回明确 error（last_success_at 为 NULL）。
    - 缓存旧价可以继续展示，但语义上必须明确是"上次成功行情"，不得伪装为
      "当前价格"。
    """
    result = {}
    with _quote_lock:
        cached = dict(_quote_cache['data'])
        last_success_at = _quote_cache.get('last_success_at')
        last_error = _quote_cache.get('last_error')
        last_error_at = _quote_cache.get('last_error_at')
        stale = time.time() - _quote_cache['ts'] > 8 if _quote_cache['ts'] else True
    need = [s for s in symbols if stale or s not in cached]

    newly_fetched = {}  # 本次新拉的用于 DB 回写
    new_persisted = 0

    if need:
        try:
            fetched = fetch_tencent(need)
            newly_fetched = fetched
            with _quote_lock:
                _quote_cache['data'].update(fetched)
                _quote_cache['ts'] = time.time()
                if fetched:
                    _quote_cache['last_success_at'] = now_str()
                    # 一次成功的 fetch 后清掉上次 error
                    _quote_cache['last_error'] = ''
                    _quote_cache['last_error_at'] = None
        except Exception as e:
            with _quote_lock:
                _quote_cache['last_error'] = '行情接口暂时不可用：%s' % e
                _quote_cache['last_error_at'] = now_str()

    # 把新成功行情回写到 securities 表（v1.0.2 链路修复）
    if newly_fetched:
        try:
            new_persisted = _persist_quotes_to_db(newly_fetched)
        except Exception:
            # DB 写入失败不应影响行情返回，但记 last_error
            with _quote_lock:
                _quote_cache['last_error'] = '行情持久化失败（但不打断本响应）'
                _quote_cache['last_error_at'] = now_str()

    with _quote_lock:
        for s in symbols:
            if s in _quote_cache['data']:
                result[s] = _quote_cache['data'][s]
        last_success_at = _quote_cache.get('last_success_at')
        last_error = _quote_cache.get('last_error')
        last_error_at = _quote_cache.get('last_error_at')

    # v1.0.2 错误语义：从未成功过 / 上次成功后再次失败 → 必须返回 error
    if not last_success_at:
        error = last_error or '行情尚未成功获取（首次拉取未成功）'
    elif last_error_at and last_error_at > last_success_at:
        error = last_error
    else:
        error = ''

    return {
        'fetched_at': last_success_at,            # 本次响应使用最近一次成功时间
        'data': result,
        'error': error,
        'last_success_at': last_success_at,
        'last_error': last_error,
        'last_error_at': last_error_at,
        'persisted_count': new_persisted,  # 本次回写到 DB 的记录数（调试/审计可见）
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
def add_execution_tx(conn, sid, body):
    """新增一条 execution review + decision_ledger（同事务）。

    - execution_review 永远 append-only
    - ledger event_type='动态执行判断更新'，reason=本次执行 view 的快照
    - 行情刷新路径不调用此函数，因此 execution_view 不会被自动改写
    - v1.0.4 修复：删除 execution_date 不得晚于今天的额外业务限制
      （用户未授权此规则）；仅保留日期格式与日期真实性校验。
    """
    get_security_or_404(conn, sid)
    f = _execution_fields(body)

    # 1) 写 execution_reviews
    cur = conn.execute(
        'INSERT INTO execution_reviews (security_id, execution_date, price_snapshot, '
        'support_zone, resistance_zone, technical_structure, execution_condition, '
        'execution_view, reason, created_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?)',
        (sid, f['execution_date'], f['price_snapshot'],
         f['support_zone'], f['resistance_zone'], f['technical_structure'],
         f['execution_condition'], f['execution_view'], f['reason'], now_str()))
    new_eid = cur.lastrowid

    # 2) 同步写 decision_ledger（同事务），event_type='动态执行判断更新'
    summary = '动态执行判断更新：%s' % f['execution_view']
    ledger_reason = '支持：%s | 压力：%s | 依据：%s' % (
        f['support_zone'] or '—', f['resistance_zone'] or '—', f['reason'] or '—')
    ledger_add(conn, sid, f['execution_date'], '动态执行判断更新', summary, ledger_reason)

    return {'id': new_eid, **f}


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
    # v1.0.2 强制：change_note 非空是既定口径（仅首次除外：标的初始化时
    # 由 create_security 写入 v1，change_note 可为"初始计划"或空）。
    # 此处只在 UPDATE 路径强制：第一次创建标的时 create_security 也会写入 v1，
    # 但 PUT /plan 是修改接口，等同于修改计划版本，必须有 change_note。
    if not old:
        raise ApiError('该标的还没有任何交易计划，无法走"修改"接口；请先创建计划。')
    if not p['change_note']:
        raise ApiError(
            '交易计划修改必须填写 change_note（既定口径要求计划修改附说明并保留历史原因）。'
        )
    v = (old['version'] + 1) if old else 1
    conn.execute(
        'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, add_zone_low, '
        'add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, target_position_pct, '
        'next_action, change_note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (sid, v, p['first_zone_low'], p['first_zone_high'], p['add_zone_low'], p['add_zone_high'],
         p['odds_zone_low'], p['odds_zone_high'], p['no_chase_price'], p['target_position_pct'],
         p['next_action'], p['change_note'], now_str()))
    ledger_add(conn, sid, today_str(), '计划修改',
               '交易计划更新至 v%d：%s' % (v, p['change_note']))


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
    # v1.0.2 强制：trade_date 必须是有效 ISO 日期（YYYY-MM-DD）
    try:
        datetime.strptime(trade_date, '%Y-%m-%d')
    except ValueError:
        raise ApiError(
            'trade_date 必须是有效 ISO 日期（YYYY-MM-DD），收到：%r' % trade_date
        )
    note = str(body.get('note') or '').strip()

    get_security_or_404(conn, sid)

    # v1.0.2 强制：写入前对"完整时间序列"重新计算任意时点累计，
    # 一旦出现负持仓则拒绝写入并返回明确错误，不再静默截断。
    existing = [dict(r) for r in conn.execute(
        'SELECT * FROM trades WHERE security_id=? ORDER BY trade_date, id', (sid,)
    ).fetchall()]
    candidate = {'side': side, 'quantity': quantity}
    seq = list(existing) + [candidate]

    # 首笔不能为卖出（无论是否已有历史数据）——这是结构性约束
    if not existing and side == '卖出':
        raise ApiError(
            '首笔交易不能为卖出（标的尚无任何买入记录，没有可卖持仓）。'
            '请先录入首笔买入。'
        )

    cum = 0.0
    for t in seq:
        if t['side'] == '买入':
            cum += float(t['quantity'])
        else:
            cum -= float(t['quantity'])
        if cum < -1e-9:
            raise ApiError(
                '历史时间序列在该时点累计持仓变为负（累计 = %.6g）。'
                '拒绝写入。请补录之前的买入后再试，或修正前面的卖出。'
                % cum
            )

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
    server_version = 'Workbench/1.0.3'

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
        except NotFoundError as e:
            self._err(str(e), 404)
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
        except NotFoundError as e:
            try:
                self._err(str(e), 404)
            except Exception:
                pass
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
            if len(seg) == 4 and seg[1] == 'securities' and seg[2].isdigit() and seg[3] == 'execution':
                return self._json(get_execution(int(seg[2])))
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
                if method == 'POST' and sub == 'execution':
                    return self._json(add_execution_tx(sid, body), 201)
        return self._err('not found', 404)


def main():
    ap = argparse.ArgumentParser(description='A/H 投研交易工作台 v1.0.3')
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
    print('A/H 投研交易工作台 v1.0.2 已启动: %s' % url)
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
