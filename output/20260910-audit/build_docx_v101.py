#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_docx_v101.py - 生成 v1.0.1 生产交付审计文档
"""
import os, sys, hashlib
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUTPUT_PATH = r'D:\个股工作台\output\20260910-audit\stage3\A-H投研交易工作台交付审计文档-v1.0.1.docx'
SOURCE_HTML = r'D:\个股工作台\output\20260910-audit\stage2\intermediate\output.html'

PRIMARY = RGBColor(0x1F, 0x3A, 0x68)
BG_SOFT = 'F7F9FC'
TEXT_COLOR = RGBColor(0x21, 0x25, 0x29)
MUTED = RGBColor(0x6C, 0x75, 0x7D)
ACCENT = RGBColor(0xC0, 0x39, 0x2B)
WARN = RGBColor(0xB7, 0x79, 0x1F)
SUCCESS = RGBColor(0x2D, 0x6A, 0x4F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

CN_FONT = '宋体'
EN_FONT = 'Times New Roman'
MONO_FONT = 'Consolas'


def set_cell_shading(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tc_pr.append(shd)


def set_cell_borders(cell, hex_color='DEE2E6', size=4):
    tc_pr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        b = OxmlElement(f'w:{edge}')
        b.set(qn('w:val'), 'single')
        b.set(qn('w:sz'), str(size))
        b.set(qn('w:color'), hex_color)
        tcBorders.append(b)
    tc_pr.append(tcBorders)


def set_run_font(run, size_pt=10.5, bold=False, italic=False,
                 cn_font=CN_FONT, en_font=EN_FONT, color=None):
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), cn_font)
    rFonts.set(qn('w:ascii'), en_font)
    rFonts.set(qn('w:hAnsi'), en_font)


def add_para(doc, text='', size_pt=10.5, bold=False, italic=False,
             align=None, color=None, indent_pt=None,
             line_spacing=1.5, space_before=0, space_after=4,
             cn_font=CN_FONT, en_font=EN_FONT):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = line_spacing
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    if indent_pt is not None:
        p.paragraph_format.first_line_indent = Pt(indent_pt)
    if text:
        r = p.add_run(text)
        set_run_font(r, size_pt=size_pt, bold=bold, italic=italic,
                     cn_font=cn_font, en_font=en_font, color=color)
    return p


def add_heading_h1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(12)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '18')
    bottom.set(qn('w:color'), '1F3A68')
    bottom.set(qn('w:space'), '4')
    pBdr.append(bottom)
    pPr.append(pBdr)
    r = p.add_run(text)
    set_run_font(r, size_pt=22, bold=True, color=PRIMARY)
    return p


def add_heading_h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), '24')
    left.set(qn('w:color'), '1F3A68')
    left.set(qn('w:space'), '8')
    pBdr.append(left)
    pPr.append(pBdr)
    p.paragraph_format.left_indent = Pt(8)
    r = p.add_run(text)
    set_run_font(r, size_pt=15, bold=True, color=PRIMARY)
    return p


def add_heading_h3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_run_font(r, size_pt=12.5, bold=True, color=PRIMARY)
    return p


def add_callout(doc, text, kind='warn'):
    palette = {
        'warn':   ('FEF7E6', 'B7791F', '⚠ 警示'),
        'danger': ('FCE8E6', 'C0392B', '✕ 严禁'),
        'ok':     ('E8F5E9', '2D6A4F', '✓ 说明'),
    }
    bg, border, label = palette[kind]
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    cell = table.rows[0].cells[0]
    set_cell_shading(cell, bg)
    set_cell_borders(cell, hex_color=border, size=8)
    p_label = cell.paragraphs[0]
    p_label.paragraph_format.line_spacing = 1.5
    p_label.paragraph_format.space_after = Pt(4)
    r1 = p_label.add_run(label + '   ')
    set_run_font(r1, size_pt=10, bold=True, color=RGBColor(int(border[0:2],16), int(border[2:4],16), int(border[4:6],16)))
    p_body = cell.add_paragraph()
    p_body.paragraph_format.line_spacing = 1.5
    p_body.paragraph_format.space_after = Pt(0)
    r2 = p_body.add_run(text)
    set_run_font(r2, size_pt=10, color=TEXT_COLOR)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_code_block(doc, code_text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.35
    p.paragraph_format.left_indent = Pt(0)
    p.paragraph_format.space_after = Pt(8)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), '18')
    left.set(qn('w:color'), '1F3A68')
    left.set(qn('w:space'), '6')
    pBdr.append(left)
    pPr.append(pBdr)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'F7F9FC')
    pPr.append(shd)
    p.paragraph_format.left_indent = Pt(8)
    r = p.add_run(code_text)
    set_run_font(r, size_pt=9, en_font=MONO_FONT, cn_font=MONO_FONT,
                 color=TEXT_COLOR)


def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.autofit = False if col_widths else True
    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        set_cell_shading(cell, '1F3A68')
        set_cell_borders(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.line_spacing = 1.35
        r = p.add_run(h)
        set_run_font(r, size_pt=10, bold=True, color=WHITE)
    for i, row in enumerate(rows):
        for j, cell_spec in enumerate(row):
            if isinstance(cell_spec, tuple):
                text, opts = cell_spec
            else:
                text, opts = cell_spec, {}
            cell = table.rows[1 + i].cells[j]
            set_cell_borders(cell)
            if i % 2 == 1:
                set_cell_shading(cell, 'F7F9FC')
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.35
            r = p.add_run(str(text))
            set_run_font(r,
                         size_pt=opts.get('size', 10),
                         bold=opts.get('bold', False),
                         italic=opts.get('italic', False),
                         color=opts.get('color'),
                         en_font=MONO_FONT if opts.get('mono') else EN_FONT,
                         cn_font=MONO_FONT if opts.get('mono') else CN_FONT)
    if col_widths:
        for j, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[j].width = w
    return table


def add_signature_block(doc):
    table = doc.add_table(rows=2, cols=2)
    for j, label in enumerate(['编制方（开发组）', '审计方（独立第三方）']):
        cell = table.rows[0].cells[j]
        set_cell_shading(cell, 'E8EEF7')
        set_cell_borders(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.4
        r = p.add_run(label)
        set_run_font(r, size_pt=10.5, bold=True, color=PRIMARY)
    body = ['姓名：\n\n\n日期：\n\n\n签名：\n', '姓名：\n\n\n日期：\n\n\n签名：\n']
    for j, content in enumerate(body):
        cell = table.rows[1].cells[j]
        set_cell_borders(cell)
        tr = cell._tc.getparent()
        trPr = tr.find(qn('w:trPr'))
        if trPr is None:
            trPr = OxmlElement('w:trPr')
            tr.insert(0, trPr)
        trHeight = OxmlElement('w:trHeight')
        trHeight.set(qn('w:val'), '2400')
        trHeight.set(qn('w:hRule'), 'atLeast')
        trPr.append(trHeight)
        for line in content.split('\n'):
            p = cell.add_paragraph()
            p.paragraph_format.line_spacing = 1.6
            r = p.add_run(line)
            set_run_font(r, size_pt=10)
        if cell.paragraphs[0].text == '':
            cell._tc.remove(cell.paragraphs[0]._element)


# =============== 文档主体 ===============
doc = Document()
section = doc.sections[0]
section.page_height = Cm(29.7)
section.page_width = Cm(21.0)
section.top_margin = Cm(2.2)
section.bottom_margin = Cm(2.2)
section.left_margin = Cm(2.5)
section.right_margin = Cm(2.2)
style = doc.styles['Normal']
style.font.size = Pt(10.5)
rPr = style.element.get_or_add_rPr()
rFonts = rPr.find(qn('w:rFonts'))
if rFonts is None:
    rFonts = OxmlElement('w:rFonts')
    rPr.append(rFonts)
rFonts.set(qn('w:eastAsia'), CN_FONT)
rFonts.set(qn('w:ascii'), EN_FONT)
rFonts.set(qn('w:hAnsi'), EN_FONT)

# 封面
tp = doc.add_paragraph()
tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
tp.paragraph_format.space_before = Pt(150)
tp.paragraph_format.space_after = Pt(8)
tp.paragraph_format.line_spacing = 1.3
tr = tp.add_run('A/H 投研交易工作台')
set_run_font(tr, size_pt=30, bold=True, color=PRIMARY)

sp = doc.add_paragraph()
sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
sp.paragraph_format.space_after = Pt(36)
sr = sp.add_run('生产交付审计文档 · Production Delivery Audit Memo  ·  v1.0.1')
set_run_font(sr, size_pt=13, italic=True, color=MUTED)

meta = [
    ('项目代号',     'AH-WORKBENCH-MVP'),
    ('版本',         'v1.0.1（v1.0.0 修复版本，无功能变更）'),
    ('交付日期',     '2026-09-10'),
    ('编制人',       '投研工作台开发组（WorkBuddy 协作 + 人工复核）'),
    ('审计对象',     '源码、数据库、接口、UI、安全、运维、修复点'),
    ('适用范围',     '第三方独立审计 / 内部合规复核'),
]
meta_table = doc.add_table(rows=len(meta), cols=2)
meta_table.autofit = False
for i, (k, v) in enumerate(meta):
    c0, c1 = meta_table.rows[i].cells
    set_cell_borders(c0, hex_color='1F3A68', size=12)
    set_cell_borders(c1, hex_color='1F3A68', size=12)
    c0.width = Cm(4.5)
    c1.width = Cm(11.0)
    p0 = c0.paragraphs[0]
    p0.paragraph_format.line_spacing = 1.5
    r0 = p0.add_run(k)
    set_run_font(r0, size_pt=11, bold=True, color=PRIMARY)
    p1 = c1.paragraphs[0]
    p1.paragraph_format.line_spacing = 1.5
    r1 = p1.add_run(v)
    set_run_font(r1, size_pt=11)

note = doc.add_paragraph()
note.alignment = WD_ALIGN_PARAGRAPH.CENTER
note.paragraph_format.space_before = Pt(32)
note.paragraph_format.line_spacing = 1.7
nr = note.add_run(
    '本文档为面向第三方审计与内部合规复核的完整交付物清单与审计指引。\n'
    '本版本在 v1.0.0 基础上完成 13 项数据完整性修复（详见 §2.5 与 §4），不引入新功能、'
    '不改变投资口径。新增交付物：测试套件、fixture、两个设计稿（冲正与 research_pool）。'
)
set_run_font(nr, size_pt=11, italic=True, color=MUTED)

doc.add_page_break()

# 目录
add_heading_h1(doc, '目录')
toc = [
    ('1. 文档元信息与版本控制', '第 3 页'),
    ('2. v1.0.1 修复范围与系统边界', '第 4 页'),
    ('3. 系统架构与技术栈', '第 5 页'),
    ('4. 交付物清单（含 SHA-256）', '第 6 页'),
    ('5. 数据模型（v1.0.1 Schema）', '第 7 页'),
    ('6. REST API 规格（12 个端点）', '第 9 页'),
    ('7. 前端页面与交互', '第 10 页'),
    ('8. 安全审计要点（修正 v1.0.0 用词）', '第 11 页'),
    ('9. 测试报告：46/46 全通过', '第 12 页'),
    ('10. 部署、运维与数据所有权', '第 14 页'),
    ('11. 风险登记册与已知限制（含冲正/研究池设计稿）', '第 15 页'),
    ('12. 第三方审计重点与建议', '第 16 页'),
    ('13. 关键代码节选（非完整源码）', '第 17 页'),
    ('14. 仍未解决的开放问题', '第 19 页'),
]
for title, page in toc:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.6
    p.paragraph_format.space_after = Pt(2)
    pPr = p._p.get_or_add_pPr()
    tabs = OxmlElement('w:tabs')
    tab = OxmlElement('w:tab')
    tab.set(qn('w:val'), 'right')
    tab.set(qn('w:leader'), 'dot')
    tab.set(qn('w:pos'), '8800')
    tabs.append(tab)
    pPr.append(tabs)
    r1 = p.add_run(title + '\t')
    set_run_font(r1, size_pt=11, color=PRIMARY)
    r2 = p.add_run(page)
    set_run_font(r2, size_pt=11, color=MUTED)

doc.add_page_break()

# §1
add_heading_h1(doc, '1. 文档元信息与版本控制')
add_heading_h3(doc, '1.1 文档版本')
add_table(doc, ['字段', '值'], [
    [('文档版本', {}), ('v1.0.1', {})],
    [('编制日期', {}), ('2026-09-10', {})],
    [('编制人',   {}), ('投研工作台开发组（WorkBuddy 协作 + 人工复核）', {})],
    [('审阅人',   {}), ('（待独立审计方填写）', {})],
    [('密级',     {}), ('内部 · 仅供审计与合规使用', {})],
    [('上一版本',  {}), ('v1.0.0（仍保留于历史文档位置，已被 v1.0.1 替代）', {})],
], col_widths=[Cm(4.0), Cm(11.5)])

add_heading_h3(doc, '1.2 变更记录（v1.0.0 → v1.0.1）')
add_table(doc, ['版本', '日期', '作者', '变更摘要'], [
    [('v1.0.1', {'bold': True}), ('2026-09-10', {}), ('开发组', {}),
     ('完整数据完整性修复：FOREIGN KEY / UNIQUE / CHECK / PRAGMA、'
      '多币种换算、行情字段修正、事务原子化、备份 API、'
      '持仓状态一致性提示、示例数据迁出生产库、追加测试套件。'
      '无功能新增。', {})],
    [('v1.0.0', {}), ('2026-09-10', {}), ('开发组', {}),
     ('首次交付：MVP v1.0.0', {})],
], col_widths=[Cm(2.0), Cm(2.5), Cm(2.0), Cm(9.0)])

add_heading_h3(doc, '1.3 v1.0.0 → v1.0.1 修复要点（13 项）')
add_table(doc, ['编号', '修复点', '对应章节'], [
    [('FIX-01', {'mono':True}), ('腾讯行情解析字段位置：原代码用 f[30] 已是正确（实测 A 股 + 港股都在 f[30]）；v1.0.1 文档与代码一致并提供回归测试',
      {}), ('§4.2 + §9'), ],
    [('FIX-02', {'mono':True}), ('业务表加 FOREIGN KEY → securities(id) ON DELETE RESTRICT', {}), ('§5')],
    [('FIX-03', {'mono':True}), ('PRAGMA foreign_keys=ON 默认启用并对每个新连接生效', {}), ('§5 + §8')],
    [('FIX-04', {'mono':True}), ('securities 加 UNIQUE(exchange, code) 防止重复证券', {}), ('§5 + §9')],
    [('FIX-05', {'mono':True}), ('trades 加 DB 层 CHECK: price>0 / quantity>0 / fee>=0', {}), ('§5 + §9')],
    [('FIX-06', {'mono':True}), ('业务写入 + ledger 写入同一 transaction，失败整体 rollback', {}), ('§9')],
    [('FIX-07', {'mono':True}), ('/api/quotes 同时返回 last_success_at 与 last_error；前端显示最后成功行情时间', {}),
     ('§6 + §7')],
    [('FIX-08', {'mono':True}), ('HKD 持仓缺汇率时 market_value=None, position_pct=None（不再输出错误比例）', {}), ('§9')],
    [('FIX-09', {'mono':True}), ('持仓/状态一致性仅做提示，不自动改 status', {}), ('§9')],
    [('FIX-10', {'mono':True}), ('示例数据 seed 移出生产库 init_db；正式生产 DB 默认空；fixture 单独保存于 tests/fixtures/', {}), ('§10')],
    [('FIX-11', {'mono':True}), ('SQLite 在线 Backup API（make_backup / 备份一致性回归）', {}), ('§10')],
    [('FIX-12', {'mono':True}), ('backup 文档说明修正：不要求"先停服务"才复制，提供在线备份路径；备份后还原启动回归测试通过', {}), ('§10')],
    [('FIX-13', {'mono':True}), ('migrate_v101：v1.0.0 现有数据库无损升级到 v1.0.1 schema（重建表 + 临时关闭外键 + 残表清理）', {}),
     ('§5 + §10')],
], col_widths=[Cm(2.0), Cm(11.5), Cm(2.0)])

add_heading_h3(doc, '1.4 文档范围声明')
add_callout(doc,
    '本系统为个人投研工作台（非券商交易终端、非组合管理系统），不承担自动选股、自动交易、'
    '合规报送、监管接口、税务计算、多账户/多用户权限角色等职责。'
    '本版本（v1.0.1）在不增加功能的前提下完成 13 项数据完整性修复，详见 §2.5 与 §4。',
    kind='warn')

doc.add_page_break()

# §2
add_heading_h1(doc, '2. v1.0.1 修复范围与系统边界')
add_heading_h3(doc, '2.1 本轮修复依据')
add_para(doc,
    '本轮（v1.0.1）由用户在 v1.0.0 交付后下达明确指令启动，14 项"必须处理"指令逐条落实。'
    '审计方应以此为基线核对本版本实现。')

add_heading_h3(doc, '2.2 系统边界（与 v1.0.0 一致）')
add_heading_h3(doc, '2.3 明确不做（与 v1.0.0 一致）— 防止范围蔓延')
add_callout(doc,
    '本 MVP 明确拒绝实现以下功能。任何要求新增此清单内能力的请求，应作为新项目立项而非范围变更。',
    kind='danger')
add_table(doc, ['明确不做', '原因'], [
    [('自动选股 / 自动打分',     {}), ('不替代深穿研究', {})],
    [('自动生成新投资规则',       {}), ('不擅自改写研究逻辑', {})],
    [('自动交易 / 算法下单',      {}), ('不代替人做执行判断', {})],
    [('行情变化自行修改交易计划', {}), ('计划修改必须由人发起并附说明', {})],
    [('复杂收益归因 / 因子归因', {}), ('超出 MVP 范围', {})],
    [('量化评分 / 量化回测',      {}), ('不在工作台职责之内', {})],
    [('技术指标系统（MA/MACD/...）',{}), ('用户基于研究结论而非指标', {})],
    [('组合优化 / VaR / Monte Carlo',{}), ('超出 MVP 范围', {})],
    [('多账户 / 多用户 / 角色权限', {}), ('个人工具，无需', {})],
    [('社交 / 新闻门户 / 研报聚合',  {}), ('数据源与深穿会话负责', {})],
    [('报价"建议买入"信号',         {}), ('系统只显示客观事实，价格/区间比对交给人', {})],
], col_widths=[Cm(7.0), Cm(8.5)])

add_heading_h3(doc, '2.4 v1.0.1 范围限制（与 v1.0.0 一致）')
add_para(doc, '请参照 §2.3。该清单下的功能不是 bug，而是设计决策。', italic=True, color=MUTED)

add_heading_h3(doc, '2.5 本轮明确未做的（未实施，待用户批准）')
add_table(doc, ['项', '状态', '依据文档'], [
    [('trades 冲正（reversal）业务接口', {}), ('设计稿已写出，未实现', {'bold': True}),
     ('tests/design_reversal.md', {'mono': True})],
    [('research_pool 历史性重构',         {}), ('设计稿已写出，未实施', {'bold': True}),
     ('tests/design_research_pool_history.md', {'mono': True})],
    [('示例数据预置',                     {}), ('已移除（默认空库）', {'bold': True}),
     ('§10', {'mono': True})],
    [('trades UPDATE / DELETE 业务接口',   {}), ('仍然不存在',  {}), ('§8')],
    [('多行情源 / 多币种系统 / 移动端 / 量化指标 / Markdown 导入',
      {}), ('不在本版本范围',  {}), ('§2.3')],
], col_widths=[Cm(8.5), Cm(4.0), Cm(3.0)])

add_heading_h3(doc, '2.6 与"深穿"会话的关系（不变）')
add_table(doc, ['环节', '负责方'], [
    [('标的筛选与拉网',          {}), ('深穿会话', {})],
    [('单股深穿 / 估值 / 风险评估',{}), ('深穿会话', {})],
    [('输出标准化信息卡',         {}), ('深穿会话（输出）→ 工作台（导入）', {})],
    [('日常跟踪与提示',           {}), ('工作台', {})],
    [('出现重大变化回归深穿',     {}), ('工作台（识别）→ 深穿会话（出结论）→ 工作台（更新）', {})],
], col_widths=[Cm(7.0), Cm(8.5)])

doc.add_page_break()

# §3 架构（保持精简）
add_heading_h1(doc, '3. 系统架构与技术栈')
add_heading_h3(doc, '3.1 总体架构')
add_code_block(doc,
    '┌──────────────────────────────────────────────────────────────┐\n'
    '│                     浏览器前端 (Chrome / Edge)                │\n'
    '│  ┌──────────────┬──────────────┬──────────────────────────┐  │\n'
    '│  │ 今日工作台    │ 标的库        │ 个股详情 / 流水 / 台账    │  │\n'
    '│  │              │              │  (SPA, 单页路由)         │  │\n'
    '│  └──────────────┴──────────────┴──────────────────────────┘  │\n'
    '│              vanilla JS · 零框架 · 39 KB                     │\n'
    '└──────────────────────────────────────────────────────────────┘\n'
    '          │ HTTP/1.1 (JSON) · localhost:8765（默认）\n'
    '          ▼\n'
    '┌──────────────────────────────────────────────────────────────┐\n'
    '│              Python 3.13 HTTP 服务 (stdlib only)              │\n'
    '│   ┌──────────┬───────────┬───────────┬───────────┬─────────┐  │\n'
    '│   │ REST API │ 静态资源   │ SQLite    │ 行情代理   │ 备份    │  │\n'
    '│   │ (12端点)│ 服务器    │ (PRAGMA fk=ON) │ (qq.com) │ (在线 API) │\n'
    '│   └──────────┴───────────┴───────────┴───────────┴─────────┘  │\n'
    '└──────────────────────────────────────────────────────────────┘\n'
    '          │                                  │\n'
    '          ▼                                  ▼\n'
    '┌──────────────────────────┐      ┌──────────────────────────┐\n'
    '│  data/workbench.db       │      │ 腾讯免费行情接口           │\n'
    '│  (SQLite, WAL, v1.0.1)   │      │ qt.gtimg.cn (只读 GET)    │\n'
    '└──────────────────────────┘      └──────────────────────────┘')

add_heading_h3(doc, '3.2 技术栈（v1.0.1）')
add_table(doc, ['组件', '选择'], [
    [('后端语言',     {}), ('Python 3.13.12（标准库 + 原始 SQL）', {})],
    [('HTTP 服务器',  {}), ('Python 标准库 http.server', {})],
    [('数据库',       {}), ('SQLite (WAL, PRAGMA foreign_keys=ON)', {})],
    [('前端',         {}), ('原生 HTML + CSS + JS（零框架）', {})],
    [('行情数据源',   {}), ('腾讯免费行情 (qt.gtimg.cn)', {})],
    [('备份机制',     {}), ('SQLite 原生 Backup API（不需停服）', {'bold': True})],
    [('示例数据',     {}), ('tests/fixtures/sample_seed.py（独立于生产库）', {'bold': True})],
], col_widths=[Cm(4.0), Cm(11.5)])

add_heading_h3(doc, '3.3 目录结构（v1.0.1）')
add_code_block(doc,
    'D:\\个股工作台\\\n'
    '├── app\\\n'
    '│   ├── server.py               # v1.0.1 后端（49.2 KB）\n'
    '│   └── static\\\n'
    '│       ├── index.html          # 单页入口\n'
    '│       ├── app.js              # 前端逻辑（39.4 KB, v1.0.1 适配）\n'
    '│       └── style.css           # 样式（13.6 KB）\n'
    '├── tests\\\n'
    '│   ├── test_v101.py            # 46 个断言自动化回归\n'
    '│   ├── fixtures/\\\n'
    '│   │   └── sample_seed.py      # 示例数据独立 fixture\n'
    '│   ├── design_reversal.md      # trades 冲正设计稿（未实施）\n'
    '│   └── design_research_pool_history.md  # research_pool 重构设计稿\n'
    '├── data/\n'
    '│   ├── workbench.db           # v1.0.1 schema, 默认空库\n'
    '│   └── backup/                # 在线备份 + 测试备份\n'
    '├── 启动工作台.bat              # Windows 启动器\n'
    '└── output/                     # 本审计文档')

doc.add_page_break()

# §4 交付物清单（含 SHA-256，v1.0.1）
add_heading_h1(doc, '4. 交付物清单（含 SHA-256）')
add_heading_h3(doc, '4.1 源代码交付清单')
add_table(doc, ['#', '文件路径', '字节数', 'SHA-256'], [
    [('1', {}),
     ('app/server.py', {'mono': True}),
     ('49,234', {'bold': True}),
     ('eddad0a4215cf86fa9898f5d1999e881fe7786a30824d6040c28c768d2bbc1c1', {'mono': True})],
    [('2', {}),
     ('app/static/index.html', {'mono': True}),
     ('934', {'bold': True}),
     ('fb4c57198af812b4a317f40609a223ed47377598b034f30bb3bb32ac6f39aa8b', {'mono': True})],
    [('3', {}),
     ('app/static/app.js', {'mono': True}),
     ('39,385', {'bold': True}),
     ('9ac5cc38a525dff00243a7bb85424132d467fce1da85fc5c2cf51ee486883513', {'mono': True})],
    [('4', {}),
     ('app/static/style.css', {'mono': True}),
     ('13,584', {'bold': True}),
     ('185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635', {'mono': True})],
    [('5', {}),
     ('启动工作台.bat', {'mono': True}),
     ('445', {'bold': True}),
     ('8ae2a47b8da27c6ca3d43550fd372c4e6177fa3d0f13b44ab2af664ceada22c0', {'mono': True})],
], col_widths=[Cm(1.2), Cm(4.0), Cm(1.8), Cm(8.5)])

add_heading_h3(doc, '4.2 v1.0.1 新增交付物（测试 + 设计 + fixture）')
add_table(doc, ['#', '文件路径', '字节数', 'SHA-256'], [
    [('6', {}),
     ('tests/test_v101.py', {'mono': True}),
     ('23,140', {'bold': True}),
     ('91c4408eed89f1369c9219cdf9401650d7772e4532ddacf6732f131920a1f886', {'mono': True})],
    [('7', {}),
     ('tests/fixtures/sample_seed.py', {'mono': True}),
     ('6,900', {'bold': True}),
     ('57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde', {'mono': True})],
    [('8', {}),
     ('tests/design_reversal.md', {'mono': True}),
     ('4,604', {'bold': True}),
     ('0d1cfe29282e4604372f39b351ae8951ee72a378b4d7e9631531108c1ab76032', {'mono': True})],
    [('9', {}),
     ('tests/design_research_pool_history.md', {'mono': True}),
     ('4,462', {'bold': True}),
     ('94ab1a27958c98ecf2624e9e3e93064e36abcfbfed44a6dd3ed913061f7994e4', {'mono': True})],
], col_widths=[Cm(1.2), Cm(4.5), Cm(1.8), Cm(8.0)])

add_para(doc,
    '合计源代码 5 个文件，104,582 字节；新增交付物 4 个（含 46 个测试断言 + 2 个设计稿 + 1 个 fixture）。',
    italic=True, color=MUTED)

add_heading_h3(doc, '4.3 数据文件交付清单')
add_table(doc, ['文件', '字节数', 'SHA-256', '说明'], [
    [('data/workbench.db', {'mono': True}),
     ('52,224', {'bold': True}),
     ('实际取运行时校验（写入会改变）', {'italic': True, 'color': MUTED}),
     ('SQLite 数据库；v1.0.1 schema 已迁；默认空库（已移除示例证券）', {})],
], col_widths=[Cm(4.0), Cm(1.8), Cm(7.0), Cm(2.7)])

add_heading_h3(doc, '4.4 数据备份（v1.0.1 在线备份）')
add_table(doc, ['文件', '说明'], [
    [('data/backup/workbench-pre-v101-20260910_155602.db', {'mono': True}),
     ('v1.0.0 状态备份（修复前的原始数据，含示例美图 + 道通 + 历史 trades/ledger）', {})],
    [('data/backup/workbench-<时间戳>.db', {'mono': True}),
     ('v1.0.1 在线 Backup API 生成（无需停服）', {})],
], col_widths=[Cm(7.5), Cm(8.0)])

add_heading_h3(doc, '4.5 验证方法')
add_para(doc, '审计方可使用以下命令独立验证文件完整性（Windows PowerShell / macOS / Linux 均适用）：')
add_code_block(doc,
    'Get-FileHash -Path "app\\server.py" -Algorithm SHA256\n'
    '# 期望输出：EDDAD0A4215CF86FA9898F5D1999E881FE7786A30824D6040C28C768D2BBC1C1')

doc.add_page_break()

# §5 数据模型
add_heading_h1(doc, '5. 数据模型（v1.0.1 Schema）')
add_heading_h3(doc, '5.1 v1.0.1 关键变更')
add_table(doc, ['项', 'v1.0.0', 'v1.0.1'], [
    [('业务表 FOREIGN KEY', {}), ('无', {'color': ACCENT}),
     ('research / trade_plans / trades / decision_ledger.security_id → securities(id) ON DELETE RESTRICT', {'bold': True})],
    [('securities UNIQUE', {}), ('无', {'color': ACCENT}),
     ('UNIQUE(exchange, code)', {'bold': True})],
    [('trades CHECK', {}), ('仅应用层校验', {'color': ACCENT}),
     ('DB CHECK: price>0 / quantity>0 / fee>=0 / side IN (买入,卖出)', {'bold': True})],
    [('PRAGMA foreign_keys', {}), ('未启用 (默认 OFF)', {'color': ACCENT}),
     ('每个连接 ON', {'bold': True})],
    [('securities 额外列', {}), ('无 research_pool / current_price', {'color': ACCENT}),
     ('已补列', {'bold': True})],
    [('settings 关键键', {}), ('无', {'color': ACCENT}),
     ('hkd_cny_rate / account_size_cny / schema_version', {'bold': True})],
], col_widths=[Cm(4.0), Cm(5.5), Cm(6.0)])

add_heading_h3(doc, '5.2 表清单（v1.0.1）')
add_table(doc, ['表名', '职责', '是否 append-only'], [
    [('securities',       {'mono': True}),('标的本身（代码、市场、行业、A/H 关联）', {}),('元信息可更新；禁止删', {})],
    [('research',         {'mono': True}),('研究结论（版本化）', {}),                        ('是（永远新增版本）', {'bold': True})],
    [('trade_plans',      {'mono': True}),('交易计划（版本化）', {}),                        ('是（同上）', {'bold': True})],
    [('trades',           {'mono': True}),('真实交易流水', {}),                             ('是（仅新增；冲正尚未实现）', {'bold': True})],
    [('decision_ledger',  {'mono': True}),('决策台账', {}),                                 ('是（纯 append-only）', {'bold': True})],
    [('settings',         {'mono': True}),('运行期配置（账户规模、汇率、schema_version）', {}),('可更新', {})],
], col_widths=[Cm(3.5), Cm(7.5), Cm(4.5)])

add_heading_h3(doc, '5.3 关键 DDL（v1.0.1）')
add_code_block(doc,
    'CREATE TABLE securities (\n'
    '  id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '  code TEXT NOT NULL,\n'
    '  exchange TEXT NOT NULL CHECK (exchange IN (\'SH\',\'SZ\',\'HK\')),\n'
    '  name TEXT NOT NULL,\n'
    '  currency TEXT NOT NULL DEFAULT \'CNY\',\n'
    '  market TEXT NOT NULL DEFAULT \'A股\',\n'
    '  sector TEXT DEFAULT \'\',\n'
    '  ah_link_id INTEGER,\n'
    '  notes TEXT DEFAULT \'\',\n'
    '  status TEXT NOT NULL DEFAULT \'等价格\',\n'
    '  research_pool TEXT DEFAULT \'\',\n'
    '  current_price REAL,\n'
    '  current_price_updated_at TEXT,\n'
    '  created_at TEXT, updated_at TEXT,\n'
    '  UNIQUE(exchange, code)                           -- v1.0.1 新增\n'
    ');\n'
    '\n'
    'CREATE TABLE trades (\n'
    '  id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
    '  security_id INTEGER NOT NULL\n'
    '    REFERENCES securities(id) ON DELETE RESTRICT,  -- v1.0.1 新增\n'
    '  trade_date TEXT NOT NULL,\n'
    '  side TEXT NOT NULL CHECK (side IN (\'买入\',\'卖出\')),\n'
    '  price REAL NOT NULL CHECK (price > 0),           -- v1.0.1 新增\n'
    '  quantity REAL NOT NULL CHECK (quantity > 0),     -- v1.0.1 新增\n'
    '  fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),    -- v1.0.1 新增\n'
    '  note TEXT DEFAULT \'\',\n'
    '  created_at TEXT\n'
    ');\n'
    '-- 其他业务表 research / trade_plans / decision_ledger\n'
    '-- 同样具有 security_id REFERENCES securities(id) ON DELETE RESTRICT')

add_heading_h3(doc, '5.4 数据迁移（v1.0.0 → v1.0.1）')
add_table(doc, ['项', '说明'], [
    [('migrate_v101() 自动触发', {}), ('init_db(seed=False) 时对已存在 DB 自动调用', {})],
    [('缺失列补齐', {}), ('securities 加 research_pool / current_price / current_price_updated_at（ALTER TABLE）', {})],
    [('外键 + UNIQUE', {}), ('通过"重建表"模式（CREATE TABLE new → INSERT → DROP → RENAME），临时 PRAGMA foreign_keys=OFF 包裹', {})],
    [('trades CHECK', {}), ('同上重建表方式', {})],
    [('残表清理', {}), ('每次迁移开始 DROP TABLE IF EXISTS *__new（避免上次中断留下）', {})],
    [('数据保留', {}), ('迁移过程不删任何业务数据，INSERT FROM old SELECT 保持 rowid / created_at 不变', {'bold': True})],
    [('settings 默认键', {}), ('hkd_cny_rate / account_size_cny / schema_version=1.0.1 自动写入（缺则补）', {})],
], col_widths=[Cm(5.0), Cm(10.5)])

doc.add_page_break()

# §6 REST API
add_heading_h1(doc, '6. REST API 规格（v1.0.1：共 12 个端点）')
add_heading_h3(doc, '6.1 接口总览（实测 12 个）')

add_table(doc, ['方法', '路径', '用途', '事务'], [
    [('GET',  {}),(' /api/securities',                  {'mono': True}),('列出全部标的', {}),('-', {})],
    [('POST', {}),(' /api/securities',                  {'mono': True}),('创建标的', {}), ('事务内', {'bold': True})],
    [('GET',  {}),(' /api/securities/{id}',             {'mono': True}),('标的详情', {}),('-', {})],
    [('PUT',  {}),(' /api/securities/{id}',             {'mono': True}),('更新基本信息', {}),('事务内', {'bold': True})],
    [('POST', {}),(' /api/securities/{id}/status',      {'mono': True}),('状态变更（reason 必填）', {}),
     ('事务内', {'bold': True})],
    [('POST', {}),(' /api/securities/{id}/trades',      {'mono': True}),('新增交易', {}),('事务内', {'bold': True})],
    [('POST', {}),(' /api/securities/{id}/ledger',      {'mono': True}),('新增决策台账备注', {}),
     ('事务内', {'bold': True})],
    [('PUT',  {}),(' /api/securities/{id}/research',    {'mono': True}),('新增研究版本', {}),
     ('事务内', {'bold': True})],
    [('PUT',  {}),(' /api/securities/{id}/plan',        {'mono': True}),('新增交易计划版本', {}),
     ('事务内', {'bold': True})],
    [('GET',  {}),(' /api/quotes?symbols=...',          {'mono': True}),('腾讯行情代理', {}),('-', {})],
    [('GET',  {}),(' /api/settings',                    {'mono': True}),('读取设置', {}),('-', {})],
    [('PUT',  {}),(' /api/settings',                    {'mono': True}),('更新设置', {}),('事务内', {'bold': True})],
], col_widths=[Cm(1.8), Cm(5.5), Cm(5.5), Cm(2.7)])

add_heading_h3(doc, '6.2 v1.0.1 新增 / 修改的端点字段')
add_table(doc, ['端点', '变化'], [
    [('GET /api/quotes', {'mono': True}),
     ('响应同时返回 last_success_at 与 last_error；前端据此显示"最后成功行情时间"与失败提示', {})],
    [('GET /api/securities/{id}', {'mono': True}),
     ('响应 position 内增加 currency / market_value / market_value_currency / fx_rate_used / fx_rate_missing / position_pct；'
      '响应增加 position_consistency（持仓状态一致性提示）', {})],
    [('GET /api/quotes (failure path)', {'mono': True}),
     ('失败时仍保留 data 中上一次成功的股票（不伪装为最新）', {})],
    [('POST /api/securities', {'mono': True}),
     ('应用层先校验 + DB 层 UNIQUE 兜底；同一 exchange+code 拒绝重复', {})],
], col_widths=[Cm(7.0), Cm(8.5)])

add_heading_h3(doc, '6.3 错误码与边界（v1.0.1）')
add_table(doc, ['HTTP', '含义', '触发条件'], [
    [('200', {}),('成功', {}),('-', {})],
    [('400', {}),('业务校验失败', {}),
     ('状态变更缺 reason / 价格<=0 / 数量<=0 / 手续费<0 / 卖出超持仓 / 重复 (exchange,code) / settings 非数字', {})],
    [('404', {}),('标的不存在', {}),('标的无 / static 资源路径穿越', {})],
    [('500', {}),('服务端异常', {}),('意外错误。IntegrityError 一律转为 400', {'bold': True})],
], col_widths=[Cm(2.0), Cm(4.0), Cm(9.5)])

add_heading_h3(doc, '6.4 关键完整性输入校验（应用 + DB 双层）')
add_table(doc, ['字段', '应用层', 'DB 层'], [
    [('trades.side', {}),('必须为 买入/卖出', {}),('CHECK (side IN (买入,卖出))', {'mono': True})],
    [('trades.price', {}),('> 0', {}),('CHECK (price > 0)', {'mono': True})],
    [('trades.quantity', {}),('> 0', {}),('CHECK (quantity > 0)', {'mono': True})],
    [('trades.fee', {}),('>= 0', {}),('CHECK (fee >= 0)', {'mono': True})],
    [('securities.exchange', {}),('IN {SH,SZ,HK}', {}),('CHECK (exchange IN (SH,SZ,HK))', {'mono': True})],
    [('securities (exchange,code)', {}),('重复返回 ApiError 400', {}),('UNIQUE(exchange, code)', {'mono': True})],
    [('状态变更 reason', {}),('必填', {}),('-', {})],
    [('卖出超持仓', {}),('拒绝', {}),('-（业务校验）', {})],
    [('任意 security_id 引用', {}),('-', {}),('FOREIGN KEY REFERENCES securities(id) ON DELETE RESTRICT', {'mono': True})],
], col_widths=[Cm(4.5), Cm(5.0), Cm(6.0)])

doc.add_page_break()

# §7 前端
add_heading_h1(doc, '7. 前端页面与交互（v1.0.1）')
add_heading_h3(doc, '7.1 单页应用结构')
add_table(doc, ['区域', '职责'], [
    [('顶部状态条', {}),('展示账户总规模（点击修改）、当前服务状态、refreshQuotes 按钮、上次成功 / 失败行情时间', {})],
    [('左侧导航',    {}),('「今日工作台」「标的库」「新建标的」三个 Tab', {})],
    [('主内容区',    {}),('按 Tab 渲染', {})],
], col_widths=[Cm(4.0), Cm(11.5)])

add_heading_h3(doc, '7.2 v1.0.1 UI 变化')
add_table(doc, ['位置', '变化'], [
    [('首页 / 列表 / 详情头部', {}),
     ('"行情时间"字段统一显示：A 股/港股均展示 market_time（YYYY-MM-DD HH:MM:SS）', {})],
    [('顶部状态条', {}),
     ('区分 last_success_at 与 last_error：失败时显示「行情获取失败，价格可能过期」+ 最后成功时间', {})],
    [('个股详情 · 持仓区', {}),
     ('增加"持仓市值（已折算）"显式提示；HKD 缺汇率时显示"无法计算 / 待汇率"（不再错误除算）', {})],
    [('个股详情 · 顶部 banner', {}),
     ('"持仓 / 状态一致性"提示：有持仓但 status≠持仓中 / 状态=持仓中 但无持仓时显示对应 issue（不自动改）', {})],
    [('首页"处理/跟踪"分组', {}),
     ('逻辑不变（事实判断），仅同步行情时间字段', {})],
], col_widths=[Cm(4.5), Cm(11.0)])

add_heading_h3(doc, '7.3 关键交互（事实化展示）')
add_table(doc, ['操作', '系统行为'], [
    [('点击"买入/卖出"按钮', {}),
     ('弹出表单，提交后生成一条 trade + 一条 ledger；不做任何"建议"', {})],
    [('修改交易计划',         {}),
     ('弹出表单，保存后生成新版本 + 自动写入台账', {})],
    [('变更状态',              {}),
     ('必填"变更原因"字段，否则按钮不可用。提交后自动写入台账', {})],
    [('编辑账号总规模 / 汇率', {}),
     ('点击顶部数字或设置弹窗，保存后立即生效', {})],
    [('刷新行情',              {}),
     ('手动触发 GET /quotes；60 秒后自动刷新；失败时显示上次成功时间', {})],
], col_widths=[Cm(5.0), Cm(10.5)])

doc.add_page_break()

# §8 安全（修正 v1.0.0 用词）
add_heading_h1(doc, '8. 安全审计要点（修正 v1.0.0 用词）')
add_heading_h3(doc, '8.1 用词修正说明')
add_callout(doc,
    'v1.0.0 文档中部分表述使用了"绝对不可能"等绝对化措辞（如"SQL 注入：不可能"）。'
    '此类表述在第三方审计中通常要求改写——任何代码层面的缓解都只能证明"在已验证的条件下有效"，'
    '不能保证未来无新攻击面。v1.0.1 全部改为"在已验证条件下有效缓解"。',
    kind='warn')

add_heading_h3(doc, '8.2 攻击面清单（v1.0.1，措辞修正）')
add_table(doc, ['攻击面', '状态', '已验证缓解'], [
    [('公网监听', {}),
     ('未暴露', {}),
     ('服务绑定 127.0.0.1；端口 8765 仅本地可达（验证：netstat -an | findstr 8765 应只见 127.0.0.1）', {})],
    [('认证授权', {}),
     ('N/A（本系统单用户工具）', {}),
     ('无登录会话；风险仅限于本地物理 / 系统级账户', {})],
    [('SQL 注入', {}),
     ('已通过参数化查询大幅降低风险', {'bold': True}),
     ('全部 SQL 使用 ? 占位符；无 f-string 字符串拼接；测试覆盖 5+ 条非法 INSERT', {})],
    [('路径穿越', {}),
     ('已缓解', {}),
     ('静态资源 _static() 校验路径前缀、拒绝 .. 与绝对路径；测试：GET /static/../server.py → 404', {})],
    [('XSS', {}),
     ('低风险', {}),
     ('前端使用 textContent 渲染（esc()）；不调用 innerHTML', {})],
    [('CSRF', {}),
     ('N/A', {}),
     ('外部站点无法跨域访问 localhost:8765；浏览器同源策略保护', {})],
    [('第三方依赖漏洞', {}),
     ('N/A', {}),
     ('零第三方 Python 依赖（仅 stdlib）；前端仅原生 DOM API', {})],
    [('数据外泄', {}),
     ('已通过"无上传通道"设计大幅降低风险', {'bold': True}),
     ('代码层面无任何外发逻辑；唯一外网调用 GET qt.gtimg.cn 是只读行情', {})],
    [('数据库完整性约束被绕过', {}),
     ('已修', {'color': SUCCESS, 'bold': True}),
     ('v1.0.0 未启用 PRAGMA foreign_keys=ON / 缺 UNIQUE / 缺 CHECK 均为已识别修复；v1.0.1 加固', {})],
    [('行情数据被伪装为最新', {}),
     ('已修', {'color': SUCCESS, 'bold': True}),
     ('v1.0.1 行情失败时仍返回 data 中上次成功项，前端明示"可能过期"', {})],
    [('trades 误录无法修复', {}),
     ('已识别风险 + 设计稿待批', {}),
     ('tests/design_reversal.md 已写冲正方案；本版本未实施', {})],
], col_widths=[Cm(3.5), Cm(3.5), Cm(8.5)])

add_heading_h3(doc, '8.3 数据所有权')
add_callout(doc,
    '本工作台不依赖任何云端 SaaS，所有数据保存于本地 data/workbench.db。\n'
    '所有读操作：行情数据仅 GET 至 qt.gtimg.cn（公开免费接口）。\n'
    '所有写操作：仅写入本地 SQLite 文件，无任何上传通道。',
    kind='ok')

doc.add_page_break()

# §9 测试报告（核心）
add_heading_h1(doc, '9. 测试报告：46/46 全通过')
add_heading_h3(doc, '9.1 测试覆盖一览（v1.0.1）')
add_table(doc, ['#', '覆盖项', '断言数', '结果'], [
    [('1', {}), ('A 股真实行情解析（fetch_tencent）', {}), ('2', {}), ('✅', {})],
    [('2', {}), ('港股真实行情解析', {}), ('3', {}), ('✅', {})],
    [('3', {}), ('行情失败时 last_success_at / last_error 同时返回', {}), ('3', {}), ('✅', {})],
    [('4', {}), ('过期行情标记', {}), ('1', {}), ('✅', {})],
    [('5', {}), ('DB Schema：FOREIGN KEY × 4 / UNIQUE / CHECK × 3 / side IN / PRAGMA', {}), ('9', {}), ('✅', {})],
    [('6', {}), ('重复证券 (exchange, code) 被 DB UNIQUE 拦截', {}), ('1', {}), ('✅', {})],
    [('7', {}), ('trades 非法值（price<=0 / qty<=0 / fee<0 / side 非法）DB 拦截', {}), ('4', {}), ('✅', {})],
    [('8', {}), ('超卖拦截（应用层）', {}), ('1', {}), ('✅', {})],
    [('9', {}), ('业务写入 + ledger 同 transaction 失败整体 rollback', {}), ('2', {}), ('✅', {})],
    [('10', {}), ('研究 / 计划版本化（历史保留）', {}), ('2', {}), ('✅', {})],
    [('11', {}), ('多币种：HKD 缺汇率 → market_value=None / position_pct=None', {}), ('5', {}), ('✅', {})],
    [('12', {}), ('持仓/状态一致性提示（不自动改）', {}), ('2', {}), ('✅', {})],
    [('13', {}), ('生产空库初始化（init_db seed=False → 0 securities）', {}), ('1', {}), ('✅', {})],
    [('14', {}), ('SQLite 在线 Backup 一致性', {}), ('2', {}), ('✅', {})],
    [('15', {}), ('settings 关键键在迁移后存在（备份中验证）', {}), ('3', {}), ('✅', {})],
    [('16', {}), ('server.py 不出现"UPDATE trades"业务路径', {}), ('2', {}), ('✅', {})],
    [('17', {}), ('0. 备份生产 DB', {}), ('3', {}), ('✅', {})],
], col_widths=[Cm(1.0), Cm(9.0), Cm(1.5), Cm(4.0)])

add_para(doc, '断言总数：46 ✅ / 0 ❌（2026-09-10 16:24 实测）',
         bold=True, color=SUCCESS)

add_heading_h3(doc, '9.2 测试运行')
add_para(doc, '执行命令：')
add_code_block(doc,
    '# 全量测试\n'
    'python tests/test_v101.py\n'
    '\n'
    '# 备份生产 DB 后再跑（自动 restore）\n'
    '# 测试脚本会先把生产 DB 备份到 data/backup/workbench-test-restore-<时间>.db\n'
    '# 然后清理、跑 assertion、最后从备份还原')

add_heading_h3(doc, '9.3 仍然存在的"未覆盖"项')
add_para(doc, '以下场景在本版本自动化回归中尚未覆盖，建议下版本补充：', italic=False)
for item in [
    'SQLite 并发写（多进程同时写入）— 当前预期单用户串行访问',
    '10,000+ 笔交易流水的性能 / 大数据量 UI 渲染',
    '断网/弱网/超时降级（已 last_success_at 保护但未做 30s 心跳）',
    'A/H 自动关联建议 — 当前 ah_link_id 需手工维护',
]:
    p = doc.add_paragraph(item, style='List Bullet')
    p.paragraph_format.line_spacing = 1.5
    for r in p.runs:
        set_run_font(r, size_pt=10.5)

doc.add_page_break()

# §10 部署 / 运维 / 备份
add_heading_h1(doc, '10. 部署、运维与数据所有权（v1.0.1）')
add_heading_h3(doc, '10.1 系统要求')
add_table(doc, ['项', '要求'], [
    [('操作系统', {}),('Windows 10/11 / macOS 12+ / Linux', {})],
    [('Python',   {}),('3.10+（已部署 3.13.12）', {})],
    [('磁盘',     {}),('数据库文件 < 100 MB（实际约 52 KB）', {})],
    [('网络',     {}),('仅在 60s 自动刷新 + 手动刷新时联网', {})],
], col_widths=[Cm(4.0), Cm(11.5)])

add_heading_h3(doc, '10.2 启动 / 停止')
add_code_block(doc,
    '# Windows（双击启动器）\n'
    '启动工作台.bat\n'
    '\n'
    '# 跨平台：\n'
    'python app/server.py                          # 默认启动\n'
    'python app/server.py --port 9000              # 自定义端口\n'
    'python app/server.py --no-browser             # 不自动打开浏览器\n'
    'python app/server.py --seed                   # 显式加载 fixture 中的示例数据（仅开发/测试用）\n'
    '\n'
    '# 在线备份（无需停服）：\n'
    'python app/server.py --backup                 # 默认写到 data/backup/workbench-<时间>.db\n'
    'python app/server.py --backup /path/to/x.db  # 自定义目标\n'
    '\n'
    '# 停止：Ctrl+C 或 taskkill /F /PID <pid>')

add_heading_h3(doc, '10.3 数据备份（修正 v1.0.0 措辞）')
add_callout(doc,
    'v1.0.0 文档建议"复制 data/workbench.db 即备份"——这在 SQLite WAL 模式下不够安全（WAL 文件可能尚未 checkpoint）。\n'
    'v1.0.1 改为两种路径：\n'
    '  • 推荐：python server.py --backup（或 make_backup(dst) 调用 SQLite 原生 Backup API），无需停服；\n'
    '  • 兼容：先停服再复制（stop 服务 → cp 文件 → restart）。',
    kind='warn')

add_heading_h3(doc, '10.4 备份→还原→启动一致性回归（实测）')
add_code_block(doc,
    '# 测试脚本内置（tests/test_v101.py §13）：\n'
    '1. sqlite3.connect(SRC_DB) 打开源\n'
    '2. sqlite3.connect(DST_DB) 打开目标\n'
    '3. src.backup(dst)         一致性复制\n'
    '4. 验证行数 / 关键记录存在\n'
    '# 全部通过（46/46）')

add_heading_h3(doc, '10.5 数据库迁移路径')
add_table(doc, ['场景', '操作'], [
    [('首次启动', {}),('init_db(seed=False) 自动建表', {})],
    [('v1.0.0 → v1.0.1 升级', {}),('init_db(seed=False) 自动调用 migrate_v101()', {})],
    [('回退 v1.0.1 → v1.0.0', {}),('当前不支持自动回退（SQLite schema 演进单向）', {'color': WARN})],
], col_widths=[Cm(5.0), Cm(10.5)])

add_heading_h3(doc, '10.6 已知运维注意事项')
for item in [
    '启动前确保 8765 端口未被占用；可用 --port 切换',
    '数据库文件绝对不可手动编辑，请通过界面操作',
    '迁移过程在 PRAGMA foreign_keys=OFF 下重建表，确保所有数据完整复制',
    'WAL 模式下偶发残留 *.db-wal /*.db-shm 文件；正常停止服务后会自动 checkpoint',
]:
    p = doc.add_paragraph(item, style='List Bullet')
    p.paragraph_format.line_spacing = 1.5
    for r in p.runs:
        set_run_font(r, size_pt=10.5)

doc.add_page_break()

# §11 风险
add_heading_h1(doc, '11. 风险登记册与已知限制（含设计稿）')
add_heading_h3(doc, '11.1 已修复（v1.0.1 范围内）')
add_table(doc, ['编号', '风险描述', '修复方式'], [
    [('R-001', {'mono':True}), ('trades CHECK 仅应用层；DB 层可被绕过', {'color': ACCENT}),
     ('v1.0.1 加 DB CHECK（FIX-05）', {'color': SUCCESS})],
    [('R-002', {'mono':True}), ('业务表 security_id 无外键；孤儿记录破坏 append-only', {'color': ACCENT}),
     ('v1.0.1 加 FOREIGN KEY + PRAGMA fk=ON（FIX-02, 03）', {'color': SUCCESS})],
    [('R-003', {'mono':True}), ('重复 (exchange, code) 反复创建标的', {'color': ACCENT}),
     ('v1.0.1 加 UNIQUE + 应用层预检（FIX-04）', {'color': SUCCESS})],
    [('R-004', {'mono':True}), ('事务不原子：业务成功但台账缺失（单条 insert，但跨表）', {'color': ACCENT}),
     ('v1.0.1 显式 BEGIN/COMMIT/ROLLBACK + 服务层 _run_in_transaction（FIX-06）', {'color': SUCCESS})],
    [('R-005', {'mono':True}), ('备份文档教用户"直接复制"，WAL 模式不安全', {'color': ACCENT}),
     ('v1.0.1 用 SQLite 原生 Backup API（FIX-11, 12）', {'color': SUCCESS})],
    [('R-006', {'mono':True}), ('行情接口失败时返回空 data，使用方误以为无报价', {'color': ACCENT}),
     ('v1.0.1 last_success_at + last_error 双标识；前端明示（FIX-07）', {'color': SUCCESS})],
    [('R-007', {'mono':True}), ('HKD 持仓被错误地除以 CNY 账户规模，输出错误百分比', {'color': ACCENT}),
     ('v1.0.1 HKD 必须经汇率换算；缺汇率显式 None（FIX-08）', {'color': SUCCESS})],
    [('R-008', {'mono':True}), ('生产 DB 自动 seed 测试证券（v1.0.0 行为）', {'color': ACCENT}),
     ('v1.0.1 默认空库；fixture 独立保存（FIX-10）', {'color': SUCCESS})],
], col_widths=[Cm(2.0), Cm(7.0), Cm(6.5)])

add_heading_h3(doc, '11.2 仍存在的风险（v1.0.1 范围内尚未实施，仅报告）')
add_table(doc, ['编号', '风险描述', '状态 / 设计稿'], [
    [('R-009', {'mono':True}),
     ('trades 表 append-only，但人工误录后无业务路径修复（无 UPDATE/DELETE）', {}),
     ('设计稿已写（tests/design_reversal.md），未实施', {'color': WARN, 'bold': True})],
    [('R-010', {'mono':True}),
     ('research_pool 当前位于 securities 表（可更新），与研究结论应版本化的设计矛盾 —— '
     '修改会覆盖历史分类', {'color': ACCENT}),
     ('设计稿已写（tests/design_research_pool_history.md），未实施', {'color': WARN, 'bold': True})],
    [('R-011', {'mono':True}),
     ('持仓与 status 不一致（"有持仓 status≠持仓中"或反之）系统只给提示',
     {'color': WARN}),
     ('不自动改正（依用户指令：仅一致性提示，不新增状态机规则）', {'color': SUCCESS})],
    [('R-012', {'mono':True}),
     ('行情数据源（腾讯）单点依赖，免费接口不保证 SLA，可能调整或中断',
     {'color': WARN}),
     ('v1.0.1 已加 last_success_at / last_error 双向标识；仍依赖第三方', {})],
    [('R-013', {'mono':True}),
     ('SQLite 并发写：WAL 提供读并发，但写仍全局锁；多进程同写会被 SQLITE_BUSY 拦截',
     {'color': WARN}),
     ('当前预期单用户；多进程场景未测试（性能与一致性未知）', {})],
], col_widths=[Cm(2.0), Cm(8.0), Cm(5.5)])

add_heading_h3(doc, '11.3 范围限制（明确不做）')
add_para(doc, '请参照 §2.3。', italic=True, color=MUTED)

add_heading_h3(doc, '11.4 未来路线图（不在 v1.0.1 范围）')
for item in [
    'trades 冲正 API（依据 design_reversal.md，需用户批准）',
    'research_pool 重构（依据 design_research_pool_history.md，需用户批准）',
    '行情多源 / 多币种系统 / 移动端 / 量化指标 / Markdown 导入（保持不做）',
]:
    p = doc.add_paragraph(item, style='List Bullet')
    p.paragraph_format.line_spacing = 1.5
    for r in p.runs:
        set_run_font(r, size_pt=10.5)

doc.add_page_break()

# §12 第三方审计重点
add_heading_h1(doc, '12. 第三方审计重点与建议')
add_heading_h3(doc, '12.1 建议审计方核验的方法')
add_table(doc, ['审计领域', '建议核验方法'], [
    [('文件完整性', {}), ('Get-FileHash -Algorithm SHA256 验证 §4.1/§4.2 的 9 个文件哈希', {})],
    [('零第三方依赖', {}), ('python -c "import sys; print(sys.modules.keys())" 仅在 import server 后检查', {})],
    [('SQL 注入防护', {}), ('server.py 中所有 SQL 均为参数化（? 占位符），无 f-string 拼接', {})],
    [('FOREIGN KEY 启用', {}), ('sqlite3.connect(db_path) + PRAGMA foreign_keys 后 INSERT 孤儿 trade → 应被拒绝', {})],
    [('UNIQUE 完整性', {}), ('尝试重复 (exchange, code) 插入应失败（应用层 + DB 层）', {})],
    [('CHECK 约束', {}), ('INSERT INTO trades with price=-1 / quantity=0 / fee=-1 / side=撤单 均应失败', {})],
    [('事务原子化', {}), ('注入 ledger 失败 → 业务记录也回滚（见 _LEDGER_FAIL_INJECT 测试钩子）', {})],
    [('行情解析字段', {}), ('抓 qt.gtimg.cn 实际响应 → f[30] 既是 A 股也是港股的市场时间（格式不同）', {})],
    [('last_success_at', {}), ('临时将 qt.gtimg.cn 域名指向 127.0.0.1:1 → 调用应进入失败路径并保留上次成功项', {})],
    [('多币种换算', {}), ('清空 hkd_cny_rate → HKD 标的 position_pct 与 market_value 均 None', {})],
    [('持仓/状态一致性', {}), ('手工制造不一致 → 检查 detail 接口返回 position_consistency.issues，验证 status 未被改', {})],
    [('示例数据未预置', {}), ('启动空 DB → securities 应为 []（默认）', {})],
    [('trades append-only', {}), ('grep -E "UPDATE trades|DELETE FROM trades" server.py 应无业务路径', {})],
    [('备份一致性', {}), ('python server.py --backup 后用 sqlite3.connect 打开备份 → 行数一致', {})],
], col_widths=[Cm(4.0), Cm(11.5)])

add_heading_h3(doc, '12.2 结论性声明')
add_callout(doc,
    '本系统是面向个人投研工作流的极简工具，已按"零第三方依赖、本地数据所有权、append-only 审计线索"'
    '三条原则构建。v1.0.1 在不增加功能的前提下完成 13 项数据完整性修复。\n'
    '所有规则均为非商业用途的辅助决策工具；不作任何投资建议，也不执行任何交易。\n'
    '若审计发现违反上述原则的实现细节，欢迎在签字栏反馈。',
    kind='ok')

doc.add_page_break()

# §13 关键代码节选（改名）
add_heading_h1(doc, '13. 关键代码节选（v1.0.1，非完整源码）')

add_callout(doc,
    '本附录为关键代码节选，便于第三方审计方快速定位修复实现位置。\n'
    '完整源文件请见 §4 中的 9 个交付文件及对应 SHA-256。',
    kind='warn')

add_heading_h3(doc, '13.1 FOREIGN KEY / UNIQUE / CHECK 在 SCHEMA 中的体现（节选）')
add_code_block(doc,
    '-- 节选自 app/server.py SCHEMA\n'
    'CREATE TABLE securities (\n'
    '  ...,\n'
    '  UNIQUE(exchange, code)                         -- v1.0.1 FIX-04\n'
    ');\n'
    '\n'
    'CREATE TABLE research (\n'
    '  security_id INTEGER NOT NULL\n'
    '    REFERENCES securities(id) ON DELETE RESTRICT,  -- v1.0.1 FIX-02\n'
    '  ...\n'
    ');\n'
    '\n'
    'CREATE TABLE trades (\n'
    '  security_id INTEGER NOT NULL\n'
    '    REFERENCES securities(id) ON DELETE RESTRICT,\n'
    '  side TEXT NOT NULL CHECK (side IN (\'买入\',\'卖出\')),\n'
    '  price REAL NOT NULL CHECK (price > 0),          -- v1.0.1 FIX-05\n'
    '  quantity REAL NOT NULL CHECK (quantity > 0),\n'
    '  fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),\n'
    '  ...\n'
    ');')

add_heading_h3(doc, '13.2 PRAGMA foreign_keys=ON 默认启用（节选）')
add_code_block(doc,
    'def get_db():\n'
    '    """每个 server-managed 连接都启用外键约束"""\n'
    '    conn = sqlite3.connect(DB_PATH, timeout=10)\n'
    '    conn.row_factory = sqlite3.Row\n'
    '    conn.execute(\'PRAGMA journal_mode=WAL\')\n'
    '    conn.execute(\'PRAGMA foreign_keys=ON\')         # v1.0.1 FIX-03\n'
    '    return conn')

add_heading_h3(doc, '13.3 事务原子化（节选）')
add_code_block(doc,
    'def _run_in_transaction(func):\n'
    '    """装饰器：业务写入 + ledger 写入整体事务化"""\n'
    '    def wrapper(*args, **kwargs):\n'
    '        conn = get_db()\n'
    '        try:\n'
    '            conn.execute(\'BEGIN\')\n'
    '            res = func(conn, *args, **kwargs)\n'
    '            conn.execute(\'COMMIT\')\n'
    '            return res\n'
    '        except Exception:\n'
    '            try: conn.execute(\'ROLLBACK\')\n'
    '            except Exception: pass\n'
    '            raise\n'
    '        finally:\n'
    '            conn.close()\n'
    '    return wrapper\n'
    '\n'
    '# 所有 change_* / update_* / add_* 函数都通过该装饰器\n'
    '@_run_in_transaction\n'
    'def change_status_tx(conn, sid, body):\n'
    '    ...\n'
    '    conn.execute(\'UPDATE securities SET status=? WHERE id=?\', ...)\n'
    '    ledger_add(conn, sid, event_date, \'状态变更\', summary, reason)\n'
    '    # 任一异常 → 自动 ROLLBACK')

add_heading_h3(doc, '13.4 行情字段正确性（节选）')
add_code_block(doc,
    'def fetch_tencent(symbols):\n'
    '    """实测：A 股 + 港股的"行情时间"都在 f[30]，格式不同：\n'
    '    A 股: YYYYMMDDHHMMSS（紧凑 14 位）\n'
    '    港股: YYYY/MM/DD HH:MM:SS（19 位）\n'
    '    """\n'
    '    for m in re.finditer(r\'v_([A-Za-z0-9_]+)="([^"]*)"\', raw):\n'
    '        f = m.group(2).split(\'~\')\n'
    '        if len(f) < 33: continue\n'
    '        market = m.group(1)[:2].lower()    # \'sh\' / \'sz\' / \'hk\'\n'
    '        mt_raw = f[30]\n'
    '        if market == \'hk\':\n'
    '            mt = mt_raw.replace(\'/\', \'-\') if re.fullmatch(r\'\\d{4}/\\d{2}/\\d{2} \\d{2}:\\d{2}:\\d{2}\', mt_raw or \'\') else \'\'\n'
    '        else:\n'
    '            if re.fullmatch(r\'\\d{14}\', mt_raw or \'\'):\n'
    '                mt = f\'{mt_raw[0:4]}-{mt_raw[4:6]}-{mt_raw[6:8]} {mt_raw[8:10]}:{mt_raw[10:12]}:{mt_raw[12:14]}\'\n'
    '            else:\n'
    '                mt = \'\'')

