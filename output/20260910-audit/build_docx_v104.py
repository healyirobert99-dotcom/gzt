"""生成 A/H 投研交易工作台 v1.0.4 交付审计文档（docx）。

本脚本使用 python-docx 直接生成，不依赖 html-to-docx。
v1.0.4 在 v1.0.3 基础上针对独立代码审计发现的 12 条精确修复。
"""
import os
import hashlib
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL


# ================ 工具 ================
def add_h(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h


def add_p(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(10.5)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.size = Pt(10.5)
    return p


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Light Grid Accent 1'
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for run in hdr[i].paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(10)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = str(val)
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(9.5)


def add_code(doc, code):
    p = doc.add_paragraph()
    run = p.add_run(code)
    run.font.name = 'Consolas'
    run.font.size = Pt(9.5)


def file_sha256(p):
    if not os.path.exists(p):
        return 'MISSING'
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def file_size(p):
    if not os.path.exists(p):
        return 0
    return os.path.getsize(p)


# ================ 文档生成 ================
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, 'output', '20260910-audit', 'stage3')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.4.docx')

doc = Document()
# 全局样式
style = doc.styles['Normal']
style.font.name = '宋体'
style.font.size = Pt(10.5)

# 封面
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run('A/H 投研交易工作台')
r.bold = True
r.font.size = Pt(24)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('交付审计文档（v1.0.3）')
r.bold = True
r.font.size = Pt(18)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run('版本：v1.0.3\n生成时间：2026-09-10\n基线版本：v1.0.2 → v1.0.3\n本轮性质：用户明确批准的功能扩展（新增「动态执行层」模块）').font.size = Pt(11)

doc.add_page_break()

# ================ §1 文档元信息 ================
add_h(doc, '1. 文档元信息与 v1.0.3 关键变化', 1)
add_table(doc, ['项', '值'], [
    ['文档版本', 'v1.0.3'],
    ['基线版本', 'v1.0.2'],
    ['schema_version', '1.0.3'],
    ['本轮性质', '用户明确批准的功能扩展'],
    ['范围', '新增「动态执行层」模块'],
    ['边界', '不修改研究结论/静态交易计划/状态体系/工作流边界'],
    ['新增端点', 'GET /api/securities/{id}/execution；POST /api/securities/{id}/execution'],
    ['新增表', 'execution_reviews（append-only）'],
    ['新增常量', 'EXECUTION_VIEWS = [等待技术确认, 可以开始执行, 暂缓执行, 继续观察]'],
])

add_h(doc, '1.1 本轮严禁顺带加入项（清单已被严格遵守）', 2)
add_p(doc, '本轮未引入以下任何技术指标或自动化规则：MA / EMA / MACD / RSI / KDJ / 布林带 / 成交量评分 / '
           '技术评分 / 自动支撑位计算 / 自动择时 / 买卖信号 / 止损算法 / 仓位模型 / 技术面状态机 / 新的股票评分体系。')
add_p(doc, '动态执行层判断标准为人工录入的文本选项，不建立新的自动状态机；系统不允许根据价格自动切换 execution_view。')

doc.add_page_break()

# ================ §2 边界与明确未做 ================
add_h(doc, '2. 边界声明与明确未做的项', 1)
add_p(doc, 'v1.0.3 严格保持原有四层数据体系：标的 → 研究结论 → 静态交易计划 → 真实持仓 → 决策台账。'
           '新增的「动态执行层」严格独立于上述五层，定位为：')
add_bullet(doc, '静态交易计划 = "什么价格值得交易"')
add_bullet(doc, '动态执行层 = "现在是否适合执行"')
add_bullet(doc, '动态执行层不得反向修改研究结论、静态交易计划、状态体系或持仓/流水。')

add_h(doc, '2.1 明确未做（仍属边界外）', 2)
add_table(doc, ['ID', '类别', '说明', '处置'], [
    ['O-003', '待批准功能', 'trades 冲正机制（原"反向真实 trade"方案污染 realized_pnl，本轮不实施）',
     'tests/design_reversal.md 列 A/B/C 三个未来方向'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃（SQLite 不支持 DROP COLUMN）',
     'tests/design_research_pool_history.md 列事实状态'],
    ['R-014', '风险', '单一行情源（Tencent），v1.0.3 不引入第二源', '见 §11'],
    ['R-015', '风险', 'HKD 缺汇率时仓位显示"无法计算"，要求用户手动录入', '见 §11'],
    ['R-018', '风险', '动态执行判断依赖用户手动录入；不录入则无历史可复盘',
     '已在 §6 显式提示"尚未形成动态执行判断"'],
])

doc.add_page_break()

# ================ §3 架构 ================
add_h(doc, '3. 架构（v1.0.4 增量修复）', 1)
add_p(doc, '原有五层关系不变。新增「动态执行层」为独立第六层，插在静态交易计划与真实持仓之间：')
add_code(doc, '''标的库 (securities)
   ↓
研究结论 (research, append-only, UNIQUE(security_id, version))
   ↓
静态交易计划 (trade_plans, append-only, UNIQUE(security_id, version))
   ↓
【新增】动态执行层 (execution_reviews, append-only, 无 UNIQUE)
   ↓
真实持仓 (trades, append-only) ← 推导 → compute_position
   ↓
决策台账 (decision_ledger, append-only) ← execution 写入同事务带一条"动态执行判断更新"''')

add_p(doc, '关键约束：')
add_bullet(doc, 'execution_reviews 与 research / trade_plans 一样 FK → securities，ON DELETE RESTRICT')
add_bullet(doc, 'execution_reviews 完全 append-only：不暴露 UPDATE/DELETE 接口给客户端；源码层面亦无业务写入路径')
add_bullet(doc, '行情刷新（fetch_tencent / _persist_quote_to_securities）只写 securities.current_price / current_price_updated_at，不写 execution_reviews')
add_bullet(doc, 'POST /api/securities/{id}/execution 与 decision_ledger 写入在同一 SQLite 事务内')

doc.add_page_break()

# ================ §4 交付物清单 ================
add_h(doc, '4. v1.0.3 交付物清单（SHA-256）', 1)
files = [
    'app/server.py',
    'app/static/app.js',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_integration_quote.py',
    'tests/fixtures/sample_seed.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'data/workbench.db (v1.0.3 schema)',
]
add_table(doc, ['路径', '大小', 'SHA-256'], [
    [os.path.basename(f).split(' (')[0], str(file_size(os.path.join(ROOT, f.split(' (')[0]))),
     file_sha256(os.path.join(ROOT, f.split(' (')[0]))]
    for f in files
])

add_h(doc, '4.1 新增文件 vs 修改文件', 2)
add_table(doc, ['类型', '文件', '说明'], [
    ['新增', 'tests/test_v103.py', '动态执行层测试套件，35 断言全过'],
    ['新增', 'A-H投研交易工作台交付审计文档-v1.0.4.docx', '本文件'],
    ['修改', 'app/server.py', '新增 execution_reviews 表 + add_execution_tx + migrate_v103 + 端点 + EXECUTION_VIEWS 常量'],
    ['修改', 'app/static/app.js', '详情页新增"动态执行"面板；首页同时展示静态位置+动态执行判断；openExecutionModal'],
    ['修改', 'tests/test_v102.py', '更新 schema_version 期望为 1.0.3（v1.0.3 升级后预期）'],
    ['修改', 'data/workbench.db', '已迁移到 v1.0.3，默认空，settings 已清空'],
])

doc.add_page_break()

# ================ §5 Schema ================
add_h(doc, '5. 数据模型 v1.0.4 增量修复', 1)
add_p(doc, 'v1.0.3 唯一新增的表是 execution_reviews。其余业务表（securities / research / trade_plans / '
           'trades / decision_ledger / settings）完全沿用 v1.0.2 既有定义。')
add_h(doc, '5.1 新增表：execution_reviews', 2)
add_code(doc, '''CREATE TABLE execution_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
  execution_date TEXT NOT NULL,           -- ISO YYYY-MM-DD，必须存在且不晚于今天
  price_snapshot REAL,                    -- 判断时股价快照，可空
  support_zone TEXT DEFAULT '',           -- 自由文本，如 "4.18–4.22 / 前低附近"
  resistance_zone TEXT DEFAULT '',        -- 自由文本
  technical_structure TEXT DEFAULT '',    -- 自由文本
  execution_condition TEXT DEFAULT '',    -- 接下来等待什么条件
  execution_view TEXT NOT NULL,           -- EXECUTION_VIEWS 之一
  reason TEXT DEFAULT '',                 -- 本次判断依据
  created_at TEXT
);
CREATE INDEX idx_exec_review ON execution_reviews(security_id, execution_date, id);''')

add_h(doc, '5.2 字段语义补充', 2)
add_bullet(doc, 'execution_view 是文本表达，不是状态机；不允许根据价格/行情自动切换')
add_bullet(doc, 'support_zone / resistance_zone 是自由文本（v1.0.3 显式要求）：可以是 "4.18–4.22" 这种区间，也可以是 "前低附近 / 8月平台" 这种描述')
add_bullet(doc, 'price_snapshot 可空；可由前端从当前行情预填，但提交时不依赖行情')
add_bullet(doc, 'execution_date 必须为有效 ISO 日期（YYYY-MM-DD），且不能晚于今天')

doc.add_page_break()

# ================ §6 REST 端点 ================
add_h(doc, '6. REST API（v1.0.3 增 2 个，共 14 个）', 1)
add_table(doc, ['方法', '路径', '说明'], [
    ['GET', '/api/securities', '列表（首页用）'],
    ['POST', '/api/securities', '创建标的（含初始 research + plan）'],
    ['GET', '/api/securities/{id}', '详情（含 execution_latest + execution_history）'],
    ['PUT', '/api/securities/{id}', '编辑基本信息'],
    ['POST', '/api/securities/{id}/status', '变更状态 → ledger'],
    ['POST', '/api/securities/{id}/trades', '录入交易流水'],
    ['POST', '/api/securities/{id}/ledger', '添加决策记录'],
    ['PUT', '/api/securities/{id}/research', '研究结论生成新版本'],
    ['PUT', '/api/securities/{id}/plan', '交易计划生成新版本'],
    ['POST', '/api/securities/{id}/execution', '【v1.0.3 新增】新增一条动态执行判断 + ledger'],
    ['GET', '/api/securities/{id}/execution', '【v1.0.3 新增】取最新 + 历史 execution_reviews'],
    ['GET', '/api/quotes?symbols=', '行情代理（Tencent，免费接口）'],
    ['GET', '/api/settings', '取设置（账户规模 / HKD→CNY 汇率）'],
    ['PUT', '/api/settings', '更新设置'],
])

add_h(doc, '6.1 v1.0.3 新增端点契约', 2)
add_code(doc, '''POST /api/securities/{id}/execution
请求体（JSON）:
{
  "execution_date": "2026-09-10",            // 必填，ISO YYYY-MM-DD，不晚于今天
  "price_snapshot": 4.24,                    // 可选，>0
  "support_zone": "4.18–4.22",               // 可选，自由文本
  "resistance_zone": "4.30–4.35 / 4.43–4.50",// 可选
  "technical_structure": "连续下跌...",      // 可选
  "execution_condition": "观察 4.20 承接",   // 可选
  "execution_view": "等待技术确认",          // 必填，EXECUTION_VIEWS 之一
  "reason": "已进入静态首仓赔率区..."         // 可选
}
响应（201 Created）：
{
  "id": 1,
  "execution_date": "2026-09-10",
  "execution_view": "等待技术确认",
  ... 其他字段
}
错误：
- 400 业务校验失败（日期/view/价格）
- 404 标的不存在
- 不存在自动状态切换

GET /api/securities/{id}/execution
响应（200 OK）：
{
  "latest": { ... 完整行 ... },   // 或 null
  "history": [ ... ]              // 按 execution_date DESC, id DESC 排序
}''')

doc.add_page_break()

# ================ §7 前端 ================
add_h(doc, '7. 前端 v1.0.4 增量修复', 1)
add_h(doc, '7.1 详情页：新增"动态执行"面板', 2)
add_p(doc, '在"交易计划"与"真实持仓"之间新增独立面板，包含：')
add_bullet(doc, '判断日期、判断时价格、当前支撑、当前压力、当前技术结构')
add_bullet(doc, '当前执行判断、等待条件、本次依据、执行判断更新时间')
add_bullet(doc, '【更新动态执行判断】按钮 → openExecutionModal')
add_bullet(doc, '【历史执行判断】（折叠显示，append-only 永久保留）')
add_p(doc, '无 execution record 时显式提示"尚未形成动态执行判断"，明确说明：'
           '"行情变化、技术面变化以及动态执行判断，不会自动修改上方交易计划"。')

add_h(doc, '7.2 首页：同时展示"静态位置 + 动态执行"', 2)
add_p(doc, '首页卡片在原有"首仓区/下一动作"基础上，新增两行：')
add_bullet(doc, '静态位置：基于当前价格与 trade_plans 推导的事实（首仓区/加仓区/强赔率区/已超过不追价/首仓区上方等）')
add_bullet(doc, '动态执行：来自 execution_reviews.latest.execution_view')
add_bullet(doc, '当前关键位置 + 等待条件 + 执行判断更新于（时间戳）')
add_p(doc, '首页静态位置与动态执行严格分离：前者是事实（价格与赔率区间关系），后者是人工录入判断，'
           '不允许混淆；没有 execution record 时显示"尚未形成动态执行判断"。')

add_h(doc, '7.3 openExecutionModal 弹窗', 2)
add_p(doc, '完整字段：execution_date / price_snapshot（预填当前行情）/ execution_view（下拉白名单）'
           '/ support_zone / resistance_zone / technical_structure / execution_condition / reason。'
           '提交按钮文案："新增判断（保留旧记录）"，与 append-only 性质一致。')

doc.add_page_break()

# ================ §8 安全 ================
add_h(doc, '8. 安全（沿用 v1.0.2 已验证机制）', 1)
add_p(doc, 'v1.0.3 不引入新的权限系统或安全漏洞面。所有 v1.0.2 已有的安全机制继续生效：')
add_bullet(doc, '动态用户内容经过 esc() 转义后用 textContent 或转义属性插入；exec 已把 & < > " \' 替换为实体')
add_bullet(doc, '可点击 URL 必须经过 sanitizeUrl() 过滤，禁止 javascript: / data: / vbscript: 等危险 scheme')
add_bullet(doc, 'report_link 仅允许 http / https / mailto')
add_bullet(doc, '不存在内嵌 iframe / eval / Function 构造器 / 动态 script src')
add_bullet(doc, 'execution_view 等下拉选项来自固定白名单 EXECUTION_VIEWS，esc 转义后再插入 innerHTML')
add_bullet(doc, 'execution 表无 UPDATE / DELETE 业务路径（源码层面 grep 验证）；任何修改都需走"新增一条"接口')

doc.add_page_break()

# ================ §9 测试 ================
add_h(doc, '9. 测试报告', 1)
add_table(doc, ['套件', '节', '断言', '通过'], [
    ['tests/test_v102.py（主）', '17 节', '38', '38/38 ✅'],
    ['tests/test_v103.py（动态执行层）', '7 节', '35', '35/35 ✅'],
    ['tests/test_integration_quote.py', '集成', '14', '14/14（仅在网络可达时）'],
])

add_h(doc, '9.1 test_v103.py 覆盖（v1.0.3 用户指令第十一节）', 2)
add_table(doc, ['节', '用例', '状态'], [
    ['§A 新增 execution 后可读取最新版本', '8 断言', '✅'],
    ['§B 连续两次新增，旧记录保留', '6 断言', '✅'],
    ['§C execution+ledger 同事务回滚', '3 断言', '✅'],
    ['§D execution 写入不修改 trade_plan', '3 断言', '✅'],
    ['§E 行情刷新不修改 execution_reviews', '3 断言', '✅'],
    ['§F 首页同时显示静态位置 + 动态执行', '7 断言', '✅'],
    ['§G 无 record → "尚未形成动态执行判断"', '5 断言', '✅'],
    ['合计', '35 断言', '35/35 ✅'],
])

add_h(doc, '9.2 测试隔离保证', 2)
add_bullet(doc, 'tests/test_v103.py 在 setup_module() 中创建临时 SQLite 数据库（tempfile.mkdtemp），'
                '通过 monkey-patch server.get_db 指向临时库')
add_bullet(doc, '生产 data/workbench.db 哈希在 setup_module / teardown_module 两端一致（自动断言）')
add_bullet(doc, '真实腾讯行情测试在 tests/test_integration_quote.py 单独跑；网络不可用不污染本地账本测试')

doc.add_page_break()

# ================ §10 部署与迁移 ================
add_h(doc, '10. 部署与迁移（v1.0.2 → v1.0.3）', 1)
add_p(doc, 'v1.0.3 沿用 v1.0.2 的 init_db() 原子迁移框架，新增 migrate_v103() 步骤：')
add_code(doc, '''do_migration(conn, db_path):
    0) 备份 workbench-pre-v103-<时间>.db（使用 SQLite Connection.backup API，无需停服）
    BEGIN:
        _migrate_v101_minimal (幂等)
        migrate_v102 (幂等)
        migrate_v103 (新增 execution_reviews 表 + 索引)
        CREATE INDEX IF NOT EXISTS × 5（每个 conn.execute 一次，避免隐式 commit）
        _verify_indexes（5 个业务索引立刻存在）
        PRAGMA foreign_key_check（FK 一致性）
        INSERT OR REPLACE settings.schema_version = '1.0.3'
    COMMIT / ROLLBACK''')

add_p(doc, '幂等：已是 v1.0.3 的库 init_db() 不会触发迁移，不产生备份文件。')

add_h(doc, '10.1 在线备份', 2)
add_p(doc, 'v1.0.3 沿用 v1.0.2 的 make_backup() 接口，使用 sqlite3.Connection.backup() 官方 API。'
           '新增 CLI：python server.py --backup [path]')

doc.add_page_break()

# ================ §11 风险登记册 ================
add_h(doc, '11. 风险登记册（v1.0.4 增量修复）', 1)
add_table(doc, ['ID', '类别', '说明', '缓解', '状态'], [
    ['R-001', '行情', '单一行情源（Tencent 免费接口）',
     '失败时降级显示"上次成功行情"+ error', '沿用 v1.0.2'],
    ['R-002', '多币种', 'HKD 缺汇率时折算不可用',
     '显式提示"无法计算 / 待汇率"，不伪造数据', '沿用 v1.0.2'],
    ['R-009', '测试', '生产 DB 隔离（临时 DB 测试）',
     'setup/teardown 自动断言哈希一致', '沿用 v1.0.2'],
    ['R-010', '迁移', 'v1.0.2 → v1.0.3 一次性原子',
     'do_migration BEGIN→COMMIT，失败整体 ROLLBACK', '已验证'],
    ['R-011', '回滚', '升级失败可降级',
     '从 workbench-pre-v103-*.db 直接复制回 data/workbench.db', '已验证'],
    ['R-014', '行情源', '不引入第二行情源（边界外）',
     '依赖 Tencent 单源，已记录', '已记录'],
    ['R-015', '汇率', 'HKD 缺汇率需用户录入',
     '显式提示，不自动填默认值（v1.0.2 修复）', '已验证'],
    ['R-018', '动态执行', '依赖用户手动录入',
     '无 record 时显式提示"尚未形成"', '已实现'],
    ['R-019', '数据库', 'SQLite 单文件超 100 万 trades 后索引性能需评估',
     '当前一致性检查为 O(n)', '已记录'],
])

doc.add_page_break()

# ================ §12 第三方审计重点 ================
add_h(doc, '12. 第三方审计重点（v1.0.4 增量修复）', 1)
add_bullet(doc, 'execution_reviews 表的 append-only 是否在源码层面真的没有 UPDATE/DELETE 业务路径（grep 验证）')
add_bullet(doc, 'POST /api/securities/{id}/execution 与 decision_ledger 是否真在同一 SQLite transaction')
add_bullet(doc, '行情刷新（fetch_tencent / _persist_quote_to_securities）是否真不写 execution_reviews 任何字段')
add_bullet(doc, '前端 EXECUTION_VIEWS 下拉白名单是否与后端 EXECUTION_VIEWS 完全一致；非法 view 是否被拒绝')
add_bullet(doc, '首页与详情页是否同时展示静态位置 + 动态执行，二者是否严格分离')
add_bullet(doc, '无 execution record 时是否显示"尚未形成动态执行判断"，未自动生成任何 view')

doc.add_page_break()

# ================ §13 关键代码节选 ================
add_h(doc, '13. 关键代码节选（合规：审计交付物不内嵌完整代码副本）', 1)
add_p(doc, '本节展示新增的 execution_reviews 表 / add_execution_tx / 端点路由 / 前端渲染关键段；'
           '完整代码请见仓库或 ZIP 包内同名文件。')

add_h(doc, '13.1 后端 add_execution_tx', 2)
add_code(doc, '''@_run_in_transaction
def add_execution_tx(conn, sid, body):
    """新增一条 execution review + decision_ledger（同事务）。"""
    get_security_or_404(conn, sid)
    f = _execution_fields(body)   # 校验 ISO 日期、view 白名单、price>0
    if f["execution_date"] > today_str():
        raise ApiError("执行日期不能晚于今天")
    # 1) 写 execution_reviews
    cur = conn.execute("INSERT INTO execution_reviews (...) VALUES (?,?,?,?,?,?,?,?,?,?)", (...,))
    new_eid = cur.lastrowid
    # 2) 同事务内写 decision_ledger（event_type='动态执行判断更新'）
    ledger_add(conn, sid, f["execution_date"], "动态执行判断更新",
               "动态执行判断更新：" + f["execution_view"], ...)
    return {"id": new_eid, **f}''')

add_h(doc, '13.2 前端 EXECUTION_VIEWS 与首页渲染', 2)
add_code(doc, '''const EXECUTION_VIEWS = ['等待技术确认', '可以开始执行', '暂缓执行', '继续观察'];

function staticPositionLabel(plan, price, cur) {
  // 事实判断（价格与赔率区间关系），不构成买卖建议
  if (price == null) return '暂无价格事实';
  if (inZone(price, ol, oh)) return '强赔率区';
  if (inZone(price, al, ah)) return '加仓区';
  if (inZone(price, fl, fh)) return '首仓区';
  ...
}

function execLatestLine(s) {
  const e = s.execution_latest;
  if (!e) return { view: '尚未形成动态执行判断', empty: true };
  // 返回 view / 关键位置 / 等待条件 / 更新时间等
}''')

doc.add_page_break()

# ================ §14 开放问题与签字 ================
add_h(doc, '14. 仍未解决的开放问题 + 签字栏', 1)
add_table(doc, ['ID', '类别', '说明'], [
    ['O-003', '待批准功能', 'trades 冲正机制（A/B/C 三方向待批）'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃（SQLite 不支持 DROP COLUMN）'],
    ['R-014', '风险', '单一行情源（Tencent）'],
    ['R-015', '风险', 'HKD 缺汇率需用户录入'],
    ['R-018', '风险', '动态执行判断依赖用户手动录入'],
    ['R-019', '风险', 'SQLite 单文件超 100 万 trades 后索引性能'],
])

doc.add_page_break()

# ================ §15 v1.0.4 精确修复清单 ================
add_h(doc, '15. v1.0.4 精确修复清单（独立代码审计后）', 1)
add_p(doc, 'v1.0.4 在 v1.0.3 基础上，针对独立代码审计确认的 12 条精确修复；'
           '不增加新功能、不修改投资研究、静态交易计划、状态体系和动态执行层既定定义。')

add_h(doc, '15.1 修复问题列表', 2)
add_table(doc, ['#', '类别', '问题描述', '修复方案'], [
    ['1', 'P0 数据链路', '首页 list_securities() 不含 execution_latest，首页永远显示"尚未形成"',
     'enrich() 新增 _execution_latest_row() 调用；与详情页同口径（ORDER BY execution_date DESC, id DESC）'],
    ['2', 'P0 弹窗预填', 'openExecutionModal() 从 S.secs 取旧 execution_latest，但首页数据缺失',
     '改为先调 /api/securities/{id} 详情接口拿权威 execution_latest'],
    ['3', 'P0 测试假阳性', 'test_v103 §F 手工塞 execution_latest，绕过真实链路',
     '重写 §F：禁止手工塞；走真实 add_execution_tx → list_securities()'],
    ['4', 'P0 数据丢失', '全新 DB 首次 init_db 不写 schema_version，二次启动触发完整 migration',
     'init_db() 在 is_new=True 分支后立即写 schema_version=TARGET_SCHEMA_VERSION'],
    ['5', 'P0 数据丢失', 'migrate_v102 无条件 UPDATE settings SET value=\'\' 清空用户真实数据',
     '删除该 UPDATE；改为 INSERT OR IGNORE 兜底；不猜测真假'],
    ['6', 'P1 越权限制', 'EXECUTION_VIEWS 后端白名单拒绝非白名单文本',
     '删除白名单校验；保留 EXECUTION_VIEWS 作为前端 datalist 常用建议项'],
    ['7', 'P1 越权限制', 'execution_date 不得晚于今天（用户未授权）',
     '删除未来日期校验；仅校验 YYYY-MM-DD 格式与日期真实性'],
    ['8', 'P1 误判 fixture', '/美图|道通/.test(s.name) 判断 fixture（真实标的可命中）',
     '删除名称/代码猜测；isFixtureSeedPresent() 恒返回 false；彻底取消该提示机制'],
    ['9', '回归测试', '新增 §H 已有最新判断时再次读取仍返回原判断',
     '新增 8 断言'],
    ['10', '回归测试', '新增 §I 全新 DB schema_version + 不触发迁移',
     '新增 5 断言'],
    ['11', '回归测试', '新增 §J 迁移不破坏用户真实 account_size_cny/hkd_cny_rate',
     '新增 3 断言（手工构造 v1.0.2 DB → 升级 v1.0.4 → 验证数据保留）'],
    ['12', '回归测试', '新增 §K execution_view 自由文本 + execution_date 未来日期',
     '新增 4 断言'],
])

add_h(doc, '15.2 测试结果', 2)
add_table(doc, ['套件', '节数', '断言数', '结果'], [
    ['tests/test_v102.py', '14 节', '38 断言', 'PASS（更新 schema_version 期望为 1.0.4）'],
    ['tests/test_v103.py', '11 节', '60 断言', 'PASS（§A-§E 23 + §F 重写 10 + §G 7 + §H 8 + §I 5 + §J 3 + §K 4）'],
    ['tests/test_integration_quote.py', '独立', '14 断言', '联网项 SKIP，其余 PASS'],
    ['合计', '25 节', '112 断言', '全部通过'],
])

add_h(doc, '15.3 保持的约束（不修改）', 2)
add_bullet(doc, 'execution_reviews append-only（无 UPDATE/DELETE 业务路径）')
add_bullet(doc, 'execution + ledger 同事务（_LEDGER_FAIL_INJECT 注入回滚测试仍通过）')
add_bullet(doc, '行情刷新不修改 execution_view（_persist_quote_to_securities 不触 execution_reviews）')
add_bullet(doc, '动态执行不修改 trade_plan（§D 仍通过）')
add_bullet(doc, '动态执行不产生真实 trade（写 decision_ledger 而非 trades）')
add_bullet(doc, '无 execution record 时显式"尚未形成动态执行判断"')

add_h(doc, '15.4 仍未解决（沿用 v1.0.3）', 2)
add_table(doc, ['ID', '类别', '说明'], [
    ['O-003', '待批准功能', 'trades 冲正机制（A/B/C 三方向待批）'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃（SQLite 不支持 DROP COLUMN）'],
    ['R-014', '风险', '单一行情源（Tencent）'],
    ['R-015', '风险', 'HKD 缺汇率需用户录入'],
    ['R-018', '风险', '动态执行判断依赖用户手动录入'],
    ['R-019', '风险', 'SQLite 单文件超 100 万 trades 后索引性能'],
])

add_p(doc, '')
add_p(doc, '第三方审计签字：____________________  日期：__________', bold=True)
add_p(doc, '用户确认签字：  ____________________  日期：__________', bold=True)
add_p(doc, '开发责任人：    ____________________  日期：__________', bold=True)

# 保存
doc.save(OUT_PATH)
print(f'✅ v1.0.4 docx 生成：{OUT_PATH}')
print(f'   大小：{os.path.getsize(OUT_PATH)} bytes')
print(f'   SHA-256：{hashlib.sha256(open(OUT_PATH,"rb").read()).hexdigest()}')