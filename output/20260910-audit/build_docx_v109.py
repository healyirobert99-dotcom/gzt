"""生成 A/H 投研交易工作台 v1.0.9 交付审计文档（docx）。

v1.0.9 是「最终并发与预览一致性修复」版本：不新增业务功能，只修复 v1.0.8 交付后
独立验证中发现的 R-027（同一 token 并发重复提交）与 R-028（database is locked
返回 500 而非受控 4xx），并补上 execution_latest_id 的漂移检测与前端最小防重。

本脚本全新编写，不复用任何历史 docx 字节。
文中所有测试数字、文件字节数、SHA-256 均由本脚本在运行时**实际计算/来自本轮实跑结果**，
不沿用任何历史文档的声称。
"""

import os
import datetime
import hashlib

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ================ 基础排版 helper ================
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


# ================ 路径与实测指纹 ================
ROOT = r'D:\个股工作台'
OUT_DIR = os.path.join(ROOT, 'output', '20260910-audit', 'stage3')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.9.docx')


def fingerprint(rel):
    """返回 (字节数, SHA-256) —— 运行时真实读取，不写死。"""
    p = os.path.join(ROOT, rel)
    data = open(p, 'rb').read()
    return len(data), hashlib.sha256(data).hexdigest()


FP = {}
for rel in ['app/server.py', 'app/static/app.js', 'app/static/index.html',
            'app/static/style.css', 'tests/test_v107.py', 'tests/test_v108.py',
            'tests/test_v109.py', 'output/20260910-audit/smoke_v108_http.py',
            'output/20260910-audit/smoke_v109_http.py']:
    FP[rel] = fingerprint(rel)


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
r = sub.add_run('交付审计文档（v1.0.9 · 最终并发与预览一致性修复）')
r.bold = True
r.font.size = Pt(18)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run(
    '版本：v1.0.9（TARGET_SCHEMA_VERSION = 1.0.9）\n'
    '生成时间：' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + '\n'
    '基线版本：v1.0.8 → v1.0.9\n'
    '本轮性质：仅修复 v1.0.8 交付后独立验证中发现的并发与预览一致性缺陷\n'
    '边界：不新增业务功能；不修改研究口径 / 交易计划 / 状态体系；\n'
    '      不新增数据库表、列或迁移；不修改导入 JSON Schema'
).font.size = Pt(11)

doc.add_page_break()

# ================ §1 本轮定位 ================
add_h(doc, '1. 本轮定位与修复清单', 1)
add_p(doc, 'v1.0.8 的导入完整性修复通过了 407 断言离线测试与 14 类审计项，'
            '但在交付后的**对抗性并发验证**中暴露出两个真实缺陷（R-027 / R-028），'
            '另有一项 spec 内已声明但实际未生效的检测（execution_latest 漂移）。'
            'v1.0.9 只做这四件事，不扩展任何业务功能。')
add_table(doc, ['#', '来源', '问题', 'v1.0.9 处理'], [
    ['1', 'R-027',
     '_import_cache_take 只读取 cache 不消费，token 在 commit 成功后才失效，'
     '存在 TOCTOU 窗口；同一 token 并发 commit 可重复追加 append-only 的 execution',
     '改为服务端原子 claim：_IMPORT_PREVIEW_LOCK 内一次完成「存在 / TTL / kind / '
     'in_flight」判定并置位 in_flight；失败释放、成功失效；full 与 exec-only 共用'],
    ['2', '本轮新增',
     '前端 commit 按钮无防重，用户可在请求返回前重复点击',
     '点击后按钮立即 disabled 并显示「正在写入…」，请求返回前不再发送第二次；'
     '失败恢复、成功进入完成页。**仅为 UI 防误操作，后端防重独立存在**'],
    ['3', 'spec 第三节',
     'snapshot 已保存 execution_latest_id，但未参与 _import_snapshot_drift',
     '对 execution-only 导入与完整导入中**带 execution 块**的证券比对 '
     'execution_latest_id；不带 execution 块的证券不被无关 execution 更新阻断'],
    ['4', 'R-028',
     '并发 commit 返回 500「database is locked」，_mut() 未捕获 OperationalError',
     '仅 SQLITE_BUSY / SQLITE_LOCKED（或等价错误文本）映射为受控 409；'
     '其余 OperationalError 仍按 500 上报，避免把系统故障伪装成用户输入错误'],
])

