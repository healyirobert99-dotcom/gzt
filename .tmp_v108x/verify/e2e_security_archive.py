#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端：真实服务 + 真实 Chromium，验证信息卡右上角「×」归档全链路。

安全边界（重要）
----------------
**绝不碰 data/workbench.db**。整个实验在临时沙箱里跑：
  <tmp>/app/               ← 复制自 D:\\个股工作台\\app（含本次改动）
  <tmp>/data/workbench.db  ← 复制自真实库（真实标的与行数）
沙箱用完即删；脚本结尾用 SHA-256 证明真实库逐字节未变。

三条本环境踩出来的硬约束
------------------------
1. 进程树被 Job Object 托管（kill-on-close）：脚本一退出，它起的服务就被回收。
   故"起服务 → HTTP 断言 → 真浏览器操作 → 收尾"必须全在**同一次**调用里。
2. agent-browser 跨 CLI 调用不保持页面状态（单独 open 后会退回 about:blank），
   每段"open → 操作 → 观察"必须放进**一次** batch。
3. batch 不能太长：15 条一次会挂到超时，压到 8 条以内。
   **且 × 默认 pointer-events:none —— Playwright 的可点击性检查发生在移动鼠标之前，
   必然判失败，于是 click 会一直重试到超时。必须先 hover 卡片再 click ×。
   这也正是真实用户路径：悬停才显形，显形才能点。**

