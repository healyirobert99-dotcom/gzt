"""v1.0.7 操作截图替代生成器。

由于受限环境无法启动 agent-browser 的 Chromium（SIGTERM 后无输出），
改用 SVG 生成两个操作界面示意图，标注"视觉示意（非真实浏览器截图）"。
SVG 完全基于 index.html + app.js 真实结构绘制，用于交付文档内嵌入。
"""
import os, sys, datetime

OUT_DIR = r'D:\个股工作台\output\20260910-audit\screenshots'
os.makedirs(OUT_DIR, exist_ok=True)


def base_svg(width=1100, height=720, title=''):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <style>
      .bg {{ fill: #0e1116; }}
      .panel {{ fill: #151a22; stroke: #273041; stroke-width: 1; }}
      .panel2 {{ fill: #1b212c; stroke: #273041; stroke-width: 1; }}
      .text {{ fill: #e8ecf3; font-family: "Microsoft YaHei","PingFang SC","Segoe UI",sans-serif; }}
      .muted {{ fill: #8a94a6; font-family: "Microsoft YaHei","PingFang SC","Segoe UI",sans-serif; }}
      .accent {{ fill: #4f8cff; }}
      .brand {{ fill: #e8ecf3; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-weight: 700; font-size: 15px; }}
      .nav {{ fill: #8a94a6; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 13px; }}
      .navOn {{ fill: #e8ecf3; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-weight: 600; font-size: 13px; }}
      .h2 {{ fill: #e8ecf3; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 17px; font-weight: 600; }}
      .h3 {{ fill: #e8ecf3; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 14px; font-weight: 600; }}
      .kv-w {{ fill: #8a94a6; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 12px; }}
      .kv-v {{ fill: #e8ecf3; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 13px; }}
      .warn-bg {{ fill: #f0a92c1f; stroke: #f0a92c; stroke-width: 1; }}
      .warn-text {{ fill: #f0a92c; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 12px; }}
      .tag-good {{ fill: #22c3a622; stroke: #22c3a6; stroke-width: 1; }}
      .tag-good-text {{ fill: #22c3a6; font-family: "Microsoft YaHei","PingFang SC",sans-serif; font-size: 11px; font-weight: 600; }}
      .code-text {{ fill: #c9d4e3; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px; }}
    </style>
  </defs>
  <rect class="bg" width="{width}" height="{height}"/>
  <!-- topbar -->
  <rect x="0" y="0" width="{width}" height="54" fill="#151a22ee"/>
  <line x1="0" y1="54" x2="{width}" y2="54" stroke="#273041" stroke-width="1"/>
  <text class="brand" x="24" y="33">A/H 投研交易工作台</text>
  <text class="nav" x="220" y="33">今日工作台</text>
  <text class="nav" x="320" y="33">标的库</text>
  <text class="navOn" x="395" y="33">导入与更新</text>
  <text class="muted" x="900" y="33" text-anchor="end">v1.0.7 · {title}</text>
</svg>'''


# ========== 截图 1：① 导入研究结果 —— 第 3 步：导入完成 ==========
shot1 = base_svg(width=1100, height=720, title='① 导入研究结果')
shot1 += '''
  <!-- main -->
  <g transform="translate(40, 96)">
    <text class="h2" x="0" y="0">① 导入研究结果 · 第 3 步：导入完成</text>
    <text class="muted" x="0" y="22">所有写入均同步写入 decision_ledger；研究/计划/状态等历史版本永久保留。</text>

    <!-- summary panel -->
    <g transform="translate(0, 40)">
      <rect class="panel" width="1020" height="186" rx="12"/>
      <text class="kv-w" x="22" y="32">导入完成</text>
      <text class="kv-v" x="170" y="32" style="font-size:16px;font-weight:600;fill:#4f8cff">成功处理 2 只</text>

      <text class="kv-w" x="22" y="62">新建标的</text>
      <text class="kv-v" x="170" y="62" style="font-size:16px;font-weight:600">1</text>

      <text class="kv-w" x="22" y="92">状态变更</text>
      <text class="kv-v" x="170" y="92" style="font-size:16px;font-weight:600">1</text>

      <text class="kv-w" x="22" y="122">新增研究版本</text>
      <text class="kv-v" x="170" y="122" style="font-size:16px;font-weight:600">1</text>

      <text class="kv-w" x="280" y="62">新增静态计划版本</text>
      <text class="kv-v" x="450" y="62" style="font-size:16px;font-weight:600">1</text>

      <text class="kv-w" x="280" y="92">新增动态执行判断</text>
      <text class="kv-v" x="450" y="92" style="font-size:16px;font-weight:600">1</text>

      <text class="kv-w" x="280" y="122">内容无变化跳过</text>
      <text class="kv-v" x="450" y="122" style="font-size:16px;font-weight:600">0</text>

      <line x1="22" y1="140" x2="998" y2="140" stroke="#273041" stroke-width="1"/>
      <text class="muted" x="22" y="166">本轮原子化写入：securities / research / trade_plans / execution_reviews / decision_ledger；trades 0 条变更。</text>
    </g>

    <!-- detail table -->
    <g transform="translate(0, 252)">
      <text class="h3" x="0" y="0">明细</text>
      <rect class="panel" x="0" y="14" width="1020" height="200" rx="12"/>
      <!-- 表头 -->
      <text class="kv-w" x="22" y="40">标的</text>
      <text class="kv-w" x="200" y="40">exchange · code</text>
      <text class="kv-w" x="380" y="40">类型</text>
      <text class="kv-w" x="480" y="40">状态变化</text>
      <text class="kv-w" x="610" y="40">研究</text>
      <text class="kv-w" x="710" y="40">计划</text>
      <text class="kv-w" x="810" y="40">执行</text>
      <line x1="22" y1="50" x2="998" y2="50" stroke="#273041" stroke-width="1"/>

      <!-- row 1: 已有证券 -->
      <text class="kv-v" x="22" y="80">美图公司</text>
      <text class="kv-v" x="200" y="80">HK · 01357</text>
      <rect class="tag-good" x="380" y="64" width="50" height="20" rx="4"/>
      <text class="tag-good-text" x="405" y="78" text-anchor="middle">已存在</text>
      <text class="kv-v" x="480" y="80" style="fill:#f0a92c;font-weight:600">是</text>
      <text class="kv-v" x="610" y="80">v2</text>
      <text class="kv-v" x="710" y="80">v2</text>
      <text class="kv-v" x="810" y="80">新增 #2</text>

      <line x1="22" y1="100" x2="998" y2="100" stroke="#273041" stroke-width="0.5"/>

      <!-- row 2: 新建证券 -->
      <text class="kv-v" x="22" y="130">测试新标的</text>
      <text class="kv-v" x="200" y="130">SH · 600001</text>
      <rect class="tag-good" x="380" y="114" width="40" height="20" rx="4"/>
      <text class="tag-good-text" x="400" y="128" text-anchor="middle">新建</text>
      <text class="kv-v" x="480" y="130">—</text>
      <text class="muted" x="610" y="130">—</text>
      <text class="muted" x="710" y="130">—</text>
      <text class="muted" x="810" y="130">—</text>

      <line x1="22" y1="150" x2="998" y2="150" stroke="#273041" stroke-width="0.5"/>

      <text class="muted" x="22" y="190">所有写入均同步写入 decision_ledger（append-only）。研究/计划/状态等历史版本永久保留。</text>
    </g>

    <!-- footer -->
    <g transform="translate(0, 500)">
      <rect x="0" y="0" width="120" height="34" rx="8" fill="none" stroke="#4f8cff" stroke-width="1"/>
      <text class="kv-v" x="60" y="22" text-anchor="middle">返回导入与更新</text>

      <rect x="140" y="0" width="120" height="34" rx="8" fill="#4f8cff"/>
      <text x="200" y="22" text-anchor="middle" fill="#0e1116" font-family="Microsoft YaHei" font-size="13" font-weight="600">返回工作台</text>
    </g>
  </g>

  <!-- 标注 -->
  <text class="muted" x="20" y="700" font-size="11">※ 视觉示意（基于 index.html + app.js 实际结构渲染；非真实浏览器截图）</text>
  <text class="muted" x="1080" y="700" font-size="11" text-anchor="end">v1.0.7 导入与更新 · 截图 1 / 2</text>
</svg>
'''

with open(os.path.join(OUT_DIR, 'screenshot-1-full-import-done.svg'), 'w', encoding='utf-8') as f:
    f.write(shot1)
print('[1/2] screenshot-1-full-import-done.svg')


# ========== 截图 2：② 快速更新动态执行 —— 第 2 步：预览 ==========
shot2 = base_svg(width=1100, height=720, title='② 快速更新动态执行')
shot2 += '''
  <!-- main -->
  <g transform="translate(40, 96)">
    <text class="h2" x="0" y="0">② 快速更新动态执行 · 第 2 步：预览</text>

    <!-- preview panel -->
    <g transform="translate(0, 30)">
      <rect class="panel" width="1020" height="488" rx="12"/>
      <text class="h3" x="22" y="34">即将新增 execution</text>
      <line x1="22" y1="44" x2="998" y2="44" stroke="#273041" stroke-width="1"/>

      <text class="kv-w" x="22" y="74">标的</text>
      <text class="kv-v" x="170" y="74" style="font-weight:600">美图公司（HK · 01357 · id=17）</text>

      <text class="kv-w" x="22" y="104">当前状态</text>
      <text class="kv-v" x="170" y="104">可交易（不会被本次导入修改）</text>

      <text class="kv-w" x="22" y="134">上一条 execution</text>
      <text class="kv-v" x="170" y="134">2026-09-09 · 等待技术确认</text>

      <line x1="22" y1="160" x2="998" y2="160" stroke="#273041" stroke-width="0.5"/>

      <text class="kv-w" x="22" y="190">判断日期</text>
      <text class="kv-v" x="170" y="190" style="font-weight:600">2026-09-10</text>

      <text class="kv-w" x="22" y="220">判断时价格</text>
      <text class="kv-v" x="170" y="220">4.18</text>

      <text class="kv-w" x="22" y="250">当前执行判断</text>
      <text class="kv-v" x="170" y="250" style="font-weight:600">等待技术确认</text>

      <text class="kv-w" x="22" y="280">支撑</text>
      <text class="kv-v" x="170" y="280">4.10-4.15</text>

      <text class="kv-w" x="280" y="280">压力</text>
      <text class="kv-v" x="430" y="280">4.30-4.35</text>

      <text class="kv-w" x="22" y="320">技术结构</text>
      <text class="kv-v" x="170" y="320">已回到下方支撑区</text>

      <text class="kv-w" x="22" y="350">等待条件</text>
      <text class="kv-v" x="170" y="350">观察是否止跌收回 4.20</text>

      <text class="kv-w" x="22" y="380">依据</text>
      <text class="kv-v" x="170" y="380">今日回到支撑区且短线结构走稳</text>

      <!-- warn banner -->
      <g transform="translate(0, 410)">
        <rect class="warn-bg" x="22" y="0" width="976" height="62" rx="6"/>
        <rect x="22" y="0" width="76" height="62" rx="6" fill="#f0a92c"/>
        <text x="60" y="38" text-anchor="middle" fill="#0e1116" font-family="Microsoft YaHei" font-size="11" font-weight="600">仅追加</text>
        <text class="warn-text" x="120" y="26">本次确认将<b>追加一条</b>execution（append-only），同步写入 decision_ledger。</text>
        <text class="warn-text" x="120" y="48">研究 / 静态计划 / 持仓 / 状态不会被修改。</text>
      </g>
    </g>

    <!-- footer -->
    <g transform="translate(0, 560)">
      <rect x="0" y="0" width="100" height="34" rx="8" fill="none" stroke="#4f8cff" stroke-width="1"/>
      <text class="kv-v" x="50" y="22" text-anchor="middle">返回修改</text>

      <rect x="120" y="0" width="160" height="34" rx="8" fill="#4f8cff"/>
      <text x="200" y="22" text-anchor="middle" fill="#0e1116" font-family="Microsoft YaHei" font-size="13" font-weight="600">确认并写入</text>
    </g>
  </g>

  <text class="muted" x="20" y="700" font-size="11">※ 视觉示意（基于 index.html + app.js 实际结构渲染；非真实浏览器截图）</text>
  <text class="muted" x="1080" y="700" font-size="11" text-anchor="end">v1.0.7 导入与更新 · 截图 2 / 2</text>
</svg>
'''

with open(os.path.join(OUT_DIR, 'screenshot-2-execution-update-preview.svg'), 'w', encoding='utf-8') as f:
    f.write(shot2)
print('[2/2] screenshot-2-execution-update-preview.svg')

print()
print('NOTE: 真实 Chromium 启动受限于当前环境（agent-browser install 输出 SIGTERM 静默）。')
print('      已基于 index.html / app.js 实际渲染结构生成视觉示意 SVG。')
print('      这两份图保存在', OUT_DIR)
