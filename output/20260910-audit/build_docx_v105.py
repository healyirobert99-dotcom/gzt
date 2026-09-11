"""生成 A/H 投研交易工作台 v1.0.5 交付审计文档（docx）。

本脚本使用 python-docx 直接生成，不依赖 html-to-docx。
v1.0.5 在 v1.0.4 基础上针对独立代码审计发现的真实账本错误 + 前端契约漏洞
+ 内部版本号混乱进行 8 条精确修复。
绝不沿用 v1.0.3 / v1.0.4 docx 的"小补丁式"复用。
"""
import os
import hashlib
import datetime
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ================ 工具 ================
def add_h(doc, text, level=1):
    return doc.add_heading(text, level=level)


def add_p(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(10.5)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    return p


def add_code(doc, code):
    p = doc.add_paragraph()
    r = p.add_run(code)
    r.font.name = 'Consolas'
    r.font.size = Pt(9.5)


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
OUT_PATH = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.5.docx')

doc = Document()
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
r = sub.add_run('交付审计文档（v1.0.5）')
r.bold = True
r.font.size = Pt(18)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run(
    '版本：v1.0.5（封板准确性修复）\n'
    '生成时间：' + datetime.datetime.now().strftime('%Y-%m-%d') + '\n'
    '基线版本：v1.0.4 → v1.0.5\n'
    '本轮性质：用户明确批准的问题修复（真实账本错误 + 前端契约 + 内部版本号一致性）\n'
    '边界：不增加业务规则、不修改研究/静态计划/状态体系/动态执行既定定义'
).font.size = Pt(11)

doc.add_page_break()

# ================ §1 文档元信息 ================
add_h(doc, '1. 文档元信息（v1.0.5 真实状态）', 1)
add_table(doc, ['项', '值'], [
    ['文档版本', 'v1.0.5'],
    ['基线版本', 'v1.0.4'],
    ['schema_version（数据库目标版本）', '1.0.5'],
    ['Handler.server_version', 'Workbench/1.0.5'],
    ['argparse description', 'A/H 投研交易工作台 v1.0.5'],
    ['启动成功打印', 'A/H 投研交易工作台 v1.0.5 已启动: <url>'],
    ['前端文件头注释', 'A/H 投研交易工作台 · 前端  v1.0.5'],
    ['PACK_NOTES / PACK_MANIFEST', 'v1.0.5（与代码一致）'],
    ['本轮性质', '用户明确批准的问题修复'],
    ['范围', '8 条精确修复（无新功能、无新字段、无新状态）'],
])

add_h(doc, '1.1 v1.0.5 严禁顺带加入项', 2)
add_p(doc, '本轮严格不允许：MA / EMA / MACD / RSI / KDJ / 布林带 / 自动支撑位 / 自动择时 / '
           '买卖信号 / 止损算法 / 仓位模型 / 状态机 / 新字段（trades 或 execution_reviews）/ '
           '新端点。v1.0.5 唯一改动是修复已有逻辑 + 提升前端契约一致性 + 统一内部版本号。')

doc.add_page_break()

# ================ §2 历史行为（已修复 / 不再适用） ================
add_h(doc, '2. 历史行为（v1.0.3 已修复 / v1.0.4 已修复的内容，明确标注不再适用）', 1)
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
     'v1.0.5 起修复：6 处版本标识全部统一为 v1.0.5'],
])

add_h(doc, '2.1 v1.0.3 → v1.0.4 → v1.0.5 数据库 schema 变更说明', 2)
add_p(doc, '本轮未引入任何数据库 schema 变更（不新增表 / 不改列 / 不改约束）。'
           'v1.0.5 唯一与数据库相关的改动是 TARGET_SCHEMA_VERSION 从 1.0.4 改为 1.0.5 —— '
           'init_db() 检测到旧库后会按当前正式版本治理方式，仅把 settings.schema_version 写入新值。'
           'do_migration 不引入新步骤，幂等三步（_migrate_v101_minimal / migrate_v102 / migrate_v103）继续生效。')

doc.add_page_break()

