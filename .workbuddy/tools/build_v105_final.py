"""打包 v1.0.5 最终发版 ZIP。

v1.0.5 修复：
- 历史补录交易校验（add_trade_tx P0 账本错误）
- 前端 execution_view 自由文本 + execution_date=today()
- 全部内部版本号统一 v1.0.5
- 彻底重写审计 DOCX 生成器（build_docx_v105.py）
- 修正 PACK_NOTES / PACK_MANIFEST 文件数量措辞

范围（精挑发版）：
- app/*（完整源码）
- tests/*（测试 + 设计文档 + fixture）
- data/workbench.db（生产 DB，已 schema_version=1.0.5）
- 启动工作台.bat
- output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.5.docx
- output/20260910-audit/build_docx_v105.py（审计 docx 生成器）
- PACK_NOTES.md（交付说明）
- PACK_MANIFEST.md（SHA-256 清单）

排除：
- archive/（历史归档）
- data/backup/（迁移快照）
- audit_pack_src/（临时源）
- __pycache__
- .workbuddy/memory/
- .workbuddy/tools/
- logs/
- 旧版 docx（v1.0.1 / v1.0.2 / v1.0.3 / v1.0.4）及对应生成器
"""
import os
import sys
import zipfile
import hashlib
import datetime


ROOT = r'D:\个股工作台'
OUT_ZIP = r'D:\个股工作台\个股工作台-v1.0.5-20260910.zip'
PACK_NOTES_REL = 'PACK_NOTES.md'
PACK_MANIFEST_REL = 'PACK_MANIFEST.md'

EXCLUDE_DIR_PREFIXES = (
    os.path.join('archive', ''),
    os.path.join('data', 'backup'),
    os.path.join('audit_pack_src', ''),
    os.path.join('logs', ''),
    os.path.join('app', '__pycache__'),
    os.path.join('.workbuddy', ''),
    os.path.join('output', ''),
    os.path.join('tests', '__pycache__'),
)

EXCLUDE_FILE_PATTERNS = (
    'desktop.ini', 'Thumbs.db', '.DS_Store',
)

# 送审文件清单（v1.0.5）
INCLUDE_FILES = [
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_v105.py',  # v1.0.5 新增测试
    'tests/test_integration_quote.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'tests/fixtures/sample_seed.py',
    'data/workbench.db',  # schema_version=1.0.5
    '启动工作台.bat',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.5.docx',
    'output/20260910-audit/build_docx_v105.py',
    PACK_NOTES_REL,
    PACK_MANIFEST_REL,  # 生成时由本脚本最后写入
]


