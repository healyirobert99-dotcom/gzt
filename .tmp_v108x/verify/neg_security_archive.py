#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""负向验证：把「标的归档」的关键点逐一回退，tests/test_security_archive.py 必须逐条报红。

为什么必须做
------------
"写完就绿"不能证明断言有约束力 —— 断言可能恒真（比如断言的是自己刚写下的常量）。
做法：把项目复制到临时沙箱，对**副本**做一次精确的文本回退，跑同一份测试，
要求指定的那条断言从 PASS 翻成 FAIL；沙箱用完即弃，绝不触碰工作区。

每个变体都带 (文件, 原文, 替换文)；替换前必须先断言"原文确实存在"，
否则说明回退没生效 —— 那种情况会以 [BROKEN] 报出来，不能算通过。
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
TEST_REL = 'tests/test_security_archive.py'

FAIL = 0
TOTAL = 0
SANDBOXES = []


def report(name, ok, detail=''):
    global FAIL, TOTAL
    TOTAL += 1
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAIL += 1


def build_sandbox():
    box = tempfile.mkdtemp(prefix='wb_negarch_')
    SANDBOXES.append(box)
    shutil.copytree(os.path.join(ROOT, 'app'), os.path.join(box, 'app'))
    os.makedirs(os.path.join(box, 'tests'), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, 'tests', 'test_security_archive.py'),
                 os.path.join(box, 'tests', 'test_security_archive.py'))
    return box


def run_suite(box):
    r = subprocess.run([PY, TEST_REL], cwd=box, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=600)
    out = (r.stdout or '') + (r.stderr or '')
    m = re.search(r'汇总：TOTAL=(\d+)\s+PASS=(\d+)\s+FAIL=(\d+)', out)
    stats = tuple(int(x) for x in m.groups()) if m else (0, 0, -1)
    return out, stats


def mutate(box, rel, old, new):
    p = os.path.join(box, *rel.split('/'))
    with open(p, encoding='utf-8', newline='') as f:
        txt = f.read()
    if old not in txt:
        return False
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(txt.replace(old, new, 1))
    return True


BACKEND = 'app/server.py'
JS = 'app/static/app.js'
CSS = 'app/static/style.css'