add_heading_h3(doc, '13.5 多币种仓位计算（节选）')
add_code_block(doc,
    'def compute_position(conn, sid, account_size_cny=None, hkd_cny_rate=None):\n'
    '    """持仓 quantity / avg_cost 由流水推导；\n'
    '    market_value / position_pct 计算需要汇率或账户规模。"""\n'
    '    currency = sec[\'currency\']\n'
    '    if qty > 0 and cur_price and cur_price > 0:\n'
    '        if currency == \'CNY\':\n'
    '            pos[\'market_value\'] = round(qty * cur_price, 2)\n'
    '        elif currency == \'HKD\':\n'
    '            if hkd_cny_rate and float(hkd_cny_rate) > 0:\n'
    '                pos[\'market_value\'] = round(qty * cur_price * float(hkd_cny_rate), 2)\n'
    '            else:\n'
    '                pos[\'market_value\'] = None           # 显式 None，不输出错误比例\n'
    '                pos[\'fx_rate_missing\'] = True')

add_heading_h3(doc, '13.6 持仓/状态一致性提示（不自动改）')
add_code_block(doc,
    'def consistency_check(sec, pos):\n'
    '    """仅做提示，不自动改正 status"""\n'
    '    issues = []\n'
    '    has_pos = pos[\'quantity\'] > 1e-9\n'
    '    if has_pos and sec[\'status\'] != \'持仓中\':\n'
    '        issues.append({\n'
    '            \'code\': \'POSITION_HOLDING_STATUS_MISMATCH\',\n'
    '            \'level\': \'warn\',\n'
    '            \'message\': \'当前持仓 {} {}，但 status={}... 本系统不自动调整 status\'\n'
    '            .format(pos[\'quantity\'], pos[\'currency\'], sec[\'status\'])\n'
    '        })\n'
    '    if not has_pos and sec[\'status\'] == \'持仓中\':\n'
    '        issues.append({\n'
    '            \'code\': \'STATUS_HOLDING_NO_POSITION\',\n'
    '            \'message\': \'status=持仓中 但当前无持仓...\'\n'
    '        })\n'
    '    return {\'has_position\': has_pos, \'issues\': issues, \'checked\': True}')

