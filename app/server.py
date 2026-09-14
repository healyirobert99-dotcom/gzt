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

v1.0.7 新增（用户明确批准）：「导入与更新」交互层
- 复用现有 securities / research / trade_plans / execution_reviews / decision_ledger
  数据结构和正式写入逻辑（create_security_tx / update_research_tx / update_plan_tx /
  add_execution_tx + ledger_add）。**不修改数据库结构、不改动既有写入函数**。
- 两个独立入口：
  ① "导入研究结果"（format=ah-workbench-import）—— 一次导入一只或多只标的的
     identity + 可选 status + research + trade_plan + 可选 execution；
  ② "快速更新动态执行"（format=ah-workbench-execution）—— 仅给已有标的追加一条 execution。
- 固定流程：粘贴 JSON → preview_import（仅解析+对比+生成 diff）→ 用户确认 →
  commit_import（事务原子化走正式写入链路）。预读+确认前禁止触库。
- 证券识别只用 exchange + code，禁止用公司名猜测。
- 差异对比（必须规则）：
  · status 字段：若导入值与库内当前不同，必须单独在 preview 中要求用户"再次确认"，
    不允许 import 模块自动覆盖；
  · research：与最新版本逐字段对比；内容相同 → 不生成新版本；
    内容变化 → 走 update_research_tx（append-only，旧版永久保留）；
    若该标的尚无研究 → create_security_tx 已隐含建立 v1；
  · trade_plan：与最新版本逐字段对比；内容相同 → 不生成新版本；
    内容变化 → 走 update_plan_tx（append-only）；
    若该标的尚无计划 → 同上隐含建立 v1；
  · execution：永远 append-only；不可用 import 模块改写已有 execution。
- 批量导入一致性：任何一项在 commit 阶段失败 → 整体 ROLLBACK；
  完整返回失败标的 + 原因；不得产生"半完成"状态，不得静默跳过。
- 非法 JSON / 必填缺失 / 数值非法 / 日期非法 → 在 preview 阶段全部报告，
  永不触库。
- 不实现：AI 自由文本解析、Markdown 解析、LLM 解析、Excel/CSV 导入、
  文件拖拽导入、自动联网补全。只接受固定的稳定 JSON。
- 新增 REST 端点：
  POST /api/import/preview            （格式 A，预览一批研究/计划/execution）
  POST /api/import/commit             （格式 A，正式写入一批）
  POST /api/import/execution/preview  （格式 B，预览一条 execution）
  POST /api/import/execution/commit   （格式 B，正式写入一条 execution）
- 不得修改 execution_date 默认值（由前端传）；快速更新入口找不到标的直接 400 拒绝。
- 单笔导入不得触碰 trades 表（trades 由"录入交易流水"入口独立管理）。

v1.0.8 导入完整性封板（用户明确批准，只修问题不加模块）：
- token 改为服务端随机 token：secrets.token_urlsafe(32)，存入服务端 preview cache；
  TTL=300s；一次性（commit 成功即失效）；客户端无法构造。
  **不再把 base64(JSON) 称为"预览 token"。**
- preview 时同时保存 snapshot：涉及证券的 security_id / status /
  research 最新 version / trade_plan 最新 version / execution_latest.id。
- commit 前重新读库对照 snapshot；若 status / research version / plan version 改变，
  或原不存在的证券已出现 → 拒绝，提示"工作台数据自预览后已发生变化，请重新解析预览。"
- status 确认不来自导入 JSON：status_change_confirmed 一律忽略；
  preview 初次返回 change_confirmed 恒为 False；
  commit 请求单独携带 confirmed_status_changes（下标或 {exchange,code} 列表）。
- 同一批 securities[] 内 (exchange, code) 必须唯一，重复 → preview 整体拒绝。
- core_validations / wall_conditions 按 ah-workbench-import v1.0 固定 Schema 严格校验：
  · core_validations[] 每项 {'content': 非空文本, 'status': 跟踪中|已验证|已恶化}
  · wall_conditions[]  每项 {'content': 非空文本, 'triggered': true|false（严格布尔）}
  禁止字符串 / 数字 / null / 缺 content 的对象；不猜测、不自动转换。
- 已有证券 name != 库内 name → 预览显式提示名称不一致（仍按 exchange+code 识别），
  本轮不自动修改 name。

v1.0.9 最终并发与预览一致性修复（用户明确批准，不加业务功能、不动 Schema）：
- preview token 改为**服务端原子 claim**：在 _IMPORT_PREVIEW_LOCK 内一次性完成
  「存在性 / TTL / kind / in_flight」四项检查，并把 in_flight 原子置 True。
  已处于 in_flight 的 token → 第二个 commit 立即被拒（不再依赖"成功后失效"兜底）。
  commit 成功 → 删除 token；commit 失败 → 若未过期则释放 in_flight，允许修正后重试。
  full import 与 execution-only **共用同一机制**；不依赖前端按钮防重。
- execution_latest_id 纳入漂移检测：仅对 **execution-only 导入** 与
  **完整导入中带 execution 块的证券**生效；完整导入中不带 execution 块的证券
  不因无关的 execution 更新而被阻断。
- 「database is locked」不再伪装成 400：仅 SQLITE_BUSY / SQLITE_LOCKED
  （或等价错误文本）返回受控 409「数据库正在处理另一项写入，请稍后重试。」；
  其余 OperationalError（no such table / I/O 等）仍按 500 服务器错误处理。

v1.0.10 启动脚本交付修复（用户明确批准，无业务变更、无 Schema 变更、无接口变更）：
- 根因：v1.0.9 及更早交付包内的 启动工作台.bat 用 `set "PY=python"` + `where python`
  判定解释器。本机持久 PATH 上唯一可见的 python.exe 是
  %LOCALAPPDATA%\\Microsoft\\WindowsApps 下的 **Microsoft Store 执行别名存根**，
  `where` 会命中它 → 守卫恒为"通过" → 实际拉起的是商店存根，
  表现为双击窗口一闪而过 / 弹出应用商店。
- 修复：交付包内 启动工作台.bat 换成 ASCII-only 候选链版本 ——
  ① pinned 受管解释器 → ② 遍历受管 versions 目录 → ③ py 启动器 → ④ PATH 上的 python；
  每个候选由 :try 子程序**真跑一次** `sys.version_info >= (3,8)` 才接受，
  并显式拒绝路径含 WindowsApps 的候选。
- 路径不含任何非 ASCII 字节（用户名含中文，故统一用 %USERPROFILE% 展开），
  规避 cmd.exe 按控制台代码页逐字节解释导致的路径污染。
- **服务端本身零改动**：本版仅替换交付包内的启动脚本与随之重算的
  Manifest / 审计文档，server.py 的业务逻辑与 v1.0.9 完全一致。

边界（与需求文档一致，不变）：
  - 标的库 / 研究结论（版本化）/ 交易计划（版本化）/ 真实持仓（由流水推导）/ 交易流水（append-only）
  - 决策台账 decision_ledger（append-only）
  - 行情代理：只提供客观价格事实，不生成任何建议
  - 不重做研究、不改投资口径、不自动判断买卖
  - importer 不得修改 trades 历史 / 不得 DELETE 任何历史版本 / 不得覆盖已有
    securities 行（身份信息由"编辑基本信息"入口单独管理）

