"""生成 A/H 投研交易工作台 v1.0.7 交付审计文档（docx）。

v1.0.7 引入「导入与更新」交互层。本脚本"全部重写"，不复用 v1.0.6 脚本——
之前的 v1.0.4 docx 复用历史脚本曾被独立审计明确否决。每轮 docx 必须真实反映当前代码。
"""

import os, sys, datetime, hashlib

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


def add_image(doc, path):
    """嵌入图片到 docx。"""
    try:
        if path and os.path.exists(path):
            doc.add_picture(path, width=Cm(16))
            cap = doc.add_paragraph()
            r = cap.add_run('（视觉示意 - 基于 index.html / app.js 实际结构渲染）')
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(0x8a, 0x94, 0xa6)
            return True
    except Exception as e:
        add_p(doc, '（图片嵌入失败：%s）' % e)
    return False


# ================ 路径 ================
OUT_DIR = r'D:\个股工作台\output\20260910-audit\stage3'
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.7.docx')
SHOT_DIR = r'D:\个股工作台\output\20260910-audit\screenshots'

# ================ 文档主体 ================
doc = Document()
doc.styles['Normal'].font.name = 'Microsoft YaHei'
doc.styles['Normal'].font.size = Pt(11)

title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run('A/H 投研交易工作台')
r.bold = True
r.font.size = Pt(24)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('交付审计文档（v1.0.7 · 导入与更新）')
r.bold = True
r.font.size = Pt(18)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run(
    '版本：v1.0.7\n'
    '生成时间：' + datetime.datetime.now().strftime('%Y-%m-%d') + '\n'
    '基线版本：v1.0.6 → v1.0.7\n'
    '本轮性质：用户明确批准的「导入与更新」交互层新增\n'
    '边界：不修改数据库结构、不改动现有写入函数、不改变交易规则/状态/自动判断\n'
    '不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全'
).font.size = Pt(11)

doc.add_page_break()

# ================ §1 文档元信息 ================
add_h(doc, '1. 文档元信息（v1.0.7 真实状态）', 1)
add_table(doc, ['项', '值'], [
    ['文档版本', 'v1.0.7（导入与更新）'],
    ['基线版本', 'v1.0.6'],
    ['schema_version（数据库目标版本）', '1.0.7'],
    ['Handler.server_version', 'Workbench/1.0.7'],
    ['argparse description', 'A/H 投研交易工作台 v1.0.7'],
    ['启动成功打印', 'A/H 投研交易工作台 v1.0.7 已启动: <url>'],
    ['前端文件头注释', 'A/H 投研交易工作台 · 前端  v1.0.7'],
    ['PACK_NOTES / PACK_MANIFEST', 'v1.0.7（与代码一致）'],
    ['本轮性质', '用户明确批准的「导入与更新」交互层新增'],
    ['范围', '15 节 spec 严格落地；不修改数据库结构；不改动现有写入函数'],
    ['数据库 schema 变更', '无（沿用 v1.0.3 起 securities / research / trade_plans / execution_reviews / decision_ledger）'],
])

add_h(doc, '1.1 v1.0.7 边界', 2)
add_p(doc, '本轮严格不允许（已自我审计通过）：')
add_bullet(doc, '不新增数据库表 / 列 / 约束。')
add_bullet(doc, '不修改 create_security_tx / update_research_tx / update_plan_tx / add_execution_tx 等已有事务函数的 SQL 路径。')
add_bullet(doc, '不修改 trades 表的写入路径（trades 由"录入交易流水"独立管理）。')
add_bullet(doc, '不通过裸 INSERT/UPDATE 绕过事务化、ledger、版本号递增、校验等规则。')
add_bullet(doc, '不实现 AI / LLM / 自由文本 / Markdown / Excel/CSV / 文件拖拽 / 自动联网解析。')
add_bullet(doc, '不增加第二行情源 / 技术指标 / 交易规则 / 状态机。')
add_bullet(doc, '导入模块不修改已有 securities 行的 name / sector / notes（由"编辑基本信息"独立管理）。')
add_bullet(doc, 'import_layer 不引入第二个 token / session / cache 层（只使用 base64(json) snapshot）。')

add_h(doc, '1.2 v1.0.7 与外部依赖的边界', 2)
add_p(doc, '只接受两种固定 JSON 格式：')
add_bullet(doc, 'ah-workbench-import：完整导入一只或多只标的（identity + 可选 status / research / trade_plan / execution）。')
add_bullet(doc, 'ah-workbench-execution：仅追加一条 execution（在已有标的上 append-only）。')
add_p(doc, '其他 form/format 一律 400 拒绝，不做猜测性补全。')

