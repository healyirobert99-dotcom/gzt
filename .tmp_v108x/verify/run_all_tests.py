# -*- coding: utf-8 -*-
"""跑全部离线测试套件并汇总（逐个 subprocess，输出落盘后解析）。

不用 shell 循环 + 管道：本环境里复合命令/管道容易被 SIGTERM 静默掉。

各套件的汇总格式**互不统一**（实测）：
  test_security_archive.py   「汇总：TOTAL=122  PASS=122  FAIL=0  SKIP=0」
  test_data_update_btn.py    「数据更新按钮测试: PASS 42 / FAIL 0 / SKIP 0  (共 42 断言)」
  test_v102 / v109 / v110    「总计: PASS 38    FAIL 0」/「v1.0.9 测试: PASS 83 / FAIL 0 (共 83 断言)」
  test_v103/105/106/107/108  只打 `FAIL_COUNT = 0`（v105 例外，有汇总行）
  test_integration_quote     「总计: PASS 14    FAIL 0    SKIP 0」
故：优先取「同行同时含 PASS n 与 FAIL n」的汇总行；取不到时回退为
数 `[PASS]` / `[FAIL]` 断言行 + FAIL_COUNT。

本脚本**不含**下列进程内/浏览器探针（它们依赖真实库副本或 Chromium，见 MEMORY.md）：
  check_archive_import.py（归档×导入，进程内 39 断言）、
  browser_e2e_archive.py（38）、browser_e2e_archive_edge.py（32）、
  check_ah_link_archive.py（11）、neg_archive_import_contract.py（负向 8）。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PY = sys.executable

SUITES = [
    'tests/test_v102.py', 'tests/test_v103.py', 'tests/test_v105.py',
    'tests/test_v106.py', 'tests/test_v107.py', 'tests/test_v108.py',
    'tests/test_v109.py', 'tests/test_v110.py',
    'tests/test_data_update_btn.py', 'tests/test_integration_quote.py',
    'tests/test_security_archive.py',
]

# 已知基线（上一轮封板记录），用于交叉核对解析是否正确
BASELINE = {
    'tests/test_v102.py': 38, 'tests/test_v103.py': 60,
    'tests/test_v105.py': 25, 'tests/test_v106.py': 28,
    'tests/test_v107.py': 127, 'tests/test_v108.py': 129,
    'tests/test_v109.py': 83, 'tests/test_v110.py': 14,
    'tests/test_data_update_btn.py': 42,
    'tests/test_integration_quote.py': 14,
    'tests/test_security_archive.py': 122,      # 113 + §D#11 共 6 条（归档×导入）
                                                # + §D#12 共 3 条（行情兜底）
}

RE_SUM = re.compile(r'PASS[ =:]+(\d+).*?FAIL[ =:]+(\d+)')
RE_FAILCNT = re.compile(r'FAIL_COUNT\s*=\s*(\d+)')


def parse(out):
    lines = out.splitlines()
    for line in reversed(lines):                       # 1) 权威汇总行
        m = RE_SUM.search(line)
        if m:
            p, f = int(m.group(1)), int(m.group(2))
            m_t = (re.search(r'TOTAL=(\d+)', line)
                   or re.search(r'共\s*(\d+)\s*断言', line))
            m_s = re.search(r'SKIP[ =:]+(\d+)', line)
            s = int(m_s.group(1)) if m_s else 0
            t = int(m_t.group(1)) if m_t else (p + f + s)
            return (t, p, f, s, line.strip())
    p = sum(1 for l in lines if ('[PASS]' in l or '[\u2705]' in l))   # 2) 回退：数断言行
    f = sum(1 for l in lines if ('[FAIL]' in l or '[\u274c]' in l))
    mf = RE_FAILCNT.search(out)
    if mf:
        f = max(f, int(mf.group(1)))
    if p or f or mf or '全部通过' in out:
        return (p + f, p, f, 0, '（无汇总行；按断言行计数）')
    return None


total = passed = failed = skipped = 0
lines = []
mismatch = []
for rel in SUITES:
    r = subprocess.run([PY, '-u', os.path.join(ROOT, rel)],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', cwd=ROOT, timeout=900)
    out = (r.stdout or '') + (r.stderr or '')
    got = parse(out)
    if got:
        t, pa, fa, sk, line = got
        total += t; passed += pa; failed += fa; skipped += sk
        flag = ''
        if rel in BASELINE and t != BASELINE[rel]:
            flag = '   ← 与基线 %d 不一致' % BASELINE[rel]
            mismatch.append(rel)
        lines.append('%-32s %-58s%s' % (rel, line, flag))
    else:
        failed += 1
        lines.append('%-32s （无法解析汇总，exit=%d）' % (rel, r.returncode))
        mismatch.append(rel)

with open(os.path.join(HERE, 'all_suites_out.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n\n' + '=' * 70 + '\n')
    fh.write('合计：TOTAL=%d  PASS=%d  FAIL=%d  SKIP=%d\n'
             % (total, passed, failed, skipped))
    fh.write('基线核对：%s\n'
             % ('全部一致' if not mismatch else '不一致 → %s' % mismatch))
    fh.write('=' * 70 + '\n')

print('\n'.join(lines))
print('\n' + '=' * 70)
print('合计：TOTAL=%d  PASS=%d  FAIL=%d  SKIP=%d' % (total, passed, failed, skipped))
print('基线核对：%s' % ('全部一致' if not mismatch else '不一致 → %s' % mismatch))
print('=' * 70)
sys.exit(1 if (failed or mismatch) else 0)
