import os
os.chdir(r'D:\个股工作台')
for p in ['.workbuddy/memory/MEMORY.md', '.workbuddy/memory/ENV-TRAPS.md']:
    b = open(p, 'rb').read()
    t = b.decode('utf-8')
    print('%-38s %6d B  %5d chars  %4d lines' % (p, len(b), len(t), t.count('\n')))
t = open('.workbuddy/memory/MEMORY.md', encoding='utf-8').read()
print('MEMORY.md 压缩: 11039 -> %d chars (%.0f%%)' % (len(t), (1 - len(t) / 11039) * 100))
keys = ['交付库 ≠ 工作区库', 'render = renderTerminal', '死代码', '10c6466', 'R-030',
        'force 语义', 'ENV-TRAPS.md', 'ah-workbench-feature-verify']
for k in keys:
    print(('  OK   ' if k in t else '  缺失 ') + k)
env = open('.workbuddy/memory/ENV-TRAPS.md', encoding='utf-8').read()
print('--- ENV-TRAPS 关键点 ---')
for k in ['agent-browser', 'Job Object', 'MSYS2 版 ssh', 'chcp 65001', 'WindowsApps',
          '静默回滚', 'heredoc']:
    print(('  OK   ' if k in env else '  缺失 ') + k)