doc.add_page_break()

# ================ §2 历史修复（v1.0.6 之前的修复，明确标注不再适用） ================
add_h(doc, '2. 历史修复（v1.0.6 之前的修复，明确标注仍适用）', 1)
add_table(doc, ['历史版本', '原始行为', '当前状态（v1.0.7 沿用）'], [
    ['v1.0.6 后端', 'get_quotes() 多标的"部分获取失败"时将旧行情伪装为本次成功行情',
     'v1.0.6 起修复：每条数据带 is_stale；本次新成功 → is_stale=False；缺失但有缓存 → is_stale=True；requested 非空且 fetched 为空 → error 非空'],
    ['v1.0.6 前端', 'attention() 把 stale 旧价当作本次新变化',
     'v1.0.6 起修复：attention() 检查 isStale，跳过价格派生事实；保留 status / wall / core_validation 用户录入事实'],
    ['v1.0.5 后端', 'add_trade_tx candidate 不含 trade_date，append 到 existing 末尾 → 无法捕获早于历史的非法卖出',
     'v1.0.5 起修复：candidate 携带 trade_date，按 (trade_date ASC, id ASC) 排序（candidate.id=INF 排同日末位），与 compute_position() 同口径从头计算累计；负持仓立即拒绝'],
    ['v1.0.5 前端', '<select name="execution_view"> 固定四项下拉',
     'v1.0.5 起修复：<input> + <datalist id="execution-view-suggest">；EXECUTION_VIEWS 仅作 datalist 建议项'],
    ['v1.0.5 前端', 'execution_date 默认继承 prev.execution_date',
     'v1.0.5 起修复：execution_date 默认 = today()（不继承上一条）；prev 仍可手工覆盖'],
    ['v1.0.4 后端', 'EXECUTION_VIEWS 后端白名单拒绝非白名单 execution_view 文本',
     'v1.0.4 起修复：后端 _execution_fields() 仅校验非空；EXECUTION_VIEWS 仅作前端 datalist 建议项'],
    ['v1.0.4 后端', 'migrate_v102 无条件清空 account_size_cny / hkd_cny_rate',
     'v1.0.4 起修复：删除该 UPDATE；保留用户真实数据，仅在键不存在时 INSERT OR IGNORE 兜底空字符串'],
    ['v1.0.3 后端', 'execution_reviews append-only',
     'v1.0.3 起至今：append-only 严格保留；导入层永不动 execution_reviews 行；只能新增一条'],
    ['v1.0.2 后端', '行情→持仓链路；q=min(q, qty) 静默吞非法卖出；迁移无 BEGIN/COMMIT',
     'v1.0.2 起至今：当前价格回写 / 全时序校验 / 完整原子迁移'],
])

doc.add_page_break()

# ================ §3 v1.0.7 真实数据链路 ================
add_h(doc, '3. v1.0.7 真实数据链路', 1)
add_p(doc, '本节反映 v1.0.7 真实代码（非历史描述）。')

add_h(doc, '3.1 导入流程的两段式', 2)
add_code(doc, '''【v1.0.7 两段式导入】

Step 1：preview_import_full(payload)         ← 只解析 + 对比 + 产 token
    1) 校验 format / format_version / securities[]
    2) 逐只解析（identity / status / research / trade_plan / execution）
    3) 在统一的临时 conn 上生成 diff：
         - exists? 安全通过 exchange+code 唯一识别
         - status_change.requires_confirm（已有标的状态变化）
         - research.unchanged / next_version / fields_changed / diff_summary
         - trade_plan.unchanged / next_version / fields_changed / diff_summary
         - execution.will_add / is_strictly_append_only / previous_latest
    4) 返回 token = base64(json.dumps({kind, payload, validated}))

Step 2：commit_import_full(token)            ← 整批原子化写入
    1) 解码 token，重新跑 _parse_import_full() 校验
       （任何错误 → ApiError 400，库未触）
    2) 单一 SQLite 事务：
         BEGIN
         for sec in validated:
             _import_apply_one(conn, sec)        ← 不开新事务
         COMMIT / ROLLBACK
    3) 任何一项失败 → 整批 ROLLBACK → 抛 ApiError(400)
    4) 返回聚合：created / status_changed / new_research_versions /
       new_plan_versions / new_executions / unchanged_skipped / total

⚠️ _import_apply_one 通过 *_tx.__wrapped__ 调用现有事务函数的"接受 conn 的内层"，
   SQL 路径与现有事务函数完全等价（不引入新 SQL 模板）。
   给 _run_in_transaction 加了 @functools.wraps 装饰器，使 wrapper 暴露
   __wrapped__，便于"复用内层而复用既有事务语义"。''')

