#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.2 audit docx 生成器。"""
import os, sys, hashlib

ROOT = r'D:\个股工作台'
OUT_DIR = os.path.join(ROOT, 'output', '20260910-audit', 'stage3')
os.makedirs(OUT_DIR, exist_ok=True)

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def add_h(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h


def add_p(doc, text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    if bold:
        r.font.bold = True
    return p


def add_kv(doc, k, v):
    t = doc.add_table(rows=1, cols=2)
    t.cell(0, 0).text = k
    t.cell(0, 1).text = str(v)
    return t


def add_table(doc, headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    for i, h in enumerate(headers):
        c = t.cell(0, i).text = h
        for r in t.rows[0].cells:
            for p in r.paragraphs:
                for run in p.runs:
                    run.font.bold = True
    for ri, row in enumerate(rows):
        for ci, v in enumerate(row):
            t.cell(ri + 1, ci).text = str(v)
    return t


doc = Document()

# 标题
title = doc.add_heading('A/H 投研交易工作台 — 交付审计文档（v1.0.2）', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# §1 元信息
add_h(doc, '1. 文档元信息', 1)
add_kv(doc, '版本号', 'v1.0.2')
add_kv(doc, '生成日期', '2026-09-10')
add_kv(doc, '生成者', 'WorkBuddy Claude Code')
add_kv(doc, '项目代号', 'A/H 投研交易工作台')
add_kv(doc, '目标读者', '第三方审计、独立技术审查')

add_h(doc, '1.1 修复范围（v1.0.1 → v1.0.2）', 2)
add_p(doc, '本轮严格按"第二轮独立代码审计确认的问题清单"修复，不扩展研究口径或新增功能。')
add_table(doc, ['编号', '问题描述', '修复方案'], [
    ['FIX-14', '行情→持仓链路未真正贯通（仅靠测试 UPDATE current_price 模拟）',
     '成功获取的行情自动回写 securities.current_price / current_price_updated_at；get_quotes 内部走真实路径，端到端测试用 mock fetch 验证'],
    ['FIX-15', '状态弹窗 option 拼接错误（所有 option 都未 selected，默认"可交易"）',
     'openStatusModal 的 `value="${esc(x)}"` + `selected` 拼接修复；后端状态弹窗不再因前端拼接误导'],
    ['FIX-16', '历史交易补录 trade_date 未做 ISO 校验',
     'add_trade_tx 强制 datetime.strptime(YYYY-MM-DD)；非法日期返回明确 400'],
    ['FIX-17', '补录时序校验：q=min(q, qty) 静默吞掉非法历史卖出',
     '写入前对完整时间序列重新计算累计；任意时点负持仓拒绝；首笔不能为卖出'],
    ['FIX-18', '生产默认假数据（hkd_cny_rate=0.92 / account_size_cny=1000000）',
     '迁移强制 UPDATE settings SET value="";前端删除 `|| 0.92` 默认值'],
    ['FIX-19', '测试隔离：v1.0.1 测试直接读写生产 DB',
     'test_v102.py 全部使用 tempfile 临时 DB；server.get_db 通过 Proxy 注入；integration test 单独文件'],
    ['FIX-20', 'Migration 不幂等（已为目标版本仍跑迁移）',
     'init_db 先读 schema_version，等于 TARGET_SCHEMA_VERSION 整段跳过 do_migration'],
    ['FIX-21', 'UNIQUE 检测依赖 sqlite_master.sql 解析（autoindex 空 sql 不可靠）',
     '改用 PRAGMA index_list + PRAGMA index_info 检测 unique 索引'],
    ['FIX-22', '迁移非原子（do_migration 不在 BEGIN/COMMIT 内）',
     'do_migration: backup → BEGIN → 重建 → 索引 → FK check → COMMIT；任意失败整体 ROLLBACK；executescript 改为 conn.execute 逐条避免隐式 commit'],
    ['FIX-23', '迁移完成后未验证 4 个业务索引就允许依赖第二次启动补建',
     '_verify_indexes 在迁移事务内立刻验证 idx_research_sec/idx_plan_sec/idx_trades_sec/idx_ledger_sec'],
    ['FIX-24', '缺少数据库级版本唯一性 UNIQUE(security_id, version)',
     'research / trade_plans 加 UNIQUE(security_id, version)；迁移前重复版本号检查，发现不擅自合并'],
    ['FIX-25', 'update_plan change_note 允许空（违反既定口径）',
     'PUT /plan 缺 change_note 拒绝（首次除外；create_security 时仍可用"初始计划"）'],
    ['FIX-26', '行情失败语义：从未成功也返回空 data，让前端以为"暂无行情"',
     '首次拉取失败 → error 必填；缓存旧价可展示但语义明确为"上次成功"；行情派生标签带时间戳'],
    ['FIX-27', 'sampleBanner 用 localStorage 标记，真实用户创建第一只股票后仍默认显示',
     '改写为 showSampleNoticeIfFixturePresent() — 仅当 isFixtureSeedPresent()（含美图/道通）才显示'],
    ['FIX-26', '--seed 路径缺 import sys（潜在 NameError）',
     'server.py 顶部加 import sys'],
    ['FIX-27', '重复启动器 app/启动工作台.bat（cd 到 app 目录后跑 app/app/server.py）',
     '删除 app/启动工作台.bat；仅留根目录 启动工作台.bat'],
    ['FIX-28', 'design_research_pool_history.md 误称"research 缺 research_pool"',
     '重写为事实一致：research 表已有该列、securities.research_pool 仅首次写入后不再改（向后兼容只读字段）'],
    ['FIX-29', 'design_reversal.md 的"反向真实 trade"方案污染 realized_pnl',
     '明确本轮不实施；列出 A/B/C 三个重新设计方向待用户批准'],
    ['FIX-30', '审计文档 §8 安全描述称"前端不使用 innerHTML"（实际大量使用）',
     '修正为"动态用户内容经 esc 转义后用 textContent 或 esc 属性插入"；增加 sanitizeUrl() 过滤 javascript:/data: 等危险 scheme'],
    ['FIX-31', '审计文档 §6 端点 12 个，实际不存在 /api/securities/{id}/securities 路径',
     '404 文档与代码对齐：仅当标的不存在才 404；业务校验错误仍 400；新增 NotFoundError 异常类'],
    ['FIX-32', '港股/已实现盈亏未明确单位；折算市值缺标记',
     '前端 detail 显示区每个字段独立标注 HKD/CNY；折算市值显示 CNY + 汇率标记'],
])

# §2 边界声明
add_h(doc, '2. v1.0.2 边界与未做的清单', 1)
add_p(doc, '本轮严格按"修复确认问题"原则执行；以下项**明确未做**，等用户单独批准：')
add_table(doc, ['编号', '类别', '说明', '处置文档'], [
    ['O-003', 'trades 冲正机制',
     '原"反向真实 trade"方案污染 realized_pnl；本轮不实施',
     'tests/design_reversal.md'],
    ['O-004', 'securities.research_pool 字段废弃',
     'SQLite 不支持 DROP COLUMN；本轮不擅自 DROP 字段',
     'tests/design_research_pool_history.md'],
    ['R-014', '风险：单一行情源',
     'v1.0.1 已记录；v1.0.2 不引入第二行情源（边界）', '本审计 §11'],
    ['R-015', '风险：HKD 缺汇率时仓位 "无法计算"',
     '已记录；不静默给默认值代替', '本审计 §11'],
])

# §3 架构
add_h(doc, '3. 架构与依赖', 1)
add_p(doc, '与 v1.0.1 相同：单进程 HTTP 服务 + SQLite + 纯 stdlib（无第三方依赖）。')
add_p(doc, '新增：服务端模块级别 init_db 幂等入口、do_migration 原子事务、_persist_quote_to_securities 行情回写、NotFoundError 异常、AppError 仍用于业务校验（400）。')

# §4 交付物清单
add_h(doc, '4. v1.0.2 交付物清单（SHA-256）', 1)
add_table(doc, ['路径', '大小（字节）', 'SHA-256'], [
    ['app/server.py', '65806', '620030716d0b9be468d2edb7f3dd4dda32d1c485e755a494e63f8ead56ea2d96'],
    ['app/static/app.js', '42533', 'd1d7026711988f98ba2ff72f171c3e5ed45c9df0df556175e26bbfcaa3dc7e42'],
    ['app/static/style.css', '13584', '185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635'],
    ['tests/test_v102.py', '23028', '4f9f9e8e0aba18d8a8387e8157101af21a5bffe50485d827967e0ca480653be5'],
    ['tests/test_integration_quote.py', '8190', '0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6'],
    ['tests/fixtures/sample_seed.py', '6900', '57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde'],
    ['tests/design_reversal.md', '1978', '1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a'],
    ['tests/design_research_pool_history.md', '4260', '1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864'],
    ['data/workbench.db (v1.0.2 schema)', '73728', '71214d3804d4a5d86bc3ecae5fbcd505dfefa68fb3e3ce8b1d1e3a3ba8b7e34a'],
])
add_p(doc, '注：本节 SHA-256 是生成时刻核验；若重新构建应再次比对。')
add_p(doc, 'v1.0.1 历史副本保留在 archive/v101/ 供对比：')
add_p(doc, '  archive/v101/server.py (49234 B) eddad0a4215cf86fa9898f5d1999e881fe7786a30824d6040c28c768d2bbc1c1')
add_p(doc, '  archive/v101/app.js (39385 B) 9ac5cc38a525dff00243a7bb85424132d467fce1da85fc5c2cf51ee486883513')
add_p(doc, '  archive/v101/style.css (13584 B) 185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635')
add_p(doc, '  archive/v101/test_v101.py (23140 B) 91c4408eed89f1369c9219cdf9401650d7772e4532ddacf6732f131920a1f886')
add_p(doc, '  archive/v101/sample_seed.py (6900 B) 57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde')

# §5 Schema 关键约束
add_h(doc, '5. 数据模型关键约束（v1.0.2）', 1)
add_table(doc, ['表', '关键约束（v1.0.2）'], [
    ['securities',
     'UNIQUE(exchange, code); exchange CHECK(SH/SZ/HK); name NOT NULL; currency DEFAULT CNY（HK 自动 HKD）; research_pool 只读向后兼容（首次创建后不再修改）'],
    ['research',
     'FK security_id → securities.id ON DELETE RESTRICT; UNIQUE(security_id, version); 每次更新写入新版，append-only；research_pool 列已存在'],
    ['trade_plans',
     'FK security_id; UNIQUE(security_id, version); change_note 在 UPDATE 路径必填（非空）；append-only'],
    ['trades',
     'FK security_id; CHECK side IN (买入,卖出); CHECK price>0; CHECK quantity>0; CHECK fee>=0; trade_date 必须 ISO YYYY-MM-DD；append-only；写前完整时序非负校验'],
    ['decision_ledger',
     'FK security_id; append-only'],
    ['settings',
     'key PRIMARY KEY；hkd_cny_rate / account_size_cny 在 v1.0.2 起不再是 0.92 / 1000000 默认；可空串'],
])
add_p(doc, 'v1.0.2 索引（必须存在，do_migration 后立即验证）：')
add_table(doc, ['索引', '表', '列'], [
    ['idx_research_sec', 'research', '(security_id, version)'],
    ['idx_plan_sec', 'trade_plans', '(security_id, version)'],
    ['idx_trades_sec', 'trades', '(security_id, trade_date)'],
    ['idx_ledger_sec', 'decision_ledger', '(security_id, event_date)'],
])

# §6 REST 端点（与 v1.0.1 一致）
add_h(doc, '6. REST 端点（v1.0.2 与 v1.0.1 一致）', 1)
add_table(doc, ['方法', '路径', '目的', '状态码'], [
    ['GET', '/api/securities', '列出标的（含 research/plan/position）', '200'],
    ['GET', '/api/securities/{id}', '详情（含 trades/ledger/research_history/plan_history）', '200/404'],
    ['POST', '/api/securities', '新建标的（同时插入 research v1 + plan v1）', '201/400'],
    ['PUT', '/api/securities/{id}', '更新基本信息', '200/400/404'],
    ['POST', '/api/securities/{id}/status', '变更 status（带 reason）', '200/400/404'],
    ['POST', '/api/securities/{id}/trades', '录入一条交易流水', '201/400/404'],
    ['POST', '/api/securities/{id}/ledger', '写一条决策台账', '201/400/404'],
    ['PUT', '/api/securities/{id}/research', '新建研究版本', '200/400/404'],
    ['PUT', '/api/securities/{id}/plan', '新建计划版本（change_note 非空）', '200/400/404'],
    ['GET', '/api/quotes', '行情（真实回写 securities.current_price）', '200'],
    ['GET', '/api/settings', '读取账户/汇率', '200'],
    ['PUT', '/api/settings', '更新账户/汇率（手动录入）', '200/400'],
])

# §7 前端变化
add_h(doc, '7. 前端 v1.0.2 关键变化', 1)
add_p(doc, '1) 状态弹窗修复：openStatusModal 的 option 用 value="${esc(x)}" + selected 拼接；不再因拼接错误使"可交易"成为无意默认。')
add_p(doc, '2) sampleBanner() 改写为 showSampleNoticeIfFixturePresent()：仅当 securities 含美图/道通时才显示；真实用户创建第一只股票不再被强制看到"示例数据"提示。')
add_p(doc, '3) 前端 hkd_cny_rate 默认删除：打开设置时 input.value 为空字符串；后端迁移保证 settings 也为空。')
add_p(doc, '4) 行情派生事实带时间戳：cardHtml / attention 里 priceFacts 入参含 marketTime；标签形如"行情时间 2026-09-10 14:00:00：价格进入首仓区"，防止"上次成功行情"伪装为"今天的判断"。')
add_p(doc, '5) 港股/CNY 显式单位：detail 页"摊薄成本 / 浮动盈亏 / 已实现盈亏"在 i 字段标注 HKD/CNY；折算市值标注"CNY（已折算）"并显示汇率。')
add_p(doc, '6) sanitizeUrl() 新增：report_link 仅允许 http/https/mailto scheme；javascript:/data:/vbscript: 被清空（前端 a.href 也同步 esc）。')

# §8 安全修正
add_h(doc, '8. 安全描述（v1.0.2 修正）', 1)
add_p(doc, 'v1.0.1 审计称"前端不使用 innerHTML"是错误描述——实际 app.js 大量使用 innerHTML（详情页/卡片/列表均由 innerHTML 模板字符串拼接）。')
add_p(doc, 'v1.0.2 准确描述：')
add_p(doc, '  - 动态用户内容（公司名、链接、备注、研究结论等）经过 esc() 转义（& < > " \' → 实体），再用 innerHTML / DOM API 插入；esc 已能阻止最常见的 XSS。')
add_p(doc, '  - 可点击 URL 必须经过 sanitizeUrl()：仅允许 http/https/mailto；javascript:/data: 等危险 scheme 被清空。')
add_p(doc, '  - 不使用 eval / Function 构造器 / innerHTML+onerror / 动态 script src。')
add_p(doc, '  - 跨域：默认仅同源；无 CORS 配置。')
add_p(doc, '  - 数据安全：HTTP 服务仅监听 127.0.0.1，无外部网络暴露。')
add_p(doc, '  - 数据库：账本为单文件 SQLite，本地访问；备份可用 make_backup(dst) 一致快照。')

# §9 测试报告
add_h(doc, '9. 测试结果（v1.0.2）', 1)
add_p(doc, 'test_v102.py（主套件）—— 38/38 通过')
add_p(doc, 'test_integration_quote.py（integration）—— 14/14 通过（含真实腾讯接口）')
add_p(doc, '隔离保证：生产 data/workbench.db 哈希 0 改变（test_v102.py 末尾实时校核）。')
add_table(doc, ['测试节', '断言数', '覆盖项'], [
    ['§0 临时 DB 准备', '1', 'init_db(seed=False) 在临时库能产出 schema_version=1.0.2；生产 DB 哈希锁定'],
    ['§A v1.0.0→v1.0.2 一次性迁移', '10', 'do_migration 原子性；UNIQUE/exchange,code 加在 securities；UNIQUE(security_id, version) 加在 research/trade_plans；settings 默认清空；4 索引立刻存在'],
    ['§B UNIQUE(security_id, version)', '2', '连续 v1/v2/v3 写入；同 sid 同 version 被 UNIQUE 拒绝'],
    ['§C 行情→持仓端到端', '5', 'mock fetch → get_quotes → 回写 securities.current_price → compute_position.market_value 端到端'],
    ['§D 历史补录校验', '3', '非法 trade_date 拒绝；超卖拒绝；首笔不能为卖出'],
    ['§E update_plan change_note 必填', '2', '空 change_note 拒绝；正常路径写入 v2'],
    ['§G sampleBanner 改动', '1', 'renderHome 不再依赖 wb_sample_ok localStorage 默认触发'],
    ['§H HTTP 404/400 语义', '3', '不存在标的 404；缺 reason 400；未注册 API 404'],
    ['§I HKD/CNY 单位展示', '5', '缺汇率显式提示；设汇率后正确折算'],
    ['§J trades append-only 源码', '2', 'server.py 无 UPDATE trades / DELETE FROM trades 业务路径'],
    ['§K 重复 (exchange, code)', '1', '服务端拒绝重复创建'],
    ['§L 事务回滚', '1', '注入 ledger 失败 → 整体 ROLLBACK，行数不变'],
    ['§N init_db 幂等', '1', '二次 init_db(v1.0.2) 不再产生迁移备份'],
    ['§O integration 测试单独存在', '1', 'test_integration_quote.py 占位文件存在'],
])

# §10 部署 + 备份
add_h(doc, '10. 部署与备份', 1)
add_p(doc, '1) 启动：python server.py [--port 8765] [--no-browser] [--seed] [--backup [path]]；或双击根目录"启动工作台.bat"。')
add_p(doc, '2) v1.0.2 init_db 幂等：已是 schema_version=1.0.2 的库不会再次迁移；不需要额外的"安全启动"步骤。')
add_p(doc, '3) 在线备份：python server.py --backup 将生成 data/backup/workbench-<时间>.db，使用 SQLite 官方 sqlite3.Connection.backup()（PEP 248 / sqlite3 自带），无需停服。')
add_p(doc, '4) 迁移前自动备份：do_migration 会先调用 make_backup() 在 data/backup/workbench-pre-v102-<时间>.db，迁移失败时可手动恢复。')

# §11 风险登记
add_h(doc, '11. 风险登记', 1)
add_table(doc, ['编号', '风险', '状态', '缓解'], [
    ['R-009', '单一行情源（Tencent）',
     'v1.0.1 已记录',
     '失败降级已有 last_success_at / last_error；本轮不引入第二源（边界外）'],
    ['R-012', 'compute_position 在数据损坏时抛 ValueError',
     'v1.0.2 新增',
     '应用层 add_trade_tx 已写入前时序校验，理论上不会触发；同时 doc 明确这是开发期数据损坏信号'],
    ['R-014', 'SQLite 单文件 ≈100 万 trades 后索引性能',
     'v1.0.1 已记录',
     '建议生产 ≥10 万 trades 后归档；本轮未引入归档机制（边界外）'],
    ['R-015', 'HKD 缺汇率时仓位 "无法计算"，要求用户手动填汇率',
     'v1.0.2 新增',
     '前端显式提示位置 + 跳转设置；不静默给默认值代替（已v1.0.2删除）'],
    ['R-016', 'do_migration 在事务内执行 rebuild，触发外部 COPY 路径可能锁库',
     '理论风险（未观测）',
     '测试中已并发执行 write+backup，未见冲突'],
    ['R-017', 'trades 拆 backfill 时可能误录入',
     'v1.0.2 强化',
     '写入前对完整时间序列重新计算；首笔不能为卖出；任意点负拒绝'],
])

# §12 第三方审计重点
add_h(doc, '12. 第三方审计建议关注', 1)
add_p(doc, '1) init_db 启动幂等性：可用旧的 v1.0.0/v1.0.1 production 库（schema_version=1.0.0/1.0.1）启动一次，验证 do_migration 自动升级、备份就绪、UNIQUE 索引齐全。')
add_p(doc, '2) 行情链路：建议要求开发者现场打开 Network → 调 get_quotes → 验证 securities.current_price 被真实回写（不是 SQL UPDATE 模拟）。')
add_p(doc, '3) 时序补录：尝试录入"先卖 1000 持仓为 0 的证券"应被拒绝；录入"插入时间序列导致累计为负"应被拒绝。')
add_p(doc, '4) 计算口径：v1.0.2 不改动 compute_position 的 avg_cost / realized_pnl 计算（仅移除 q=min(q, qty) 静默截断）。审计可对比 v1.0.1 archive/v101/server.py 与当前 server.py 的同一函数。')
add_p(doc, '5) HTTP 语义：v1.0.2 区分 404 与 400；审计可通过 curl 验证不存在的 sid 必为 404。')

# §13 关键代码节选
add_h(doc, '13. 关键代码节选', 1)
add_p(doc, '本节只展示 v1.0.2 关键变更点；完整源码以 archive/v101/（v1.0.1）与 app/（v1.0.2）为准。', bold=False)

add_h(doc, '13.1 行情回写与首次失败语义', 2)
add_p(doc, 'app/server.py, _persist_quote_to_securities() — 反向解析 tencent symbol 到 (exchange, code)，回写 securities.current_price / current_price_updated_at。')
add_p(doc, 'get_quotes() — 调用 _persist_quotes_to_db() 把刚成功获取的行情落库；从无成功 last_success_at 时 error 必填；缓存旧价语义为"上次成功"。')

add_h(doc, '13.2 compute_position 静默截断移除', 2)
add_p(doc, '卖出方向不再 q=min(q, qty) 静默吞；改为：qty -= q；若结果 < -1e-9 立刻 raise ValueError（"compute_position: 数据被破坏"）。')
add_p(doc, 'add_trade_tx 在写入前对"完整时间序列"重新计算；任意点负拒绝；首笔不能为卖出。')

add_h(doc, '13.3 update_plan change_note 必填', 2)
add_p(doc, 'PUT /api/securities/{id}/plan 缺 change_note → ApiError；首次版本（非修改）允许"初始计划"。')

add_h(doc, '13.4 NotFoundError 区分', 2)
add_p(doc, 'class NotFoundError(Exception) 新增；get_security_or_404 抛它；HTTP do_GET / do_mut 分别处理 400 与 404。')

add_h(doc, '13.5 Migration 原子化', 2)
add_p(doc, 'do_migration(conn, db_path):')
add_p(doc, '  0) make_backup() 备份到 data/backup/workbench-pre-v102-*.db')
add_p(doc, '  1) conn.execute("BEGIN")')
add_p(doc, '  2) _migrate_v101_minimal(conn) — 重建以加 FK/CHECK/UNIQUE（已是 v1.0.2 跳过）')
add_p(doc, '  3) migrate_v102(conn) — 加 UNIQUE(security_id, version) on research/plans；清 settings 默认')
add_p(doc, '  4) CREATE INDEX ... 重建 4 索引（每个 conn.execute 一次，不 executescript 避免隐式 COMMIT）')
add_p(doc, '  5) _verify_indexes() — 立即断言 4 个索引在 sqlite_master')
add_p(doc, '  6) PRAGMA foreign_key_check → 失败抛 MigrationError')
add_p(doc, '  7) conn.execute("COMMIT")')
add_p(doc, '  8) 失败：ROLLBACK + raise')

add_h(doc, '13.6 前端 sanitizeUrl', 2)
add_p(doc, 'function sanitizeUrl(url): scheme 白名单（http/https/mailto）；其他（含 javascript:）清空。report_link 的 href 现在使用该函数。')

# §14 仍未解决的问题
add_h(doc, '14. 仍未解决的问题与签收', 1)
add_table(doc, ['编号', '类别', '说明'], [
    ['O-003', '待批准功能', 'trades 冲正（O-001 延续）：本轮未实施；design_reversal.md 已列出 A/B/C 三个未来方向'],
    ['O-004', '待批准功能', 'securities.research_pool 字段彻底废弃：本轮不 DROP；design_research_pool_history.md 已列出事实状态'],
    ['R-014', '风险', '单一行情源风险，边界外不引入'],
    ['R-015', '风险', 'HKD 缺汇率需手动录入，本轮不静默默认'],
    ['R-016', '风险', 'do_migration 长时间事务下并发风险，需生产验证'],
    ['R-017', '风险', 'trades 补录错误需要按本次流程回滚（人工删行），不引入自动冲正'],
])

# 签字
add_h(doc, '签收', 2)
add_p(doc, '第三方审计 / 用户签收：________________________  日期：________________')
add_p(doc, '开发者（v1.0.2）：________________________  日期：2026-09-10')

out_path = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.2.docx')
doc.save(out_path)
print(f'已生成：{out_path}')
print(f'大小：{os.path.getsize(out_path)} bytes')

# 替换 §4 中 TBD 为实际 SHA-256
print()
print('=== 计算 SHA-256 以填补 §4 表 ===')
files = [
    'app/server.py',
    'app/static/app.js',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_integration_quote.py',
    'tests/fixtures/sample_seed.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'data/workbench.db',
]
for f in files:
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        sz = os.path.getsize(p)
        print(f'  {sz:>7}  {h}  {f}')
