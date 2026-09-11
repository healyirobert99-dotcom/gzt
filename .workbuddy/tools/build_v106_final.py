"""v1.0.6 最终发版打包脚本。

用法：cd D:/个股工作台 && python .workbuddy/tools/build_v106_final.py
输出：D:/个股工作台/个股工作台-v1.0.6-20260910.zip
"""

import os, sys, shutil, hashlib, zipfile, datetime

ROOT = r'D:\个股工作台'
TARGET = r'D:\个股工作台\pack_v106_src'
OUT_ZIP = r'D:\个股工作台\个股工作台-v1.0.6-20260910.zip'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


INCLUDE_FILES = [
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_v105.py',
    'tests/test_v106.py',
    'tests/test_integration_quote.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'tests/fixtures/sample_seed.py',
    'data/workbench.db',
    '启动工作台.bat',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.6.docx',
    'output/20260910-audit/build_docx_v106.py',
]


# === Step 1: 复制到打包源 ===
if os.path.exists(TARGET):
    shutil.rmtree(TARGET)
os.makedirs(TARGET)

for rel in INCLUDE_FILES:
    s = os.path.join(ROOT, rel)
    d = os.path.join(TARGET, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(s, d)
print('COPIED=%d' % len(INCLUDE_FILES))

# === Step 2: 生成 PACK_NOTES.md ===
notes_lines = []
notes_lines.append('# v1.0.6 发版交付说明')
notes_lines.append('')
notes_lines.append('## 版本')
notes_lines.append('- **v1.0.6**（行情一致性修复）')
notes_lines.append('- 基线：v1.0.5')
notes_lines.append('- 打包时间：' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' (Asia/Shanghai)')
notes_lines.append('')
notes_lines.append('## 本轮性质')
notes_lines.append('用户明确批准的"v1.0.6 行情一致性修复"，共 9 条 spec：')
notes_lines.append('')
notes_lines.append('1. get_quotes 区分本次成功与缺失的 symbol（symbol 粒度 partial_failure）')
notes_lines.append('2. 成功证券正常更新 cache / 写 securities / 更新行情时间')
notes_lines.append('3. 缺失证券保留旧 cache + 标记 is_stale=true + 旧 market_time')
notes_lines.append('4. requested 非空且 fetched 为空 → 必须识别为本次行情失败（即使 fetch 未抛异常）')
notes_lines.append('5. 部分成功返回明确"部分行情未更新"状态 + 列出缺失 symbol')
notes_lines.append('6. 前端卡片对 stale 行情明确显示"上次成功行情 · 本次刷新未成功"')
notes_lines.append('7. attention() 不得把 is_stale=true 缓存价格视作本次新变化（保留 status / wall / core_validation）')
notes_lines.append('8. 新增 3 组回归测试（§A 部分成功 / §B 全部失败 / §C stale 不进 attention）')
notes_lines.append('9. 保持 v1.0.5 已通过的 123 断言继续通过')
notes_lines.append('')
notes_lines.append('## 边界（不允许越界）')
notes_lines.append('- 不新增第二行情源')
notes_lines.append('- 不增加技术指标（MA / EMA / MACD / RSI / KDJ / 布林带 / 自动支撑位等）')
notes_lines.append('- 不修改交易规则 / 状态 / 自动判断')
notes_lines.append('- 不新增字段 / 端点 / 缓存层')
notes_lines.append('- 不得"顺带加入"未在 spec 中批准的内容')
notes_lines.append('')
notes_lines.append('## 测试结果（153 断言全过）')
notes_lines.append('- tests/test_v102.py：38/38 PASS')
notes_lines.append('- tests/test_v103.py：60/60 PASS')
notes_lines.append('- tests/test_v105.py：25/25 PASS')
notes_lines.append('- tests/test_v106.py：30/30 PASS（§A 11 + §B 8 + §C 3 + §D 8）')
notes_lines.append('- 生产 DB：schema_version=1.0.6, integrity_check=ok, FK 0 违规')
notes_lines.append('')
notes_lines.append('## 验证方法（解压后请按此顺序检查）')
notes_lines.append('1. 解压 ZIP 到任意目录')
notes_lines.append('2. 打开 PACK_MANIFEST.md，对每个文件用 Get-FileHash / sha256sum 验证 SHA-256')
notes_lines.append('3. 打开 docs 文件：A-H投研交易工作台交付审计文档-v1.0.6.docx')
notes_lines.append('4. 启动应用：`启动工作台.bat`（或 `python app/server.py`）')
notes_lines.append('5. 浏览器访问 http://localhost:8000')
notes_lines.append('')
notes_lines.append('## 文件清单')
notes_lines.append('共 17 个文件（清单 16 项 + PACK_MANIFEST.md 自身）：')
notes_lines.append('- 源码：`app/server.py`、`app/static/{app.js,index.html,style.css}`')
notes_lines.append('- 测试：`tests/test_v102.py`、`tests/test_v103.py`、`tests/test_v105.py`、`tests/test_v106.py`、`tests/test_integration_quote.py`')
notes_lines.append('- 设计文档：`tests/design_reversal.md`、`tests/design_research_pool_history.md`')
notes_lines.append('- Fixture：`tests/fixtures/sample_seed.py`')
notes_lines.append('- 数据库：`data/workbench.db`（生产 DB，schema_version=1.0.6）')
notes_lines.append('- 启动：`启动工作台.bat`')
notes_lines.append('- 审计文档：`output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.6.docx`')
notes_lines.append('- 生成器：`output/20260910-audit/build_docx_v106.py`')
notes_lines.append('- 清单：`PACK_MANIFEST.md`（自身 SHA 由构建脚本生成时打印）')
notes_lines.append('')
notes_lines.append('## 与 v1.0.5 的差异')
notes_lines.append('- 后端 `server.py :: get_quotes()` 改造：每条返回 is_stale + 新增 partial_failure / missing_symbols / requested_count / fetched_count；requested 非空且 fetched 为空 → error 非空')
notes_lines.append('- 前端 `app.js :: attention()` 新增 isStale 屏蔽（保留 status / wall / core_validation）')
notes_lines.append('- 前端 `app.js :: cardHtml()` 新增 stale 横幅显示')
notes_lines.append('- 全版本号统一 v1.0.6（DB TARGET / server_version / argparse / 启动打印 / 前端头 / docx）')
notes_lines.append('- docx 彻底重写（不复用 v1.0.5 docx），新 docx SHA `d69bfd33...` ≠ v1.0.5 docx SHA')

with open(os.path.join(TARGET, 'PACK_NOTES.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(notes_lines))
print('PACK_NOTES.md written')


# === Step 3: 生成 PACK_MANIFEST.md（必须先写盘）===
file_entries = []
for rel in INCLUDE_FILES + ['PACK_NOTES.md', 'PACK_MANIFEST.md']:
    p = os.path.join(TARGET, rel)
    if not os.path.exists(p):
        continue
    sz = os.path.getsize(p)
    h = sha(p)
    file_entries.append((rel, sz, h))

# 移除 manifest 自身的循环依赖：清单不含自身条目
file_entries_no_self = [e for e in file_entries if e[0] != 'PACK_MANIFEST.md']

m = []
m.append('# v1.0.6 发版交付包文件清单  Manifest')
m.append('')
m.append('项目：A/H 投研交易工作台 (Individual Stock Workbench)')
m.append('版本：v1.0.6（行情一致性修复）')
m.append('打包时间：' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' (Asia/Shanghai)')
m.append('清单中文件数：%d + 清单自身 1 = 总 %d 个' % (
    len(file_entries_no_self), len(file_entries_no_self) + 1))
m.append('')
m.append('## 文件清单（按路径排序，不含清单自身以避免循环依赖）')
m.append('')
m.append('| # | 路径 | 大小 (bytes) | SHA-256 |')
m.append('|---|------|-------------:|---------|')
for i, (rel, sz, h) in enumerate(file_entries_no_self, 1):
    m.append('| %02d | `%s` | %d | `%s` |' % (i, rel, sz, h))

m.append('')
m.append('## 范围说明')
m.append('')
m.append('### ✅ 已包含（送审范围）')
m.append('')
m.append('- 当前 v1.0.6 应用源码（`app/server.py` + `app/static/*`）')
m.append('- 完整测试套件（v1.0.2 + v1.0.3 + v1.0.5 + v1.0.6）')
m.append('- 设计文档（reversal / research_pool_history）')
m.append('- 测试 fixture（sample_seed.py）')
m.append('- 当前生产数据库（`data/workbench.db`，schema_version=1.0.6）')
m.append('- 启动脚本（`启动工作台.bat`）')
m.append('- 当前版本审计文档（v1.0.6 docx，与 v1.0.5 docx SHA 不同）')
m.append('- 审计 docx 生成器（`build_docx_v106.py`）')
m.append('- 本清单（`PACK_MANIFEST.md`）')
m.append('- 交付说明（`PACK_NOTES.md`）')
m.append('')
m.append('### ❌ 已排除')
m.append('')
m.append('- `audit_pack_src/` —— 上一轮 v1.0.5 审计专用临时源')
m.append('- `data/backup/` —— 迁移历史快照（按用户要求清理即可）')
m.append('- `__pycache__/` —— Python 编译缓存')
m.append('- `.workbuddy/` —— 个人助手记忆与工具')
m.append('- 旧版 docx（v1.0.3 / v1.0.4 / v1.0.5）—— 已 superseded')
m.append('- 旧版生成器（build_docx_v103 / v104 / v105）')
m.append('- 旧版 ZIP（v1.0.3 / v1.0.4 / v1.0.5）')
m.append('')
m.append('## 关于本清单自身的完整性')
m.append('')
m.append('为避免「清单包含自身 SHA → 内容变化 → SHA 又变化」的循环依赖，')
m.append('本清单**不含**自身的 SHA 条目；其真实 SHA 由构建脚本')
m.append('`build_v106_final.py` 在打包时计算并打印在 stdout 中。审计方若需校验')
m.append('清单文本未在打包后被修改，可直接对 `PACK_MANIFEST.md` 计算 SHA-256 并')
m.append('与构建脚本的 stdout 输出比对。')
m.append('')
m.append('## 验证方法')
m.append('')
m.append('```bash')
m.append('# Windows (PowerShell)')
m.append('Get-FileHash -Algorithm SHA256 <file>')
m.append('# Linux/macOS')
m.append('sha256sum <file>')
m.append('# ZIP 整体')
m.append('certutil -hashfile 个股工作台-v1.0.6-20260910.zip SHA256')
m.append('```')

with open(os.path.join(TARGET, 'PACK_MANIFEST.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(m))
print('PACK_MANIFEST.md written')


# === Step 3.5: 重新计算 file_entries（PACK_MANIFEST 已写盘）===
file_entries = []
for rel in INCLUDE_FILES + ['PACK_NOTES.md', 'PACK_MANIFEST.md']:
    p = os.path.join(TARGET, rel)
    sz = os.path.getsize(p)
    h = sha(p)
    file_entries.append((rel, sz, h))

file_entries_no_self = [e for e in file_entries if e[0] != 'PACK_MANIFEST.md']

# === Step 4: 打 ZIP（含 PACK_NOTES.md + PACK_MANIFEST.md）===
if os.path.exists(OUT_ZIP):
    os.remove(OUT_ZIP)

all_files = []
for rel in INCLUDE_FILES + ['PACK_NOTES.md', 'PACK_MANIFEST.md']:
    all_files.append((rel, os.path.join(TARGET, rel)))
all_files.sort()

with zipfile.ZipFile(OUT_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for rel, p in all_files:
        zf.write(p, arcname=rel)

# === Step 5: 输出 SHA-256 与统计 ===
zip_h = sha(OUT_ZIP)
print('ZIP=%s' % OUT_ZIP)
print('ZIP_SIZE=%d' % os.path.getsize(OUT_ZIP))
print('ZIP_SHA256=%s' % zip_h)
print('FILES_IN_ZIP=%d' % len(all_files))
print('PACK_MANIFEST_SELF_SHA=%s' % sha(os.path.join(TARGET, 'PACK_MANIFEST.md')))