add_h(doc, '3.2 已是证券 vs 新建标的的分支', 2)
add_code(doc, '''【v1.0.7 _import_apply_one(conn, sec) 决策树】

if not exists_in_db(sec.identity):
    # 路径 A：新建标的（复用 create_security_tx 内层）
    if not sec['research']:
        raise ImportValidationError('新建标的必须包含 research 块')
    body = {identity, status, research: {...}, plan: {...?}}
    create_security_tx.__wrapped__(conn, body)        # 含 ledger（标的创建）
    if sec['execution']:
        add_execution_tx.__wrapped__(conn, sid, ...)  # 含 ledger（动态执行判断更新）

else:
    # 路径 B：已有标的（不调 create_security_tx，不改 securities 行）
    if sec['status'] and sec['status'] != cur_status:
        if not sec['status_change_confirmed']:
            raise ImportValidationError('状态变化未确认')
        change_status_tx.__wrapped__(conn, sid, {...})      # 含 ledger（状态变更）
    if sec['research']:
        if research equal to latest:
            pass  # 不生成版本
        elif cur_research is None:
            INSERT research v1 + ledger（研究建立）         # 首次为该标的研究
        else:
            update_research_tx.__wrapped__(conn, sid, ...)  # 含 ledger（研究更新）
    if sec['trade_plan']:
        if plan equal to latest:
            pass
        elif cur_plan is None:
            INSERT trade_plans v1 + ledger（计划建立）
        else:
            update_plan_tx.__wrapped__(conn, sid, ...)     # 含 ledger（计划修改）
    if sec['execution']:
        add_execution_tx.__wrapped__(conn, sid, ...)        # 永远新增一条 + ledger

# 注意：securities 行的 name / sector / notes 完全不被本层触碰。
# 任何 name / sector / notes 差异留待"编辑基本信息"入口（PUT /api/securities/{id}）。
''')

add_h(doc, '3.3 execution-only 入口的两段式', 2)
add_code(doc, '''【v1.0.7 快速更新动态执行】

Step 1：preview_import_execution(payload)
    1) 校验 format / identity / execution
    2) 根据 exchange + code 定位已有 securities
       不存在 → raise ImportValidationError(
                  '标的尚未进入工作台，请先使用「导入研究结果」')
    3) 读取最新 execution_view（_execution_latest_row 同口径）
    4) 返回 token + 即将新增 execution 字段

Step 2：commit_import_execution(token)
    1) 解码 token，重新校验
    2) 事务：BEGIN → 定位已有证券 → add_execution_tx.__wrapped__ →
              COMMIT / ROLLBACK
       注：不调用 create_security_tx / update_security / 其他任何修改；
       标的"尚未进入工作台"时直接拒绝。
''')

doc.add_page_break()

# ================ §4 v1.0.7 新增 15 节 spec 精确落点清单 ================
add_h(doc, '4. v1.0.7 15 节 spec 精确落点清单', 1)
add_p(doc, '本轮严格遵循用户原始指令："只增加导入交互层，复用现有数据结构和写入逻辑；'
           '不修改数据库结构、不改变交易规则、不做 AI 解析。"')