# ================ §3 真实数据链路 ================
add_h(doc, '3. v1.0.5 真实数据链路', 1)
add_p(doc, '本节反映 v1.0.5 真实代码（非历史描述）。')
add_code(doc, '''标的库 (securities)
   ↓
研究结论 (research, append-only, UNIQUE(security_id, version))
   ↓
静态交易计划 (trade_plans, append-only, UNIQUE(security_id, version))
   ↓
【v1.0.3】动态执行层 (execution_reviews, append-only, 无 UNIQUE)
   ↓
真实持仓 (trades, append-only) ← 推导 → compute_position (按 trade_date ASC, id ASC 排序)
   ↓
决策台账 (decision_ledger, append-only) ← execution 写入同事务带一条"动态执行判断更新"''')

add_h(doc, '3.1 列表 / 详情一致性', 2)
add_p(doc, 'list_securities() 在 enrich() 中调用 _execution_latest_row()，'
           '从 execution_reviews 取最新一条（ORDER BY execution_date DESC, id DESC）。'
           '详情页 get_detail() 通过 _execution_latest_row() 取同一行。'
           '两个口径完全一致，避免首页"尚未形成"假象。')

add_h(doc, '3.2 execution + ledger 同事务保证', 2)
add_p(doc, 'POST /api/securities/{id}/execution 经 _run_in_transaction 装饰器管理 BEGIN/COMMIT/ROLLBACK：')
add_bullet(doc, '成功：INSERT execution_reviews → INSERT decision_ledger → COMMIT')
add_bullet(doc, '任一失败：整体 ROLLBACK，execution_reviews 与 decision_ledger 不留半成品')

add_h(doc, '3.3 execution + trade 边界', 2)
add_p(doc, 'execution_review 的写入路径与 trades 完全独立：')
add_bullet(doc, 'POST /api/securities/{id}/execution 仅写 execution_reviews + decision_ledger，不动 trades')
add_bullet(doc, 'POST /api/securities/{id}/trades 仅写 trades + decision_ledger，不动 execution_reviews')
add_bullet(doc, 'compute_position() 仅依赖 trades，不读 execution_reviews')

doc.add_page_break()

# ================ §4 v1.0.5 8 条精确修复 ================
add_h(doc, '4. v1.0.5 8 条精确修复清单', 1)
add_p(doc, 'v1.0.5 严格遵循用户原始指令："只修复独立代码审计确认的问题，不新增任何业务模块、投资规则、状态或自动判断"。')

add_table(doc, ['#', '严重度', '问题描述', '修复方案'], [
    ['1', 'P0 账本错误',
     'add_trade_tx() 中 candidate 不携带 trade_date，append 到 existing 末尾；当日后写入的合法新交易可能在排序上被错认为"接在现有之后"，导致补录更早日期的卖出时，校验看不到真实时序下累计为负，非法交易被 INSERT 进数据库，事后 compute_position() 才抛异常，账本永久残留非法数据',
     'candidate 携带 trade_date，按 (trade_date ASC, id ASC) 与 compute_position() 完全一致排序；candidate.id=float("inf") 在同日排到末位保持 FIFO；从头重新计算累计持仓，负持仓立即 raise ApiError；事务回滚保证数据库零污染'],
    ['2', 'FAIL 前端契约',
     'execution_view 仍用 <select> 固定四项；浏览器中无法输入 "首仓可以执行，加仓等待确认" 这类自由文本；若数据库已存自由文本，重新打开弹窗会回到默认值，与后端已删除白名单的真实状态不一致',
     '改为 <input name="execution_view" list="execution-view-suggest"> + <datalist id="execution-view-suggest">；4 个文本只作建议项（<option>）；用户可输入任意非空文本；输入框 value 来自 prev.execution_view || ""（原样预填）'],
    ['3', 'FAIL 默认值错误',
     'execution_date 默认 = prev.execution_date || today()；新判断会被错误记录成上一条历史判断的日期，而不是今天',
     'execution_date 默认 = today()；不再继承 prev.execution_date（用户仍可手动覆盖）；6 项内容（execution_view / support_zone / resistance_zone / technical_structure / execution_condition / reason）继续从 prev 继承'],
    ['4', 'FAIL 前端契约（新增测试保证）',
     '现有测试只测后端 API，未测前端 HTML 模板',
     '新增 test_v105 §E / §F / §G / §H 静态扫描 app.js，断言：（a）execution_view 不再 <select>；（b）输入框带 list="execution-view-suggest"；（c）datalist id 存在且通过 EXECUTION_VIEWS.map 渲染；（d）自定义文本可作为 input value 原样预填；（e）execution_date 使用 today() 而非 prev.execution_date || today()'],
    ['5', 'P2 一致性',
     '内部 6 处版本号散落（TARGET_SCHEMA_VERSION=1.0.4 / Handler.server_version=Workbench/1.0.3 / argparse description v1.0.3 / 启动打印 v1.0.2 / 前端头 v1.0.3 / PACK_NOTES v1.0.4）',
     '全部统一为 v1.0.5；本轮不引入新迁移函数，仅按 init_db() 现有逻辑把 settings.schema_version 写入新 TARGET 值'],
    ['6', 'FAIL 审计文档本身',
     'v1.0.4 ZIP 内 docx 字节级与上一轮被否决文件完全相同（SHA-256 全等）；生成器仍在硬编码 v1.0.3 / schema_version=1.0.3 / 后端白名单 / 未来日期校验',
     '彻底重写 build_docx_v105.py；新 docx 不复用 v1.0.4 任何段落；明确标注"v1.0.3 / v1.0.4 历史行为已修复"；版本号与代码完全一致'],
    ['7', 'FAIL 文件清单措辞',
     'v1.0.4 ZIP 内 PACK_MANIFEST 写 "内含文件数：16（本清单自身另计）" 表述歧义——既可说"清单自身已计入"也可说"清单自身未计入"',
     '改为更清晰的措辞："清单中 N 个条目（PACK_MANIFEST.md 自身条目不在内）；加 PACK_MANIFEST.md 自身后 ZIP 总文件数为 N+1"'],
    ['8', '回归测试',
     '8 条修复均无配套真实账本测试',
     '新增 test_v105.py（25 断言全过）：§A 基线 / §B 拒绝补录 + 零污染 / §C 拒绝后 get_detail / §D 同日先后合法 / §E 前端 <select> 废弃 / §F datalist 数据源 / §G 自定义预填 / §H execution_date=today'],
])

