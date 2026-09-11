"""build_v107_zip.py — 把 v1.0.7 封板交付物打包为 ZIP

被打包内容:
  - 核心源码:app/server.py, app/static/app.{js,css}, app/static/index.html
  - 测试:tests/test_v102.py ... test_v107.py(历史 + 本次)
  - 示例 JSON:samples/json/example-*.json
  - 截图:output/20260910-audit/screenshots/*.svg
  - 交付文档:output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.7.docx
  - 交付备注:output/20260910-audit/PACK_NOTES-v1.0.7.md
  - 交付清单:output/20260910-audit/PACK_MANIFEST-v1.0.7.md
  - 数据库 schema_version 校验记录

不打包内容:
  - .workbuddy/(本地构建工具)
  - workbench.db / backup/(生产数据库)
  - .git/
  - __pycache__/
  - *.pyc
"""

import os
import sys
import zipfile
import hashlib
import shutil

ROOT = 'D:\\个股工作台'
OUT_DIR = os.path.join(ROOT, 'output', '20260910-audit')
ZIP_PATH = os.path.join(ROOT, '个股工作台-v1.0.7-20260911.zip')

# 打包文件清单(相对 ROOT)
FILES = [
    'app/server.py',
    'app/static/app.js',
    'app/static/index.html',
    'app/static/style.css',
    'tests/test_v102.py',
    'tests/test_v103.py',
    'tests/test_v105.py',
    'tests/test_v106.py',
    'tests/test_v107.py',
    'samples/json/example-full-import.json',
    'samples/json/example-execution-update.json',
    'output/20260910-audit/screenshots/screenshot-1-full-import-done.svg',
    'output/20260910-audit/screenshots/screenshot-2-execution-update-preview.svg',
    'output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.7.docx',
    'output/20260910-audit/PACK_NOTES-v1.0.7.md',
    'output/20260910-audit/PACK_MANIFEST-v1.0.7.md',
]

# 额外条目:运行时需要的占位文件 + README
EXTRA_FILES = {
    'README.txt': (
        '个股工作台 v1.0.7 封板交付包\n'
        '\n'
        '使用步骤:\n'
        '  1. 解压本 ZIP 到任意目录\n'
        '  2. cd <解压目录>\n'
        '  3. python app/server.py\n'
        '  4. 浏览器自动打开 http://127.0.0.1:8000\n'
        '\n'
        '文档:\n'
        '  - output/20260910-audit/PACK_NOTES-v1.0.7.md\n'
        '  - output/20260910-audit/PACK_MANIFEST-v1.0.7.md\n'
        '  - output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.7.docx\n'
        '\n'
        '测试:\n'
        '  python tests/test_v102.py    # 38 断言\n'
        '  python tests/test_v103.py    # 60 断言\n'
        '  python tests/test_v105.py    # 25 断言\n'
        '  python tests/test_v106.py    # 30 断言\n'
        '  python tests/test_v107.py    # 126 断言\n'
    ),
}

os.chdir(ROOT)
if os.path.exists(ZIP_PATH):
    os.remove(ZIP_PATH)

manifest_lines = []
total_bytes = 0
with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for rel in FILES:
        if not os.path.exists(rel):
            print('MISSING:', rel)
            sys.exit(1)
        with open(rel, 'rb') as f:
            data = f.read()
        zf.writestr(rel, data)
        sha = hashlib.sha256(data).hexdigest()
        manifest_lines.append(f'{len(data):>9}  {sha[:12]}  {rel}')
        total_bytes += len(data)
    for name, content in EXTRA_FILES.items():
        data = content.encode('utf-8')
        zf.writestr(name, data)
        sha = hashlib.sha256(data).hexdigest()
        manifest_lines.append(f'{len(data):>9}  {sha[:12]}  {name}')
        total_bytes += len(data)

zip_size = os.path.getsize(ZIP_PATH)
zip_sha = hashlib.sha256(open(ZIP_PATH, 'rb').read()).hexdigest()

# 把 manifest 写到 OUT_DIR(不打包进 ZIP,避免鸡生蛋)
manifest_path = os.path.join(OUT_DIR, 'BUILD_LOG-v1.0.7.md')
with open(manifest_path, 'w', encoding='utf-8') as f:
    f.write(f'# v1.0.7 ZIP 构建日志\n\n')
    f.write(f'- ZIP_PATH: `{ZIP_PATH}`\n')
    f.write(f'- ZIP_BYTES: {zip_size}\n')
    f.write(f'- ZIP_SHA256: `{zip_sha}`\n')
    f.write(f'- TOTAL_ENTRIES_BYTES(打包前): {total_bytes}\n')
    f.write(f'- ENTRIES:\n\n')
    for line in manifest_lines:
        f.write(f'  {line}\n')

print('=== BUILD LOG ===')
print(f'ZIP_PATH     = {ZIP_PATH}')
print(f'ZIP_BYTES    = {zip_size}')
print(f'ZIP_SHA256   = {zip_sha}')
print(f'LOG_PATH     = {manifest_path}')
print(f'ENTRIES      = {len(FILES) + len(EXTRA_FILES)}')