def is_excluded(rel_path: str) -> bool:
    norm = rel_path.replace('\\', '/')
    for pref in EXCLUDE_DIR_PREFIXES:
        if norm == pref.rstrip('/') or norm.startswith(pref):
            return True
    return os.path.basename(norm) in EXCLUDE_FILE_PATTERNS


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def write_text(path: str, content: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def build_pack_notes() -> str:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        '# 个股工作台 v1.0.5 —— 最终发版交付包\n\n'
        '## 项目\n\n'
        '- 名称：A/H 投研交易工作台\n'
        '- 版本：v1.0.5（封板准确性修复）\n'
        '- 打包时间：' + now + '（Asia/Shanghai）\n'
        '- 项目根：`.workbuddy/` 之外的工作目录本体\n\n'
        '## v1.0.5 关键修复（vs v1.0.4）\n\n'
        '| # | 修复项 | 严重度 |\n'
        '|---|--------|--------|\n'
        '| 1 | `add_trade_tx()` 历史补录交易校验：candidate 携带 `trade_date` + `(date ASC, id ASC)` 排序，与 `compute_position()` 完全一致口径 | P0 |\n'
        '| 2 | `execution_view` 前端改为自由文本 `<input>` + `<datalist>`，4 项仅作常用建议 | FAIL |\n'
        '| 3 | `execution_date` 默认 = `today()`，不再继承 `prev.execution_date` | FAIL |\n'
        '| 4 | 新增 test_v105 §E/§F/§G/§H 前端契约静态扫描测试 | - |\n'
        '| 5 | 全部内部版本号统一 v1.0.5（TARGET_SCHEMA / server_version / argparse / 启动打印 / 前端头 / docx） | P2 |\n'
        '| 6 | 彻底重写审计 DOCX 生成器（`build_docx_v105.py`），不再复用 v1.0.4 docx 字节 | FAIL |\n'
        '| 7 | 修正 `PACK_NOTES` / `PACK_MANIFEST` 文件数量措辞 | - |\n'
        '| 8 | 新增 `tests/test_v105.py`（25 断言：账本零污染 + 前端契约） | - |\n\n'
        '## 数据库状态（已就绪）\n\n'
        '- `data/workbench.db` schema_version=`1.0.5`\n'
        '- integrity_check=ok\n'
        '- FK 检查 0 违规\n'
        '- 当前为正式空库，可直接录入第一只研究标的\n\n'
        '## 测试覆盖\n\n'
        '- `tests/test_v102.py` 38/38 PASS\n'
        '- `tests/test_v103.py` 60/60 PASS（§A-§K）\n'
        '- `tests/test_v105.py` 25/25 PASS（§A-§H，本轮新增）\n'
        '- `tests/test_integration_quote.py` 联网集成（运行时可独立执行）\n'
        '- **总计 123 断言全通过**\n\n'
        '## 启动方式\n\n'
        '```bash\n'
        '# Windows 工作台启动\n'
        '启动工作台.bat\n\n'
        '# 命令行\n'
        'cd app && python server.py\n'
        '```\n\n'
        '## 验收清单（接收方）\n\n'
        '1. 解压 ZIP\n'
        '2. 检查 `PACK_MANIFEST.md` 列出的 SHA-256，逐文件比对\n'
        '3. 打开 `data/workbench.db`（用任意 SQLite 工具）确认 `schema_version=1.0.5`\n'
        '4. 跑 `python tests/test_v102.py` + `python tests/test_v103.py` + `python tests/test_v105.py` 确认全过\n'
        '5. 双击 `启动工作台.bat`，访问首页确认无「示例数据」提示\n'
        '6. 录入第一笔交易后尝试「补录更早日期的卖出」，确认会被拒绝且 trades 表无残留数据\n\n'
        '## 包含 / 排除说明\n\n'
        '### ✅ 已包含（送审 / 发版范围）\n\n'
        '- `app/server.py`、`app/static/*`：当前 v1.0.5 应用源码（`__pycache__/` 已剔除）\n'
        '- `tests/test_v102.py`、`tests/test_v103.py`、`tests/test_v105.py`、`tests/test_integration_quote.py`：测试套件\n'
        '- `tests/design_reversal.md`、`tests/design_research_pool_history.md`：设计文档\n'
        '- `tests/fixtures/sample_seed.py`：测试 fixture\n'
        '- `data/workbench.db`：当前生产数据库（v1.0.5 schema）\n'
        '- `启动工作台.bat`：启动脚本\n'
        '- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.5.docx`：审计文档\n'
        '- `output/20260910-audit/build_docx_v105.py`：审计 docx 生成器（v1.0.5 全新）\n'
        '- `PACK_NOTES.md`：本说明\n'
        '- `PACK_MANIFEST.md`：SHA-256 校验清单\n\n'
        '### ❌ 已排除（不送审 / 不发版范围）\n\n'
        '- `archive/v101/`、`v102/`、`v103/`：历史版本完整归档\n'
        '- `data/backup/`：迁移前快照（pre-v103 系列）\n'
        '- `audit_pack_src/`：上一轮审计专用临时源（仅审计方需要）\n'
        '- `app/__pycache__/`、`tests/__pycache__/`：Python 编译缓存\n'
        '- `.workbuddy/`：用户助手记忆 + 工具脚本（私有）\n'
        '- `logs/`：空目录\n'
        '- `output/20260910-audit/stage1/`、`stage2/`、`trace/`、`working/`：审计过程产物\n'
        '- 旧版 docx (`v1.0.1`、`v1.0.2`、`v1.0.3`、`v1.0.4`) 及对应生成器 (`build_docx_v101.py`、`v102.py`、`v103.py`、`v104.py`)\n'
        '- 旧版全量 ZIP (`个股工作台-v1.0.4-20260910.zip`) 和审计交付包 ZIP\n\n'
        '## 验证方法\n\n'
        '```bash\n'
        '# Windows (PowerShell)\n'
        'Get-FileHash -Algorithm SHA256 <file>\n\n'
        '# Linux/macOS\n'
        'sha256sum <file>\n'
        '```\n\n'
        '## 已知保留约束（v1.0.5 继续生效）\n\n'
        '- `execution_reviews` append-only，无 UPDATE / DELETE 业务接口\n'
        '- `execution_reviews` + `decision_ledger` 同 SQLite 事务写入\n'
        '- 行情刷新（`/api/quote/refresh`）不得修改 `execution_reviews`\n'
        '- 动态执行层不得反向修改 `trade_plan`\n'
        '- 动态执行层不得生成真实 `trades`\n'
        '- 无 execution record 时显示「尚未形成动态执行判断」\n'
        '- `add_trade_tx` 写入前必须按 `(trade_date ASC, id ASC)` 排序验证累计持仓，负持仓立即拒绝（v1.0.5 新增）\n'
        '- `execution_date` 只校验 ISO 格式与日期真实性，不再限制未来日期\n'
        '- `execution_view` 后端仅校验非空，前端用 `<datalist>` 提供 4 个常用建议项\n'
    )