doc.add_page_break()

# ================ §5 关键代码节选（修复前 vs 修复后） ================
add_h(doc, '5. 关键代码节选（修复前 vs 修复后）', 1)

add_h(doc, '5.1 §1 历史补录交易校验（add_trade_tx）—— 真实 P0 修复', 2)
add_p(doc, '【修复前 —— 历史行为 / v1.0.5 起不再使用】', bold=True)
add_code(doc, '''existing = [dict(r) for r in conn.execute(
    "SELECT * FROM trades WHERE security_id=? ORDER BY trade_date, id", (sid,)
).fetchall()]
candidate = {"side": side, "quantity": quantity}
seq = list(existing) + [candidate]   # 永远 append 到末尾

# 校验按列表顺序跑，结果：补录"卖在买之前"看不到真实累计为负，新增非法数据被 INSERT
cum = 0.0
for t in seq:
    if t["side"] == "买入":
        cum += float(t["quantity"])
    else:
        cum -= float(t["quantity"])
    if cum < -1e-9:
        raise ApiError(...)
# ↑ 此异常要等到 INSERT 之后 compute_position() 抛错才被外部感知，账本已污染''')

add_p(doc, '【修复后 —— v1.0.5 真实生效代码】', bold=True)
add_code(doc, '''existing = [dict(r) for r in conn.execute(
    "SELECT id, trade_date, side, quantity FROM trades "
    "WHERE security_id=? ORDER BY trade_date, id", (sid,)
).fetchall()]
# 新候选用 float("inf") 作为 id：在同 trade_date 时排到末位（FIFO），
# 但若 trade_date 早于既有，则按时间序排到前面并触发负累计校验。
candidate = {
    "id": float("inf"),
    "trade_date": trade_date,
    "side": side,
    "quantity": quantity,
}
seq = sorted(existing + [candidate], key=lambda t: (t["trade_date"], t["id"]))

cum = 0.0
for t in seq:
    if t["side"] == "买入":
        cum += float(t["quantity"])
    else:
        cum -= float(t["quantity"])
    if cum < -1e-9:
        raise ApiError(
            "历史时间序列在该时点（%s）累计持仓变为负（累计 = %.6g）。"
            "拒绝写入。请补录之前的买入后再试，或修正前面的卖出。"
            % (t.get("trade_date"), cum)
        )
# ↑ 现在排序后看到的就是真实时序；负累计在事务 BEGIN 之前就 raise，trades 表 INSERT 不会被执行''')

