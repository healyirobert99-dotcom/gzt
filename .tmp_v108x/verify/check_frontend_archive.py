import os
import subprocess

os.chdir(r'D:\个股工作台')
NODE = r'C:\Users\宜春法院\.workbuddy\binaries\node\versions\22.22.2-2\node.exe'

for f in ('app/static/app.js',):
    r = subprocess.run([NODE, '--check', f], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    print('--check %-20s rc=%d %s' % (f, r.returncode, (r.stderr or '').strip()[:400]))

js = open('app/static/app.js', encoding='utf-8').read()
css = open('app/static/style.css', encoding='utf-8').read()

print('--- app.js 关键点 ---')
for name, k in [
    ('状态 archived', "archived: [], settings: {}"),
    ('loadAll 三请求', "/api/securities/archived"),
    ('卡片 × 按钮', 'class="card-archive" data-archive-id="${s.id}"'),
    ('阻止冒泡', "event.stopPropagation();event.preventDefault();openArchiveModal"),
    ('影响面字段', 'const ARCHIVE_IMPACT_FIELDS'),
    ('归档弹窗', 'async function openArchiveModal(id)'),
    ('恢复弹窗', 'async function openRestoreModal(id)'),
    ('已归档行', 'function uiArchivedRow(s)'),
    ('已归档区', 'function uiArchivedSection()'),
    ('首页挂载', '${uiArchivedSection()}'),
    ('调 impact 接口', "/archive-impact'"),
    ('调归档接口', "/archive',\n      { method: 'POST'"),
    ('调恢复接口', "/unarchive', { method: 'POST'"),
    ('原因字段', 'class="archive-reason"'),
]:
    print(('  OK   ' if k in js else '  缺失 ') + name)

print('--- style.css 关键点 ---')
for name, k in [
    ('预留槽位', '.terminal-card-head { padding-right: 24px; }'),
    ('默认隐藏', 'opacity: 0; pointer-events: none;'),
    ('悬停显形', '.terminal-card:hover .card-archive'),
    ('无障碍聚焦', '.card-archive:focus-visible'),
    ('影响面网格', '.archive-impact {'),
    ('已归档区', '.archive-row {'),
]:
    print(('  OK   ' if k in css else '  缺失 ') + name)

print('--- 死代码检查（死代码是真问题，不得再新增）---')
for name, k in [('死类名 .fld 已移除', 'class="fld"')]:
    print(('  OK   ' if k not in js else '  仍存在 ') + name)