VARIANTS = [
    ('V01 归档连带删除子表行（退化成真删除）', BACKEND,
     "    conn.execute('UPDATE securities SET archived_at=?, updated_at=? WHERE id=?',\n"
     "                 (value, now_str(), sid))",
     "    conn.execute('UPDATE securities SET archived_at=?, updated_at=? WHERE id=?',\n"
     "                 (value, now_str(), sid))\n"
     "    if value:\n"
     "        for _t in ('research', 'trade_plans', 'execution_reviews', 'trades'):\n"
     "            conn.execute('DELETE FROM %s WHERE security_id=?' % _t, (sid,))",
     '§A#5 归档不减少任何子表行数'),

    ('V02 归档不写决策台账（静默状态变化）', BACKEND,
     "    ledger_add(conn, sid, today_str(), event_type, summary, reason)\n"
     "    return {'changed': True, 'security_id': sid, 'archived_at': value,",
     "    return {'changed': True, 'security_id': sid, 'archived_at': value,",
     '§A#7 归档使 decision_ledger 恰好 +1'),

    ('V03 归档不幂等（重复归档重复留痕、改写时间戳）', BACKEND,
     "    if bool(sec.get('archived_at')) == bool(value):",
     "    if False:",
     '§A#10b 重复归档不再追写台账'),

    ('V04 list_securities 不过滤归档（归档后仍在工作台）', BACKEND,
     "    where = {'active': ' WHERE archived_at IS NULL',",
     "    where = {'active': '',",
     '§A#4 归档后不再出现在 /api/securities'),

    ('V05 归档把 status 改成第六种状态', BACKEND,
     "    conn.execute('UPDATE securities SET archived_at=?, updated_at=? WHERE id=?',\n"
     "                 (value, now_str(), sid))",
     "    conn.execute(\"UPDATE securities SET archived_at=?, updated_at=?, status='已归档' \"\n"
     "                 \"WHERE id=?\", (value, now_str(), sid))",
     '§A#9 归档不改变 status'),

    ('V06 init_db 不调用幂等补列（用户的库会 no such column 直接崩）', BACKEND,
     "        # 幂等补列（不依赖 schema_version 迁移，见 _ensure_security_columns 注释）\n"
     "        _ensure_security_columns(conn)\n",
     "        pass  # 负向验证：故意去掉幂等补列\n",
     '§B#2 schema_version 已等于目标'),

    ('V07 重建路径的 INSERT 复制列漏掉 archived_at（迁移静默清空该列）', BACKEND,
     "'status','research_pool','current_price','current_price_updated_at','created_at','updated_at',\n"
     "            'archived_at')",
     "'status','research_pool','current_price','current_price_updated_at','created_at','updated_at')",
     '§B#5d 重建 DDL 列集合 == INSERT 复制列集合'),

    ('V08 前端 × 不阻止冒泡（点叉会跳到详情页）', JS,
     "onclick=\"event.stopPropagation();event.preventDefault();openArchiveModal(${s.id})\"",
     "onclick=\"openArchiveModal(${s.id})\"",
     '§D#2 × 的 onclick 在 openArchiveModal 之前'),

    ('V09 前端去掉悬停显形（× 永远不出现）', CSS,
     ".terminal-card:hover .card-archive,\n"
     ".terminal-card.keyboard-focus .card-archive,\n"
     ".terminal-card.selected-card .card-archive { opacity: 1; pointer-events: auto; }",
     ".terminal-card:hover .card-archive,\n"
     ".terminal-card.keyboard-focus .card-archive,\n"
     ".terminal-card.selected-card .card-archive { }",
     '§D#3c 悬停卡片时显形'),

    ('V10 前端 loadAll 不拉已归档（恢复入口数据源断了）', JS,
     "    api('/api/securities'), api('/api/securities/archived'), api('/api/settings')]);",
     "    api('/api/securities'), api('/api/settings')]);",
     '§D#5b loadAll 同时拉取已归档列表'),

    ('V11 键盘守卫退回不含 button（Enter 吞掉 × 点击）', JS,
     "active.matches('a[href], button, input, textarea, select, [contenteditable=\"true\"]')",
     "active.matches('input, textarea, select, [contenteditable=\"true\"]')",
     '§D#7 键盘快捷键守卫覆盖 button'),

    ('V12 ?archived= 去掉白名单改静默兜底', BACKEND,
     "                mode = _ARCHIVED_MODES.get(raw)",
     "                mode = _ARCHIVED_MODES.get(raw, 'active')",
     '§C#8 ?archived=bogus'),

    ('V13 归档成功后前端不重绘（卡片不消失）', JS,
     "    await loadAll();\n    await render();\n    toast(res.changed ? ('已归档 · ' + res.name)",
     "    await loadAll();\n    toast(res.changed ? ('已归档 · ' + res.name)",
     '§D#5 归档成功后在该函数体内重新 loadAll + render'),

    ('V14 一键删除恢复入口（已归档区不渲染）', JS,
     "${uiArchivedSection()}",
     "",
     '§D#6 首页渲染「已归档」区'),
]


if __name__ == '__main__':
    print('=' * 74)
    print('负向验证：逐点回退，要求指定断言由 PASS 翻成 FAIL')
    print('=' * 74)

    print('\n--- 基线：未改动的沙箱副本应全绿 ---')
    base = build_sandbox()
    out, (t, p, f) = run_suite(base)
    report('基线副本 TOTAL=%d PASS=%d FAIL=%d' % (t, p, f),
           f == 0 and t > 0 and p == t)

    print('\n--- 变体（每个变体一个独立沙箱）---')
    for name, rel, old, new, expect in VARIANTS:
        box = build_sandbox()
        if not mutate(box, rel, old, new):
            report(name, False, '[BROKEN] 回退原文未找到，变体未生效！')
            continue
        out, (t, p, f) = run_suite(box)
        if f < 0:
            report(name, False, '[BROKEN] 无法解析测试汇总输出')
            tail = '\n'.join(out.strip().splitlines()[-14:])
            print('       ---- 沙箱输出尾部 ----')
            for line in tail.splitlines():
                print('       | ' + line)
            print('       ------------------------')
            continue
        red = [l.strip() for l in out.splitlines() if l.startswith('  [FAIL]')]
        report(name, f > 0 and any(expect in l for l in red),
               'FAIL=%d 命中期望断言=%s' % (f, any(expect in l for l in red)))
        if not any(expect in l for l in red):
            print('       期望：%s' % expect)
            print('       实际 FAIL：%s' % ('; '.join(red[:4]) or '（无）'))

    for box in SANDBOXES:
        shutil.rmtree(box, ignore_errors=True)

    print('\n' + '=' * 74)
    print('负向验证汇总：TOTAL=%d  PASS=%d  FAIL=%d' % (TOTAL, TOTAL - FAIL, FAIL))
    print('=' * 74)
    sys.exit(1 if FAIL else 0)
