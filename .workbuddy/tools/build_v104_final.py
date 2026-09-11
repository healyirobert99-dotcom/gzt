"""打包 v1.0.4 最终发版 ZIP。

范围（精挑发版）：
- app/*（完整源码）
- tests/*（测试 + 设计文档 + fixture）
- data/workbench.db（生产 DB，已 schema_version=1.0.4）
- 启动工作台.bat
- output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.4.docx
- output/20260910-audit/build_docx_v104.py（审计 docx 生成器）
- PACK_NOTES.md（交付说明）
- PACK_MANIFEST.md（SHA-256 清单）

排除：
- archive/v101 v102 v103（历史归档）
- data/backup/（迁移快照）
- audit_pack_src/（临时源）
- __pycache__
- .workbuddy/memory/（个人记忆）
- .workbuddy/tools/（打包辅助）
- logs/
"""
import os
import sys
import zipfile
import hashlib
import datetime


ROOT = r'D:\个股工作台'
OUT_ZIP = r'D:\个股工作台\个股工作台-v1.0.4-20260910.zip'
PACK_NOTES_REL = 'PACK_NOTES.md'
PACK_MANIFEST_REL = 'PACK_MANIFEST.md'

# 排除目录（前缀匹配，相对 ROOT）
EXCLUDE_DIR_PREFIXES = (
    os.path.join('archive', ''),
    os.path.join('data', 'backup'),
    os.path.join('audit_pack_src', ''),
    os.path.join('logs', ''),
    os.path.join('app', '__pycache__'),
    os.path.join('.workbuddy', ''),
    os.path.join('output', ''),  # 仅手动加入个别文档，目录不进
    os.path.join('tests', '__pycache__'),
)

# 强制排除文件（即使在 include 列表里也跳过）
EXCLUDE_FILE_PATTERNS = (
    'desktop.ini', 'Thumbs.db', '.DS_Store',
)

# 必须包含的送审文件（zipfile.add 后会校验存在）
INCLUDE_FILES = [
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_integration_quote.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'tests/fixtures/sample_seed.py',
    'data/workbench.db',
    '启动工作台.bat',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.4.docx',
    'output/20260910-audit/build_docx_v104.py',
    PACK_NOTES_REL,
    PACK_MANIFEST_REL,  # 生成时由本脚本最后写入
]