数据：../data/workbench.db (SQLite, WAL)
启动：python server.py [--port 8765] [--no-browser] [--seed] [--backup [path]]
"""
import argparse
import functools
import json
import os
import re
import secrets
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

# v1.0.7 新增：导入格式常量
IMPORT_FORMAT_FULL = 'ah-workbench-import'
IMPORT_FORMAT_EXEC_ONLY = 'ah-workbench-execution'
IMPORT_FORMAT_VERSION = '1.0'
IMPORT_KEYS_FULL = ('securities', 'format', 'format_version', 'generated_at')
IMPORT_KEYS_EXEC_ONLY = ('identity', 'execution', 'format', 'format_version')

# v1.0.8 新增：研究数组固定 Schema（ah-workbench-import v1.0 正式固定 Schema）
# core_validations[] 每项必须为 {'content': 非空文本, 'status': 三选一}
# wall_conditions[]  每项必须为 {'content': 非空文本, 'triggered': 严格布尔}
# 禁止字符串 / 数字 / null / 缺 content 的对象直接入库；不做猜测或自动转换。
VALIDATION_STATUSES = ['跟踪中', '已验证', '已恶化']

# v1.0.8 新增：服务端 preview token 参数
# preview 生成随机 token（secrets.token_urlsafe），token → preview snapshot 存在服务端内存中；
# TTL 5 分钟；commit 成功后 token 立即失效；客户端无法自行构造 token。
# v1.0.9：同一 token 并发 commit 由 cache 内的 in_flight 标记原子拦截（见 _import_cache_claim）。
IMPORT_PREVIEW_TTL_SECONDS = 300

# v1.0.9 新增：SQLite 写入冲突（SQLITE_BUSY / SQLITE_LOCKED）的受控响应。
# 只把这两类错误映射为 HTTP 409；其余 OperationalError 仍按 500 处理，
# 避免把 no such table / I/O 等真实系统故障伪装成用户输入错误。
DB_BUSY_PRIMARY_CODES = (5, 6)   # sqlite3: SQLITE_BUSY=5, SQLITE_LOCKED=6
DB_BUSY_MESSAGE = '数据库正在处理另一项写入，请稍后重试。'

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


class DbConflictError(Exception):
    """数据库写入冲突（SQLITE_BUSY / SQLITE_LOCKED）→ HTTP 409。

    v1.0.9：与 ApiError(400) 严格区分 —— 「稍后重试即可」不是用户输入错误，
    也不是服务器故障。任何把真正系统故障（no such table / I/O error）
    伪装成 400 的做法都被明确禁止。
    """


def _is_db_busy_error(e):
    """判定一个 sqlite3.OperationalError 是否属于 BUSY / LOCKED 族。

    v1.0.9：优先用 Python 3.11+ 提供的 sqlite_errorcode（扩展码取低 8 位主码，
    SQLITE_BUSY=5 / SQLITE_LOCKED=6）；退化路径才用错误文本匹配。
    其它 OperationalError（no such table、disk I/O error、database disk image
    is malformed …）必须返回 False，由上层按 500 处理。
    """
    code = getattr(e, 'sqlite_errorcode', None)
    if isinstance(code, int) and (code & 0xFF) in DB_BUSY_PRIMARY_CODES:
        return True
    msg = str(e).lower()
    return ('database is locked' in msg
            or 'database table is locked' in msg
            or 'database is busy' in msg)


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

TARGET_SCHEMA_VERSION = '1.0.10'


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


def get_quotes(symbols, force=False):
    """拉取/返回行情快照。

    v1.0.6 行情一致性修复：
    - 区分"本次成功取得行情的 symbol"与"本次请求但未取得新行情的 symbol"，
      不得把缓存旧价伪装成本次成功行情。
    - 返回的每条 data 都带 is_stale 字段：本次成功 → False；本次缺失但有缓存 → True。
    - requested 非空但 fetched 完全为空，即使 fetch_tencent() 未抛异常，也必须
      把本次视为"行情获取失败"，返回 error 非空。
    - 部分成功 → 返回 partial_failure=True + missing_symbols 列表。
    - 持久化只针对本次新成功返回的行情；stale 行情不动 DB。

    force 参数（顶栏「数据更新」按钮，本次新增）：
      默认 False —— 8 秒内同一 symbol 复用缓存，供 60 秒后台轮询使用，省流量。
      显式 True  —— 忽略缓存窗口，对本次请求的**全部** symbol 重新联网拉取。
                    没有这一条，手动点按钮会拿到几秒前的缓存却提示"已更新"，
                    按钮就成了没有语义的空壳。
    """
    result = {}
    need = list(symbols)
    newly_fetched = {}  # 本次新拉的用于 DB 回写
    new_persisted = 0
    fetch_error = None

    # 1) 读取缓存快照（在锁外构造每个 symbol 的基础 dict，避免与写缓存争锁）
    with _quote_lock:
        cached_snapshot = dict(_quote_cache['data'])
        cache_ts = _quote_cache['ts']
        last_success_at = _quote_cache.get('last_success_at')
        last_error = _quote_cache.get('last_error')
        last_error_at = _quote_cache.get('last_error_at')

    stale_window = time.time() - cache_ts > 8 if cache_ts else True
    if force:
        # 手动「数据更新」：忽略 8 秒缓存窗口，本次请求的全部 symbol 一律重拉。
        need_list = list(need)
    else:
        need_list = [s for s in need if stale_window or s not in cached_snapshot]

    # 2) 拉取本次真正需要请求的 symbol
    if need_list:
        try:
            fetched = fetch_tencent(need_list)
        except Exception as e:
            fetch_error = '行情接口暂时不可用：%s' % e
            fetched = {}
        # 写入缓存 + 记录 last_success（仅当确实有结果）
        with _quote_lock:
            if fetched:
                _quote_cache['data'].update(fetched)
                _quote_cache['last_success_at'] = now_str()
                # 只要本次有哪怕 1 条成功，就清掉 last_error
                _quote_cache['last_error'] = ''
                _quote_cache['last_error_at'] = None
            else:
                # 本次没拉到任何新行情
                _quote_cache['last_error'] = fetch_error or '行情接口返回为空（无法解析任何 symbol）'
                _quote_cache['last_error_at'] = now_str()
            _quote_cache['ts'] = time.time()
            last_success_at = _quote_cache.get('last_success_at')
            last_error = _quote_cache.get('last_error')
            last_error_at = _quote_cache.get('last_error_at')
        newly_fetched = fetched

    # 3) 持久化本次新成功行情到 DB（stale 不写）
    if newly_fetched:
        try:
            new_persisted = _persist_quotes_to_db(newly_fetched)
        except Exception:
            with _quote_lock:
                _quote_cache['last_error'] = '行情持久化失败（但不打断本响应）'
                _quote_cache['last_error_at'] = now_str()

    # 4) 构造每条结果：本次成功 → is_stale=False；本次缺失但有缓存 → is_stale=True；
    #    本次缺失且无缓存 → 仍输出 dict 但 current=None + is_stale=True。
    missing_symbols = []
    partial_failure = False
    with _quote_lock:
        for s in need:
            if s in newly_fetched:
                q = dict(newly_fetched[s])
                q['is_stale'] = False
                result[s] = q
            elif s in cached_snapshot:
                q = dict(cached_snapshot[s])
                q['is_stale'] = True
                result[s] = q
                missing_symbols.append(s)
                partial_failure = True
            else:
                # 首次就拿不到这条
                result[s] = {
                    'symbol': s,
                    'name': '',
                    'code': '',
                    'market': '',
                    'currency': '',
                    'current': None,
                    'prev_close': None,
                    'change': None,
                    'change_pct': None,
                    'market_time': None,
                    'source': 'tencent',
                    'fetched_at': None,
                    'is_stale': True,
                }
                missing_symbols.append(s)
                partial_failure = True

    # 5) 顶层 error 语义
    if need_list and not newly_fetched:
        # requested 非空但本次一条都没拿到
        if not last_success_at:
            error = last_error or '行情尚未成功获取（首次拉取未成功）'
        elif last_error_at and last_error_at > last_success_at:
            error = last_error
        else:
            error = '行情接口本次未返回任何新行情'
        partial_failure = True
    elif partial_failure:
        error = '部分行情未更新（%d/%d）：%s' % (
            len(missing_symbols), len(need),
            '、'.join(missing_symbols[:10]) + ('...' if len(missing_symbols) > 10 else '')
        )
    elif last_error_at and last_error_at > last_success_at:
        error = last_error
    else:
        error = ''

    return {
        'fetched_at': last_success_at,
        'data': result,
        'error': error,
        'last_success_at': last_success_at,
        'last_error': last_error,
        'last_error_at': last_error_at,
        'persisted_count': new_persisted,
        'partial_failure': partial_failure,
        'missing_symbols': missing_symbols,
        'requested_count': len(need),
        'fetched_count': len(newly_fetched),
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
    加上 @functools.wraps 后，外层可访问 func.__wrapped__ 走"已有 conn"分支
    （v1.0.7 导入层大事务复用此特性）。
    """
    @functools.wraps(func)
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

    # v1.0.2 起强制：写入前对"完整时间序列"重新计算任意时点累计，
    # 出现负持仓则拒绝写入并返回明确错误。
    # v1.0.5 修复：之前 candidate 只含 side+quantity，append 到 seq 末尾，
    # 若 trade_date 早于历史首笔，校验看不到真实时序下累计为负，新交易仍会
    # 被 INSERT 到 DB，事后 compute_position 才抛异常——结果是非法账本留下。
    # 现统一按 trade_date ASC + id ASC（candidate.id=INF 排同日末位）与
    # compute_position() 完全一致，从头计算累计持仓。
    existing = [dict(r) for r in conn.execute(
        'SELECT id, trade_date, side, quantity FROM trades '
        'WHERE security_id=? ORDER BY trade_date, id', (sid,)
    ).fetchall()]
    # 新候选用 float('inf') 作为 id，使其在同 trade_date 时排在既有交易之后（FIFO），
    # 但若 trade_date 早于既有，则按时间序排到前面并触发负累计校验。
    candidate = {
        'id': float('inf'),
        'trade_date': trade_date,
        'side': side,
        'quantity': quantity,
    }
    seq = sorted(existing + [candidate], key=lambda t: (t['trade_date'], t['id']))

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
                '历史时间序列在该时点（%s）累计持仓变为负（累计 = %.6g）。'
                '拒绝写入。请补录之前的买入后再试，或修正前面的卖出。'
                % (t.get('trade_date'), cum)
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


