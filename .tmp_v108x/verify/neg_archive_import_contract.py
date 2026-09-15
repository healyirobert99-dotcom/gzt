# -*- coding: utf-8 -*-
"""负向验证：把 §D#11 / §D#12 的每条新断言"反向打坏"，确认它们真的会翻红。

项目铁律（MEMORY.md 硬性约定 7）：新增契约断言必须做负向验证 —— 否则无法区分
"断言在守护不变式"与"断言恒真"。做法：把仓库复制到临时目录，注入一个**真实
会出问题的改动**，在副本里跑 tests/test_security_archive.py，要求目标标签 FAIL。

每次注入都在全新副本上做，互不污染；真实仓库一个字节都不改。

四个注入（对应 §D#11 / §D#11d / §D#11c / §D#12b）：
  M1  导入匹配查询加上 `AND archived_at IS NULL` → 归档标的再也导不进来
  M2  _import_apply_one 里读 archived_at（导入层开始触碰归档状态）
  M3  在 _set_archived_at 之外再造一个 archived_at 写入口（双写入口 = 未来必然漂移）
  M4  删掉 app.js 的「暂无行情」兜底（已归档标的行情渲染成空）

另两个注入（对应 §D#10d / §D#10e，「··· 更多」转发器）：
  M5  openMoreActions 里先查一次活跃列表再 return → 已归档标的 4 项一并静默失效
  M6  某一项把 ${id} 换成 ${s.id} → 不再是"纯 id 透传"，4 项不再一致

再两个注入（对应 §C#15 / §C#15b，并发 append-only 台账）：
  M7  去掉 _set_archived_at 的幂等守卫 → 并发下重复追加「标的归档」
  M8  写了台账却返回 changed=False → 幽灵行（写了却不报告）
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
TEST = 'tests/test_security_archive.py'

PASS = 0
FAIL = 0


def step(label, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [PASS] %s' % label)
    else:
        FAIL += 1
        print('  [FAIL] %s  ← %s' % (label, detail))


MUTATIONS = [
    dict(
        key='M1',
        expect='§D#11 标的匹配点均不按 archived_at 过滤',
        desc='导入匹配查询加上 AND archived_at IS NULL',
        target='app/server.py',
        old="""        row = conn.execute(
            'SELECT * FROM securities WHERE exchange=? AND code=?',
            (exchange, code)).fetchone()
        exists = row is not None""",
        new="""        row = conn.execute(
            'SELECT * FROM securities WHERE exchange=? AND code=? AND archived_at IS NULL',
            (exchange, code)).fetchone()
        exists = row is not None""",
    ),
    dict(
        key='M2',
        expect='§D#11d 导入路径 7 个函数体内完全不出现 archived_at',
        desc='_import_apply_one 开始读 archived_at',
        target='app/server.py',
        old="""    is_new = row is None
    out = {
        'index': idx,""",
        new="""    is_new = row is None
    _was_archived = dict(row)['archived_at'] if row else None
    out = {
        'index': idx,""",
    ),
    dict(
        key='M3',
        expect='§D#11c archived_at 全项目只有 1 个写入口',
        desc='再造第二个 archived_at 写入口',
        target='app/server.py',
        old="""def _impact_after(sid):""",
        new="""def _legacy_hard_archive(conn, sid):
    \"\"\"注入用：第二个修改 archived_at 的入口（真实项目里必须不存在）。\"\"\"
    conn.execute('UPDATE securities SET archived_at=?, updated_at=? WHERE id=?',
                 (now_str(), now_str(), sid))


def _impact_after(sid):""",
    ),
    dict(
        key='M4',
        expect='§D#12b 全部行情渲染点都有「暂无行情」兜底',
        desc='删掉 app.js 的「暂无行情」兜底',
        target='app/static/app.js',
        old=None,  # 特殊处理：全局删除
        new=None,
        replace_all=('暂无行情', ''),
    ),
    dict(
        key='M5',
        expect='§D#10d 「··· 更多」是纯转发器',
        desc='openMoreActions 里先查一次活跃列表（已归档标的的 4 项会一并失效）',
        target='app/static/app.js',
        old="""function openMoreActions(id) {
  openModal('更多操作', `<div class="more-actions">""",
        new="""function openMoreActions(id) {
  const s = S.secs.find(x => x.id === Number(id)); if (!s) return;
  openModal('更多操作', `<div class="more-actions">""",
    ),
    dict(
        key='M6',
        expect='§D#10e 「··· 更多」的 4 项都把原始 id 传下去',
        desc='把某一项的 ${id} 换成 ${s.id}（不再是纯 id 透传）',
        target='app/static/app.js',
        old='onclick="closeModal();openStatusModal(${id})">变更状态',
        new='onclick="closeModal();openStatusModal(${s.id})">变更状态',
    ),
    dict(
        key='M7',
        expect='§C#15 并发归档：每轮 changed=True 恰好 1 个',
        desc='去掉 _set_archived_at 的幂等守卫（并发下必然重复追加台账）',
        target='app/server.py',
        old="""    if bool(sec.get('archived_at')) == bool(value):
        return {'changed': False, 'security_id': sid,
                'archived_at': sec.get('archived_at'), 'name': sec['name']}""",
        new="""    if False:   # 注入：去掉幂等守卫
        return {'changed': False, 'security_id': sid,
                'archived_at': sec.get('archived_at'), 'name': sec['name']}""",
    ),
    dict(
        key='M8',
        expect='§C#15b 并发归档：台账增量恰等于 changed=True 数',
        desc='写了台账却报告 changed=False（幽灵行：写了却没报告）',
        target='app/server.py',
        old="""    return {'changed': True, 'security_id': sid, 'archived_at': value,
            'name': sec['name'], 'code': sec['code'], 'exchange': sec['exchange']}""",
        new="""    return {'changed': False, 'security_id': sid, 'archived_at': value,
            'name': sec['name'], 'code': sec['code'], 'exchange': sec['exchange']}""",
    ),
]


def run_case(mut):
    box = tempfile.mkdtemp(prefix='neg_arch_%s_' % mut['key'])
    proj = os.path.join(box, 'proj')
    shutil.copytree(ROOT, proj, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', 'data', 'output', 'archive', '*.zip', '.tmp_v108x'))
    path = os.path.join(proj, *mut['target'].split('/'))
    src = open(path, encoding='utf-8').read()
    if mut.get('replace_all'):
        a, b = mut['replace_all']
        if a not in src:
            return None, '注入锚点不存在：%r' % a
        src = src.replace(a, b)
    else:
        if mut['old'] not in src:
            return None, '注入锚点不存在'
        if src.count(mut['old']) != 1:
            return None, '注入锚点不唯一（%d 处）' % src.count(mut['old'])
        src = src.replace(mut['old'], mut['new'])
    open(path, 'w', encoding='utf-8', newline='').write(src)

    r = subprocess.run([PY, TEST], cwd=proj, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith('[FAIL]')]
    hit = [l for l in fails if mut['expect'] in l]
    total = re.search(r'汇总：TOTAL=(\d+)\s+PASS=(\d+)\s+FAIL=(\d+)', out)
    shutil.rmtree(box, ignore_errors=True)
    return (hit, fails, total.groups() if total else None), None


def main():
    print('=' * 78)
    print('负向验证：§C#15 + §D#10d/#10e + §D#11 / §D#12 新断言是否真的会翻红')
    print('=' * 78)
    for mut in MUTATIONS:
        res, err = run_case(mut)
        if err:
            step('%s 注入成功（%s）' % (mut['key'], mut['desc']), False, err)
            continue
        hit, fails, totals = res
        print('  %s 注入：%s' % (mut['key'], mut['desc']))
        print('    目标标签命中 FAIL = %d 条；该副本 TOTAL/PASS/FAIL = %s' % (len(hit), totals))
        for l in hit[:2]:
            print('      %s' % l[:150])
        step('%s 注入后目标断言确实翻红（%s）' % (mut['key'], mut['expect']),
             len(hit) >= 1, '未命中；副本 FAIL 共 %d 条：%s'
             % (len(fails), [l[:60] for l in fails[:3]]))
        step('%s 注入没有把负向副本整体打崩（能跑到汇总行）' % mut['key'], totals is not None)

    print()
    print('=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