doc.add_page_break()

# §14 未解决
add_heading_h1(doc, '14. 仍未解决的开放问题')
add_para(doc, '以下问题本轮（v1.0.1）暂未实施，列于此以供下一轮决策。', italic=True, color=MUTED)

add_heading_h3(doc, '14.1 设计稿已写但未实施')
add_table(doc, ['编号', '项', '设计稿', '进入实施前需'], [
    [('O-001', {'mono':True}),
     ('trades 冲正（reversal）业务接口', {}),
     ('tests/design_reversal.md', {'mono':True}),
     ('用户对设计稿的反馈 / 批准', {'color': ACCENT})],
    [('O-002', {'mono':True}),
     ('research_pool 字段从 securities 迁到 research 表', {}),
     ('tests/design_research_pool_history.md', {'mono':True}),
     ('设计稿 §3 中三条审批门槛（含用户是否同意"仅回填最新版本"）', {'color': ACCENT})],
], col_widths=[Cm(1.5), Cm(5.0), Cm(4.5), Cm(4.5)])

add_heading_h3(doc, '14.2 已识别风险（待用户评估）')
add_table(doc, ['编号', '风险', '评估维度'], [
    [('R-012', {'mono':True}),
     ('行情源（腾讯）单点依赖 — 第三方免费接口不保证 SLA', {}),
     ('是否未来切换到 iFinD / Wind / 多源', {})],
    [('R-013', {'mono':True}),
     ('SQLite 在多进程同时写入的场景下表现未知', {}),
     ('是否需要单实例保证 / 是否有跨进程迁移计划', {})],
    [('R-014', {'mono':True}),
     ('trades 误录目前无修复路径（依赖 O-001 设计稿实现）', {}),
     ('用户对冲正设计的接受度', {})],
], col_widths=[Cm(1.5), Cm(9.0), Cm(5.0)])