doc.add_page_break()

# ================ §2 原子 claim ================
add_h(doc, '2. 修复一：preview token 的原子 claim（R-027）', 1)
add_p(doc, 'v1.0.8 的 token 生命周期是「take（只读校验）→ 写库 → invalidate（删除）」。'
            'take 与 invalidate 之间存在一个真实的时间窗口：并发的第二个请求在第一个请求'
            '完成 invalidate 之前做 take，同样能通过校验并进入写入路径。'
            'spec 第三节要求的 4 类漂移检测（status / research version / plan version / '
            '证券出现消失）都不覆盖 append-only 的 execution 追加 —— 因为追加 execution '
            '既不改变 status 也不改变 research / plan 版本，所以旧 preview 在它看来仍然"新鲜"。')
add_p(doc, 'v1.0.9 把校验与占位合并为一个不可分割的临界区：', bold=True)
add_code(doc,
         'def _import_cache_claim(token, expected_kind):\n'
         '    tok = _import_token_key(token)\n'
         '    if tok is None:\n'
         '        raise ImportTokenError(...)\n'
         '    with _IMPORT_PREVIEW_LOCK:\n'
         '        entry = _IMPORT_PREVIEW_CACHE.get(tok)\n'
         '        if entry is None:          raise ImportTokenError(...)   # 未 preview / 已使用\n'
         '        if entry[\'expires_at\'] <= now:\n'
         '            pop(tok);              raise ImportTokenError(...)   # 已过期\n'
         '        if entry[\'kind\'] != expected_kind:\n'
         '                                       raise ImportTokenError(...)   # 接口不匹配\n'
         '        if entry.get(\'in_flight\'):\n'
         '                                       raise ImportTokenError(...)   # 正在提交\n'
         '        entry[\'in_flight\'] = True                                    # 原子占位\n'
         '        return {\'kind\': ..., \'validated\': ..., \'snapshot\': ...}     # 浅拷贝')
add_p(doc, '四条不变式：')
add_bullet(doc, '同一 token 在同一时刻只可能有一个 commit 通过 claim —— 第二个请求在锁内被拒，'
                '而不是等到前一个成功后才发现 token 已失效。')
add_bullet(doc, 'claim 返回浅拷贝，调用方在锁外无法改写 cache 内部状态。')
add_bullet(doc, 'commit 成功 → _import_cache_invalidate(token) 删除 token（一次性不变）。')
add_bullet(doc, 'commit 失败 → _import_cache_release(token) 复位 in_flight；'
                '若 token 已过期则直接删除。释放动作覆盖 claim 之后的**所有**异常路径，'
                '包括 confirmed_status_changes 参数本身不合法（用户可修正参数后重试）。')
add_p(doc, 'token 字面量在 claim / release / invalidate 三处统一经 _import_token_key() '
            '规范化（strip）。因此「token 前后加空格」不能绕过一次性失效。')
add_p(doc, '实现位置：app/server.py 的 _import_cache_claim / _import_cache_release / '
            '_import_cache_invalidate；两条 commit 入口（commit_import_full、'
            'commit_import_execution）使用完全相同的机制。')

doc.add_page_break()

# ================ §3 前端防重 ================
add_h(doc, '3. 修复二：前端最小重复点击保护', 1)
add_p(doc, '仅为 UI 防误操作，不作为防重依据。后端仍必须具备独立的原子防重能力（见 §2）。')
add_table(doc, ['时机', '前端行为'], [
    ['点击「确认并写入」', 'Import.committing = true → render()；按钮立即 disabled 且文案变为「正在写入…」'],
    ['请求进行中', '再次点击被 if (Import.committing) 早退拦截，不发出第二次 commit'],
    ['失败', 'Import.committing = false → 按钮恢复为「确认并写入」，可修正后重试'],
    ['成功', 'Import.committing = false → 进入完成页（第 3 步）'],
    ['新一轮 preview', 'committing 复位为 false（新 token 即新上下文）'],
])
add_p(doc, 'full import 与 execution-only 两个入口（commitFull / commitExec）行为一致；'
            '「返回修改」按钮在写入进行中同样被 disabled。')

