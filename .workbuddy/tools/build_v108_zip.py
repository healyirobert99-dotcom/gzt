# -*- coding: utf-8 -*-
"""构建 v1.0.8 交付 ZIP + PACK_MANIFEST（数量与 ZIP 实际内容严格一致）。

设计要点（针对 v1.0.7 交付缺陷）：
  - Manifest 逐行对应 ZIP 内真实存在的文件，不含任何 ZIP 中不存在的脚本；
  - 文件数量由 ZIP 实际内容统计得到，不人工填写；
  - SHA-256 对 ZIP 内每个文件真实计算；
  - Manifest 自身也列入清单（SHA 标注为"—"），避免数量口径歧义；
  - README.txt 默认地址为 http://127.0.0.1:8765。

运行：python .workbuddy/tools/build_v108_zip.py
"""

import os
import io
import sys
import zipfile
import hashlib

ROOT = r'D:\个股工作台'
VERSION = 'v1.0.8'
ZIP_PATH = os.path.join(ROOT, '个股工作台-v1.0.8-20260911.zip')
MANIFEST_REL = 'output/20260910-audit/PACK_MANIFEST-v1.0.8.md'
MANIFEST_ABS = os.path.join(ROOT, MANIFEST_REL)

# ---- 交付文件清单（全部为相对 ROOT 的路径） ----
FILES = [
    # 应用
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    '启动工作台.bat',
    # 数据库
    'data/workbench.db',
    # 测试
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_v105.py',
    'tests/test_v106.py',
    'tests/test_v107.py',
    'tests/test_v108.py',
    'tests/test_integration_quote.py',   # v1.0.7 ZIP 缺失，导致 test_v102 解压后失败
    'tests/fixtures/sample_seed.py',
    'tests/design_reversal.md',
    'tests/design_research_pool_history.md',
    # 样例 JSON
    'samples/json/example-full-import.json',
    'samples/json/example-execution-update.json',
    # 审计与证据
    'output/20260910-audit/PACK_NOTES-v1.0.8.md',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.8.docx',
    'output/20260910-audit/smoke_v108_http.py',
]

README = """个股工作台 {ver} 封板交付包

项目: A/H 投研交易工作台
版本: {ver}（导入完整性封板修复）

使用步骤:
  1. 解压本 ZIP 到任意目录
  2. cd <解压目录>
  3. python app/server.py
  4. 浏览器自动打开 http://127.0.0.1:8765

注意: 默认端口为 8765（用 --port 可指定其它端口）。

文档:
  - output/20260910-audit/PACK_NOTES-v1.0.8.md
  - output/20260910-audit/PACK_MANIFEST-v1.0.8.md
  - output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.8.docx

测试（离线套件，共 407 断言）:
  python tests/test_v102.py    # 38
  python tests/test_v103.py    # 60
  python tests/test_v105.py    # 25
  python tests/test_v106.py    # 28
  python tests/test_v107.py    # 127
  python tests/test_v108.py    # 129

联网测试（需外网，单独执行）:
  python tests/test_integration_quote.py        # 14

端到端冒烟（真实 HTTP，本机临时端口）:
  python output/20260910-audit/smoke_v108_http.py   # 14
""".format(ver=VERSION)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    missing = [f for f in FILES if not os.path.isfile(os.path.join(ROOT, f))]
    if missing:
        print('缺少文件，终止：')
        for m in missing:
            print('  -', m)
        return 1

    # ---------- 第一遍：写入除 manifest 之外的全部内容 ----------
    entries = {}   # arcname -> bytes（用于计算 SHA）
    for rel in FILES:
        with open(os.path.join(ROOT, rel), 'rb') as f:
            entries[rel] = f.read()
    entries['README.txt'] = README.encode('utf-8')

    # ---------- 生成 Manifest ----------
    lines = []
    lines.append('# 个股工作台 %s —— PACK_MANIFEST（交付物清单）' % VERSION)
    lines.append('')
    lines.append('生成日期: 2026-09-11')
    lines.append('版本号: Workbench %s' % VERSION)
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 文件清单')
    lines.append('')
    lines.append('| # | 相对路径 | 字节数 | SHA-256 |')
    lines.append('|---|---|---:|---|')

    order = ['README.txt'] + FILES
    rows = []
    for i, rel in enumerate(order, 1):
        data = entries[rel]
        rows.append((i, rel, len(data), sha256_bytes(data)))
    # manifest 自身列入清单（SHA 标注为 —，避免自指循环）
    rows.append((len(order) + 1, MANIFEST_REL, None, '—（本清单自身，不含 SHA）'))

    for i, rel, size, sha in rows:
        size_s = str(size) if size is not None else '—（随本清单生成）'
        lines.append('| %02d | `%s` | %s | `%s` |' % (i, rel, size_s, sha))

    total = len(rows)
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 总计')
    lines.append('')
    lines.append('- **ZIP 内文件总数: %d 个**（含本 Manifest 自身）' % total)
    total_bytes = sum(len(entries[r]) for r in order)
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
    manifest_text = '\n'.join(lines) + '\n'

    with open(MANIFEST_ABS, 'w', encoding='utf-8', newline='\n') as f:
        f.write(manifest_text)

    # ---------- 第二遍：打包（含 manifest） ----------
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in order:
            z.writestr(rel, entries[rel])
        z.writestr(MANIFEST_REL, manifest_text.encode('utf-8'))

    # ---------- 校验 ----------
    with zipfile.ZipFile(ZIP_PATH) as z:
        names = z.namelist()
    print('ZIP: %s' % ZIP_PATH)
    print('ZIP 内文件数 = %d' % len(names))
    print('Manifest 列出条目 = %d' % total)
    ok = (len(names) == total)
    print('数量一致 = %s' % ('是' if ok else '否'))
    # Manifest 中列出的路径是否都真实存在
    listed = [r[1] for r in rows]
    ghost = [p for p in listed if p not in names]
    print('幽灵条目 = %s' % (ghost or '无'))
    print('ZIP SHA-256 = %s' % sha256_file(ZIP_PATH))
    return 0 if (ok and not ghost) else 1


if __name__ == '__main__':
    sys.exit(main())
