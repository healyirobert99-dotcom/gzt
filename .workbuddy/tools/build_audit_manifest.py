"""生成 AUDIT_MANIFEST.md（不含自身条目，避免鸡生蛋）"""
import os, hashlib

target = r'D:\个股工作台\audit_pack_src'

files = []
for root, _, fs in os.walk(target):
    for f in fs:
        if f in ('AUDIT_MANIFEST.md', 'build_log.txt'):
            continue  # 排除自身与构建日志，避免互锁
        p = os.path.join(root, f)
        rel = os.path.relpath(p, target).replace('\\', '/')
        sz = os.path.getsize(p)
        h = hashlib.sha256()
        with open(p, 'rb') as fp:
            for chunk in iter(lambda: fp.read(8192), b''):
                h.update(chunk)
        files.append((rel, sz, h.hexdigest()))

files.sort()
total_size = sum(s for _, s, _ in files)

lines = []
lines.append('# 审计交付包文件清单  Manifest')
lines.append('')
lines.append('项目: A/H 投研交易工作台 (Individual Stock Workbench)')
lines.append('版本: v1.0.3')
lines.append('打包时间: 2026-09-10 17:40 (Asia/Shanghai)')
lines.append('送审文件数: %d （仅含送审源码与文档；本清单与构建日志的 SHA 在构建脚本输出与 build_log.txt 中查证）' % len(files))
lines.append('送审文件总大小: %d bytes (%.1f KB)' % (total_size, total_size / 1024.0))
lines.append('')
lines.append('## 送审文件清单（按路径排序）')
lines.append('')
lines.append('| # | 路径 | 大小 (bytes) | SHA-256 |')
lines.append('|---|------|-------------:|---------|')
for i, (rel, s, h) in enumerate(files, 1):
    lines.append('| %02d | `%s` | %d | `%s` |' % (i, rel, s, h))

lines.append('')
lines.append('## 范围说明（Inclusion / Exclusion）')
lines.append('')
lines.append('### 已包含（送审计范围）')
lines.append('')
lines.append('- `app/server.py`、`app/static/*` —— 当前 v1.0.3 应用源码（`__pycache__/` 已剔除）')
lines.append('- `tests/test_v102.py`、`tests/test_v103.py`、`tests/test_integration_quote.py` —— 测试套件')
lines.append('- `tests/design_reversal.md`、`tests/design_research_pool_history.md` —— 设计文档')
lines.append('- `tests/fixtures/sample_seed.py` —— 测试 fixture')
lines.append('- `data/workbench.db` —— 当前生产数据库（v1.0.3 schema）')
lines.append('- `启动工作台.bat` —— 启动脚本')
lines.append('- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.3.docx` —— 当前版本审计文档')
lines.append('- `output/20260910-audit/build_docx_v103.py` —— 审计文档生成器')
lines.append('- `output/20260910-audit/pipeline-state.yaml` —— 审计流水线状态')
lines.append('- `AUDIT_MANIFEST.md` —— 本清单（自身 SHA 在 `build_log.txt` 中查证）')
lines.append('- `build_log.txt` —— 构建日志（ZIP 整体 SHA + 15 个送审文件 SHA + 本清单 SHA）')
lines.append('')
lines.append('### 已排除（不送审计范围）')
lines.append('')
lines.append('- `app/__pycache__/` —— Python 编译缓存')
lines.append('- `data/backup/workbench-pre-v101-*`、`pre-v102-*`、`pre-v103-*` —— 5 个历史快照')
lines.append('- `archive/v101/`、`archive/v102/` —— 历史版本完整归档（含已废弃 server.py / app.js / test_v101.py 等）')
lines.append('- `output/20260910-audit/stage1/`、`stage2/intermediate/`、`trace/`、`working/` —— 审计过程产物 / 空目录')
lines.append('- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档.docx` —— 原始版（已被 v1.0.3 取代）')
lines.append('- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.1.docx`、`v1.0.2.docx` —— 已 superseded')
lines.append('- `output/20260910-audit/build_docx_v101.py`、`build_docx_v102.py` —— 已 superseded 生成器')
lines.append('- `logs/` —— 空目录')
lines.append('- `.workbuddy/` —— 个人助手记忆，不属于审计范围')
lines.append('- `audit_pack_src/` —— 打包临时目录（打包后保留以便复核，审计方无需关注）')
lines.append('- `个股工作台-v1.0.3-20260910.zip` —— 已存在的旧包（不含审计筛选）')
lines.append('')
lines.append('## 审计要点（提请审计方关注）')
lines.append('')
lines.append('1. **v1.0.3 新增「动态执行层」**：append-only `execution_reviews` 表 + 4 视图白名单 + 行情刷新不触 execution_view')
lines.append('2. **事务原子性**：`execution_reviews` 与 `decision_ledger` 同一 SQLite 事务，含 `_LEDGER_FAIL_INJECT` 回滚测试')
lines.append('3. **回归测试**：test_v102.py 38 断言 + test_v103.py 35 断言，全部通过')
lines.append('4. **设计文档**：详见 `tests/design_reversal.md` 与 `tests/design_research_pool_history.md`')
lines.append('5. **完整审计文档**：详见内含 `A-H投研交易工作台交付审计文档-v1.0.3.docx`')
lines.append('')
lines.append('## 验证方法')
lines.append('')
lines.append('审计方可按本清单逐文件比对 SHA-256 哈希值，确认无篡改。')
lines.append('')
lines.append('```bash')
lines.append('# Windows (PowerShell)')
lines.append('Get-FileHash -Algorithm SHA256 <file>')
lines.append('# Linux/macOS')
lines.append('sha256sum <file>')
lines.append('```')
lines.append('')
lines.append('## 关于本清单自身的完整性')
lines.append('')
lines.append('本清单只列 15 个送审文件的 SHA-256，**不含**自身与 `build_log.txt` 的条目，')
lines.append('以避免「清单记录自身 SHA → 内容变化 → SHA 又变化」的循环依赖。')
lines.append('')
lines.append('**审计方验证步骤**：')
lines.append('1. 解压 ZIP')
lines.append('2. 对照本清单的 15 项 SHA，比对 ZIP 内对应文件的实际 SHA-256')
lines.append('3. 打开 `build_log.txt` 比对其【1】节 ZIP 整体 SHA 与本 ZIP 的 SHA')
lines.append('4. 打开 `build_log.txt` 比对其【2】节中 %d 个文件的 SHA-256' % len(files))
lines.append('5. 需要校验本清单 / 构建日志自身时，对它们直接计算 SHA-256')
lines.append('')

content = '\n'.join(lines)

mfst_path = os.path.join(target, 'AUDIT_MANIFEST.md')
with open(mfst_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 写完后算真实 SHA（用于打包脚本读取）
final_sz = os.path.getsize(mfst_path)
final_h = hashlib.sha256()
with open(mfst_path, 'rb') as fp:
    for chunk in iter(lambda: fp.read(8192), b''):
        final_h.update(chunk)

print('FILES=%d TOTAL=%d' % (len(files), total_size))
print('MANIFEST_FINAL_SIZE=%d' % final_sz)
print('MANIFEST_FINAL_SHA=%s' % final_h.hexdigest())