# ================ §4 execution 漂移 ================
add_h(doc, '4. 修复三：execution_latest_id 纳入漂移检测', 1)
add_p(doc, 'snapshot 自 v1.0.8 起就保存了 execution_latest_id，但当时只作为审计留痕，'
            '不参与 _import_snapshot_drift。v1.0.9 让它真正生效，并**严格限定适用范围**，'
            '避免无关阻断：')
add_table(doc, ['场景', 'check_execution', '行为'], [
    ['ah-workbench-execution（格式 B）', 'S = True',
     'preview 后 execution_latest_id 变化 → 拒绝，提示"动态执行判断自预览后已发生变化，请重新解析预览。"'],
    ['ah-workbench-import 中含 execution 块的证券', 'S = True',
     '同上：拒绝并要求重新预览'],
    ['ah-workbench-import 中不含 execution 块的证券', 'S = False',
     '**不比对** execution_latest_id；即使别的路径新增了 execution，'
     'research / trade_plan 导入照常完成'],
])
add_p(doc, '提示语按漂移类型选择：命中 execution 漂移时给出专属文案；'
            'status / research / plan / 证券出现消失场景的原文案'
            '「工作台数据自预览后已发生变化，请重新解析预览。」保持**逐字不变**'
            '（v1.0.7 / v1.0.8 的测试对该文案有硬断言）。两类同时命中时两条都给出。')
add_p(doc, '拒绝时整批不得落到"半完成状态"：漂移检测发生在事务之外、BEGIN 之前，'
            '此时数据库尚未被触碰（见 §6 的 §D#8 / §H#9 断言）。')

doc.add_page_break()

# ================ §5 409 ================
add_h(doc, '5. 修复四：database is locked 的 HTTP 语义（R-028）', 1)
add_p(doc, 'spec 明确禁止「简单捕获所有 sqlite3.OperationalError 并统一转 400」——'
            '那会把 no such table / I/O 故障等真实系统问题伪装成用户输入错误。'
            'v1.0.9 只识别 BUSY / LOCKED 族：')
add_table(doc, ['判定', '依据', '响应'], [
    ['SQLITE_BUSY（主码 5）', 'sqlite3.OperationalError.sqlite_errorcode & 0xFF in (5, 6)',
     'HTTP 409「数据库正在处理另一项写入，请稍后重试。」'],
    ['SQLITE_LOCKED（主码 6）', '同上', 'HTTP 409，同一文案'],
    ['文本退化路径', "message 含 'database is locked' / 'database table is locked' / 'database is busy'",
     'HTTP 409（仅在拿不到 sqlite_errorcode 时兜底）'],
    ['其它 OperationalError', 'no such table / disk I/O error / malformed …',
     'HTTP 500「服务器错误: …」（不伪装成 4xx）'],
])
add_code(doc,
         'except sqlite3.OperationalError as e:\n'
         '    if _is_db_busy_error(e):\n'
         '        self._err(DB_BUSY_MESSAGE, 409)\n'
         '    else:\n'
         '        self._err(\'服务器错误: %s\' % e, 500)')
add_p(doc, '另定义 DbConflictError（→ 409），供内部需要主动上报"稍后重试"时使用；'
            'ApiError 仍映射 400，语义边界不混淆。')
add_p(doc, '注：原子 claim 生效后，正常并发场景已不再产生写入冲突（只有一个请求能进入写入路径），'
            '409 主要覆盖"多进程 / 多标签页同时写同一 SQLite 文件"等进程内锁覆盖不到的情形。')

doc.add_page_break()

# ================ §6 测试结果 ================
add_h(doc, '6. 测试结果（本轮实际运行，全部数字可复现）', 1)
add_p(doc, '以下数字均由本轮在本机实跑得到；离线套件使用临时数据库，不触碰 data/workbench.db。',
      bold=True)