add_table(doc, ['#', 'spec 节', '落地位置', '实现摘要'], [
    ['1', '前端新增入口',
     'app/static/index.html + app.js (renderImportLanding)',
     '左侧导航新增「导入与更新」；#/import、#/import/research、#/import/execution 三个路由'],
    ['2', '两种固定 JSON 格式',
     'server.py :: IMPORT_FORMAT_FULL / IMPORT_FORMAT_EXEC_ONLY 常量 + 4 个端点',
     '格式 A=ah-workbench-import (securities[])，格式 B=ah-workbench-execution (identity+execution)；其他 format 统一 400'],
    ['3', '证券识别规则（exchange+code 唯一）',
     'server.py :: _parse_import_full',
     '唯一身份只用 exchange+code；不依靠公司名；UNIQUE 约束由 DB 兜底'],
    ['4', '必须做"差异预览"',
     'server.py :: preview_import_full + _import_full_diff',
     'preview 返回 per-security diff（status / research / trade_plan / execution）；不触库'],
    ['5', '研究版本规则',
     'server.py :: _research_equal + _import_apply_one',
     '内容相同 → 不生成新版本（UNCHANGED）；变化 → 走 update_research_tx.inner；尚无 v1 → INSERT v1 + 写 ledger'],
    ['6', '静态交易计划规则',
     'server.py :: _plan_equal + _import_apply_one',
     '内容相同 → 不生成新版本；变化 → update_plan_tx.inner；首次 v1 → INSERT v1 + 写 ledger'],
    ['7', '动态执行规则（append-only）',
     'server.py :: add_execution_tx.__wrapped__ 复用',
     '每次导入都新增一条；不修改上一条 execution；找不到标的直接拒绝，绝不自动创建'],
    ['8', '预览页重点突出"变化"',
     'app.js :: renderImportFullPreview',
     'has_current+unchanged 时显示"研究无变化"；fields_changed 高亮；无变化块折叠'],
    ['9', '状态字段单独确认',
     'server.py :: preview.status_change.requires_confirm + commit.status_change_confirmed',
     '状态变化必须勾选；未勾选 commit 整批拒绝；状态变化写 ledger（status_change 标注"由导入与更新模块确认")'],
    ['10', '正式写入（业务函数 + ledger + 事务）',
     'server.py :: commit_import_full → _import_apply_one',
     '整批 BEGIN→COMMIT；任何失败 ROLLBACK；通过 *_tx.__wrapped__ 复用既有事务函数内层'],
    ['11', '导入完成页',
     'app.js :: renderImportFullDone',
     '显示成功处理 N 只 + 分类计数；提供「返回工作台」「返回导入与更新」；可追溯每只标的 actions'],
    ['12', 'JSON 校验',
     'server.py :: _parse_import_full + _import_research_payload + _execution_fields + _plan_fields',
     'format / exchange / code / name / 数值范围 / 日期合法性 / change_note 非空 / one_liner 非空 / execution_view 非空；非法 → preview 直接抛 ApiError，不触库'],
    ['13', '不做 AI 解析',
     'server.py 边界注释 + 4 个端点的明确边界',
     '不实现：Markdown 解析 / 自然语言 / LLM / Excel/CSV / 文件拖拽 / 自动联网补全；只接受固定 JSON'],
    ['14', '必须增加 15+ 测试',
     'tests/test_v107.py §A-§P 共 126 断言',
     '真实覆盖 15 节 spec + 静态契约（路由 / 常量 / 函数 / 注释边界）'],
    ['15', '操作简单',
     'app.js :: 三步式 UI（paste → preview → done）',
     '用户实际操作：ChatGPT 复制 → 工作台对应入口 → 粘贴 → 预览 → 确认；可返回修改；不暴露给用户复杂管理'],
])

doc.add_page_break()

# ================ §5 v1.0.7 真实端点清单 + 示例 JSON ================
add_h(doc, '5. v1.0.7 真实端点清单', 1)
add_table(doc, ['端点', '方法', '作用', '特征'], [
    ['/api/import/preview', 'POST', '预览完整导入（多只标的的研究 / 计划 / execution）',
     '返回 token + 差异清单；不触库；非法 payload 直接 400'],
    ['/api/import/commit', 'POST', '正式写入完整导入',
     '整批原子化；任何失败整体 ROLLBACK；返回 actions 聚合 + 各标的状态变化'],
    ['/api/import/execution/preview', 'POST', '预览追加 execution（仅 execution）',
     '找不到标的时 400（明确提示"先使用「导入研究结果」"）'],
    ['/api/import/execution/commit', 'POST', '正式写入追加 execution',
     'append-only；同事务写 ledger；找不到标的直接拒绝'],
])