add_h(doc, '5.2 §2 + §3 execution_view / execution_date 前端真实代码', 2)
add_p(doc, '【修复后 —— app.js openExecutionModal 关键段】', bold=True)
add_code(doc, '''async function openExecutionModal(id) {
  const s = findSec(id); if (!s) return;
  // 走 /api/securities/{id} 详情接口拿权威 execution_latest
  const detail = await api(`/api/securities/${id}`);
  const prev = (detail && detail.execution_latest) || {};

  // v1.0.5：execution_date 默认 = today()。新判断记录当前时点；
  // 6 项内容继续从 prev 继承（微调体验）。
  const todayVal = today();
  let prePrice = "";
  const q = quoteOf(s);
  if (q && q.current != null) prePrice = q.current;
  const prevViewRaw = prev.execution_view || "";   // 原样预填（任意非空文本）

  openModal("更新动态执行判断 · " + s.name, `
    ${fld("判断日期",
      `<input name="execution_date" type="date" value="${esc(todayVal)}" required>`, true)}
    <div class="grid2">
      ${fld("判断时价格（" + esc(s.currency) + "）",
        `<input name="price_snapshot" type="number" step="any" value="${prePrice}">`)}
      ${fld("当前执行判断（自由文本）",
        `<input name="execution_view" list="execution-view-suggest"
               value="${esc(prevViewRaw)}" required
               placeholder="可以是任意文本，常用：等待技术确认 / 可以开始执行 / 暂缓执行 / 继续观察">
         <datalist id="execution-view-suggest">
            ${EXECUTION_VIEWS.map(v => `<option value="${esc(v)}">`).join("")}
         </datalist>`, true)}
    </div>
    ... 6 项自由文本字段 ...
  `, ...);
}''')

doc.add_page_break()

# ================ §6 测试 ================
add_h(doc, '6. 测试报告', 1)
add_table(doc, ['套件', '节数', '断言数', '结果'], [
    ['tests/test_v102.py', '14 节', '38 断言', '38/38 ✅（schema_version 期望更新为 1.0.5）'],
    ['tests/test_v103.py', '11 节', '60 断言', '60/60 ✅（§A-§K 全部保持）'],
    ['tests/test_v105.py', '8 节（§A-§H）', '25 断言', '25/25 ✅（本轮新增）'],
    ['tests/test_integration_quote.py', '集成', '14 断言', '联网项 SKIP（DNS 不可达），其余 PASS'],
    ['合计', '33+ 节', '123 断言', '全部通过'],
])

add_h(doc, '6.1 test_v105.py 各节覆盖（v1.0.5 新增）', 2)
add_table(doc, ['节', '用例', '断言数'], [
    ['§A', '基线：先有合法买入', '2'],
    ['§B', '拒绝补录更早日期的卖出 + 零污染', '5'],
    ['§C', '拒绝后 get_detail 仍可正常计算', '1'],
    ['§D', '同日先买后卖合法（candidate.id=INF）', '3'],
    ['§E', 'execution_view 不再 <select>、改用 <input list=...>', '3'],
    ['§F', 'datalist 数据源 4 个常用建议项 + map 渲染', '5'],
    ['§G', '自定义 execution_view 原样预填', '3'],
    ['§H', 'execution_date=today()；不继承 prev', '3'],
])

add_h(doc, '6.2 测试隔离保证', 2)
add_bullet(doc, '每个测试在 setup_module() 创建临时 SQLite 数据库（tempfile.mkdtemp），通过 monkey-patch server.get_db 指向临时库')
add_bullet(doc, '生产 data/workbench.db 哈希在 setup_module / teardown_module 两端一致（自动断言）')
add_bullet(doc, '真实腾讯行情测试在 tests/test_integration_quote.py 单独跑；网络不可用不污染本地账本测试')
add_bullet(doc, 'test_v105.py 同样适用此规则（§B 拒绝前后都验证 trades 表行数不变）')

doc.add_page_break()

# ================ §7 部署与迁移 ================
add_h(doc, '7. 部署与迁移（v1.0.4 → v1.0.5）', 1)
add_p(doc, 'v1.0.5 不引入新迁移函数。init_db() 检测到旧库后会按当前正式版本治理方式，'
           '把 settings.schema_version 写入新 TARGET 值：1.0.5。do_migration 内部三个迁移函数继续幂等。')
