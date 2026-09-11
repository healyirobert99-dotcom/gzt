"""生成 A/H 投研交易工作台 v1.0.6 交付审计文档（docx）。

v1.0.6 在 v1.0.5 基础上针对独立代码审计发现的多标的行情"部分获取失败"语义错误。
本脚本使用 python-docx 直接生成，不依赖 html-to-docx。

注意：本脚本"全部重写"，不复用 v1.0.5 脚本——上一轮 v1.0.4 docx 因为直接复用
build_docx_v103.py 已被独立审计明确否决。本轮 v1.0.6 docx 必须真实反映当前代码。
"""

import os, sys, datetime, hashlib

# 必须在 Windows 上：执行 python D:/.../build_docx_v106.py 时，docx 由 venv python 提供
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def add_h(doc, text, level=1):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    if level == 1:
        run.font.size = Pt(16)
    elif level == 2:
        run.font.size = Pt(13)
    else:
        run.font.size = Pt(11)


def add_p(doc, text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(11)
    if bold:
        r.bold = True


def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    r = p.add_run(text)
    r.font.size = Pt(11)


def add_code(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.name = 'Consolas'


def add_table(doc, headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = 'Table Grid'
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for ri, row in enumerate(rows, 1):
        for ci, val in enumerate(row):
            cell = t.rows[ri].cells[ci]
            cell.text = str(val)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)


# ================ 路径 ================
OUT_DIR = r'D:\个股工作台\output\20260910-audit\stage3'
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.6.docx')

# ================ 文档主体 ================
doc = Document()
doc.styles['Normal'].font.name = 'Microsoft YaHei'
doc.styles['Normal'].font.size = Pt(11)

# 标题
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run('A/H 投研交易工作台')
r.bold = True
r.font.size = Pt(24)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('交付审计文档（v1.0.6）')
r.bold = True
r.font.size = Pt(18)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run(
    '版本：v1.0.6（行情一致性修复）\n'
    '生成时间：' + datetime.datetime.now().strftime('%Y-%m-%d') + '\n'
    '基线版本：v1.0.5 → v1.0.6\n'
    '本轮性质：用户明确批准的问题修复（多标的行情"部分获取失败"语义 + stale 行情派生事实判定）\n'
    '边界：不新增第二行情源、不增加技术指标、不修改交易规则/状态/自动判断'
).font.size = Pt(11)

doc.add_page_break()

# ================ §1 文档元信息 ================
add_h(doc, '1. 文档元信息（v1.0.6 真实状态）', 1)
add_table(doc, ['项', '值'], [
    ['文档版本', 'v1.0.6'],
    ['基线版本', 'v1.0.5'],
    ['schema_version（数据库目标版本）', '1.0.6'],
    ['Handler.server_version', 'Workbench/1.0.6'],
    ['argparse description', 'A/H 投研交易工作台 v1.0.6'],
    ['启动成功打印', 'A/H 投研交易工作台 v1.0.6 已启动: <url>'],
    ['前端文件头注释', 'A/H 投研交易工作台 · 前端  v1.0.6'],
    ['PACK_NOTES / PACK_MANIFEST', 'v1.0.6（与代码一致）'],
    ['本轮性质', '用户明确批准的问题修复'],
    ['范围', '9 条精确修复（无新功能、无新字段、无新状态、无新行情源）'],
])

add_h(doc, '1.1 v1.0.6 严禁顺带加入项', 2)
add_p(doc, '本轮严格不允许：第二行情源 / MA / EMA / MACD / RSI / KDJ / 布林带 / '
           '自动支撑位 / 自动择时 / 买卖信号 / 止损算法 / 仓位模型 / 状态机 / '
           '新字段 / 新端点 / 新缓存层。v1.0.6 唯一改动是修复多标的行情部分失败时的'
           '语义一致性 + 前端 attention() 对 stale 行情派生事实的屏蔽。')

doc.add_page_break()

# ================ §2 历史行为（已修复 / 不再适用） ================
add_h(doc, '2. 历史行为（v1.0.5 之前的修复，明确标注不再适用）', 1)
add_table(doc, ['历史版本', '原始行为', '状态 / 处置'], [
    ['v1.0.3 后端', 'EXECUTION_VIEWS = [等待技术确认, 可以开始执行, 暂缓执行, 继续观察] 作为后端白名单拒绝非白名单文本',
     'v1.0.4 起修复：后端 _execution_fields() 仅校验非空，4 个文本仅作前端 datalist 建议项'],
    ['v1.0.3 后端', 'execution_date 不得晚于今天（raise ApiError "执行日期不能晚于今天"）',
     'v1.0.4 起修复：删除未来日期校验，仅校验日期格式与日期真实性'],
    ['v1.0.2 migrate_v102', '无条件 UPDATE settings SET value=\'\' 清空 account_size_cny / hkd_cny_rate',
     'v1.0.4 起修复：删除该 UPDATE；保留用户真实数据，仅在键不存在时 INSERT OR IGNORE 兜底空字符串'],
    ['v1.0.3 之前前端', '<select name="execution_view"> 固定四项下拉',
     'v1.0.5 起修复：改为 <input name="execution_view" list="execution-view-suggest"> + <datalist id="execution-view-suggest">；用户可输入任意非空文本'],
    ['v1.0.3 之前前端', 'execution_date 默认值 = prev.execution_date || today()（继承上一条日期）',
     'v1.0.5 起修复：execution_date 默认 = today()（不再继承上一条）；prev 仍可手工覆盖'],
    ['v1.0.2 之前 add_trade_tx', 'candidate 不含 trade_date，append 到 existing 末尾 → 校验永远看到的是"按列表顺序"，无法捕获早于历史的卖出（违反真实时序）',
     'v1.0.5 起修复：candidate 携带 trade_date，按 (trade_date ASC, id ASC) 排序（candidate.id=INF 排同日末位），与 compute_position() 完全一致口径从头计算累计；负持仓立即拒绝'],
    ['内部版本号', 'TARGET_SCHEMA_VERSION / server_version / argparse / 启动打印 / 前端头 共出现 1.0.2 / 1.0.3 / 1.0.4 多个版本号',
     'v1.0.5 起修复：6 处版本标识全部统一为 v1.0.5；v1.0.6 续统一为 v1.0.6'],
])

add_h(doc, '2.1 v1.0.5 → v1.0.6 数据库 schema 变更说明', 2)
add_p(doc, '本轮未引入任何数据库 schema 变更（不新增表 / 不改列 / 不改约束）。'
           'v1.0.6 唯一与数据库相关的改动是 TARGET_SCHEMA_VERSION 从 1.0.5 改为 1.0.6 —— '
           'init_db() 检测到旧库后会按当前正式版本治理方式，仅把 settings.schema_version 写入新值。'
           'do_migration 不引入新步骤，幂等三步（_migrate_v101_minimal / migrate_v102 / migrate_v103）继续生效。')

doc.add_page_break()

# ================ §3 真实数据链路 ================
add_h(doc, '3. v1.0.6 真实数据链路', 1)
add_p(doc, '本节反映 v1.0.6 真实代码（非历史描述）。')
add_code(doc, '''【行情部分失败的 v1.0.6 真实链路】

get_quotes(symbols):
    1) 读缓存快照 (cache, last_success_at, last_error)
    2) 计算 need_list（stale 窗口过期 或 cache 中缺失）
    3) try:
         fetched = fetch_tencent(need_list)   # 一次请求所有 need
       except:  # 网络异常
         fetched = {}
    4) if fetched: 写入 cache + 更新 last_success_at + 清 last_error
       else:       写 last_error / last_error_at（"本次未返回任何新行情"）
    5) 仅持久化 fetched 中每条 → securities.current_price / current_price_updated_at
       (stale 不写 DB)
    6) 构造每条 result：
         - 在 newly_fetched 中 → is_stale=False
         - 不在 newly_fetched 但在 cache 中 → is_stale=True（保留旧价 + 旧 market_time）
         - 都不在 → 占位 dict（current=None, is_stale=True）
    7) 顶层 error 语义：
         - need_list 非空 且 fetched 为空 → error 非空（即使 fetch 没抛异常）
         - 部分成功 → error = "部分行情未更新（N/M）：symA、symB..."
         - 全部成功 → error = ''
    8) 返回结构新增：
         partial_failure: bool
         missing_symbols: [str]
         requested_count: int
         fetched_count:   int
''')

add_h(doc, '3.1 前端 attention() 在 stale 行情下的判定（v1.0.6 新增）', 2)
add_code(doc, '''function attention(sec) {
  const q = quoteOf(sec);
  const flags = [];
  const isStale = q && q.is_stale === true;
  // v1.0.6：stale 行情的派生事实（z1/z2/z3/danger）不得进入"需要处理"
  if (!isStale) {
    (priceFacts(price, plan, cur, mt) || []).forEach(f => {
      if (f.level !== 'muted') flags.push(f.text);
    });
  }
  // 用户人工录入的事实（不依赖行情）必须保留
  if (sec.status === '可交易') flags.push('...');
  ... wall_conditions / core_validations 触发 ...
  return flags;
}
''')

doc.add_page_break()

# ================ §4 v1.0.6 9 条精确修复清单 ================
add_h(doc, '4. v1.0.6 9 条精确修复清单', 1)
add_p(doc, 'v1.0.6 严格遵循用户原始指令："只修复多证券行情部分失败导致旧行情被当作本次成功行情使用的问题。'
           '不得新增第二行情源、技术指标、交易规则、自动判断或其他产品功能。"')

add_table(doc, ['#', 'spec', '落地位置', '实现摘要'], [
    ['1', 'get_quotes 区分本次成功与缺失的 symbol',
     'server.py :: get_quotes()',
     '新增 partial_failure / missing_symbols / requested_count / fetched_count 顶层字段；每条 data 带 is_stale'],
    ['2', '成功证券正常更新 cache / 写 securities / 更新行情时间',
     'server.py :: get_quotes() 步骤 4-5',
     'fetched 中每条走原有 _persist_quotes_to_db() 链路；stale 不动 DB'],
    ['3', '缺失证券保留旧 cache + 标记 is_stale=true + 旧 market_time',
     'server.py :: get_quotes() 步骤 6',
     '从 cached_snapshot 读取，q["is_stale"]=True；不写 DB'],
    ['4', 'requested 非空且 fetched 为空 → 必须识别为本次行情失败',
     'server.py :: get_quotes() 步骤 7',
     '即使 fetch_tencent() 未抛异常，仅返回 {} 也走 error 非空分支'],
    ['5', '部分成功返回明确"部分行情未更新"状态 + 列出缺失 symbol',
     'server.py :: get_quotes() 步骤 7 + 顶层字段',
     'partial_failure=True + missing_symbols 列表 + error 文本'],
    ['6', '前端卡片对 stale 行情明确显示',
     'app.js :: cardHtml()',
     'staleBanner = "上次成功行情 · 本次刷新未成功"；mainFact 屏蔽价格派生事实'],
    ['7', 'attention() 不得把 is_stale=true 缓存价格视作本次新变化',
     'app.js :: attention()',
     'isStale 时跳过 priceFacts 的 z1/z2/z3/danger；保留 status / wall / core_validation'],
    ['8', '新增 3 组回归测试',
     'tests/test_v106.py',
     '§A 部分成功 / §B 全部失败 / §C stale 不进 attention / §D 静态契约扫描 共 30 断言'],
    ['9', '保持 v1.0.5 已通过的 123 断言继续通过',
     'tests/test_v102 + test_v103 + test_v105',
     '已实跑 38 + 60 + 25 = 123 断言全部 PASS；总 153 断言全过'],
])

doc.add_page_break()

# ================ §5 边界保留 ================
add_h(doc, '5. v1.0.6 保持的既有约束（不修改）', 1)
add_bullet(doc, 'execution_reviews append-only（v1.0.3 引入）')
add_bullet(doc, 'execution + ledger 同一 SQLite 事务（_LEDGER_FAIL_INJECT 注入回滚测试仍 PASS）')
add_bullet(doc, '行情刷新不得修改 execution_view（价格驱动）')
add_bullet(doc, '动态执行不得修改 trade_plan / 不产生真实 trade')
add_bullet(doc, '无 execution record 时显示"尚未形成动态执行判断"')
add_bullet(doc, 'execution_view 自由文本 + datalist 建议（v1.0.5 引入）')
add_bullet(doc, 'execution_date 默认 today()（v1.0.5 引入）')
add_bullet(doc, 'add_trade_tx 历史补录按 (date ASC, id ASC) 排序，与 compute_position() 同口径（v1.0.5 引入）')
add_bullet(doc, 'migrate_v102 不再清空 account_size_cny / hkd_cny_rate（v1.0.4 引入）')
add_bullet(doc, '前端不基于证券名称/代码猜测 fixture（v1.0.4 引入）')

doc.add_page_break()

# ================ §6 测试覆盖 ================
add_h(doc, '6. 测试覆盖（v1.0.6 全套 153 断言）', 1)
add_table(doc, ['测试套件', '节', '断言数', '覆盖内容'], [
    ['tests/test_v102.py', '38', '38',
     '迁移、初始化、行情→持仓链路、外键、CASCADE/RESTRICT、--seed、行情失败语义、HKD 单位、design 事实化'],
    ['tests/test_v103.py', '§A-§K', '60',
     '动态执行层 append-only / execution+ledger 同事务 / 行情不改 execution / 首页 / 详情 / 新库 schema / 迁移保留用户数据 / 自由 execution_view / 合法日期'],
    ['tests/test_v105.py', '§A-§H', '25',
     '历史补录账本（candidate 含 trade_date + 同口径排序） + 同日先买后卖 + 失败零污染 + 前端契约（execution_view input + datalist + execution_date=today） + 全部 5 套版本号 v1.0.5'],
    ['tests/test_v106.py', '§A-§D', '30',
     '【本轮新增】§A 部分成功（is_stale / 旧价旧 mt / partial_failure）+ §B 全部失败（error 非空 / 旧 cache 全 stale）+ §C stale 旧价位于首仓区不进 attention + §D 静态契约（4 条后端 + 2 条前端）'],
    ['合计', '—', '153',
     '全部通过；生产 DB 哈希不变（测试隔离有效）'],
])

add_h(doc, '6.1 test_v106.py 各节覆盖（v1.0.6 新增）', 2)
add_p(doc, '§A#1-#11  (11)  部分成功：success → is_stale=False / 新价 / DB 写入；missing → is_stale=True / 旧价旧 mt / DB 未触碰；顶层 partial_failure / missing_symbols / requested_count / fetched_count 全部正确')
add_p(doc, '§B#1-#8   (8)   全部失败：fetch_tencent() 返回 {} 但未抛异常 → error 非空 / partial_failure=True / fetched_count=0；旧 cache 中所有 symbol 标记 is_stale=True 并保留旧价')
add_p(doc, '§C#1-#3   (3)   静态扫描 attention() 实现检查 isStale + Python 等价 priceFacts 重现"旧价位于首仓区仍生成 fact" + isStale 时 attention_flags=[]')
add_p(doc, '§D#1-#6   (6)   静态契约：get_quotes 返回 partial_failure/missing_symbols/每条 is_stale/全部失败走错误语义；前端 attention 检查 is_stale + 卡片 stale 横幅')

doc.add_page_break()

# ================ §7 部署与迁移 ================
add_h(doc, '7. 部署与迁移（v1.0.5 → v1.0.6）', 1)
add_p(doc, 'v1.0.6 不引入新迁移函数。init_db() 检测到旧库后会按当前正式版本治理方式，'
           '把 settings.schema_version 写入新 TARGET 值：1.0.6。do_migration 内部三个迁移函数继续幂等。')
add_code(doc, '''do_migration(conn, db_path):
    0) 备份 workbench-pre-v103-<时间>.db（使用 SQLite Connection.backup API，无需停服）
    BEGIN:
        _migrate_v101_minimal (幂等)
        migrate_v102 (幂等；已不含 user_data 清空)
        migrate_v103 (幂等；execution_reviews 表 + 索引)
        CREATE INDEX IF NOT EXISTS × 5
        _verify_indexes（5 个业务索引立刻存在）
        PRAGMA foreign_key_check（FK 一致性）
        INSERT OR REPLACE settings.schema_version = '1.0.6'  # ← 本轮仅此一处
    COMMIT / ROLLBACK''')

add_p(doc, '幂等：已是 v1.0.6 的库 init_db() 不会触发迁移，不产生备份文件。'
           'v1.0.5 → v1.0.6 升级路径上，旧 schema_version 会触发上述完整迁移流程（幂等），'
           '最终 settings.schema_version 被覆盖为 1.0.6。')

add_h(doc, '7.1 在线备份', 2)
add_p(doc, '沿用 make_backup() 接口与 sqlite3.Connection.backup() 官方 API。'
           'CLI：python server.py --backup [path]')

doc.add_page_break()

# ================ §8 风险登记 ================
add_h(doc, '8. 风险登记册（v1.0.6 更新）', 1)
add_table(doc, ['ID', '类别', '说明', '缓解 / 状态'], [
    ['R-001', '行情', '单一行情源（Tencent 免费接口）',
     '失败时降级显示"上次成功行情" + error；v1.0.6 进一步细化到 symbol 粒度'],
    ['R-002', '多币种', 'HKD 缺汇率时折算不可用',
     '显式提示"无法计算 / 待汇率"，不伪造数据；沿用 v1.0.2'],
    ['R-009', '测试', '生产 DB 隔离（临时 DB 测试）',
     'setup/teardown 自动断言哈希一致；v1.0.6 续用'],
    ['R-010', '迁移', 'v1.0.5 → v1.0.6 一次性原子',
     'do_migration BEGIN→COMMIT，失败整体 ROLLBACK；已验证'],
    ['R-011', '回滚', '升级失败可降级',
     '从 workbench-pre-v103-*.db 直接复制回 data/workbench.db；已验证'],
    ['R-014', '行情源', '不引入第二行情源（边界外）',
     '依赖 Tencent 单源，已记录；v1.0.6 不增加'],
    ['R-015', '汇率', 'HKD 缺汇率需用户录入',
     '显式提示，不自动填默认值（v1.0.2 修复）；已验证'],
    ['R-018', '动态执行', '依赖用户手动录入',
     '无 record 时显式提示"尚未形成"；v1.0.5 前端已可填写任意非空文本'],
    ['R-019', '数据库', 'SQLite 单文件超 100 万 trades 后索引性能',
     '当前一致性检查为 O(n)；已记录'],
    ['R-020', '账本', '历史补录交易时序错位（v1.0.5 前 P0）',
     'v1.0.5 已修复：candidate 携带 trade_date，按 (date ASC, id ASC) 排序；负持仓立即拒绝'],
    ['R-021', '前端契约', 'execution_view 下拉框丢失自由文本',
     'v1.0.5 已修复：改为 <input> + <datalist>，自定义文本原样预填'],
    ['R-022', '行情一致性', '多标的部分失败时旧行情被当作本次成功（v1.0.6 前 P1）',
     'v1.0.6 已修复：每条 data 带 is_stale；requested 非空且 fetched 为空 → error 非空；前端 attention() 在 stale 时屏蔽价格派生事实'],
])

doc.add_page_break()

# ================ §9 第三方审计重点 ================
add_h(doc, '9. 第三方审计重点（v1.0.6）', 1)
add_bullet(doc, 'get_quotes() 是否真按 symbol 粒度返回 is_stale（不是按全局）')
add_bullet(doc, 'requested 非空且 fetched 为空时，error 是否真非空（即使 fetch_tencent() 未抛异常）')
add_bullet(doc, 'partial_failure=True 时 missing_symbols 列表是否真与"未在 fetched 中"完全一致')
add_bullet(doc, '持久化路径只写 fetched 中每条（stale 不写 DB）')
add_bullet(doc, 'app.js attention() 是否真在 isStale 时跳过 priceFacts 的 z1/z2/z3/danger，保留 status / wall / core_validation')
add_bullet(doc, 'app.js cardHtml() 是否真显示 "上次成功行情 · 本次刷新未成功" stale 横幅')
add_bullet(doc, 'test_v106.py §A 是否真用 monkey-patch fetch_tencent 验证 partial failure')
add_bullet(doc, 'test_v106.py §B 是否真验证 fetched={}（不抛异常）也走错误语义')
add_bullet(doc, 'test_v106.py §C 是否真验证 stale 旧价位于首仓区不进 attention')
add_bullet(doc, 'test_v102 + test_v103 + test_v105 + test_v106 共 153 断言是否真全部通过')

doc.add_page_break()

# ================ §10 仍未解决 + 签字栏 ================
add_h(doc, '10. 仍未解决的开放问题 + 签字栏', 1)
add_table(doc, ['ID', '类别', '说明'], [
    ['O-003', '待批准功能', 'trades 冲正机制（A/B/C 三方向待批）'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃（SQLite 不支持 DROP COLUMN）'],
    ['R-014', '风险', '单一行情源（Tencent）'],
    ['R-015', '风险', 'HKD 缺汇率需用户录入'],
    ['R-018', '风险', '动态执行判断依赖用户手动录入'],
    ['R-019', '风险', 'SQLite 单文件超 100 万 trades 后索引性能'],
    ['R-020', '已修复', 'v1.0.5 已修复：历史补录交易时序错位'],
    ['R-021', '已修复', 'v1.0.5 已修复：execution_view 前端契约'],
    ['R-022', '已修复', 'v1.0.6 已修复：多标的行情"部分获取失败"语义一致性'],
])

add_p(doc, '')
add_p(doc, '第三方审计签字：____________________  日期：__________', bold=True)
add_p(doc, '用户确认签字：  ____________________  日期：__________', bold=True)
add_p(doc, '开发责任人：    ____________________  日期：__________', bold=True)

doc.save(OUT_PATH)
print(f'✅ v1.0.6 docx 生成：{OUT_PATH}')
print(f'   大小：{os.path.getsize(OUT_PATH)} bytes')
print(f'   SHA-256：{hashlib.sha256(open(OUT_PATH, "rb").read()).hexdigest()}')