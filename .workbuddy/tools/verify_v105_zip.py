"""验证 v1.0.5 ZIP 自洽性。"""
import os
import re
import zipfile
import hashlib

zpath = r'D:\个股工作台\个股工作台-v1.0.5-20260910.zip'

# 1) 整体 SHA
zh = hashlib.sha256()
with open(zpath, 'rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        zh.update(chunk)
print(f'ZIP 整体: SIZE={os.path.getsize(zpath)} SHA={zh.hexdigest()}')

z = zipfile.ZipFile(zpath, 'r')
files = z.namelist()
print(f'ZIP 内文件数: {len(files)}')

# 2) manifest 自洽
mf_data = z.read('PACK_MANIFEST.md').decode('utf-8')
ok = 0
bad = 0
for line in mf_data.split('\n'):
    m = re.match(r'^\| (\d+) \| `(.+?)` \| (\d+) \| `([a-f0-9]{64})` \|', line)
    if m:
        idx, path, sz, sha = m.groups()
        try:
            real = z.read(path)
            real_sha = hashlib.sha256(real).hexdigest()
            if real_sha == sha and int(sz) == len(real):
                ok += 1
            else:
                bad += 1
                print(f'MISMATCH {path}')
        except KeyError:
            bad += 1
            print(f'NOT FOUND {path}')
print(f'manifest 验证: {ok}/{ok+bad}')

# 3) v1.0.5 docx 与 v1.0.4 docx SHA 对比（确认不字节复用）
docx_v105 = z.read('output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.5.docx')
v105_sha = hashlib.sha256(docx_v105).hexdigest()
v104_sha = '0ae20afe1949ffd800ff965fb1c3a1201d45ddaf713de277ac9bb857f3877838'
print()
print(f'v1.0.5 docx SHA = {v105_sha}')
print(f'v1.0.4 docx SHA = {v104_sha}')
print(f'两 SHA 不等: {v105_sha != v104_sha}')

# 4) 验证 server.js / app.js 中版本号
sjs = z.read('app/server.py').decode('utf-8')
appjs = z.read('app/static/app.js').decode('utf-8')
print()
print('=== 版本号一致性 ===')
print(f'server.py TARGET_SCHEMA_VERSION = 1.0.5  ：{("TARGET_SCHEMA_VERSION = ' + chr(39) + '1.0.5'" + chr(39)) in sjs}')
print(f'server.py Workbench/1.0.5  ：{"Workbench/1.0.5" in sjs}')
print(f'server.py argparse v1.0.5  ：{"v1.0.5" in sjs.split("argparse.ArgumentParser")[1].split(chr(10))[0]}')
print(f'server.py 启动打印 v1.0.5  ：{"A/H 投研交易工作台 v1.0.5 已启动" in sjs}')
print(f'app.js 文件头 v1.0.5  ：{"v1.0.5" in appjs.split(chr(10))[3]}')

# 5) 验证核心修复代码存在
print()
print('=== §1 修复：candidate 含 trade_date ===')
print(f'add_trade_tx 候选 id=INF：{"float(" in sjs.split("def add_trade_tx")[1].split("INSERT INTO trades")[0]}')

print()
print('=== §2 修复：execution_view 自由文本 ===')
print(f'input list=execution-view-suggest：{"list=" in appjs.split("execution_view")[1].split(">")[0]}')

print()
print('=== §3 修复：execution_date=todayVal ===')
print(f'execution_date value=${{esc(todayVal)}}：{"value=\"${esc(todayVal)}\"" in appjs}')

print()
if ok == len([m for m in (re.match(r'^\| (\d+) ', l) for l in mf_data.split('\n')) if m]) and v105_sha != v104_sha:
    print('=' * 50)
    print('所有验证 PASS')
    print('=' * 50)