add_code(doc, '''do_migration(conn, db_path):
    0) 备份 workbench-pre-v103-<时间>.db（使用 SQLite Connection.backup API，无需停服）
    BEGIN:
        _migrate_v101_minimal (幂等)
        migrate_v102 (幂等；已不含 user_data 清空)
        migrate_v103 (幂等；execution_reviews 表 + 索引)
        CREATE INDEX IF NOT EXISTS × 5
        _verify_indexes（5 个业务索引立刻存在）
        PRAGMA foreign_key_check（FK 一致性）
        INSERT OR REPLACE settings.schema_version = '1.0.5'  # ← 本轮仅此一处
    COMMIT / ROLLBACK''')

add_p(doc, '幂等：已是 v1.0.5 的库 init_db() 不会触发迁移，不产生备份文件。'
           'v1.0.4 → v1.0.5 升级路径上，旧 schema_version 会触发上述完整迁移流程（幂等），'
           '最终 settings.schema_version 被覆盖为 1.0.5。')

add_h(doc, '7.1 在线备份', 2)
add_p(doc, '沿用 make_backup() 接口与 sqlite3.Connection.backup() 官方 API。'
           'CLI：python server.py --backup [path]')

doc.add_page_break()

# ================ §8 风险登记 ================
add_h(doc, '8. 风险登记册（v1.0.5 更新）', 1)
add_table(doc, ['ID', '类别', '说明', '缓解 / 状态'], [
    ['R-001', '行情', '单一行情源（Tencent 免费接口）',
     '失败时降级显示"上次成功行情" + error；沿用 v1.0.2'],
    ['R-002', '多币种', 'HKD 缺汇率时折算不可用',
     '显式提示"无法计算 / 待汇率"，不伪造数据；沿用 v1.0.2'],
    ['R-009', '测试', '生产 DB 隔离（临时 DB 测试）',
     'setup/teardown 自动断言哈希一致；v1.0.5 续用'],
    ['R-010', '迁移', 'v1.0.4 → v1.0.5 一次性原子',
     'do_migration BEGIN→COMMIT，失败整体 ROLLBACK；已验证'],
    ['R-011', '回滚', '升级失败可降级',
     '从 workbench-pre-v103-*.db 直接复制回 data/workbench.db；已验证'],
    ['R-014', '行情源', '不引入第二行情源（边界外）',
     '依赖 Tencent 单源，已记录'],
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
])

doc.add_page_break()

# ================ §9 第三方审计重点 ================
add_h(doc, '9. 第三方审计重点（v1.0.5）', 1)
add_bullet(doc, 'add_trade_tx() 的 candidate 与 seq 排序口径是否真与 compute_position() 完全一致（v1.0.5 P0）')
add_bullet(doc, 'ADD_TRADE 拒绝后数据库 trades 行数是否真为 0（新增）或不变（已存在合法数据）（零污染）')
add_bullet(doc, 'app.js openExecutionModal 中 execution_view 是否真为 <input list="execution-view-suggest"> + <datalist>，且不再 <select>')
add_bullet(doc, 'execution_date 默认值是否真为 today()（静态扫描不再含 prev.execution_date || today()）')
add_bullet(doc, '6 处内部版本号是否真全部统一为 v1.0.5')
add_bullet(doc, 'build_docx_v105.py 是否真不再硬编码 v1.0.3 / 后端白名单 / 未来日期校验 / schema_version=1.0.3')
add_bullet(doc, 'PACK_MANIFEST 文件数量措辞是否清晰（"清单中 N 个条目 + manifest 自身 = 总 N+1"）')
add_bullet(doc, 'v1.0.3 / v1.0.4 历史行为是否真在 §2 明确标注"已修复 / 不再适用"')
add_bullet(doc, '回归 test_v102 + test_v103 + test_v105 是否真全部通过（123 断言）')

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
])

add_p(doc, '')
add_p(doc, '第三方审计签字：____________________  日期：__________', bold=True)
add_p(doc, '用户确认签字：  ____________________  日期：__________', bold=True)
add_p(doc, '开发责任人：    ____________________  日期：__________', bold=True)

# 保存
doc.save(OUT_PATH)
print(f'✅ v1.0.5 docx 生成：{OUT_PATH}')
print(f'   大小：{os.path.getsize(OUT_PATH)} bytes')
print(f'   SHA-256：{hashlib.sha256(open(OUT_PATH, "rb").read()).hexdigest()}')