# ================ v1.0.7 导入与更新 / v1.0.8 导入完整性封板 ================
#
# 边界（与 spec 一致，不变）：
#   - 不修改 securities 的历史字段（创建新标的时除外）：name / sector / notes 等若
#     有差异，留给"编辑基本信息"入口（PUT /api/securities/{id}），不在导入层修改。
#   - research / trade_plan / execution 严格 append-only / 版本化：
#     . research: 内容相同 → 不生成新版本；变化 → update_research_tx.inner
#     . trade_plan: 内容相同 → 不生成新版本；变化 → update_plan_tx.inner
#     . execution: 永远 append-only；不得 UPDATE / DELETE 已有 execution_reviews
#   - 任何 commit 失败 → 整体 ROLLBACK，不留半完成状态；不在导入层跳过或伪造成功
#   - 不修改 trades 表（trades 由"录入交易流水"独立管理）
#   - 快速 execution 入口（format=ah-workbench-execution）只在已有 securities 上
#     新增 execution；找不到标的 → 整批拒绝（不允许 importer 自动创建）
#   - 只接受固定的稳定 JSON 格式；不做自由文本解析、不做自然语言解析
#   - 不修改 ledger 历史；每条触发都按现有 ledger_add 写台账
#
# v1.0.8 导入完整性封板（对应独立审计 9 条）：
#   1) token 改为服务端随机 token（secrets.token_urlsafe）+ preview cache + TTL(5min)
#      + 一次性失效；禁止客户端自造 token；不再称 base64(JSON) 为"预览 token"。
#   2) status 确认不来自导入 JSON：status_change_confirmed 一律忽略；
#      preview 初次返回 change_confirmed 恒为 False；
#      确认只来自 commit 请求的 confirmed_status_changes 参数。
#   3) commit 前对照 preview snapshot 重新读库；漂移 → 拒绝并提示重新 preview。
#   4) 同一批 securities[] 内 (exchange, code) 必须唯一，重复 → preview 整体拒绝。
#   5) core_validations / wall_conditions 严格固定 Schema（对象 + content 非空 +
#      status 三选一 / triggered 严格布尔）；禁止字符串等错误结构入库。
#   6) 已有证券 name 不一致 → 预览显式提示（不自动修改 name）。
#
# v1.0.9 最终并发与预览一致性修复（对应 v1.0.8 交付后验证发现的 R-027 / R-028）：
#   1) R-027 修复：_import_cache_claim 在 _IMPORT_PREVIEW_LOCK 内一次完成
#      「存在 / TTL / kind / in_flight」四项判定并**原子置位 in_flight**，
#      第二个并发 commit 立即被拒 —— 消除 TOCTOU 重复提交窗口。
#      失败 → _import_cache_release 释放；成功 → _import_cache_invalidate 删除。
#      full import 与 execution-only 共用同一机制，不依赖前端按钮防重。
#   2) execution_latest_id 纳入漂移检测（仅 execution-only 与带 execution 块的
#      完整导入；不带 execution 块时不被无关的 execution 更新阻断）。
#   3) R-028 修复：SQLITE_BUSY / SQLITE_LOCKED → HTTP 409 受控冲突响应；
#      其余 OperationalError 仍 500。

# 复用原则：
#   - 整个批次的写入在「单一 SQLite 事务」内进行（事务原子性）
#   - 内层"已有 conn"的写入路径通过 *_tx.__wrapped__ 取，保持版本号/校验/ledger
#     与现有业务写入路径完全等价（不引入新版本号规则、不引入新字段）
# ------------------------------------------------------------------------

class ImportValidationError(ApiError):
    """导入层校验/解析错误 → HTTP 400。
    继承 ApiError，handler 仍能捕获并返回 400。"""


class ImportTokenError(ImportValidationError):
    """preview token 相关错误（不存在 / 过期 / 已使用 / 非法）。
    单独一类便于前端区分"数据漂移"与"token 失效"。"""


# ---------- v1.0.8：服务端 preview cache ----------
#
# 设计要点（对应本轮 spec 第一节"真正落实两段式导入"）：
#   - token 由服务端生成（secrets.token_urlsafe），客户端无法构造；
#   - preview 时保存：token → {kind, validated, snapshot, expires_at}；
#   - snapshot 记录"当时涉及证券"的 security_id / status / research 最新 version /
#     trade_plan 最新 version / execution_latest.id；
#   - TTL = IMPORT_PREVIEW_TTL_SECONDS（5 分钟）；
#   - commit 时必须命中 cache，且未过期、未使用；
#   - commit 成功后 token 立即失效（删除）；
#   - commit 时用 snapshot 对照当前 DB，漂移 → 拒绝并要求重新 preview。
#
# v1.0.9 增补（spec 第一节）：
#   - 每个条目多一个 in_flight 标记；_import_cache_claim 在锁内一次性完成
#     「存在 / TTL / kind / in_flight」判定并置位，第二个并发 commit 直接拒绝；
#   - 失败路径 _import_cache_release 复位 in_flight（token 未过期则可重试）；
#   - full import 与 execution-only 共用同一套 claim / release / invalidate。
#
# PreviewSnapshot 结构（每个条目）：
#   {
#     'exchange': str, 'code': str,
#     'exists': bool,            # preview 当时该证券是否已存在
#     'security_id': int | None,
#     'status': str | None,
#     'research_version': int | None,
#     'plan_version': int | None,
#     'execution_latest_id': int | None,
#     'check_execution': bool,   # v1.0.9：本条目是否把 execution_latest_id 纳入漂移检测
#   }
_IMPORT_PREVIEW_CACHE = {}
_IMPORT_PREVIEW_LOCK = threading.Lock()


def _import_cache_put(kind, validated, snapshot):
    """把一次 preview 的结果放入服务端 cache，返回随机 token。"""
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _IMPORT_PREVIEW_LOCK:
        # 顺手清理过期条目（避免内存无限增长）
        for t in [k for k, v in _IMPORT_PREVIEW_CACHE.items()
                  if v['expires_at'] <= now]:
            _IMPORT_PREVIEW_CACHE.pop(t, None)
        _IMPORT_PREVIEW_CACHE[token] = {
            'kind': kind,
            'validated': validated,
            'snapshot': snapshot,
            'created_at': now,
            'expires_at': now + IMPORT_PREVIEW_TTL_SECONDS,
            # v1.0.9：同一 token 的"正在提交中"标记。
            # 由 _import_cache_claim 在锁内原子置 True，成功后随 token 一起删除，
            # 失败则由 _import_cache_release 复位。彻底消除 TOCTOU 重复提交窗口。
            'in_flight': False,
        }
    return token


def _import_token_key(token):
    """规范化 token 字面量：非空字符串才返回 strip 后的值，否则 None。

    v1.0.9：claim / release / invalidate 三处必须用同一把"钥匙"，
    否则客户端在 token 前后加空格就可能绕过一次性失效。
    """
    if not isinstance(token, str):
        return None
    tok = token.strip()
    return tok or None


def _import_cache_claim(token, expected_kind):
    """原子 claim 一次 preview 结果：校验通过则把 in_flight 置 True。

    v1.0.9（spec 第一节）——以下四项检查全部在 _IMPORT_PREVIEW_LOCK 内完成，
    与置位 in_flight 构成一个不可分割的临界区：

      1) token 存在性（未 preview / 已使用 / 已清理 → 拒绝）
      2) TTL 未过期（过期则顺手清理并拒绝）
      3) kind 与当前接口匹配
      4) 该 token 当前不在 in_flight（正在提交 → 立即拒绝第二个 commit）

    返回 cache entry（调用方只读其中的 validated / snapshot）。
    失败一律抛 ImportTokenError（HTTP 400），不泄漏任何 cache 内部结构。
    """
    tok = _import_token_key(token)
    if tok is None:
        raise ImportTokenError(
            'token 缺失或格式不合法：本接口只接受服务端 preview 返回的 token')
    now = time.time()
    with _IMPORT_PREVIEW_LOCK:
        entry = _IMPORT_PREVIEW_CACHE.get(tok)
        if entry is None:
            raise ImportTokenError(
                'token 无效：未经过 preview，或已使用 / 已过期。'
                '请重新执行「解析并预览」后再提交。')
        if entry['expires_at'] <= now:
            _IMPORT_PREVIEW_CACHE.pop(tok, None)
            raise ImportTokenError(
                'token 已过期（有效期 %d 秒）。请重新执行「解析并预览」后再提交。'
                % IMPORT_PREVIEW_TTL_SECONDS)
        if entry['kind'] != expected_kind:
            raise ImportTokenError('token 与当前接口不匹配')
        if entry.get('in_flight'):
            # 关键：第二个并发 commit 在这里被拦下，而不是等到前一个成功后
            # 才发现 token 已失效。此时前一个提交可能尚未写入任何数据。
            raise ImportTokenError(
                '该预览正在提交中，请勿重复提交。'
                '若上一次提交未返回结果，请稍后重新执行「解析并预览」。')
        entry['in_flight'] = True
        # 返回浅拷贝，避免调用方在锁外意外改写 cache 内部状态
        return {
            'kind': entry['kind'],
            'validated': entry['validated'],
            'snapshot': entry['snapshot'],
        }


