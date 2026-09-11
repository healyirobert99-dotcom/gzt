# -*- coding: utf-8 -*-
"""v1.0.10 打包脚本（工作区侧构建工具，**刻意不进 ZIP**）。

流程：生成 Manifest（逐文件实测字节数 + SHA-256）→ 生成 ZIP（含 Manifest 自身）
→ 立刻回读 ZIP 校验一遍 → 打印指纹。

约定（与 v1.0.7 / v1.0.8 / v1.0.9 相同）：
  - Manifest 只列真实存在的文件；不列任何构建脚本
  - Manifest 自指条目不计字节数、不计 SHA
  - ZIP 条目顺序 == Manifest 行顺序
  - Manifest 里的字节数/SHA 一律取**实际写入 ZIP 的那份内容**

v1.0.10 新增的一处特殊处理：
  `data/workbench.db` 交付的是**空库模板**，来源不是工作区同名文件
  （工作区那份含操作者实盘数据），见 SRC_OVERRIDE。
"""

import os
import hashlib
import zipfile
import datetime

ROOT = r'D:\个股工作台'
os.chdir(ROOT)

ZIP_NAME = '个股工作台-v1.0.10-20260911.zip'
MANIFEST = 'output/20260910-audit/PACK_MANIFEST-v1.0.10.md'
TMP_ZIP = '.tmp_v108x/verify/out-v110.zip'

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
    'tests/test_v109.py',
    'tests/test_v110.py',
    'tests/test_integration_quote.py',
    'tests/fixtures/sample_seed.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    'samples/json/example-full-import.json',
    'samples/json/example-execution-update.json',
    'output/20260910-audit/PACK_NOTES-v1.0.10.md',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.10.docx',
    'output/20260910-audit/smoke_v108_http.py',
    'output/20260910-audit/smoke_v109_http.py',
    MANIFEST,
]

# 条目名 -> 实际磁盘来源。未列出者用同名路径。
# 交付库必须是空库模板：工作区 `data/workbench.db` 含操作者实盘数据（7 只标的），
# 不得夹带进交付包。
SRC_OVERRIDE = {
    'data/workbench.db': '.tmp_v108x/verify/delivery-empty-v110.db',
}


def src_of(name):
    return SRC_OVERRIDE.get(name, name)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def sz(p):
    return os.path.getsize(p)


missing = [p for p in ORDER[:-1] if not os.path.exists(src_of(p))]
if missing:
    raise SystemExit('缺少文件，无法打包：%s' % missing)

rows = [(n, name, src_of(name), sz(src_of(name)), sha(src_of(name)))
        for n, name in enumerate(ORDER[:-1], 1)]
total = sum(r[3] for r in rows)

L = []
L.append('# 个股工作台 v1.0.10 —— PACK_MANIFEST（交付物清单）')
L.append('')
L.append('生成日期: 2026-09-11')
L.append('版本号: Workbench v1.0.10')
L.append('')
L.append('---')
L.append('')
L.append('## 文件清单')
L.append('')
L.append('| # | 相对路径 | 字节数 | SHA-256 |')
L.append('|---|---|---:|---|')
for n, name, _src, s, h in rows:
    L.append('| %02d | `%s` | %d | `%s` |' % (n, name, s, h))
L.append('| %02d | `%s` | —（随本清单生成） | `—（本清单自身，不含 SHA）` |'
         % (len(ORDER), MANIFEST))
L.append('')
L.append('---')
L.append('')
L.append('## 总计')
L.append('')
L.append('- **ZIP 内文件总数: %d 个**（含本 Manifest 自身）' % len(ORDER))
L.append('- 交付内容总字节数（不含本 Manifest）: %d B' % total)
L.append('')
L.append('> 本清单列出的每一条路径都真实存在于 ZIP 中；')
L.append('> 不列出任何 ZIP 中不存在的构建脚本（文档生成脚本一律不进交付包）。')
L.append('> 文件数量由打包脚本统计，非人工填写；打包后立即回读 ZIP 逐条校验字节数与 SHA-256。')
L.append('')
L.append('### 关于 `data/workbench.db`')
L.append('')
L.append('交付的是**空库模板**（6 张业务表行数均为 0，`schema_version = 1.0.10`，')
L.append('`integrity_check = ok`，`PRAGMA foreign_key_check` 违例 0）。')
L.append('它与本机工作区的 `data/workbench.db` **不是同一份文件**：')
L.append('工作区那份含操作者的实际标的与研究数据，按交付约定不夹带进交付包。')
L.append('')
L.append('---')
L.append('')
L.append('## 自洽验证')
L.append('')
L.append('```bash')
L.append('# 1) 启动（默认端口 8765，与 README.txt 一致）')
L.append('python app/server.py')
L.append('# A/H 投研交易工作台 v1.0.10 已启动: http://127.0.0.1:8765')
L.append('')
L.append('# 2) 离线测试套件（合计 504 断言）')
L.append('python tests/test_v102.py    # 38 PASS')
L.append('python tests/test_v103.py    # 60 PASS')
L.append('python tests/test_v105.py    # 25 PASS')
L.append('python tests/test_v106.py    # 28 PASS')
L.append('python tests/test_v107.py    # 127 PASS')
L.append('python tests/test_v108.py    # 129 PASS')
L.append('python tests/test_v109.py    # 83 PASS')
L.append('python tests/test_v110.py    # 14 PASS')
L.append('')
L.append('# 3) HTTP 端到端冒烟')
L.append('python output/20260910-audit/smoke_v109_http.py   # 38 PASS')
L.append('python output/20260910-audit/smoke_v108_http.py   # 14 PASS（回归）')
L.append('')
L.append('# 4) 联网集成（需外网）')
L.append('python tests/test_integration_quote.py            # 14 PASS')
L.append('```')
L.append('')
open(MANIFEST, 'w', encoding='utf-8', newline='\n').write('\n'.join(L))

dt = datetime.datetime.now().timetuple()[:6]
with zipfile.ZipFile(TMP_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for name in ORDER:
        zi = zipfile.ZipInfo(name, date_time=dt)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o140000000
        zi.create_system = 0
        z.writestr(zi, open(src_of(name), 'rb').read())

# ---- 回读校验 ----
z2 = zipfile.ZipFile(TMP_ZIP)
names = [i.filename for i in z2.infolist()]
print('ENTRIES =', len(names), '(Manifest 声明 %d)' % len(ORDER))
bad = []
for n, name, src, s, h in rows:
    if name not in names:
        bad.append((name, 'ZIP 缺失'))
        continue
    d = z2.read(name)
    if len(d) != s:
        bad.append((name, 'size %d != %d' % (len(d), s)))
    if hashlib.sha256(d).hexdigest() != h:
        bad.append((name, 'sha 不一致'))
print('逐条校验 =', '全部通过' if not bad else bad)
print('幽灵条目 =', [p for p in names if p not in ORDER] or '无')
print('UNCOMPRESSED_TOTAL =', sum(i.file_size for i in z2.infolist()))
print('交付内容总字节数（不含 Manifest） =', total)
print('TMP_ZIP = %s (%d B)' % (TMP_ZIP, sz(TMP_ZIP)))
print('%s sha256 = %s' % (ZIP_NAME, hashlib.sha256(open(TMP_ZIP, 'rb').read()).hexdigest()))