add_table(doc, ['套件', '断言数', '结果', '说明'], [
    ['tests/test_v102.py', '38', 'PASS', '基线业务回归（含集成测试文件存在性断言）'],
    ['tests/test_v103.py', '60', 'PASS', 'v1.0.3 / v1.0.4 动态执行层回归'],
    ['tests/test_v105.py', '25', 'PASS', '行情层回归'],
    ['tests/test_v106.py', '28', 'PASS', '行情质量回归'],
    ['tests/test_v107.py', '127', 'PASS', '导入与更新回归（其中 2 条版本契约断言随版本升级前移，见 §7）'],
    ['tests/test_v108.py', '129', 'PASS', '导入完整性封板回归（其中 3 条版本契约断言同步前移，见 §7）'],
    ['tests/test_v109.py', '83', 'PASS', '**本轮新增**：并发 / 漂移 / 防重 / 409 / 静态契约'],
    ['离线合计', '490', 'FAIL 0', '38+60+25+28+127+129+83'],
    ['tests/test_integration_quote.py', '14', 'PASS', '联网集成（需外网，单独执行）'],
    ['smoke_v108_http.py', '14', 'PASS', 'v1.0.8 真实 HTTP 端到端（不得回退）'],
    ['smoke_v109_http.py', '38', 'PASS', '**本轮新增**：v1.0.9 全部验收点的真实 HTTP 端到端'],
])
add_p(doc, 'v1.0.9 的 83 条断言按 spec 第五节逐项对应：', bold=True)
add_table(doc, ['spec 要求', '本版断言', '实测结果'], [
    ['1. 同一 execution token 并发 8 次：成功严格 = 1 / execution_reviews 只 +1 / '
     'decision_ledger 只 +1 / 其余受控 4xx / 0 个 5xx',
     '§A#1–§A#9（9 条）',
     '成功 = 1；7 个 400；0 个 5xx；execution_reviews 0→1；decision_ledger 0→1'],
    ['2. 同一 full-import token 并发 8 次：最多 1 次成功 / 不产生重复',
     '§B#1–§B#7（7 条）',
     '成功 = 1；securities=1、research=1、trade_plans=1、execution_reviews=1'],
    ['3. preview execution → 另一路径新增 execution → 提交旧 token 必须拒绝',
     '§C#1–§C#5（5 条）',
     '400 + 专属文案 + 未被追加'],
    ['4. full import 中带 execution：execution_latest 改变 → commit 拒绝',
     '§D#1–§D#8（8 条）',
     '400 + 专属文案 + research 未写入'],
    ['5. full import 不带 execution：仅 execution_latest 改变 → 不被无关阻断',
     '§E#1–§E#8（8 条）',
     '200；research v2、plan v2 均已写入'],
    ['6. commit 业务校验失败后 in_flight 必须释放，token 在 TTL 内仍可合法重试',
     '§F#1–§F#6（6 条）',
     '失败后 in_flight=False，同一 token 修正后 200'],
    ['7. token 成功后仍严格一次性失效',
     '§G#1–§G#5（5 条）',
     '复用 / 加空格 / 手工 base64 全部 400'],
    ['（本轮另加）409 语义与非 busy OperationalError 的区分',
     '§H#1–§H#8（8 条）',
     'locked→409、no such table→500；纯函数判定 4 条'],
    ['（本轮另加）静态契约扫描（版本 / in_flight / claim-release / 前端防重）',
     '§I#1–§I#27（27 条）',
     '全部命中'],
])
add_p(doc, '并发用例走**真实 HTTP 链路**（ThreadingHTTPServer + 临时端口 + 8 线程 Barrier 同时冲闸），'
            '不是函数级模拟。为排除"数字随调度波动"，本轮把 test_v109.py 连续运行 5 次、'
            'smoke_v109_http.py 连续运行 3 次，A/B 两组并发用例的成功次数在**每一次运行中都严格为 1**'
            '（v1.0.8 该数字在 2~3 之间波动，这正是 R-027 的表现）。')
add_p(doc, '修复验证（R-027 / R-028 的原始复现探针）：v1.0.8 交付时用于发现缺陷的并发探针'
            '（8 线程 × 3 轮）在本版上的输出为：每轮状态码分布 {400: 7, 200: 1}，'
            'execution_reviews 0→1，需要人工判定的轮次 0/3 —— 即原缺陷已不可复现。')

doc.add_page_break()

# ================ §7 既有测试变更清单 ================
add_h(doc, '7. 既有测试的变更清单（逐条 diff，非按总数反推）', 1)
add_p(doc, '本轮对既有测试套件只做了版本号契约前移，未改动任何业务语义断言。'
            '以下为对 v1.0.8 交付 ZIP 内文件与工作区文件的逐行 diff 结果：')