def _import_cache_release(token):
    """commit 失败后的回滚路径：释放 in_flight，让用户修正后可以再次提交。

    仅当 token 仍存在且未过期时复位；已过期则直接删除（与 claim 的清理口径一致）。
    本函数永不抛异常 —— 它跑在异常处理路径上，不能掩盖原始错误。
    """
    tok = _import_token_key(token)
    if tok is None:
        return
    now = time.time()
    try:
        with _IMPORT_PREVIEW_LOCK:
            entry = _IMPORT_PREVIEW_CACHE.get(tok)
            if entry is None:
                return
            if entry['expires_at'] <= now:
                _IMPORT_PREVIEW_CACHE.pop(tok, None)
                return
            entry['in_flight'] = False
    except Exception:
        pass


def _import_cache_invalidate(token):
    """commit 成功后立即让 token 失效（一次性）。v1.0.9：连 in_flight 标记一并删除。"""
    tok = _import_token_key(token)
    if tok is None:
        return
    with _IMPORT_PREVIEW_LOCK:
        _IMPORT_PREVIEW_CACHE.pop(tok, None)


def _import_snapshot_for(conn, exchange, code):
    """读取某证券当前的"关键版本指纹"，用于漂移检测。"""
    row = conn.execute(
        'SELECT * FROM securities WHERE exchange=? AND code=?',
        (exchange, code)).fetchone()
    if row is None:
        return {
            'exchange': exchange, 'code': code,
            'exists': False,
            'security_id': None,
            'status': None,
            'research_version': None,
            'plan_version': None,
            'execution_latest_id': None,
        }
    d = dict(row)
    sid = d['id']
    r_row = current_row(conn, 'research', sid)
    p_row = current_row(conn, 'trade_plans', sid)
    e_row = _execution_latest_row(conn, sid)
    return {
        'exchange': exchange, 'code': code,
        'exists': True,
        'security_id': sid,
        'status': d['status'],
        'research_version': r_row['version'] if r_row else None,
        'plan_version': p_row['version'] if p_row else None,
        'execution_latest_id': dict(e_row)['id'] if e_row else None,
    }


def _import_snapshot_drift(conn, snapshot):
    """对照 snapshot 重新读库，返回漂移列表 [(kind, 描述), ...]（空列表 = 未漂移）。

    kind 取值：'identity'（status）、'research'、'plan'、'execution'。用于决定提示语。

    spec（v1.0.8 第三节 + v1.0.9 第三节）明确列出必须检测的漂移：
      - status 改变；
      - research 最新 version 改变；
      - trade_plan 最新 version 改变；
      - 原不存在的证券已经出现（以及反向：预览时存在、现在消失）；
      - **动态执行判断变化**：execution_latest_id 改变。

    execution 漂移的适用边界（v1.0.9 明确，避免无关阻断）：
      - snapshot 条目带 check_execution=True 时才比对：
          · ah-workbench-execution（格式 B）的 preview —— 恒为 True；
          · ah-workbench-import 中**带 execution 块**的证券 —— True；
          · ah-workbench-import 中**不带 execution 块**的证券 —— False，
            此时即使别的路径新增了 execution，也不阻断 research / trade_plan 导入。
    """
    drifts = []
    for snap in snapshot:
        cur = _import_snapshot_for(conn, snap['exchange'], snap['code'])
        label = '%s.%s' % (snap['exchange'], snap['code'])
        if not snap['exists'] and cur['exists']:
            drifts.append(('identity', '%s：预览时尚不存在，现在已被创建' % label))
            continue
        if snap['exists'] and not cur['exists']:
            drifts.append(('identity', '%s：预览时已存在，现在已被删除' % label))
            continue
        if not snap['exists']:
            continue
        if snap['status'] != cur['status']:
            drifts.append(('identity', '%s：status 由 %r 变为 %r'
                           % (label, snap['status'], cur['status'])))
        if snap['research_version'] != cur['research_version']:
            drifts.append(('research', '%s：research 最新版本由 %r 变为 %r'
                           % (label, snap['research_version'], cur['research_version'])))
        if snap['plan_version'] != cur['plan_version']:
            drifts.append(('plan', '%s：trade_plan 最新版本由 %r 变为 %r'
                           % (label, snap['plan_version'], cur['plan_version'])))
        # v1.0.9：仅当本次导入"关心"该证券的 execution 时才比对
        if snap.get('check_execution') and \
                snap['execution_latest_id'] != cur['execution_latest_id']:
            drifts.append(('execution',
                           '%s：动态执行判断（execution_latest id 由 %r 变为 %r）'
                           % (label, snap['execution_latest_id'],
                              cur['execution_latest_id'])))
    return drifts


def _import_require_no_drift(conn, snapshot):
    """漂移 → 拒绝，并按漂移类型给出准确提示语。

    v1.0.8 原文案（status / research / plan / 证券出现消失）保持逐字不变；
    v1.0.9 新增 execution 专属文案。两类同时命中时两条都给出。
    """
    drifts = _import_snapshot_drift(conn, snapshot)
    if not drifts:
        return
    heads = []
    if any(k == 'execution' for k, _ in drifts):
        heads.append('动态执行判断自预览后已发生变化，请重新解析预览。')
    if any(k != 'execution' for k, _ in drifts):
        heads.append('工作台数据自预览后已发生变化，请重新解析预览。')
    raise ImportTokenError('\n'.join(heads + [t for _, t in drifts]))


def _import_require_format(payload, expected_format):
    """校验顶层 format / format_version。"""
    if not isinstance(payload, dict):
        raise ImportValidationError('导入 JSON 必须为对象')
    fmt = payload.get('format')
    ver = payload.get('format_version')
    if fmt != expected_format:
        raise ImportValidationError(
            '不支持的 format：%r（期望：%r）' % (fmt, expected_format))
    if ver != IMPORT_FORMAT_VERSION:
        raise ImportValidationError(
            '不支持的 format_version：%r（期望：%r）' % (ver, IMPORT_FORMAT_VERSION))


def _import_validate_kv_list(items, field_name, idx):
    """v1.0.8：严格校验 core_validations / wall_conditions 的结构。

    固定 Schema（ah-workbench-import v1.0）：
      core_validations[] 每项必须是对象：
        {'content': 非空文本, 'status': '跟踪中' | '已验证' | '已恶化'}
      wall_conditions[]  每项必须是对象：
        {'content': 非空文本, 'triggered': 严格布尔}

    禁止：字符串 / 数字 / null / 数组 / 缺 content 的对象。
    不做猜测、不做自动转换（例如 'false' 字符串不会被视为 False）。
    """
    if not isinstance(items, list):
        raise ImportValidationError(
            'securities[%d].research.%s 必须是数组' % (idx, field_name))
    is_wall = (field_name == 'wall_conditions')
    for j, it in enumerate(items):
        pos = 'securities[%d].research.%s[%d]' % (idx, field_name, j)
        if not isinstance(it, dict):
            raise ImportValidationError(
                '%s 必须是对象 {"content": 非空文本, "%s": %s}；'
                '实际是 %s（禁止字符串 / 数字 / null）'
                % (pos, 'triggered' if is_wall else 'status',
                   'true|false' if is_wall else '|'.join(VALIDATION_STATUSES),
                   type(it).__name__))
        c = it.get('content')
        if not isinstance(c, str) or not c.strip():
            raise ImportValidationError('%s.content 必须是非空文本' % pos)
        if is_wall:
            t = it.get('triggered')
            # 严格布尔：不接受 0/1 / 'true' / 'false' 等
            if not isinstance(t, bool):
                raise ImportValidationError(
                    '%s.triggered 必须是 true 或 false（布尔字面量），实际是 %r'
                    % (pos, t))
        else:
            s = it.get('status')
            if not isinstance(s, str) or s.strip() not in VALIDATION_STATUSES:
                raise ImportValidationError(
                    '%s.status 必须是 %s 之一，实际是 %r'
                    % (pos, ' | '.join(VALIDATION_STATUSES), s))
    return items


def _import_research_payload(r, idx):
    """把导入 research 字典规范化（不写库）+ 必填项校验。
    复用 _research_fields 的规范化语义（json.dumps 等），但额外校验
    one_liner 非空（防止新建时给空研究）；research_date 必须是 ISO 真实日期。
    v1.0.8：core_validations / wall_conditions 按固定 Schema 严格校验结构。"""
    if not isinstance(r, dict):
        raise ImportValidationError('research 必须是对象')
    # v1.0.8：先严格结构校验（在 _research_fields 之前，避免错误结构被静默 dumps）
    _import_validate_kv_list(r.get('core_validations') or [],
                             'core_validations', idx)
    _import_validate_kv_list(r.get('wall_conditions') or [],
                             'wall_conditions', idx)
    # 复用现有校验
    norm = _research_fields(r)
    if not norm['one_liner']:
        raise ImportValidationError('research.one_liner 不能为空（一句话逻辑是研究结论的最小集）')
    # v1.0.7：导入层 JSON 校验要求日期合法
    rd = norm['research_date']
    if rd:
        try:
            datetime.strptime(rd, '%Y-%m-%d')
        except ValueError:
            raise ImportValidationError('research.research_date 不是合法 ISO 日期：%r' % rd)
    return norm


def _import_plan_payload(p):
    """规范化 trade_plan。复用 _plan_fields；额外要求 change_note 非空
    （首次新建时为"初始计划"；变更时由用户填写）。"""
    if not isinstance(p, dict):
        raise ImportValidationError('trade_plan 必须是对象')
    norm = _plan_fields(p)
    if not norm['change_note']:
        # 与 PUT /plan 等价：变更或首次都必须填写
        raise ImportValidationError(
            'trade_plan.change_note 不能为空（新建请填"初始计划"或类似说明）')
    return norm


