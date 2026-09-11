"""v1.0.6 ZIP 自洽验证脚本。"""

import os, re, hashlib, zipfile, sys

ZPATH = r'D:\个股工作台\个股工作台-v1.0.6-20260910.zip'

zh = hashlib.sha256()
with open(ZPATH, 'rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        zh.update(chunk)

z = zipfile.ZipFile(ZPATH, 'r')
files = z.namelist()
print('ZIP: SIZE=%d SHA=%s' % (os.path.getsize(ZPATH), zh.hexdigest()))
print('内含文件数:', len(files))

mf_data = z.read('PACK_MANIFEST.md').decode('utf-8')
ok = bad = 0
mismatches = []
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
                mismatches.append('MISMATCH ' + path)
        except KeyError:
            bad += 1
            mismatches.append('NOT FOUND ' + path)

print('manifest 验证:', ok, '/', ok + bad)
for mm in mismatches:
    print('  ', mm)

print()
print('=== ZIP 内容 ===')
for n in sorted(files):
    info = z.getinfo(n)
    print('  %8d  %s' % (info.file_size, n))

# 验证 docx SHA 不等于 v1.0.5 docx（不复用确认）
v106_docx_sha = hashlib.sha256(z.read('output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.6.docx')).hexdigest()
print()
print('v1.0.6 docx SHA =', v106_docx_sha)
print('v1.0.5 docx SHA = 96c1b1f0aa8eff04cfce8e7fc738dec4d69458440d9722fc24db0f13ca6347c3')
print('docx 不复用确认:', v106_docx_sha != '96c1b1f0aa8eff04cfce8e7fc738dec4d69458440d9722fc24db0f13ca6347c3')

# 验证 manifest 中不包含自身条目
print()
print('manifest 中不包含自身条目:', 'PACK_MANIFEST.md' not in [
    re.match(r'^\| (\d+) \| `(.+?)`', l).group(2)
    for l in mf_data.split('\n') if re.match(r'^\| \d+', l)
])

if bad == 0:
    print()
    print('ALL OK')
    sys.exit(0)
else:
    print('FAILED')
    sys.exit(1)