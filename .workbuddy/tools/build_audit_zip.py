"""打包 audit_pack_src 为 ZIP，并生成 build_log.txt

设计原则：避免鸡生蛋
- log 不记录 ZIP 整体 SHA（每次重打 ZIP 都会变）
- log 不记录自身 SHA（同理）
- log 只记录 15 个送审文件的 SHA（与 manifest 一致）
- 审计方用 certutil 直接校验 ZIP 整体 SHA
"""
import os, zipfile, hashlib, datetime

target = r'D:\个股工作台\audit_pack_src'
out_zip = r'D:\个股工作台\个股工作台-审计交付包-v1.0.4-20260910.zip'
log_path = r'D:\个股工作台\output\20260910-audit\build_log.txt'
log_in_pack = os.path.join(target, 'build_log.txt')

# 收集所有 ZIP 内文件
all_files_for_zip = []
for root, _, fs in os.walk(target):
    for f in fs:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, target).replace('\\', '/')
        all_files_for_zip.append((rel, p))
all_files_for_zip.sort()

# 用于 SHA 计算的文件（不含 AUDIT_MANIFEST.md 和 build_log.txt，避免互锁）
all_files = [(rel, p) for rel, p in all_files_for_zip
             if rel not in ('AUDIT_MANIFEST.md', 'build_log.txt')]

# 算每个送审文件的 SHA
file_shas = []
for rel, p in all_files:
    h = hashlib.sha256()
    with open(p, 'rb') as fp:
        for chunk in iter(lambda: fp.read(8192), b''):
            h.update(chunk)
    file_shas.append((rel, os.path.getsize(p), h.hexdigest()))

total_size = sum(s for _, s, _ in file_shas)

# 生成 build_log.txt（不含 ZIP 整体 SHA 占位，避免鸡生蛋）
log_lines = []
log_lines.append('A/H 投研交易工作台 v1.0.4 —— 审计交付包构建日志')
log_lines.append('=' * 60)
log_lines.append('构建时间: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' (Asia/Shanghai)')
log_lines.append('项目版本: v1.0.4')
log_lines.append('目标 ZIP: %s' % os.path.basename(out_zip))
log_lines.append('打包源: %s' % target)
log_lines.append('')
log_lines.append('【1】ZIP 包说明')
log_lines.append('-' * 60)
log_lines.append('内含文件数: 17（含本日志 + AUDIT_MANIFEST.md + 15 个送审文件）')
log_lines.append('送审文件累计字节数: %d (%.1f KB)' % (total_size, total_size / 1024.0))
log_lines.append('注：本日志不预计算 ZIP 整体 SHA-256（避免「log 写 SHA → 内容变 → SHA 变」循环），')
log_lines.append('    审计方拿到 ZIP 后直接用 certutil / sha256sum 计算并核对。')
log_lines.append('')
log_lines.append('【2】ZIP 内送审文件清单（含 SHA-256）')
log_lines.append('-' * 60)
log_lines.append('本日志与 AUDIT_MANIFEST.md 互不记录对方 SHA（避免循环依赖），')
log_lines.append('仅列 15 个送审文件；审计方应同时校验 ZIP 整体 SHA 与本日志全部 SHA。')
log_lines.append('%-4s  %-8s  %-66s  %s' % ('#', 'SIZE', 'PATH', 'SHA-256'))
for i, (rel, s, h) in enumerate(file_shas, 1):
    log_lines.append('%-4d  %-8d  %-66s  %s' % (i, s, rel, h))
log_lines.append('')
log_lines.append('【3】验证方法（供审计方）')
log_lines.append('-' * 60)
log_lines.append('1. 解压 ZIP')
log_lines.append('2. 对 ZIP 整体计算 SHA-256:')
log_lines.append('   Windows: certutil -hashfile 个股工作台-审计交付包-v1.0.3-20260910.zip SHA256')
log_lines.append('   Linux/macOS: sha256sum 个股工作台-审计交付包-v1.0.3-20260910.zip')
log_lines.append('3. 对 ZIP 内每个文件执行:')
log_lines.append('   Windows (PowerShell): Get-FileHash -Algorithm SHA256 <file>')
log_lines.append('   Linux/macOS: sha256sum <file>')
log_lines.append('4. 与本日志【2】节逐行比对（仅 15 个送审文件，log 与 manifest 自身不在校验列表）')
log_lines.append('5. 校验 AUDIT_MANIFEST.md 自身 SHA-256:')
log_lines.append('   Get-FileHash -Algorithm SHA256 AUDIT_MANIFEST.md')
log_lines.append('6. 校验本日志自身 SHA-256:')
log_lines.append('   Get-FileHash -Algorithm SHA256 build_log.txt')
log_lines.append('')

log_content = '\n'.join(log_lines)
os.makedirs(os.path.dirname(log_path), exist_ok=True)
with open(log_path, 'w', encoding='utf-8') as f:
    f.write(log_content)
with open(log_in_pack, 'w', encoding='utf-8') as f:
    f.write(log_content)

# 同步 build_log.txt 到 audit_pack_src，让 ZIP 包含它
log_in_pack = os.path.join(target, 'build_log.txt')
os.makedirs(os.path.dirname(log_in_pack), exist_ok=True)
with open(log_in_pack, 'w', encoding='utf-8') as f:
    f.write(log_content)
# 重新扫描 audit_pack_src（含 build_log.txt）
all_files_for_zip = []
for root, _, fs in os.walk(target):
    for f in fs:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, target).replace('\\', '/')
        all_files_for_zip.append((rel, p))
all_files_for_zip.sort()

# 打 ZIP（含 build_log.txt）
if os.path.exists(out_zip):
    os.remove(out_zip)
with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for rel, p in all_files_for_zip:
        zf.write(p, arcname=rel)

# 计算 ZIP 整体 SHA（仅用于 stdout 输出，供审计方单独记录）
zip_h = hashlib.sha256()
with open(out_zip, 'rb') as fp:
    for chunk in iter(lambda: fp.read(8192), b''):
        zip_h.update(chunk)
zip_sz = os.path.getsize(out_zip)

print('ZIP=%s' % out_zip)
print('FILES_IN_ZIP=%d' % len(all_files_for_zip))
print('FILES_IN_LOG=%d' % len(file_shas))
print('ZIP_SIZE=%d' % zip_sz)
print('ZIP_SHA=%s' % zip_h.hexdigest())
print('LOG=%s' % log_path)