def _import_execution_payload(e):
    """规范化 execution。复用 _execution_fields（日期/价格/非空校验）。"""
    if not isinstance(e, dict):
        raise ImportValidationError('execution 必须是对象')
    return _execution_fields(e)


def _research_equal(existing_row, norm):
    """比对已存 research 行 与 导入规范化后的 research 字段。
    字段差异 = 真实内容差异（json 字符串已规范化）；若完全相同 → 不生成新版本。
    """
    if existing_row is None:
        return False
    keys = ('research_pool', 'one_liner', 'positive_changes',
            'core_validations', 'wall_conditions', 'report_link', 'research_date')
    for k in keys:
        cur_v = existing_row.get(k) or ''
        new_v = norm.get(k) or ''
        if cur_v != new_v:
            return False
    return True


def _plan_equal(existing_row, norm):
    if existing_row is None:
        return False
    keys = ('first_zone_low', 'first_zone_high', 'add_zone_low', 'add_zone_high',
            'odds_zone_low', 'odds_zone_high', 'no_chase_price', 'target_position_pct',
            'next_action')
    for k in keys:
        cur_v = existing_row.get(k)
        new_v = norm.get(k)
        # 数值 / None 比较：None == None
        if (cur_v is None and new_v is not None) or (cur_v is not None and new_v is None):
            return False
        if cur_v is not None and new_v is not None:
            try:
                if abs(float(cur_v) - float(new_v)) > 1e-9:
                    return False
            except (TypeError, ValueError):
                if str(cur_v) != str(new_v):
                    return False
    return True


def _research_diff_summary(existing_row, norm):
    """生成可视化的字段级别差异摘要。"""
    if existing_row is None:
        return [{'field': 'ALL', 'before': '（无当前版本）', 'after': '新增 v1'}]
    keys = ('one_liner', 'positive_changes', 'core_validations',
            'wall_conditions', 'research_pool', 'report_link', 'research_date')
    changes = []
    for k in keys:
        cur_v = existing_row.get(k) or ''
        new_v = norm.get(k) or ''
        if cur_v != new_v:
            changes.append({'field': k, 'before': cur_v, 'after': new_v})
    return changes


def _plan_diff_summary(existing_row, norm):
    if existing_row is None:
        return [{'field': 'ALL', 'before': '（无当前版本）', 'after': '新增 v1'}]
    label_map = {
        'first_zone_low': '首仓区下限', 'first_zone_high': '首仓区上限',
        'add_zone_low': '加仓区下限', 'add_zone_high': '加仓区上限',
        'odds_zone_low': '强赔率区下限', 'odds_zone_high': '强赔率区上限',
        'no_chase_price': '不追价', 'target_position_pct': '目标仓位',
        'next_action': '下一动作',
    }
    keys = tuple(label_map.keys())
    changes = []
    for k in keys:
        cur_v = existing_row.get(k)
        new_v = norm.get(k)
        changed = False
        if (cur_v is None) != (new_v is None):
            changed = True
        elif cur_v is not None and new_v is not None:
            try:
                changed = abs(float(cur_v) - float(new_v)) > 1e-9
            except (TypeError, ValueError):
                changed = str(cur_v) != str(new_v)
        if changed:
            changes.append({
                'field': k, 'field_label': label_map[k],
                'before': str(cur_v) if cur_v is not None else '—',
                'after': str(new_v) if new_v is not None else '—',
            })
    return changes


# ---------- 完整格式 (ah-workbench-import) ----------
def _parse_import_full(payload):
    """只解析、不写库。返回 (validated_payload, errors)。
    errors 非空 → 整体拒绝（前端不许进入预览 / commit）。
    validated_payload 已统一化（identity/code 规范化、各业务块已校验）。"""
    errors = []
    _import_require_format(payload, IMPORT_FORMAT_FULL)
    sec_list = payload.get('securities')
    if not isinstance(sec_list, list) or not sec_list:
        raise ImportValidationError('securities 必须是非空数组')

    validated = []
    seen_identity = {}   # v1.0.8：(exchange, code) → 首次出现下标，用于同批去重
    for idx, raw in enumerate(sec_list):
        sec_errors = []
        if not isinstance(raw, dict):
            raise ImportValidationError('securities[%d] 必须是对象' % idx)

        # 1) identity
        ident = raw.get('identity')
        if not isinstance(ident, dict):
            raise ImportValidationError(
                'securities[%d].identity 必须存在且是对象' % idx)
        exchange = (ident.get('exchange') or '').strip()
        if exchange not in EXCHANGES:
            raise ImportValidationError(
                'securities[%d].identity.exchange 必须为 SH / SZ / HK，实际 %r'
                % (idx, exchange))
        try:
            code = _norm_code(ident.get('code'), exchange)
        except ApiError as e:
            raise ImportValidationError('securities[%d].identity.code：%s' % (idx, e))
        # v1.0.8：同一批 securities[] 内 (exchange, code) 必须唯一。
        # 禁止"预览两只均显示新建 → commit 后第二只变成已有证券更新"的行为。
        dup_key = (exchange, code)
        if dup_key in seen_identity:
            raise ImportValidationError(
                '同一批导入中 %s.%s 重复出现（securities[%d] 与 securities[%d]）。'
                '同一批次内 (exchange, code) 必须唯一，请合并为一只后重新提交。'
                % (exchange, code, seen_identity[dup_key], idx))
        seen_identity[dup_key] = idx
        name = (ident.get('name') or '').strip()
        if not name:
            raise ImportValidationError(
                'securities[%d].identity.name 不能为空' % idx)
        sector = (ident.get('sector') or '').strip()
        market = (ident.get('market') or '').strip()
        currency = (ident.get('currency') or '').strip()

        # 2) status（可选）
        raw_status = raw.get('status')
        status = None
        if raw_status is not None:
            status = str(raw_status).strip() or None
            if status and status not in STATUSES:
                raise ImportValidationError(
                    'securities[%d].status 必须是 %s 之一，实际 %r'
                    % (idx, STATUSES, status))

        # 3) research（可选，但新建时必传）
        norm_research = None
        if raw.get('research') is not None:
            try:
                norm_research = _import_research_payload(raw['research'], idx)
            except ApiError as e:
                raise ImportValidationError('securities[%d].research：%s' % (idx, e))

        # 4) trade_plan（可选）
        norm_plan = None
        if raw.get('trade_plan') is not None:
            try:
                norm_plan = _import_plan_payload(raw['trade_plan'])
            except ApiError as e:
                raise ImportValidationError(
                    'securities[%d].trade_plan：%s' % (idx, e))

        # 5) execution（可选）
        norm_exec = None
        if raw.get('execution') is not None:
            try:
                norm_exec = _import_execution_payload(raw['execution'])
            except ApiError as e:
                raise ImportValidationError(
                    'securities[%d].execution：%s' % (idx, e))

        # 6) v1.0.8：导入 JSON 中的 status_change_confirmed 一律忽略（软删除）。
        # 理由（spec 第二节）：导入 JSON 本身绝不能声明"用户已经确认"。
        # 状态确认只能由前端在 commit 请求中单独提交 confirmed_status_changes。
        # 这里不做任何读取，也不写入 validated —— 即使粘贴块里带了该字段也无效果。
        if 'status_change_confirmed' in raw:
            pass  # 显式忽略，不写入 validated

        validated.append({
            '__idx': idx,
            'identity': {
                'exchange': exchange, 'code': code, 'name': name,
                'sector': sector, 'market': market, 'currency': currency,
            },
            'status': status,
            'research': norm_research,
            'trade_plan': norm_plan,
            'execution': norm_exec,
        })
    return validated