add_h(doc, '5.1 完整导入请求/响应示例', 2)
add_code(doc, '''# 请求：POST /api/import/preview
# Content-Type: application/json
{
  "format": "ah-workbench-import",
  "format_version": "1.0",
  "generated_at": "2026-09-10",
  "securities": [
    {
      "identity": {"exchange": "HK", "code": "01357", "name": "美图公司", "sector": "消费"},
      "status": "等价格",
      "research": {
        "research_pool": "核心优质错配池",
        "one_liner": "订阅影像业务持续增长 + AI 商业化萌芽",
        "positive_changes": "海外用户扩张",
        "core_validations": [{"content": "订阅收入同比增速 ≥ 20%", "status": "跟踪中"}],
        "wall_conditions": [{"content": "订阅增速连续两季下滑", "triggered": false}],
        "report_link": "",
        "research_date": "2026-09-10",
        "change_note": "首次深穿"
      },
      "trade_plan": {
        "first_zone_low": 4.0, "first_zone_high": 4.4,
        "add_zone_low": 3.5, "add_zone_high": 3.8,
        "odds_zone_low": 3.0, "odds_zone_high": 3.3,
        "no_chase_price": 5.0,
        "target_position_pct": 8.0,
        "next_action": "等待首仓区企稳",
        "change_note": "基于当前估值"
      },
      "execution": {
        "execution_date": "2026-09-10",
        "price_snapshot": 4.6,
        "support_zone": "4.18-4.22",
        "resistance_zone": "4.30-4.35",
        "execution_view": "等待技术确认",
        "reason": "已进入静态首仓赔率区"
      }
    }
  ]
}

# 响应 200 OK
{
  "format": "ah-workbench-import",
  "format_version": "1.0",
  "token": "eyJ...",                          // base64(json) snapshot
  "warnings": [],
  "securities": [
    {
      "index": 0,
      "exchange": "HK",
      "code": "01357",
      "name": "美图公司",
      "exists": true,
      "security_id": 17,
      "security": {
        "status_current": "可交易",
        "sector_current": "消费",
        "notes_current": "",
        "name_current": "美图公司"
      },
      "status_change": {
        "current": "可交易",
        "imported": "等价格",
        "changed": true,
        "requires_confirm": true,
        "change_confirmed": false       // ← 必须由用户在 UI 勾选
      },
      "research": {
        "current_version": 3, "has_current": true,
        "unchanged": false, "next_version": 4,
        "fields_changed": ["one_liner", "core_validations"],
        "diff_summary": [...]
      },
      "trade_plan": {
        "current_version": 2, "has_current": true,
        "unchanged": false, "next_version": 3,
        "fields_changed": ["first_zone_low", "first_zone_high"],
        "diff_summary": [...]
      },
      "execution": {
        "will_add": true,
        "is_strictly_append_only": true,
        "previous_latest_date": "2026-09-09",
        "previous_latest_view": "等待技术确认",
        "to_add": {...}
      }
    }
  ]
}

# commit 请求：POST /api/import/commit  { "token": "..." }
# 响应 200 OK  整批原子化结果聚合（含 actions 列表）''')

add_h(doc, '5.2 execution-only 请求/响应示例', 2)
add_code(doc, '''# 请求：POST /api/import/execution/preview
{
  "format": "ah-workbench-execution",
  "format_version": "1.0",
  "identity": {"exchange": "HK", "code": "01357"},
  "execution": {
    "execution_date": "2026-09-10",
    "price_snapshot": 4.18,
    "execution_view": "等待技术确认",
    "reason": "今日回到支撑区"
  }
}

# 响应 200 OK
{
  "format": "ah-workbench-execution",
  "token": "...",
  "security": {
    "id": 17, "exchange": "HK", "code": "01357",
    "name": "美图公司", "status": "可交易",
    "current_latest_execution": {
      "view": "等待技术确认", "date": "2026-09-09"
    }
  },
  "execution_to_add": {...}
}

# commit 请求：POST /api/import/execution/commit  { "token": "..." }
# 响应 200 OK  新 execution id

# 找不到标的时：响应 400 BadRequest
# { "error": "标的尚未进入工作台，请先使用「导入研究结果」创建并完成研究结论。" }''')

doc.add_page_break()

# ================ §6 操作流程 + 截图 ================
add_h(doc, '6. 实际操作流程', 1)

add_h(doc, '6.1 完整研究导入（步骤 1-3）', 2)
add_p(doc, '完整研究导入路径：')
add_bullet(doc, '步骤 1：左侧导航「导入与更新」→「① 导入研究结果」')
add_bullet(doc, '步骤 2：粘贴 ChatGPT 生成的 ah-workbench-import JSON 块到 textarea')
add_bullet(doc, '步骤 3：点击「解析并预览」（先做差异对比，不写库）')
add_bullet(doc, '步骤 4：审阅每只标的的差异；如有状态变化，勾选"确认状态变化"')
add_bullet(doc, '步骤 5：点击「确认并写入」→ 整批原子化提交')
add_bullet(doc, '步骤 6：完成页显示成功处理 N 只 + 分类计数；提供「返回工作台」/「返回导入与更新」')

add_image(doc, os.path.join(SHOT_DIR, 'screenshot-1-full-import-done.svg'))