用法：python e2e_security_archive.py [port]
"""

import hashlib
import http.client
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = r'D:\个股工作台'
PY = r'C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
SHOT_DIR = os.path.join(os.path.expanduser('~'), '.agent-browser', 'tmp', 'screenshots')
OUT_DIR = os.path.join(ROOT, 'output', '20260915-archive-btn')

FAIL = 0
TOTAL = 0


def say(msg):
    print(msg, flush=True)


def step(name, ok, detail=''):
    global FAIL, TOTAL
    TOTAL += 1
    say('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAIL += 1


# ==================== 沙箱 ====================

BOX = tempfile.mkdtemp(prefix='wb_e2e_arch_')
shutil.copytree(os.path.join(ROOT, 'app'), os.path.join(BOX, 'app'))
os.makedirs(os.path.join(BOX, 'data'), exist_ok=True)
BOX_DB = os.path.join(BOX, 'data', 'workbench.db')
REAL_DB = os.path.join(ROOT, 'data', 'workbench.db')
LOG = os.path.join(BOX, 'server.log')
CHILD = ('research', 'trade_plans', 'execution_reviews', 'trades')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


shutil.copy2(REAL_DB, BOX_DB)
REAL_HASH0 = sha256(REAL_DB)


def db(sql, args=()):
    c = sqlite3.connect(BOX_DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def counts(sid):
    """该标的名下的行数（台账按 security_id 计，不是全局数）。"""
    out = {t: db('SELECT COUNT(*) c FROM %s WHERE security_id=?' % t, (sid,))[0]['c']
           for t in CHILD}
    out['ledger'] = db('SELECT COUNT(*) c FROM decision_ledger WHERE security_id=?',
                       (sid,))[0]['c']
    return out


def ledger_total():
    return db('SELECT COUNT(*) c FROM decision_ledger')[0]['c']


def port_pid(port):
    out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                         errors='replace').stdout
    for line in out.splitlines():
        if (':%d ' % port) in line and 'LISTENING' in line:
            return line.split()[-1]
    return None


def kill_port(port):
    pid = port_pid(port)
    if not pid:
        return '端口本就空闲'
    r = subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True,
                       text=True, encoding='gbk', errors='replace')
    time.sleep(1.0)
    return 'taskkill rc=%d 残留=%s' % (r.returncode, port_pid(port) or '无')


def req(method, path, payload=None, timeout=20):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=timeout)
    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    hdr = {'Content-Type': 'application/json'} if body else {}
    c.request(method, path, body=body, headers=hdr)
    r = c.getresponse()
    txt = r.read().decode('utf-8')
    c.close()
    try:
        return r.status, json.loads(txt)
    except Exception:
        return r.status, txt


def ab(*args, timeout=180):
    r = subprocess.run(['agent-browser'] + list(args), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout,
                       cwd=ROOT, shell=True)
    return r.returncode, ((r.stdout or '') + (r.stderr or '')).strip()


def ab_batch(label, cmds):
    say('\n  ---- %s（%d 条命令）----' % (label, len(cmds)))
    try:
        rc, out = ab('batch', *cmds)
    except subprocess.TimeoutExpired:
        say('  !! %s 超时（>180s）' % label)
        return ''
    for line in out.splitlines():
        say('  | ' + line)
    say('  ---- /%s ----' % label)
    return out


def blobs(out):
    res = []
    for m in re.finditer(r'\{[^{}]*\}', out):
        try:
            res.append(json.loads(m.group(0)))
        except Exception:
            pass
    return res


def shot_push(name):
    if not os.path.isdir(SHOT_DIR):
        return None
    fs = [os.path.join(SHOT_DIR, f) for f in os.listdir(SHOT_DIR) if f.endswith('.png')]
    if not fs:
        return None
    os.makedirs(OUT_DIR, exist_ok=True)
    dst = os.path.join(OUT_DIR, name)
    shutil.copy2(max(fs, key=os.path.getmtime), dst)
    return dst


PROC = None
try:
    say('=' * 74)
    say('E2E「信息卡 × 归档」  沙箱=%s  端口=%d' % (BOX, PORT))
    say('=' * 74)

    say('\n--- 启动沙箱服务 ---')
    kill_port(PORT)
    logf = open(LOG, 'w', encoding='utf-8')
    errf = open(LOG + '.err', 'w', encoding='utf-8')
    PROC = subprocess.Popen([PY, '-u', os.path.join(BOX, 'app', 'server.py'),
                             '--port', str(PORT), '--no-browser'],
                            cwd=BOX, stdout=logf, stderr=errf,
                            stdin=subprocess.DEVNULL)
    ready, last_err = False, ''
    for _ in range(40):
        time.sleep(0.5)
        if PROC.poll() is not None:
            break
        try:
            if req('GET', '/api/settings', timeout=3)[0] == 200:
                ready = True
                break
        except Exception as e:
            last_err = '%s: %s' % (type(e).__name__, e)
    logf.flush()
    errf.flush()
    step('沙箱服务在 %d 起来且 /api/settings → 200' % PORT, ready,
         'PID=%s rc=%s' % (PROC.pid, PROC.poll()))
    if not ready:
        say('  最后异常：%s' % last_err)
        say(open(LOG, encoding='utf-8', errors='replace').read()[-800:])
        say(open(LOG + '.err', encoding='utf-8', errors='replace').read()[-2000:])
        raise SystemExit(1)

    # ==================== §1 HTTP 全链路 ====================
    say('\n=== §1 HTTP 全链路（真实标的，库为副本） ===')
    st, act = req('GET', '/api/securities')
    n0 = len(act)
    step('§1#1 GET /api/securities → 200 且返回真实标的',
         st == 200 and n0 > 0, '%d 只' % n0)

    target = act[0]
    sid, tname = target['id'], target['name']
    before = counts(sid)
    lg0 = ledger_total()
    step('§1#2 选定目标 %s（%s.%s）id=%d：名下 研究%d 计划%d 执行%d 台账%d 交易%d；'
         '全局台账 %d' % (tname, target['code'], target['exchange'], sid,
                          before['research'], before['trade_plans'],
                          before['execution_reviews'], before['ledger'],
                          before['trades'], lg0),
         before['research'] >= 1 and before['trade_plans'] >= 1)

    st, im = req('GET', '/api/securities/%d/archive-impact' % sid)
    step('§1#3 archive-impact 五类计数与库内逐项一致（台账按该标的计）',
         st == 200 and im['research'] == before['research']
         and im['plans'] == before['trade_plans']
         and im['executions'] == before['execution_reviews']
         and im['trades'] == before['trades']
         and im['ledger'] == before['ledger'],
         'impact=%s' % {k: im[k] for k in
                        ('research', 'plans', 'executions', 'ledger', 'trades')})

    t0 = time.time()
    st, res = req('POST', '/api/securities/%d/archive' % sid,
                  {'reason': 'E2E 真实链路验证'})
    step('§1#4 POST archive → 200 且 changed=True',
         st == 200 and res.get('changed') is True, '耗时=%.3fs' % (time.time() - t0))

    st, act2 = req('GET', '/api/securities')
    step('§1#5 归档后默认列表少 1 只且不含目标',
         st == 200 and len(act2) == n0 - 1 and all(s['id'] != sid for s in act2),
         '%d -> %d' % (n0, len(act2)))
    st, arc = req('GET', '/api/securities/archived')
    step('§1#6 目标出现在已归档列表',
         st == 200 and any(s['id'] == sid for s in arc),
         '归档 %d 只' % (len(arc) if isinstance(arc, list) else -1))

    after = counts(sid)
    step('§1#7 归档后四张子表行数逐表不变（历史一行未动）',
         all(after[k] == before[k] for k in CHILD),
         'before=%s after=%s' % ({k: before[k] for k in CHILD},
                                 {k: after[k] for k in CHILD}))
    step('§1#8 全局台账只 +1（归档留痕，append-only）',
         ledger_total() == lg0 + 1, '台账 %d -> %d' % (lg0, ledger_total()))

    row = db('SELECT * FROM securities WHERE id=?', (sid,))[0]
    step('§1#9 库中 archived_at 已写入、status 未被改动',
         bool(row['archived_at']) and row['status'] == target['status'],
         'archived_at=%s status=%r' % (row['archived_at'], row['status']))
    lg = db('SELECT * FROM decision_ledger WHERE security_id=? ORDER BY id DESC LIMIT 1',
            (sid,))[0]
    step('§1#10 台账新增 event_type=标的归档 且 reason=提交值',
         lg['event_type'] == '标的归档' and lg['reason'] == 'E2E 真实链路验证',
         'event_type=%s reason=%r' % (lg['event_type'], lg['reason']))
    st, _ = req('GET', '/api/securities?archived=bogus')
    step('§1#11 ?archived=bogus → 400（白名单，不静默兜底）', st == 400, 'status=%d' % st)

    req('POST', '/api/securities/%d/unarchive' % sid, {})
    step('§1#12 已复位为未归档（供浏览器阶段从干净状态开始）',
         db('SELECT archived_at FROM securities WHERE id=?',
            (sid,))[0]['archived_at'] is None)

    ab('close', '--all')
    time.sleep(1)
    URL = 'http://127.0.0.1:%d/#/home' % PORT

    # ==================== §2 浏览器：悬停显形 ====================
    say('\n=== §2 真实 Chromium：未悬停 vs 悬停 ===')
    p0 = ("eval (()=>{const b=document.querySelector('.card-archive'),"
          "c=document.querySelector('.terminal-card');"
          "const rb=b.getBoundingClientRect(),rc=c.getBoundingClientRect(),"
          "s=getComputedStyle(b);return JSON.stringify({"
          "cards:document.querySelectorAll('.terminal-card').length,"
          "btns:document.querySelectorAll('.card-archive').length,"
          "op0:s.opacity,pe0:s.pointerEvents,dt:Math.round(rb.top-rc.top),"
          "dr:Math.round(rc.right-rb.right)})})()")
    p1 = ("eval (()=>{const s=getComputedStyle(document.querySelector('.card-archive'));"
          "return JSON.stringify({op1:s.opacity,pe1:s.pointerEvents,"
          "hovered:document.querySelectorAll('.terminal-card:hover').length})})()")
    out = ab_batch('BATCH-A 悬停探针', ['open ' + URL, 'wait 5000', p0,
                                        'hover .terminal-card', 'wait 900', p1])
    b = blobs(out)
    CARDS0 = None
    step('§2#1 batch 取回 2 段悬停探针', len(b) >= 2, 'blobs=%d' % len(b))
    if len(b) >= 2:
        a0, a1 = b[0], b[1]
        say('      未悬停=%s' % a0)
        say('      悬停后=%s' % a1)
        CARDS0 = a0.get('cards')
        step('§2#2 首页渲染出信息卡', (a0.get('cards') or 0) > 0, 'cards=%s' % CARDS0)
        step('§2#3 每张卡片都配一个 ×（数量相等）',
             a0.get('cards') == a0.get('btns'),
             'cards=%s btns=%s' % (a0.get('cards'), a0.get('btns')))
        step('§2#4 未悬停时 × 不可见（opacity=0）', str(a0.get('op0')) == '0',
             'opacity=%s' % a0.get('op0'))
        step('§2#5 未悬停时 × 不可点击（pointer-events=none）',
             a0.get('pe0') == 'none', 'pointer-events=%s' % a0.get('pe0'))
        step('§2#6 × 定位在卡片右上角（距上=%s 距右=%s，均 ≤12px）'
             % (a0.get('dt'), a0.get('dr')),
             (a0.get('dt') or 99) <= 12 and (a0.get('dr') or 99) <= 12)
        step('§2#7 悬停后 × 显形（opacity=1）—— 即用户要求的"悬停后出现"',
             str(a1.get('op1')) == '1', 'opacity=%s' % a1.get('op1'))
        step('§2#8 悬停后 × 变为可点击（none → auto）',
             a1.get('pe1') == 'auto', 'pointer-events=%s' % a1.get('pe1'))
        step('§2#9 真实浏览器确认 .terminal-card:hover 命中卡片',
             (a1.get('hovered') or 0) >= 1, 'hover 命中=%s' % a1.get('hovered'))

    # ==================== §3 浏览器：点 × → 影响面弹窗 ====================
    say('\n=== §3 真实 Chromium：点 × 弹出影响面确认弹窗 ===')
    pm = ("eval (()=>{const m=document.querySelector('.modal');return JSON.stringify({"
          "hash:location.hash,modals:document.querySelectorAll('.modal').length,"
          "drawers:document.querySelectorAll('.detail-drawer').length,"
          "txt:m?m.innerText.replace(/\\s+/g,' '):''})})()")
    out = ab_batch('BATCH-B 点击 × 并读弹窗',
                   ['open ' + URL, 'wait 5000', 'hover .terminal-card', 'wait 500',
                    'click .card-archive', 'wait 1800', pm, 'screenshot'])
    b = blobs(out)
    step('§3#1 batch 取回弹窗探针', len(b) >= 1, 'blobs=%d' % len(b))
    if b:
        m = b[0]
        txt = m.get('txt') or ''
        say('      弹窗=%s' % txt[:260])
        step('§3#2 点 × 弹出确认弹窗（modal 数=1）', m.get('modals') == 1,
             'modals=%s' % m.get('modals'))
        step('§3#3 stopPropagation 生效：未跳详情页（hash 仍为 #/home）',
             str(m.get('hash', '')).endswith('#/home'), 'hash=%s' % m.get('hash'))
        step('§3#4 未误开详情抽屉', m.get('drawers') == 0, 'drawers=%s' % m.get('drawers'))
        step('§3#5 弹窗标题为「归档标的」', '归档标的' in txt)
        step('§3#6 弹窗列出五类历史计数',
             all(k in txt for k in
                 ('研究版本', '交易计划', '动态执行', '决策台账', '交易流水')))
        step('§3#7 弹窗明说记录不会被删除、全部原样保留',
             '不会被删除' in txt and '全部原样保留' in txt)
        step('§3#8 弹窗标题含目标名称与代码', tname in txt and target['code'] in txt)
        step('§3#9 弹窗计数与后端 impact 一致（研究%d 计划%d 执行%d 台账%d）'
             % (im['research'], im['plans'], im['executions'], im['ledger']),
             all(re.search(r'%s\s*%d' % (lab, val), txt) for lab, val in
                 (('研究版本', im['research']), ('交易计划', im['plans']),
                  ('动态执行', im['executions']), ('决策台账', im['ledger']))))
        step('§3#10 确认按钮为「确认归档」', '确认归档' in txt)
        if shot_push('ui-archive-confirm-modal.png'):
            step('§3#11 确认弹窗截图已归档', True, OUT_DIR)

    # ==================== §4 浏览器：确认归档 ====================
    say('\n=== §4 真实 Chromium：确认归档后卡片消失、出现「已归档」区 ===')
    pa = ("eval (()=>JSON.stringify({"
          "t:(document.querySelector('.toast')||{textContent:''}).textContent,"
          "cards:document.querySelectorAll('.terminal-card').length,"
          "arcsec:document.querySelectorAll('.archive-section').length,"
          "arcrow:document.querySelectorAll('.archive-row').length,"
          "modals:document.querySelectorAll('.modal').length}))()")
    out = ab_batch('BATCH-C 确认归档',
                   ['open ' + URL, 'wait 5000', 'hover .terminal-card', 'wait 500',
                    'click .card-archive', 'wait 1800', 'click .modal .btn.primary',
                    'wait 1200', pa, 'screenshot'])
    b = blobs(out)
    step('§4#1 batch 取回归档后探针', len(b) >= 1, 'blobs=%d' % len(b))
    if b:
        a = b[-1]
        say('      归档后=%s' % a)
        step('§4#2 toast 含「已归档 · %s」' % tname,
             '已归档' in (a.get('t') or '') and tname in (a.get('t') or ''),
             'toast=%r' % (a.get('t') or '')[:80])
        step('§4#3 确认后弹窗关闭', a.get('modals') == 0, 'modals=%s' % a.get('modals'))
        step('§4#4 被归档的卡片从首页消失（卡片数 -1）',
             CARDS0 is not None and a.get('cards') == CARDS0 - 1,
             '%s -> %s' % (CARDS0, a.get('cards')))
        step('§4#5 首页出现「已归档」区且含 1 行可恢复记录',
             a.get('arcsec') == 1 and a.get('arcrow') == 1,
             'section=%s row=%s' % (a.get('arcsec'), a.get('arcrow')))
        if shot_push('ui-after-archive-click.png'):
            step('§4#6 归档后界面截图已归档', True, OUT_DIR)

    st, act3 = req('GET', '/api/securities')
    step('§4#7 浏览器点击真正落库（接口侧标的数 -1）',
         len(act3) == n0 - 1, '%d -> %d' % (n0, len(act3)))
    step('§4#8 浏览器点击确实写了台账（全局应为 +2：§1 的归档 + §4 的归档）',
         ledger_total() == lg0 + 2, '台账 %d -> %d' % (lg0, ledger_total()))

    # ==================== §5 浏览器：从「已归档」恢复 ====================
    say('\n=== §5 真实 Chromium：展开「已归档」→ 点恢复 ===')
    pr = ("eval (()=>{const m=document.querySelector('.modal');return JSON.stringify({"
          "modals:document.querySelectorAll('.modal').length,"
          "txt:m?m.innerText.replace(/\\s+/g,' '):''})})()")
    out = ab_batch('BATCH-D 展开已归档并点恢复',
                   ['open ' + URL, 'wait 5000',
                    "eval document.querySelector('.archive-section details').open=true",
                    'wait 400',
                    'eval JSON.stringify({arcrow:document.querySelectorAll(".archive-row").length})',
                    'click .archive-row .btn', 'wait 1800', pr, 'screenshot'])
    b = blobs(out)
    step('§5#1 batch 取回恢复弹窗探针', len(b) >= 2, 'blobs=%d' % len(b))
    if len(b) >= 2:
        r0, r1 = b[0], b[-1]
        say('      已归档行=%s' % r0)
        say('      恢复弹窗=%s' % (r1.get('txt') or '')[:200])
        step('§5#2 已归档区里有 1 行可恢复记录', r0.get('arcrow') == 1,
             'arcrow=%s' % r0.get('arcrow'))
        step('§5#3 点「恢复」弹出恢复确认弹窗', '恢复标的' in (r1.get('txt') or ''))
        step('§5#4 恢复弹窗说明历史没有任何改动',
             '没有任何改动' in (r1.get('txt') or ''))
        if shot_push('ui-archive-restore-modal.png'):
            step('§5#5 恢复弹窗截图已归档', True, OUT_DIR)

    pf = ("eval (()=>JSON.stringify({"
          "t:(document.querySelector('.toast')||{textContent:''}).textContent,"
          "cards:document.querySelectorAll('.terminal-card').length,"
          "arcsec:document.querySelectorAll('.archive-section').length,"
          "modals:document.querySelectorAll('.modal').length}))()")
    out = ab_batch('BATCH-E 确认恢复',
                   ['open ' + URL, 'wait 5000',
                    "eval document.querySelector('.archive-section details').open=true",
                    'wait 400', 'click .archive-row .btn', 'wait 1800',
                    'click .modal .btn.primary', 'wait 1200', pf, 'screenshot'])
    b = blobs(out)
    step('§5#6 batch 取回恢复后探针', len(b) >= 1, 'blobs=%d' % len(b))
    if b:
        f = b[-1]
        say('      恢复后=%s' % f)
        step('§5#7 toast 含「已恢复」', '已恢复' in (f.get('t') or ''),
             'toast=%r' % (f.get('t') or '')[:80])
        step('§5#8 恢复后卡片回到首页（卡片数回到初始值）',
             CARDS0 is not None and f.get('cards') == CARDS0,
             '%s -> %s' % (CARDS0, f.get('cards')))
        step('§5#9 无归档标的时「已归档」区不再渲染（不留空区块）',
             f.get('arcsec') == 0, 'arcsec=%s' % f.get('arcsec'))
        if shot_push('ui-after-restore.png'):
            step('§5#10 恢复后界面截图已归档', True, OUT_DIR)

    # ==================== §6 库侧终态 ====================
    say('\n=== §6 沙箱库终态：往返后历史净零变化 ===')
    final = counts(sid)
    step('§6#1 归档→恢复往返后四张子表行数与实验前完全一致',
         all(final[k] == before[k] for k in CHILD),
         'before=%s final=%s' % ({k: before[k] for k in CHILD},
                                 {k: final[k] for k in CHILD}))
    step('§6#2 该标的名下台账净增 2（归档 1 + 恢复 1）',
         final['ledger'] == before['ledger'] + 2,
         '台账 %d -> %d' % (before['ledger'], final['ledger']))
    row2 = db('SELECT * FROM securities WHERE id=?', (sid,))[0]
    step('§6#3 终态 archived_at 归 NULL（标的已回到工作台）',
         row2['archived_at'] is None, 'archived_at=%r' % row2['archived_at'])
    step('§6#4 终态 status 与实验前一致', row2['status'] == target['status'],
         '%r' % row2['status'])
    step('§6#5 全程只操作副本，真实库 data/workbench.db 逐字节未变',
         sha256(REAL_DB) == REAL_HASH0, 'sha256=%s' % sha256(REAL_DB)[:16])

    ab('close', '--all')

finally:
    say('\n--- 收尾 ---')
    if PROC is not None:
        try:
            PROC.terminate()
        except Exception:
            pass
    say('  ' + kill_port(PORT))
    shutil.rmtree(BOX, ignore_errors=True)
    say('  沙箱已删除')

say('\n' + '=' * 74)
say('E2E 汇总：TOTAL=%d  PASS=%d  FAIL=%d' % (TOTAL, TOTAL - FAIL, FAIL))
say('=' * 74)
sys.exit(1 if FAIL else 0)
