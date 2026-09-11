# -*- coding: utf-8 -*-
"""v1.0.8 重新打包（修正 §8.2 表述后重建 docx → Manifest → ZIP）。
本脚本为工作区侧构建工具，刻意不进入 ZIP。
"""
import os, sys, hashlib, zipfile, datetime

ROOT = r'D:\个股工作台'
os.chdir(ROOT)

OLD_ZIP = '个股工作台-v1.0.8-20260911.zip'
NEW_ZIP = '个股工作台-v1.0.8-20260911.zip'
MANIFEST = 'output/20260910-audit/PACK_MANIFEST-v1.0.8.md'

ORDER = [
    'README.txt',
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    '启动工作台.bat',
    'data/workbench.db',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_v105.py',
    'tests/test_v106.py',
    'tests/test_v107.py',
    'tests/test_v108.py',
    'tests/test_integration_quote.py',
    'tests/fixtures/sample_seed.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'samples/json/example-full-import.json',
    'samples/json/example-execution-update.json',
    'output/20260910-audit/PACK_NOTES-v1.0.8.md',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.8.docx',
    'output/20260910-audit/smoke_v108_http.py',
    MANIFEST,
]

# 1) README.txt 从旧 ZIP 原样取出（内容未变，保持逐字节一致）
old = zipfile.ZipFile(OLD_ZIP)
readme = old.read('README.txt')
open('README.txt', 'wb').write(readme)
print('README.txt 取自旧 ZIP：%d B' % len(readme))

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def sz(p):
    return os.path.getsize(p)

# 2) 生成 Manifest（22 个真实文件 + 本清单自身）
rows = []
for n, path in enumerate(ORDER[:-1], 1):
    if not os.path.exists(path):
        raise SystemExit('缺少文件: %s' % path)
    rows.append((n, path, sz(path), sha(path)))

total_bytes = sum(r[2] for r in rows)

lines = []
lines.append('# 个股工作台 v1.0.8 —— PACK_MANIFEST（交付物清单）')
lines.append('')
lines.append('生成日期: 2026-09-11')
lines.append('版本号: Workbench v1.0.8')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 文件清单')
lines.append('')
lines.append('| # | 相对路径 | 字节数 | SHA-256 |')
lines.append('|---|---|---:|---|')
for n, path, size, h in rows:
    lines.append('| %02d | `%s` | %d | `%s` |' % (n, path, size, h))
lines.append('| %02d | `%s` | —（随本清单生成） | `—（本清单自身，不含 SHA）` |'
             % (len(ORDER), MANIFEST))
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 总计')
lines.append('')
lines.append('- **ZIP 内文件总数: %d 个**（含本 Manifest 自身）' % len(ORDER))
lines.append('- 交付内容总字节数（不含本 Manifest）: %d B' % total_bytes)
lines.append('')
lines.append('> 本清单列出的每一条路径都真实存在于 ZIP 中；')
lines.append('> 不列出任何 ZIP 中不存在的构建脚本。文件数量由打包脚本统计，非人工填写。')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 自洽验证')
lines.append('')
lines.append('```bash')
lines.append('# 1) 启动（默认端口 8765）')
lines.append('python app/server.py')
lines.append('# A/H 投研交易工作台 v1.0.8 已启动: http://127.0.0.1:8765')
lines.append('')
lines.append('# 2) 离线测试套件（407 断言）')
lines.append('python tests/test_v102.py    # 38 PASS')
lines.append('python tests/test_v103.py    # 60 PASS')
lines.append('python tests/test_v105.py    # 25 PASS')
lines.append('python tests/test_v106.py    # 28 PASS')
lines.append('python tests/test_v107.py    # 127 PASS')
lines.append('python tests/test_v108.py    # 129 PASS')
lines.append('')
lines.append('# 3) HTTP 端到端冒烟（14 PASS）')
lines.append('python output/20260910-audit/smoke_v108_http.py')
lines.append('```')
lines.append('')
open(MANIFEST, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
print('Manifest 已写入：%d B，条目 %d' % (sz(MANIFEST), len(ORDER)))

# 3) 打包（保持条目顺序、DEFLATED，时间戳统一为打包时刻）
dt = datetime.datetime.now().timetuple()[:6]
if os.path.exists(NEW_ZIP):
    os.remove(NEW_ZIP)
with zipfile.ZipFile(NEW_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in ORDER:
        if not os.path.exists(path):
            raise SystemExit('打包时缺少: %s' % path)
        zi = zipfile.ZipInfo(path, date_time=dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o140000000
        zi.create_system = 0
        z.writestr(zi, open(path, 'rb').read())
print('ZIP 已重建: %s (%d B)' % (NEW_ZIP, sz(NEW_ZIP)))

z2 = zipfile.ZipFile(NEW_ZIP)
unc = sum(i.file_size for i in z2.infolist())
print('ZIP_SHA256 =', sha(NEW_ZIP))
print('ZIP_BYTES  =', sz(NEW_ZIP))
print('ENTRIES    =', len(z2.infolist()))
print('UNCOMPRESSED_TOTAL =', unc)
print('交付内容总字节数（不含 Manifest） =', total_bytes)