def _import_full_diff(conn, validated):
    """针对 validated 列表内的每只标的，对照库生成差异预览结构。"""
    out = []
    for sec in validated:
        ident = sec['identity']
        exchange = ident['exchange']
        code = ident['code']
        name = ident['name']

        row = conn.execute(
            'SELECT * FROM securities WHERE exchange=? AND code=?',
            (exchange, code)).fetchone()
        exists = row is not None
        # v1.0.8：名称一致性检查（spec 第六节）。身份只认 exchange+code；
        # name 不一致时必须在预览中显式提示，但**不自动修改** name。
        name_current = dict(row)['name'] if row else None
        name_mismatch = bool(exists and name_current != name)
        sec_view = {
            'index': sec['__idx'],
            'exchange': exchange,
            'code': code,
            'name': name,
            'identity_name': name,
            'exists': exists,
            'security_id': dict(row)['id'] if row else None,
            'security': {
                'status_current': dict(row)['status'] if row else None,
                'sector_current': dict(row)['sector'] if row else None,
                'notes_current': dict(row)['notes'] if row else None,
                'name_current': name_current,
            } if row else None,
            # v1.0.8：显式名称不一致标记 + 可直接渲染的提示文案
            'name_mismatch': name_mismatch,
            'name_mismatch_notice': (
                '名称不一致：\n工作台：%s\n导入块：%s\n'
                '证券仍按 exchange+code 识别，请人工核对。'
                % (name_current, name)) if name_mismatch else None,
        }

        # ---- status 差异
        if exists and sec['status']:
            cur = dict(row)['status']
            sec_view['status_change'] = {
                'current': cur,
                'imported': sec['status'],
                'changed': cur != sec['status'],
                'requires_confirm': cur != sec['status'],
                # v1.0.8：preview 初次返回必须为 False。
                # 导入 JSON 无法声明"已确认"；确认只来自 commit 请求的
                # confirmed_status_changes 参数（前端勾选后单独提交）。
                'change_confirmed': False,
            }
        elif not exists and sec['status']:
            sec_view['status_change'] = {
                'current': None,
                'imported': sec['status'],
                'changed': True,
                'requires_confirm': False,  # 新建时直接采用
                'change_confirmed': False,  # v1.0.8：新建也由用户勾选后提交
                'is_new': True,
            }
        else:
            sec_view['status_change'] = None

        # ---- research 差异
        if sec['research']:
            cur_row = current_row(conn, 'research', sec_view['security_id']) if exists else None
            unchanged = (exists and cur_row is not None
                         and _research_equal(cur_row, sec['research']))
            if not exists:
                cur_version = 0
                next_version = 1
            else:
                cur_version = (cur_row['version'] if cur_row else 0)
                next_version = cur_version + 1
            sec_view['research'] = {
                'current_version': cur_version if exists else 0,
                'has_current': bool(cur_row),
                'unchanged': bool(unchanged),
                'next_version': next_version if not unchanged else cur_version,
                'fields_changed': [
                    d['field'] for d in _research_diff_summary(cur_row, sec['research'])
                ] if not unchanged else [],
                'diff_summary': _research_diff_summary(cur_row, sec['research']),
            }
        else:
            sec_view['research'] = None

        # ---- trade_plan 差异
        if sec['trade_plan']:
            cur_row = current_row(conn, 'trade_plans', sec_view['security_id']) if exists else None
            unchanged = (exists and cur_row is not None
                         and _plan_equal(cur_row, sec['trade_plan']))
            if not exists:
                cur_version = 0
                next_version = 1
            else:
                cur_version = (cur_row['version'] if cur_row else 0)
                next_version = cur_version + 1
            sec_view['trade_plan'] = {
                'current_version': cur_version if exists else 0,
                'has_current': bool(cur_row),
                'unchanged': bool(unchanged),
                'next_version': next_version if not unchanged else cur_version,
                'fields_changed': [
                    d['field'] for d in _plan_diff_summary(cur_row, sec['trade_plan'])
                ] if not unchanged else [],
                'diff_summary': _plan_diff_summary(cur_row, sec['trade_plan']),
            }
        else:
            sec_view['trade_plan'] = None

        # ---- execution 永远 append-only
        if sec['execution']:
            cur_latest = _execution_latest_row(conn, sec_view['security_id']) if exists else None
            sec_view['execution'] = {
                'will_add': True,
                'is_strictly_append_only': True,
                'previous_latest_date': dict(cur_latest)['execution_date'] if cur_latest else None,
                'previous_latest_view': dict(cur_latest)['execution_view'] if cur_latest else None,
                'to_add': sec['execution'],
            }
        else:
            sec_view['execution'] = None

        out.append(sec_view)
    return out


def preview_import_full(payload):
    """公开入口：parse → diff → 服务端生成随机 token。

    v1.0.8：token 不再是 base64(JSON)；改由 secrets.token_urlsafe 生成，
    并把 validated + snapshot（当时的证券关键版本指纹）存到服务端 cache。
    客户端拿不到也无法构造 token —— 只能原样回传。

    v1.0.9：snapshot 每个条目带 check_execution 标记 —— 仅当该证券本次**带
    execution 块**时，commit 才比对其 execution_latest_id（spec 第三节）。
    """
    validated = _parse_import_full(payload)
    conn = get_db()
    try:
        diffs = _import_full_diff(conn, validated)
        snapshot = []
        for s in validated:
            snap = _import_snapshot_for(
                conn, s['identity']['exchange'], s['identity']['code'])
            # 只有本次真的会追加 execution 的证券，才把 execution 纳入漂移检测；
            # 否则该证券的 research / trade_plan 导入不应被无关的 execution 更新阻断。
            snap['check_execution'] = bool(s.get('execution'))
            snapshot.append(snap)
    finally:
        conn.close()
    token = _import_cache_put(IMPORT_FORMAT_FULL, validated, snapshot)
    warnings = []
    for d in diffs:
        if d.get('name_mismatch'):
            warnings.append(d['name_mismatch_notice'])
    return {
        'token': token,
        'token_ttl_seconds': IMPORT_PREVIEW_TTL_SECONDS,
        'securities': diffs,
        'format': IMPORT_FORMAT_FULL,
        'format_version': IMPORT_FORMAT_VERSION,
        'warnings': warnings,
    }


def commit_import_full(token, confirmed_status_changes=None):
    """公开入口：校验 token → 校验 snapshot 未漂移 → 单一事务执行整批导入。

    v1.0.8：
      - token 必须存在于服务端 preview cache（未预览 / 已使用 / 已过期 → 拒绝）；
      - commit 前重新读库对照 snapshot，漂移 → 拒绝并要求重新 preview；
      - 状态确认只来自本函数的 confirmed_status_changes 参数（不接受 JSON 自述）；
      - 整批原子化：任何一项失败 → ROLLBACK → 抛 ApiError(400)；
      - 成功后 token 立即失效（一次性）。

    v1.0.9（spec 第一节）：
      - 先用 _import_cache_claim **原子占位**（存在 / TTL / kind / in_flight 一次判定）；
      - 失败路径必须 _import_cache_release 释放 in_flight，让用户修正后可重试；
      - 成功路径 _import_cache_invalidate 删除 token。
    """
    entry = _import_cache_claim(token, IMPORT_FORMAT_FULL)
    validated = entry['validated']
    snapshot = entry['snapshot']

    # v1.0.9：claim 之后的**任何**失败路径都必须释放 in_flight，
    # 包括 confirmed_status_changes 参数本身不合法（用户可修正参数后重试）。
    conn = None
    try:
        # 状态确认集合：接受 [0, 2] 形式的 index 列表，或
        # [{'exchange':..,'code':..}] 形式的身份列表。
        confirmed = set()
        if confirmed_status_changes:
            if not isinstance(confirmed_status_changes, list):
                raise ImportValidationError('confirmed_status_changes 必须是数组')
            for it in confirmed_status_changes:
                if isinstance(it, bool):
                    raise ImportValidationError('confirmed_status_changes 元素不能是布尔值')
                if isinstance(it, int):
                    confirmed.add(it)
                elif isinstance(it, str) and it.isdigit():
                    confirmed.add(int(it))
                elif isinstance(it, dict):
                    ex = (it.get('exchange') or '').strip()
                    cd = str(it.get('code') or '').strip()
                    for s in validated:
                        ident = s['identity']
                        if ident['exchange'] == ex and ident['code'] == cd:
                            confirmed.add(s['__idx'])
                else:
                    raise ImportValidationError(
                        'confirmed_status_changes 元素必须是下标(int) 或 {exchange, code}')

        conn = get_db()
        # ---- v1.0.8：漂移检测（在事务外先读一次，快速失败）
        _import_require_no_drift(conn, snapshot)
        # 一个大事务统领整批
        conn.execute('BEGIN')
        try:
            results = []
            for sec in validated:
                results.append(_import_apply_one(conn, sec, confirmed))
            conn.execute('COMMIT')
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            raise
    except Exception:
        # v1.0.9：失败即释放 in_flight（token 未过期时可修正后重试）
        _import_cache_release(token)
        raise
    finally:
        if conn is not None:
            conn.close()
    # v1.0.8：commit 成功 → token 立即失效（一次性）
    _import_cache_invalidate(token)
    return _import_full_summary(results)