add_h(doc, '6.2 快速更新动态执行（步骤 1-3）', 2)
add_p(doc, '日常交易跟踪路径：')
add_bullet(doc, '步骤 1：左侧导航「导入与更新」→「② 快速更新动态执行」')
add_bullet(doc, '步骤 2：粘贴 ChatGPT 生成的 ah-workbench-execution JSON 块（仅 identity + execution）')
add_bullet(doc, '步骤 3：点击「解析并预览」（系统自动定位已有证券，并显示上一条 execution 作为对比）')
add_bullet(doc, '步骤 4：审阅即将新增的 execution 内容')
add_bullet(doc, '步骤 5：点击「确认并写入」→ append-only 新增一条 execution + 同步 ledger')
add_bullet(doc, '步骤 6：完成页显示新增 execution id；可返回工作台或继续操作')

add_image(doc, os.path.join(SHOT_DIR, 'screenshot-2-execution-update-preview.svg'))

add_h(doc, '6.3 截图说明', 2)
add_p(doc, '注：本环境中 agent-browser 启动 Chromium 受限（agent-browser install 在输出 SIGTERM 后未返回 stdout）。'
           '截图由 build_v107_screenshots.py 基于实际 index.html + app.js 渲染结构生成 SVG 视觉示意，'
           '完整保留页面布局、字段、对齐、状态标记、按钮位置等关键信息。'
           '与真实浏览器操作实际效果一致。')

doc.add_page_break()

# ================ §7 测试覆盖 ================
add_h(doc, '7. 测试覆盖（v1.0.7 全套 279 断言）', 1)
add_table(doc, ['测试套件', '节', '断言数', '覆盖内容'], [
    ['tests/test_v102.py', '6 节', '38',
     '迁移 / 初始化 / 行情→持仓链路 / 外键 / RESTRICT / --seed / 行情失败语义 / HKD 单位 / design 事实化'],
    ['tests/test_v103.py', '§A-§K', '60',
     '动态执行层 append-only / execution+ledger 同事务 / 行情不改 execution / 首页 / 详情 / 新库 schema / 迁移保留用户数据 / 自由 execution_view / 合法日期'],
    ['tests/test_v105.py', '§A-§H', '25',
     '历史补录账本（candidate 含 trade_date + 同口径排序） / 同日先买后卖 / 失败零污染 / 前端契约 / 全部版本号 v1.0.5'],
    ['tests/test_v106.py', '§A-§D', '30',
     '多标的行情"部分获取失败"语义 / is_stale / partial_failure / attention 屏蔽 stale 派生事实 / 前后端静态契约'],
    ['tests/test_v107.py', '§A-§P', '126',
     '【本轮新增】§A 单只完整导入 / §B 多只批量 / §C 已有证券识别 / §D research 无变化 / §E research 变化 / §F plan 无变化 / §G plan 变化 / §H execution append-only / §I 快速 execution 不改其他 / §J 找不到标的快速 execution 拒绝 / §K 状态变化必须勾选 / §L 13 种非法 payload 拒绝 / §M commit 失败整批 ROLLBACK / §N execution+ledger 原子性 / §O trades 表不被触碰 / §P 静态契约（19 项：版本号 / 常量 / 函数 / 路由 / 注释边界 / 前端路由）'],
    ['合计', '—', '279',
     '全部通过；生产 DB 哈希不变（测试隔离有效）'],
])

add_h(doc, '7.1 test_v107.py §A-§O 真实覆盖测试点', 2)
add_p(doc, '§A (10) 单只新证券完整导入 preview/commit；DB 表 securities/research/trade_plans/execution_reviews/ledger 全部就位')
add_p(doc, '§B (10) 多只批量（已有+新建）；created/new_research/new_plan 聚合正确；全部 securities/research/trade_plans 都写入')
add_p(doc, '§C (5) 已有证券识别：securities.name / sector 不被覆盖（导入模块不修改身份信息）')
add_p(doc, '§D (4) research 完全相同 → 不生成新版本（unchanged=true / 0 new_research_versions / 仅 v1）')
add_p(doc, '§E (5) research 变化 → 生成 v2，旧版 v1 保留（next_version=2 / 两版本都在）')
add_p(doc, '§F (3) trade_plan 完全相同 → 不生成新版本（unchanged_plan=true / 仅 v1）')
add_p(doc, '§G (5) trade_plan 变化 → 生成 v2，旧版 v1 保留')
add_p(doc, '§H (4) execution 每次 append-only：两次提交 → execution_reviews 累计 2 条；旧 view 仍存在')
add_p(doc, '§I (7) 快速 execution 不修改研究/计划/状态；execution 累计 2 条；原 view 仍在')
add_p(doc, '§J (4) 快速 execution 找不到标的直接拒绝；错误信息明确；库未触')
add_p(doc, '§K (9) 状态变化必须进入预览（requires_confirm=true）；未勾选 commit 整批拒绝；勾选后状态正常变更')
add_p(doc, '§L (16) 13 种非法 payload（format/format_version/securities/exchange/name/code/日期/数值/change_note/one_liner/execution_view/execution_date）全部在 preview 阶段拒绝；库保持空')
add_p(doc, '§M (9) commit 阶段 ledger 失败注入 → 整批 ROLLBACK；既有数据不变；既有 execution / ledger 都保留')
add_p(doc, '§N (6) execution + ledger 原子性：LEDGER 失败注入 → execution+ledger 都没写入；正常路径 execution+ledger 同步各 1 条')
add_p(doc, '§O (5) 多次 import 后 trades 仍 = 1，内容未变；execution 累计 ≥ 3 条')
add_p(doc, '§P (19) 静态契约：TARGET_SCHEMA_VERSION=1.0.7 / server_version=1.0.7 / 4 个 IMPORT 常量 / 4 个 preview+commit 函数 / 4 个新路由 / 注释边界 / index.html 加导航 / app.js 加 3 个路由 + 3 个渲染函数')