def main() -> None:
    # 1) 写 PACK_NOTES.md
    notes_path = os.path.join(ROOT, PACK_NOTES_REL)
    write_text(notes_path, build_pack_notes())
    print(f'[NOTES] 生成 {PACK_NOTES_REL} ({os.path.getsize(notes_path)} bytes)')

    # 2) 检查所有 INCLUDE_FILES 存在
    for rel in INCLUDE_FILES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            if rel == PACK_MANIFEST_REL:
                continue
            print(f'[ERR] 缺失: {rel}')
            sys.exit(1)

    # 3) 计算所有文件 SHA（PACK_MANIFEST.md 不含自身条目）
    file_shas = []
    for rel in INCLUDE_FILES:
        if rel == PACK_MANIFEST_REL:
            continue
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print(f'[WARN] 跳过（不存在）: {rel}')
            continue
        sz = os.path.getsize(p)
        h = sha256_file(p)
        file_shas.append((rel, sz, h))
        print(f'[HASH] {sz:>8}  {h}  {rel}')
    file_shas.sort()
    total_size = sum(s for _, s, _ in file_shas)
    pack_count = len(file_shas)  # 清单列出的条目数（不含自身）
    zip_count = pack_count + 1   # ZIP 内总文件数（含 manifest 自身）

    # 4) 生成 PACK_MANIFEST.md
    manifest_lines = []
    manifest_lines.append('# 个股工作台 v1.0.5 —— 发版包 SHA-256 清单')
    manifest_lines.append('')
    manifest_lines.append(f'项目: A/H 投研交易工作台')
    manifest_lines.append(f'版本: v1.0.5（封板准确性修复）')
    manifest_lines.append(f'打包时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (Asia/Shanghai)')
    manifest_lines.append(f'')
    manifest_lines.append(f'## 文件数量（清晰表述）')
    manifest_lines.append('')
    manifest_lines.append(f'- 清单列出的文件条目：**{pack_count} 个**（`PACK_MANIFEST.md` 自身条目不在内）')
    manifest_lines.append(f'- 加 `PACK_MANIFEST.md` 自身后，ZIP 内总文件数：**{zip_count} 个**')
    manifest_lines.append(f'- 送审文件累计字节数：{total_size}')
    manifest_lines.append('')
    manifest_lines.append('## 文件清单（按路径排序，不含 manifest 自身）')
    manifest_lines.append('')
    manifest_lines.append('| # | 路径 | 大小 (bytes) | SHA-256 |')
    manifest_lines.append('|---|------|-------------:|---------|')
    for i, (rel, sz, h) in enumerate(file_shas, 1):
        manifest_lines.append(f'| {i:02d} | `{rel}` | {sz} | `{h}` |')
    manifest_lines.append('')
    manifest_lines.append('## 验证方法')
    manifest_lines.append('')
    manifest_lines.append('接收方对每个送审文件执行 SHA-256 校验，')
    manifest_lines.append('与上表【文件清单】节比对，差异一律视作篡改。')
    manifest_lines.append('')
    manifest_lines.append('```bash')
    manifest_lines.append('# Windows (PowerShell)')
    manifest_lines.append('Get-FileHash -Algorithm SHA256 <file>')
    manifest_lines.append('# Linux/macOS')
    manifest_lines.append('sha256sum <file>')
    manifest_lines.append('```')
    manifest_lines.append('')
    manifest_lines.append('## 关于本清单自身的完整性')
    manifest_lines.append('')
    manifest_lines.append('为避免「清单包含自身 SHA → 内容变化 → SHA 又变化」的循环依赖，')
    manifest_lines.append('本清单**不含**自身的 SHA 条目。')
    manifest_lines.append('接收方如需独立验证清单文本未被在打包后修改，')
    manifest_lines.append('直接对 `PACK_MANIFEST.md` 计算 SHA-256 即可。')
    manifest_lines.append('')

    manifest_content = '\n'.join(manifest_lines)
    manifest_path = os.path.join(ROOT, PACK_MANIFEST_REL)
    write_text(manifest_path, manifest_content)
    manifest_size = os.path.getsize(manifest_path)
    manifest_sha = sha256_file(manifest_path)
    print(f'[MANIFEST] {manifest_size:>8}  {manifest_sha}  {PACK_MANIFEST_REL}')

    # 5) 打 ZIP
    if os.path.exists(OUT_ZIP):
        os.remove(OUT_ZIP)
    with zipfile.ZipFile(OUT_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in INCLUDE_FILES:
            if rel == PACK_MANIFEST_REL:
                p = manifest_path
            else:
                p = os.path.join(ROOT, rel)
            zf.write(p, arcname=rel)
    zip_size = os.path.getsize(OUT_ZIP)
    zip_sha = sha256_file(OUT_ZIP)
    print(f'[ZIP] {zip_size:>8}  {zip_sha}  {os.path.basename(OUT_ZIP)}')

    # 6) 输出最终验证信息
    print()
    print('=' * 60)
    print('【最终发版包 v1.0.5】')
    print(f'路径: {OUT_ZIP}')
    print(f'大小: {zip_size} bytes ({zip_size / 1024:.1f} KB)')
    print(f'SHA-256: {zip_sha}')
    print(f'清单条目: {pack_count}；ZIP 文件数 = {pack_count} + 1 (manifest) = {zip_count}')
    print(f'manifest 自身 SHA: {manifest_sha}')
    print('=' * 60)


if __name__ == '__main__':
    main()