def _import_apply_one(conn, sec, confirmed=None):
    """在调用方的事务内对单只标的执行正式写入（不自己开事务）。
    内层 SQL 与现有事务函数完全等价：复用 *_tx.__wrapped__ 切到"已有 conn"路径。

    v1.0.8：confirmed 是"用户已确认状态变化"的下标集合（来自 commit 请求的
    confirmed_status_changes 参数）；导入 JSON 无法自行声明已确认。
    """
    if confirmed is None:
        confirmed = set()
    idx = sec['__idx']
    ident = sec['identity']
    exchange = ident['exchange']
    code = ident['code']
    name = ident['name']
    sector = ident['sector']
    market = ident['market'] or ('港股' if exchange == 'HK' else 'A股')
    status = sec['status'] or '等价格'

    row = conn.execute(
        'SELECT * FROM securities WHERE exchange=? AND code=?',
        (exchange, code)).fetchone()
    is_new = row is None
    out = {
        'index': idx,
        'exchange': exchange,
        'code': code,
        'name': name,
        'is_new': is_new,
        'actions': {
            'created': False,
            'status_changed': False,
            'new_research_version': None,
            'new_plan_version': None,
            'new_execution_id': None,
            'unchanged_research': False,
            'unchanged_plan': False,
        }
    }

    if is_new:
        # ---- 新建标的：复用 create_security_tx 内层走完整事务化路径
        body = {
            'name': name,
            'exchange': exchange,
            'code': code,
            'sector': sector,
            'notes': '',
            'status': status,
            'market': market,
            'currency': ('HKD' if exchange == 'HK' else 'CNY'),
            'research': {
                'research_pool': '', 'one_liner': '', 'positive_changes': '',
                'core_validations': [], 'wall_conditions': [],
                'report_link': '', 'research_date': '', 'change_note': '',
            },
            'plan': {},
        }
        # 必须有 research（新建路径下 create_security_tx 不强制 research；此处强制）
        if not sec['research']:
            raise ImportValidationError(
                'securities[%d](%s.%s) 新建时必须包含 research 块（一句话逻辑必填）'
                % (idx, exchange, code))
        body['research'] = {
            'research_pool': sec['research']['research_pool'],
            'one_liner': sec['research']['one_liner'],
            'positive_changes': sec['research']['positive_changes'],
            'core_validations': json.loads(sec['research']['core_validations']),
            'wall_conditions': json.loads(sec['research']['wall_conditions']),
            'report_link': sec['research']['report_link'],
            'research_date': sec['research']['research_date'],
            'change_note': sec['research']['change_note'] or '首次深穿（导入）',
        }
        if sec['trade_plan']:
            body['plan'] = {
                'first_zone_low': sec['trade_plan']['first_zone_low'],
                'first_zone_high': sec['trade_plan']['first_zone_high'],
                'add_zone_low': sec['trade_plan']['add_zone_low'],
                'add_zone_high': sec['trade_plan']['add_zone_high'],
                'odds_zone_low': sec['trade_plan']['odds_zone_low'],
                'odds_zone_high': sec['trade_plan']['odds_zone_high'],
                'no_chase_price': sec['trade_plan']['no_chase_price'],
                'target_position_pct': sec['trade_plan']['target_position_pct'],
                'next_action': sec['trade_plan']['next_action'],
                'change_note': sec['trade_plan']['change_note'],
            }
        # 复用现有事务函数内层（不自己开事务）：
        create_security_tx_inner = create_security_tx.__wrapped__
        res = create_security_tx_inner(conn, body)
        sid = res['id']
        out['security_id'] = sid
        out['actions']['created'] = True
        # 若库内已存在同名 security（防御性），上面 CREATE 永远不会发生
    else:
        sid = dict(row)['id']
        out['security_id'] = sid
        # ---- status 变更（如有）
        cur_status = dict(row)['status']
        if sec['status'] and sec['status'] != cur_status:
            # v1.0.8：确认只来自 commit 请求的 confirmed_status_changes。
            # 导入 JSON 中的 status_change_confirmed 已被忽略，无法绕过此检查。
            if idx not in confirmed:
                raise ImportValidationError(
                    'securities[%d](%s.%s) 状态变化未在预览中确认：%s → %s。'
                    '请在预览页勾选"确认状态变化"后重新提交。'
                    % (idx, exchange, code, cur_status, sec['status']))
            # 复用现有事务内层（含 ledger 写入、校验）
            change_status_tx_inner = change_status_tx.__wrapped__
            # change_status_tx 需要 reason；导入层把"由 importer 触发"作为 reason
            change_status_tx_inner(conn, sid, {
                'status': sec['status'],
                'event_date': today_str(),
                'reason': '由导入与更新模块确认（预览页已勾选）',
            })
            out['actions']['status_changed'] = True

        # ---- research 变更（如有）
        if sec['research']:
            cur_row = current_row(conn, 'research', sid)
            if _research_equal(cur_row, sec['research']):
                out['actions']['unchanged_research'] = True
            elif cur_row is None:
                # 已有证券但还没有 research → 从 v1 开始创建（不走 update_research_tx。
                # 该路径只在数据被手工修复（缺失 research 行）时才可能命中；正常
                # 走 create_security_tx 已经创建了 v1 research。这里 INSERT 等价于
                # update_research_tx 内层路径,但允许"创建首个版本"。
                conn.execute(
                    'INSERT INTO research (security_id, version, research_pool, one_liner, '
                    'positive_changes, core_validations, wall_conditions, report_link, '
                    'research_date, change_note, created_at) '
                    'VALUES (?, 1, ?,?,?,?,?,?,?,?,?)',
                    (sid,
                     sec['research']['research_pool'], sec['research']['one_liner'],
                     sec['research']['positive_changes'],
                     sec['research']['core_validations'], sec['research']['wall_conditions'],
                     sec['research']['report_link'], sec['research']['research_date'],
                     sec['research']['change_note'] or '新建研究 v1（导入）',
                     now_str()))
                ledger_add(conn, sid, today_str(), '研究建立',
                           '新建研究结论 v1（导入）')
                out['actions']['new_research_version'] = 1
            else:
                update_research_tx_inner = update_research_tx.__wrapped__
                update_research_tx_inner(conn, sid, {
                    'research_pool': sec['research']['research_pool'],
                    'one_liner': sec['research']['one_liner'],
                    'positive_changes': sec['research']['positive_changes'],
                    'core_validations': json.loads(sec['research']['core_validations']),
                    'wall_conditions': json.loads(sec['research']['wall_conditions']),
                    'report_link': sec['research']['report_link'],
                    'research_date': sec['research']['research_date'],
                    'change_note': sec['research']['change_note'] or '导入更新（无说明）',
                })
                new_v = dict(conn.execute(
                    'SELECT MAX(version) v FROM research WHERE security_id=?', (sid,)
                ).fetchone() or {'v': 1})['v']
                out['actions']['new_research_version'] = int(new_v)

        # ---- trade_plan 变更（如有）
        if sec['trade_plan']:
            cur_row = current_row(conn, 'trade_plans', sid)
            if _plan_equal(cur_row, sec['trade_plan']):
                out['actions']['unchanged_plan'] = True
            elif cur_row is None:
                # 已有证券但还没有 trade_plan → 从 v1 开始创建（不走 update_plan_tx。
                # update_plan_tx 拒绝"修改"语义但不接受首次为空；故由导入层按
                # create_security_tx 同样的内层路径自己插入 v1，并带 ledger 记录）
                conn.execute(
                    'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, '
                    'add_zone_low, add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, '
                    'target_position_pct, next_action, change_note, created_at) '
                    'VALUES (?, 1, ?,?,?,?,?,?,?,?,?,?,?)',
                    (sid,
                     sec['trade_plan']['first_zone_low'], sec['trade_plan']['first_zone_high'],
                     sec['trade_plan']['add_zone_low'], sec['trade_plan']['add_zone_high'],
                     sec['trade_plan']['odds_zone_low'], sec['trade_plan']['odds_zone_high'],
                     sec['trade_plan']['no_chase_price'], sec['trade_plan']['target_position_pct'],
                     sec['trade_plan']['next_action'], sec['trade_plan']['change_note'],
                     now_str()))
                ledger_add(conn, sid, today_str(), '计划建立',
                           f'新建静态计划 v1（导入）：{sec["trade_plan"]["change_note"]}')
                out['actions']['new_plan_version'] = 1
            else:
                update_plan_tx_inner = update_plan_tx.__wrapped__
                update_plan_tx_inner(conn, sid, {
                    'first_zone_low': sec['trade_plan']['first_zone_low'],
                    'first_zone_high': sec['trade_plan']['first_zone_high'],
                    'add_zone_low': sec['trade_plan']['add_zone_low'],
                    'add_zone_high': sec['trade_plan']['add_zone_high'],
                    'odds_zone_low': sec['trade_plan']['odds_zone_low'],
                    'odds_zone_high': sec['trade_plan']['odds_zone_high'],
                    'no_chase_price': sec['trade_plan']['no_chase_price'],
                    'target_position_pct': sec['trade_plan']['target_position_pct'],
                    'next_action': sec['trade_plan']['next_action'],
                    'change_note': sec['trade_plan']['change_note'],
                })
                new_v = dict(conn.execute(
                    'SELECT MAX(version) v FROM trade_plans WHERE security_id=?', (sid,)
                ).fetchone() or {'v': 1})['v']
                out['actions']['new_plan_version'] = int(new_v)

    # ---- execution：永远 append-only（不论新建 / 已有），复用 add_execution_tx 内层
    if sec['execution']:
        add_execution_tx_inner = add_execution_tx.__wrapped__
        e_res = add_execution_tx_inner(conn, sid, {
            'execution_date': sec['execution']['execution_date'],
            'price_snapshot': sec['execution']['price_snapshot'],
            'support_zone': sec['execution']['support_zone'],
            'resistance_zone': sec['execution']['resistance_zone'],
            'technical_structure': sec['execution']['technical_structure'],
            'execution_condition': sec['execution']['execution_condition'],
            'execution_view': sec['execution']['execution_view'],
            'reason': sec['execution']['reason'],
        })
        out['actions']['new_execution_id'] = e_res.get('id')

    # 注意：securities 行的 name/sector/notes 不在导入层修改。
    # 如库内 name != 导入 name → 仅在 preview 中提示，不写库。
    return out