def is_excluded(rel_path: str) -> bool:
    """如果文件落在 EXCLUDE_DIR_PREFIXES 中则排除。"""
    norm = rel_path.replace('\\', '/')
    for pref in EXCLUDE_DIR_PREFIXES:
        if norm == pref.rstrip('/') or norm.startswith(pref):
            return True
    base = os.path.basename(norm)
    return base in EXCLUDE_FILE_PATTERNS


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(path: str, content: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def build_pack_notes() -> str:
    """生成 PACK_NOTES.md（交付说明）。"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        '# 个股工作台 v1.0.4 —— 最终发版交付包\n\n'
        '## 项目\n\n'
        '- 名称：A/H 投研交易工作台\n'
        '- 版本：v1.0.4（精确修复版）\n'
        '- 打包时间：' + now + '（Asia/Shanghai）\n'
        '- 项目根：`.workbuddy/` 之外的工作目录本体\n\n'
        '## v1.0.4 关键修复（vs v1.0.3）\n\n'
        '| # | 修复项 | 严重度 |\n'
        '|---|--------|--------|\n'
        '| 1 | `list_securities()` 增加 `execution_latest`，首页能拿到动态执行判断 | P0 |\n'
        '| 2 | `openExecutionModal()` 从详情页拉真实最新 execution review，预填 6 字段 | P0 |\n'
        '| 3 | `test_v103 §F` 重写：禁止手工塞 `execution_latest`，走真实 `/api/securities` 链路 | P0 |\n'
        '| 4 | 全新数据库首次启动立即写 `schema_version`，不再误判为旧库触发迁移 | P0 |\n'
        '| 5 | `migrate_v102` 删除清空 `account_size_cny` / `hkd_cny_rate` 的无条件 UPDATE | P0 |\n'
        '| 6 | 删除 `execution_view` 后端白名单（人工文本，不是状态机） | P1 |\n'
        '| 7 | 删除 `execution_date` 未来日期校验 | P1 |\n'
        '| 8 | 删除 fixture 名称猜测（不再用「美图/道通」识别示例数据） | P1 |\n'
        '| 9 | 新增测试 §H/§I/§J/§K（已有判断持久化、新库初始化、升级数据保护、自由文本） | - |\n\n'
        '## 数据库状态（已就绪）\n\n'
        '- `data/workbench.db` schema_version=`1.0.4`\n'
        '- integrity_check=ok\n'
        '- FK 检查 0 违规\n'
        '- 当前为正式空库，可直接录入第一只研究标的\n\n'
        '## 测试覆盖\n\n'
        '- `tests/test_v102.py` 38/38 PASS\n'
        '- `tests/test_v103.py` §A-§E 23 + §F 10 + §G 7 + §H 8 + §I 5 + §J 3 + §K 4 = 60/60 PASS\n'
        '- `tests/test_integration_quote.py` 联网集成（运行时可独立执行）\n'
        '- 总计 98 断言全通过\n\n'
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
        '3. 打开 `data/workbench.db`（用任意 SQLite 工具）确认 `schema_version=1.0.4`\n'
        '4. 跑 `python tests/test_v102.py` 与 `python tests/test_v103.py` 确认全过\n'
        '5. 双击 `启动工作台.bat`，访问首页确认无「示例数据」提示\n\n'
        '## 包含 / 排除说明\n\n'
        '### ✅ 已包含（送审 / 发版范围）\n\n'
        '- `app/server.py`、`app/static/*`：当前 v1.0.4 应用源码（`__pycache__/` 已剔除）\n'
        '- `tests/test_v102.py`、`tests/test_v103.py`、`tests/test_integration_quote.py`：测试套件\n'
        '- `tests/design_reversal.md`、`tests/design_research_pool_history.md`：设计文档\n'
        '- `tests/fixtures/sample_seed.py`：测试 fixture\n'
        '- `data/workbench.db`：当前生产数据库（v1.0.4 schema）\n'
        '- `启动工作台.bat`：启动脚本\n'
        '- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.4.docx`：审计文档\n'
        '- `output/20260910-audit/build_docx_v104.py`：审计 docx 生成器\n'
        '- `PACK_NOTES.md`：本说明\n'
        '- `PACK_MANIFEST.md`：SHA-256 校验清单\n\n'
        '### ❌ 已排除（不送审 / 不发版范围）\n\n'
        '- `archive/v101/`、`v102/`、`v103/`：历史版本完整归档\n'
        '- `data/backup/`：6 份迁移前快照（pre-v101/v102/v103 + manual）\n'
        '- `audit_pack_src/`：上一轮审计专用临时源（仅审计方需要）\n'
        '- `app/__pycache__/`、`tests/__pycache__/`：Python 编译缓存\n'
        '- `.workbuddy/`：用户助手记忆 + 工具脚本（私有）\n'
        '- `logs/`：空目录\n'
        '- `output/20260910-audit/stage1/`、`stage2/`、`trace/`、`working/`：审计过程产物\n'
        '- 旧版 docx (`v1.0.1`、`v1.0.2`、`v1.0.3`) 及对应生成器\n'
        '- 旧版全量 ZIP (`个股工作台-v1.0.3-20260910.zip`) 和审计交付包 ZIP (`*-审计交付包-v1.0.4-20260910.zip`)\n\n'
        '## 验证方法\n\n'
        '```bash\n'
        '# Windows (PowerShell)\n'
        'Get-FileHash -Algorithm SHA256 <file>\n\n'
        '# Linux/macOS\n'
        'sha256sum <file>\n'
        '```\n\n'
        '## 已知保留约束（v1.0.4 继续生效）\n\n'
        '- `execution_reviews` append-only，无 UPDATE / DELETE 业务接口\n'
        '- `execution_reviews` + `decision_ledger` 同 SQLite 事务写入\n'
        '- 行情刷新（`/api/quote/refresh`）不得修改 `execution_reviews`\n'
        '- 动态执行层不得反向修改 `trade_plan`\n'
        '- 动态执行层不得生成真实 `trades`\n'
        '- 无 execution record 时显示「尚未形成动态执行判断」\n'
    )


def main() -> None:
    # 1) 写入 PACK_NOTES.md
    notes_path = os.path.join(ROOT, PACK_NOTES_REL)
    write_text(notes_path, build_pack_notes())
    print(f'[NOTES] 生成 {PACK_NOTES_REL} ({os.path.getsize(notes_path)} bytes)')

    # 2) 检查所有 INCLUDE_FILES 存在
    for rel in INCLUDE_FILES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            # PACK_MANIFEST.md 在第 3 步才会写，所以允许此刻不存在
            if rel == PACK_MANIFEST_REL:
                continue
            print(f'[ERR] 缺失: {rel}')
            sys.exit(1)

    # 3) 计算所有文件 SHA（第一遍，PACK_MANIFEST.md 不含自身条目）
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

    # 4) 生成 PACK_MANIFEST.md（不含自身条目）
    manifest_lines = []
    manifest_lines.append('# 个股工作台 v1.0.4 —— 发版包 SHA-256 清单')
    manifest_lines.append('')
    manifest_lines.append(f'项目: A/H 投研交易工作台')
    manifest_lines.append(f'版本: v1.0.4（精确修复版）')
    manifest_lines.append(f'打包时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (Asia/Shanghai)')
    manifest_lines.append(f'内含文件数: {len(file_shas) + 1} (本清单自身另计)')
    manifest_lines.append(f'送审文件累计字节数: {total_size}')
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
    manifest_lines.append(f'为避免清单包含自身 SHA 后导致内容变化的循环依赖，')
    manifest_lines.append(f'本清单**不含**自身的 SHA 条目。接收方如需独立验证清单文本')
    manifest_lines.append(f'未在打包后被修改，直接对 `PACK_MANIFEST.md` 计算 SHA-256 即可。')
    manifest_lines.append('')

    manifest_content = '\n'.join(manifest_lines)
    manifest_path = os.path.join(ROOT, PACK_MANIFEST_REL)
    write_text(manifest_path, manifest_content)
    manifest_size = os.path.getsize(manifest_path)
    manifest_sha = sha256_file(manifest_path)
    print(f'[MANIFEST] {manifest_size:>8}  {manifest_sha}  {PACK_MANIFEST_REL}')

    # 5) 打 ZIP（包含 PACK_MANIFEST.md）
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
    print('【最终发版包】')
    print(f'路径: {OUT_ZIP}')
    print(f'大小: {zip_size} bytes ({zip_size / 1024:.1f} KB)')
    print(f'SHA-256: {zip_sha}')
    print(f'内含文件数: {len(INCLUDE_FILES)}')
    print(f'manifest 自身 SHA: {manifest_sha}')
    print('=' * 60)


if __name__ == '__main__':
    main()