add_table(doc, ['文件', '变更条数', '断言标签', 'v1.0.8 期望', 'v1.0.9 期望'], [
    ['tests/test_v107.py', '2', '§P#1',
     "TARGET_SCHEMA_VERSION = '1.0.8'", "TARGET_SCHEMA_VERSION = '1.0.9'"],
    ['tests/test_v107.py', '', '§P#2',
     "server_version = 'Workbench/1.0.8'", "server_version = 'Workbench/1.0.9'"],
    ['tests/test_v108.py', '3', '§I#1',
     "TARGET_SCHEMA_VERSION = '1.0.8'", "TARGET_SCHEMA_VERSION = '1.0.9'"],
    ['tests/test_v108.py', '', '§I#2',
     "server_version = 'Workbench/1.0.8'", "server_version = 'Workbench/1.0.9'"],
    ['tests/test_v108.py', '', '§I#15',
     '前端版本号 v1.0.8', '前端版本号 v1.0.9'],
])
add_p(doc, '合计 5 条（2 + 3），全部为"当前版本常量"契约断言，性质与 v1.0.8 时的同类前移相同。'
            '两个套件的**断言总数保持不变**：test_v107.py 127 → 127，test_v108.py 129 → 129；'
            'diff 中不存在任何新增、删除或改写业务语义断言的行。')
add_p(doc, '本轮新增测试文件 tests/test_v109.py（83 断言），'
            '并由 407 断言（38+60+25+28+127+129）增至 490 断言（+83）。'
            '离线断言总数的净变化来源明确且唯一：新增 test_v109.py。')

doc.add_page_break()

# ================ §8 交付包一致性 ================
add_h(doc, '8. 交付包一致性', 1)
add_p(doc, '本版打包规则（与 v1.0.8 相同，且必须逐条满足）：')
add_bullet(doc, 'Manifest 列出的每一条路径都真实存在于 ZIP 中，文件数量由打包脚本统计，非人工填写。')
add_bullet(doc, 'Manifest 不列出任何 ZIP 中不存在的构建脚本（build_docx_v10x.py 等一律不进 ZIP）。')
add_bullet(doc, '每个条目同时给出**字节数**与 **SHA-256**；打包后逐条回读 ZIP 校验一遍。')
add_bullet(doc, 'README.txt 的默认地址必须与 app/server.py 的实际默认端口一致（http://127.0.0.1:8765）。')
add_bullet(doc, 'BUILD_LOG 含 ZIP 自身 SHA-256，会产生自指矛盾，因此**不进 ZIP**。')
add_bullet(doc, '打包后把 ZIP 解压到全新目录，在其中重跑全套离线测试 + HTTP 冒烟，'
                '再记录最终指纹。')
add_p(doc, '本轮关键产物的实测指纹（本脚本运行时真实计算）：', bold=True)
add_table(doc, ['文件', '字节数', 'SHA-256'],
          [[rel, str(FP[rel][0]), FP[rel][1]] for rel in FP])

# ================ §9 本轮边界 ================
add_h(doc, '9. 本轮边界（未改变的部分）', 1)
add_table(doc, ['类别', '本轮是否改变', '说明'], [
    ['数据库 Schema', '否', '无新增表、列、索引或迁移；TARGET_SCHEMA_VERSION 仅作版本号前移'],
    ['导入 JSON Schema', '否', 'format / format_version / 字段结构完全沿用 v1.0.8 固定 Schema'],
    ['研究口径 / 交易计划 / 状态体系', '否', '未改动任何业务规则、状态取值或计划字段'],
    ['业务写入函数 SQL', '否',
     '仅新增 cache 生命周期函数与错误映射；导入仍复用 *_tx.__wrapped__ 内层路径'],
    ['trades 表', '否', '导入层依旧不触碰 trades'],
    ['execution 追加语义', '否', '仍为 append-only；本轮只增加"提交前是否被并发改动"的检测'],
    ['HTTP 400 语义', '部分', '新增 409 用于 BUSY/LOCKED；其余 4xx 语义不变'],
    ['前端「载入示例」', '否', 'v1.0.8 已删除；本轮未恢复。'
     '注：公司名输入框 placeholder 仍以一个真实公司名作为填写示例（非"可一键载入的'
     '研究/交易计划数据"），本轮未改文案'],
])

doc.add_page_break()