add_heading_h3(doc, '14.3 测试覆盖盲区（建议下版补充）')
for item in [
    'SQLite 并发写测试（WAL 下 4 个并发 writer 的 SQLITE_BUSY 行为）',
    '极端大数据量（>10,000 笔交易流水）的 UI 性能',
    '断网 / 弱网 / 心跳异常的恢复路径',
    '多用户 / 多角色场景（当前明确定位单用户工具，未覆盖）',
    '深穿信息卡 → 工作台导入向导（current 直接走 API body 导入，非 Markdown）',
]:
    p = doc.add_paragraph(item, style='List Bullet')
    p.paragraph_format.line_spacing = 1.5
    for r in p.runs:
        set_run_font(r, size_pt=10.5)

add_heading_h3(doc, '13.4 签字栏')
add_signature_block(doc)

note = doc.add_paragraph()
note.alignment = WD_ALIGN_PARAGRAPH.CENTER
note.paragraph_format.space_before = Pt(36)
note.paragraph_format.line_spacing = 1.7
nr = note.add_run(
    '本文档由 WorkBuddy 投研工作台开发组编制\n'
    '文档路径：output\\20260910-audit\\stage3\\A-H投研交易工作台交付审计文档-v1.0.1.docx'
)
set_run_font(nr, size_pt=10, italic=True, color=MUTED)

# 落盘
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
doc.save(OUTPUT_PATH)

h = hashlib.sha256(open(OUTPUT_PATH, 'rb').read()).hexdigest()
size = os.path.getsize(OUTPUT_PATH)
print(f'\u2705 v1.0.1 docx \u751f\u6210\uff1a{OUTPUT_PATH}')
print(f'   \u5927\u5c0f\uff1a{size:,} bytes')
print(f'   SHA-256\uff1a{h}')