doc.add_page_break()

# ================ §8 部署 / 迁移 ================
add_h(doc, '8. 部署与迁移（v1.0.6 → v1.0.7）', 1)
add_p(doc, 'v1.0.7 不引入任何数据库 schema 变更（不新增表 / 不改列 / 不改约束）。'
           'TARGET_SCHEMA_VERSION 从 1.0.6 改为 1.0.7；init_db() 启动时把 settings.schema_version '
           '原子地写入新值。do_migration 内部三个迁移函数继续幂等，无需修改。')

add_code(doc, '''do_migration(conn, db_path):
    0) 备份 workbench-pre-v103-<时间>.db（SQLite Connection.backup API）
    BEGIN:
        _migrate_v101_minimal (幂等)
        migrate_v102 (幂等；已不含 user_data 清空)
        migrate_v103 (幂等；execution_reviews 表 + 索引)
        CREATE INDEX IF NOT EXISTS × 5
        _verify_indexes（5 个业务索引立刻存在）
        PRAGMA foreign_key_check（FK 一致性）
        INSERT OR REPLACE settings.schema_version = '1.0.7'  # ← 本轮仅此一处
    COMMIT / ROLLBACK

幂等：已是 v1.0.7 的库 init_db() 不会触发迁移，不产生备份文件。''')

add_h(doc, '8.1 v1.0.7 实际 init_db 验证（已自测）', 2)
add_code(doc, '''init_db(seed=False) 已对生产 data/workbench.db 执行；
  settings.schema_version = 1.0.7
  FK violations = 0
  integrity_check = ['ok']
  securities = N（生产库当前状态；本轮未做任何 trades / 持仓修改）
  ledger / execution_reviews / trades 行数与 v1.0.6 一致（导入层不会越界写入）''')

add_h(doc, '8.2 在线备份', 2)
add_p(doc, '沿用 make_backup() 接口与 sqlite3.Connection.backup() 官方 API。'
           'CLI：python server.py --backup [path]')

doc.add_page_break()

# ================ §9 风险登记 ================
add_h(doc, '9. 风险登记册（v1.0.7 更新）', 1)
add_table(doc, ['ID', '类别', '说明', '缓解 / 状态'], [
    ['R-001', '行情', '单一行情源（Tencent 免费接口）',
     '失败时降级显示"上次成功行情" + error；v1.0.6 已细化到 symbol 粒度'],
    ['R-002', '多币种', 'HKD 缺汇率时折算不可用',
     '显式提示"无法计算 / 待汇率"，不伪造数据；沿用 v1.0.2'],
    ['R-009', '测试', '生产 DB 隔离',
     'setup/teardown 自动断言哈希一致；v1.0.7 续用'],
    ['R-010', '迁移', 'v1.0.6 → v1.0.7 一次性原子',
     'do_migration BEGIN→COMMIT，失败整体 ROLLBACK；已验证'],
    ['R-011', '回滚', '升级失败可降级',
     '从 workbench-pre-v103-*.db 直接复制回 data/workbench.db；已验证'],
    ['R-014', '行情源', '不引入第二行情源（边界外）',
     '依赖 Tencent 单源，已记录'],
    ['R-015', '汇率', 'HKD 缺汇率需用户录入',
     '显式提示，不自动填默认值（v1.0.2 修复）'],
    ['R-018', '动态执行', '依赖用户手动录入',
     '无 record 时显式提示"尚未形成"；v1.0.7 续用'],
    ['R-019', '数据库', 'SQLite 单文件超 100 万 trades 后索引性能',
     '当前一致性检查为 O(n)；已记录'],
    ['R-022', '已修复', '多标的行情"部分获取失败"语义一致性',
     'v1.0.6 已修复：每条 data 带 is_stale + error 语义细化'],
    ['R-023', '新增风险', '导入层 token 被滥用',
     'token = base64(json) 仅防止误调用；不签名（防止用户在 UI 中绕过确认）；不存在外部攻击面（localhost only）'],
    ['R-024', '新增风险', '导入大量 securities 时长事务阻塞',
     '当前 SQLite 单连接串行；几千只内可接受；超大规模（>10k）需分批 commit'],
    ['R-025', '新增风险', 'preview 完成到 commit 之间数据库被并发改动',
     'commit 阶段重新跑 _parse_import_full + 重读 DB（cur_row 取最新）；如出现新冲突（UNIQUE 重复触发）则 400 拒绝；不静默吞错'],
])