def _import_full_summary(results):
    """根据各 apply_one 的结果聚合最终统计。"""
    created = sum(1 for r in results if r['actions'].get('created'))
    status_changed = sum(1 for r in results if r['actions'].get('status_changed'))
    new_research = sum(1 for r in results if r['actions'].get('new_research_version'))
    new_plan = sum(1 for r in results if r['actions'].get('new_plan_version'))
    new_exec = sum(1 for r in results if r['actions'].get('new_execution_id'))
    unchanged = sum(
        1 for r in results
        if r['actions'].get('unchanged_research') and r['actions'].get('unchanged_plan')
    )
    return {
        'securities': results,
        'created_count': created,
        'status_changed_count': status_changed,
        'new_research_versions': new_research,
        'new_plan_versions': new_plan,
        'new_executions': new_exec,
        'unchanged_skipped': unchanged,
        'total': len(results),
    }


# ---------- 仅 execution 格式 (ah-workbench-execution) ----------
def _parse_import_execution(payload):
    """格式 B：identity + execution。"""
    _import_require_format(payload, IMPORT_FORMAT_EXEC_ONLY)
    ident = payload.get('identity')
    exec_b = payload.get('execution')
    if not isinstance(ident, dict):
        raise ImportValidationError('identity 必须存在且是对象')
    if not isinstance(exec_b, dict):
        raise ImportValidationError('execution 必须存在且是对象')
    exchange = (ident.get('exchange') or '').strip()
    if exchange not in EXCHANGES:
        raise ImportValidationError(
            'identity.exchange 必须为 SH / SZ / HK，实际 %r' % exchange)
    try:
        code = _norm_code(ident.get('code'), exchange)
    except ApiError as e:
        raise ImportValidationError('identity.code：%s' % e)
    norm_exec = _import_execution_payload(exec_b)
    return {
        'identity': {'exchange': exchange, 'code': code},
        'execution': norm_exec,
    }


def preview_import_execution(payload):
    """格式 B 的 preview：定位已有证券 + 显示即将新增 execution 字段。
    找不到证券 → 整批拒绝，明确告知走"导入研究结果"入口。

    v1.0.8：token 由服务端随机生成（不再 base64(JSON)），并保存 snapshot。
    """
    validated = _parse_import_execution(payload)
    conn = get_db()
    try:
        ex = validated['identity']['exchange']
        cd = validated['identity']['code']
        row = conn.execute(
            'SELECT * FROM securities WHERE exchange=? AND code=?',
            (ex, cd)).fetchone()
        if not row:
            raise ImportValidationError(
                '标的尚未进入工作台，请先使用「导入研究结果」创建并完成研究结论。')
        sec_dict = dict(row)
        cur_latest = _execution_latest_row(conn, sec_dict['id'])
        prev_view = dict(cur_latest)['execution_view'] if cur_latest else None
        prev_date = dict(cur_latest)['execution_date'] if cur_latest else None
        snap = _import_snapshot_for(conn, ex, cd)
        # v1.0.9：格式 B 恒为"关心 execution"—— 本入口的全部语义就是追加 execution。
        snap['check_execution'] = True
        snapshot = [snap]
        token = _import_cache_put(IMPORT_FORMAT_EXEC_ONLY, validated, snapshot)
        return {
            'token': token,
            'token_ttl_seconds': IMPORT_PREVIEW_TTL_SECONDS,
            'security': {
                'id': sec_dict['id'],
                'exchange': sec_dict['exchange'],
                'code': sec_dict['code'],
                'name': sec_dict['name'],
                'status': sec_dict['status'],
                'current_latest_execution': {
                    'view': prev_view,
                    'date': prev_date,
                } if cur_latest else None,
            },
            'execution_to_add': validated['execution'],
            'format': IMPORT_FORMAT_EXEC_ONLY,
            'format_version': IMPORT_FORMAT_VERSION,
            'warnings': [],
        }
    finally:
        conn.close()


def commit_import_execution(token):
    """格式 B 的 commit：定位已有证券 → 走 add_execution_tx 内层。
    找不到证券 → 拒绝。

    v1.0.8：token 必须命中服务端 preview cache（未预览 / 已使用 / 已过期 → 拒绝）；
    commit 前对照 snapshot 重新读库，漂移 → 拒绝并要求重新 preview；
    成功后 token 立即失效。

    v1.0.9（spec 第一节）：与 full import **共用同一套原子 claim 机制** ——
    _import_cache_claim 在锁内一次判定「存在 / TTL / kind / in_flight」并占位，
    因此同一 token 的并发 commit 严格只有 1 次能进入写入路径。
    """
    entry = _import_cache_claim(token, IMPORT_FORMAT_EXEC_ONLY)
    validated = entry['validated']
    snapshot = entry['snapshot']

    # v1.0.9：claim 之后的任何失败都必须释放 in_flight
    conn = None
    try:
        conn = get_db()
        _import_require_no_drift(conn, snapshot)
        conn.execute('BEGIN')
        try:
            row = conn.execute(
                'SELECT * FROM securities WHERE exchange=? AND code=?',
                (validated['identity']['exchange'], validated['identity']['code'])
            ).fetchone()
            if not row:
                raise ImportValidationError(
                    '标的尚未进入工作台，请先使用「导入研究结果」创建并完成研究结论。')
            sid = dict(row)['id']
            add_execution_tx_inner = add_execution_tx.__wrapped__
            e_res = add_execution_tx_inner(conn, sid, {
                'execution_date': validated['execution']['execution_date'],
                'price_snapshot': validated['execution']['price_snapshot'],
                'support_zone': validated['execution']['support_zone'],
                'resistance_zone': validated['execution']['resistance_zone'],
                'technical_structure': validated['execution']['technical_structure'],
                'execution_condition': validated['execution']['execution_condition'],
                'execution_view': validated['execution']['execution_view'],
                'reason': validated['execution']['reason'],
            })
            conn.execute('COMMIT')
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            raise
    except Exception:
        # v1.0.9：失败即释放 in_flight（token 未过期时可修正后重试）
        _import_cache_release(token)
        raise
    finally:
        if conn is not None:
            conn.close()
    # v1.0.8：commit 成功 → token 立即失效（一次性）
    _import_cache_invalidate(token)
    return {
        'security_id': sid,
        'security_name': dict(row)['name'],
        'security_code': dict(row)['code'],
        'security_exchange': dict(row)['exchange'],
        'new_execution_id': e_res.get('id'),
    }


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
    server_version = 'Workbench/1.0.10'

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
        except DbConflictError as e:
            # v1.0.9：受控的写入冲突 → 409（稍后重试即可，不是用户输入错误）
            try:
                self._err(str(e), 409)
            except Exception:
                pass
        except sqlite3.IntegrityError as e:
            # DB CHECK / UNIQUE / NOT NULL / FOREIGN KEY 失败 → 应用层错
            try:
                self._err('数据库完整性约束失败: %s' % e, 400)
            except Exception:
                pass
        except sqlite3.OperationalError as e:
            # v1.0.9（spec 第四节）：只有 BUSY / LOCKED 才是"受控冲突"（409），
            # 其余 OperationalError（no such table / I/O / 磁盘镜像损坏 …）
            # 一律按 500 服务器错误上报，不得伪装成用户输入错误。
            if _is_db_busy_error(e):
                try:
                    self._err(DB_BUSY_MESSAGE, 409)
                except Exception:
                    pass
            else:
                try:
                    self._err('服务器错误: %s' % e, 500)
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
                # 手动「数据更新」：force=1 时绕过后端 8 秒行情缓存，强制联网重拉。
                force = (qs.get('force', [''])[0] or '').strip().lower() in ('1', 'true', 'yes', 'on')
                return self._json(get_quotes(syms, force=force))
            if seg == ['api', 'settings']:
                return self._json(get_settings())
            return self._err('not found', 404)

        # ---- POST /api/securities
        if method == 'POST' and seg == ['api', 'securities']:
            return self._json(create_security(body), 201)
        if method == 'PUT' and seg == ['api', 'settings']:
            return self._json(update_settings(body))

        # ---- v1.0.7 导入与更新（4 个端点，v1.0.8 强化 token 与确认语义）----
        if method == 'POST' and seg == ['api', 'import', 'preview']:
            return self._json(preview_import_full(body))
        if method == 'POST' and seg == ['api', 'import', 'commit']:
            # v1.0.8：状态确认必须来自请求体单独的 confirmed_status_changes，
            # 而不是粘贴 JSON 里的 status_change_confirmed。
            return self._json(commit_import_full(
                body.get('token'), body.get('confirmed_status_changes')))
        if method == 'POST' and seg == ['api', 'import', 'execution', 'preview']:
            return self._json(preview_import_execution(body))
        if method == 'POST' and seg == ['api', 'import', 'execution', 'commit']:
            return self._json(commit_import_execution(body.get('token')))

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
    ap = argparse.ArgumentParser(description='A/H 投研交易工作台 v1.0.10')
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
    print('A/H 投研交易工作台 v1.0.10 已启动: %s' % url)
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