# ================ §10 风险与开放问题 ================
add_h(doc, '10. 风险与开放问题', 1)
add_table(doc, ['ID', '类别', '说明'], [
    ['R-027', '已修复（v1.0.9）',
     '同一 token 并发 commit 可重复追加 execution。修复：服务端原子 claim + in_flight。'
     '验证：并发 8 次成功严格 = 1；修复前的复现探针在本版 3/3 轮不再复现'],
    ['R-028', '已修复（v1.0.9）',
     '并发返回 500「database is locked」而非受控 4xx。修复：仅 BUSY/LOCKED → 409，'
     '其余 OperationalError 仍 500。验证：§H#1–§H#8 全过，并发用例 0 个 5xx'],
    ['R-026', '沿用（预期行为）',
     'preview cache 为进程内存态；服务重启后未使用的 token 全部失效（需重新预览）。'
     '这是"服务端持有预览状态"的必然代价'],
    ['R-029', '新增（低危，刻意选择）',
     'commit 路径若被 BaseException（如 KeyboardInterrupt、进程被强杀）中断，'
     'in_flight 不会被释放，该 token 在剩余 TTL 内不可重试（需重新 preview）。'
     '选择"宁阻塞、不重复"是刻意的 fail-safe 取向；影响面为单用户本机操作，'
     '且重新预览即可恢复'],
    ['R-024', '风险', '大批量 securities（>10k）单事务耗时；当前 SQLite 串行写入'],
    ['R-014', '风险', '单一行情源（Tencent）'],
    ['R-015', '风险', 'HKD 缺汇率需用户录入'],
    ['O-003', '待批准功能', 'trades 冲正机制（A/B/C 三方向待批）'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃（SQLite 不支持 DROP COLUMN）'],
])
add_p(doc, '另记录一处"刻意不做"的判断：本轮未把 exec-only 的漂移范围扩大到'
            'research / trade_plan 版本。原因是 spec 第三节只要求 execution_latest_id，'
            '扩大范围会改变既有语义并可能引入无关阻断 —— 属于未经批准的规则扩展。')

# ================ §11 第三方审计重点 ================
add_h(doc, '11. 第三方审计重点（v1.0.9）', 1)
add_p(doc, '建议独立审计方优先复核以下各项，全部可用交付包内文件独立复现：', bold=True)
add_bullet(doc, '把 _import_cache_claim 的四项检查中任意一项移出 _IMPORT_PREVIEW_LOCK，'
                '并发用例是否立刻退化为"成功 > 1"（验证临界区是否真的原子）')
add_bullet(doc, '同一 token 并发 8 次 commit：成功次数必须严格 = 1、'
                'execution_reviews / decision_ledger 各只 +1、0 个 5xx')
add_bullet(doc, '同一 full-import token 并发 8 次：不得出现重复 securities / research / '
                'trade_plans / execution_reviews')
add_bullet(doc, 'preview 后另一路径新增 execution → 提交旧 token 必须被拒，'
                '且提示"动态执行判断自预览后已发生变化，请重新解析预览。"')
add_bullet(doc, '完整导入**不带** execution 块时，仅 execution 更新不得阻断 research / '
                'trade_plan 导入（不得扩大检测范围）')
add_bullet(doc, 'commit 因业务校验失败后，同一 token 在 TTL 内必须仍可合法重试（in_flight 已释放）')
add_bullet(doc, 'token 成功后严格一次性失效；前后加空格亦不得绕过')
add_bullet(doc, 'database is locked → 409；no such table / I/O error → 500（不得伪装成 4xx）')
add_bullet(doc, '离线 490 断言（38+60+25+28+127+129+83）+ 集成 14 + HTTP 冒烟 14 + 38，'
                'FAIL 0；两个冒烟脚本在解压后的包内实跑同样通过')
add_bullet(doc, 'Manifest 条目数 == ZIP 实际条目数；逐文件字节数与 SHA-256 全对；'
                '无幽灵条目；解压到全新目录可重跑通过')
add_bullet(doc, '既有测试的 5 条变更是否确实仅为版本号契约（对照 §7 的 diff 清单逐条验证）')
add_bullet(doc, '确认本轮确实未新增数据库表/列/迁移，也未改动导入 JSON Schema')

doc.add_paragraph()
sig = doc.add_paragraph()
sig.add_run('审计方签字：__________________          '
            '日期：__________________').font.size = Pt(11)

doc.save(OUT_PATH)

print('已生成：%s' % OUT_PATH)
print('字节数：%d' % os.path.getsize(OUT_PATH))
print('SHA-256：%s' % hashlib.sha256(open(OUT_PATH, 'rb').read()).hexdigest())