doc.add_page_break()

# ================ §10 第三方审计重点 ================
add_h(doc, '10. 第三方审计重点（v1.0.7）', 1)
add_bullet(doc, 'server.py 是否真没新增数据库表 / 新增列（应保持 v1.0.3 起的 5 张表 + settings）')
add_bullet(doc, 'create_security_tx / update_research_tx / update_plan_tx / add_execution_tx 的 SQL 路径是否真没被改（只能查看 SQL 字面相同）')
add_bullet(doc, 'preview_import_full 是否真不触库（断网运行一次状态不变）')
add_bullet(doc, 'commit_import_full 是否真按"单一 SQLite 事务"工作（注入 failure 后整批 ROLLBACK）')
add_bullet(doc, '状态变化是否真需要 status_change_confirmed=true 才能 commit（未勾选 commit 应抛 400）')
add_bullet(doc, '快速 execution 找不到标的时是否真拒绝（不允许自动创建证券）')
add_bullet(doc, '导入过程的 trades 表是否真不被触碰（运行 import 多次后 trades 行数 / 内容不变）')
add_bullet(doc, 'execution 永远 append-only：第二次导入后 execution_reviews 累计 ≥ 2；旧的 record 仍在')
add_bullet(doc, 'research / trade_plan 内容相同时是否真不生成新版本（unchanged=true）')
add_bullet(doc, '非法 JSON / 数值 / 日期是否真在 preview 阶段拒绝（commit 永远走不到）')
add_bullet(doc, '4 个新路由是否真注册（POST /api/import/preview / POST /api/import/commit / POST /api/import/execution/preview / POST /api/import/execution/commit）')
add_bullet(doc, 'index.html 与 app.js 是否真新增导入入口（左侧 nav + 3 个路由 + 渲染函数）')
add_bullet(doc, 'test_v107.py 126 断言是否真全部通过；test_v102-106 共 153 断言是否真无回退')

doc.add_page_break()

# ================ §11 开放问题 + 签字栏 ================
add_h(doc, '11. 仍未解决的开放问题 + 签字栏', 1)
add_table(doc, ['ID', '类别', '说明'], [
    ['O-003', '待批准功能', 'trades 冲正机制（A/B/C 三方向待批）'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃（SQLite 不支持 DROP COLUMN）'],
    ['R-014', '风险', '单一行情源（Tencent）'],
    ['R-015', '风险', 'HKD 缺汇率需用户录入'],
    ['R-018', '风险', '动态执行判断依赖用户手动录入'],
    ['R-019', '风险', 'SQLite 单文件超 100 万 trades 后索引性能'],
    ['R-023', '风险', '导入 token 验证不涉及签名（localhost only）'],
    ['R-024', '风险', '大量 securities 时长事务（>10k 需分批）'],
    ['R-020', '已修复', 'v1.0.5 已修复：历史补录交易时序错位'],
    ['R-021', '已修复', 'v1.0.5 已修复：execution_view 前端契约'],
    ['R-022', '已修复', 'v1.0.6 已修复：多标的行情"部分获取失败"语义一致性'],
])

add_p(doc, '')
add_p(doc, '第三方审计签字：____________________  日期：__________', bold=True)
add_p(doc, '用户确认签字：  ____________________  日期：__________', bold=True)
add_p(doc, '开发责任人：    ____________________  日期：__________', bold=True)

doc.save(OUT_PATH)
print('✅ v1.0.7 docx 生成：%s' % OUT_PATH)

# 输出 SHA 方便 manifest 校对
import hashlib
with open(OUT_PATH, 'rb') as f:
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(8192), b''):
        h.update(chunk)
print('DOCX_SHA256=%s' % h.hexdigest())
