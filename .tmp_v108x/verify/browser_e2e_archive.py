# -*- coding: utf-8 -*-
"""标的「归档 / 恢复」的真实浏览器端到端验证（可在沙箱服务 8805 上重复运行）。

跑法：
    1) 起沙箱服务（真实库副本 + 端口 8805）
    2) python .tmp_v108x/verify/browser_e2e_archive.py

本脚本把**在本环境实测出来的硬约束**写死在代码里，避免下次重踩：

1. **跨 CLI 调用不保持页面状态**：单独一次 `open` 之后页面退回 about:blank。
   故每段「open → 操作 → 观察」必须放进**一次** `batch` 调用。
2. **带空格的复合选择器会被截断成第一个 token**：`click ".mfoot button.primary"`
   实际点的是外层 `.mfoot` div —— 表现为「✓ Done 但什么都没发生」（最容易误判成
   产品 bug）。**一律用无空格的 `>` 子选择器**（`.mfoot>button.primary`）。
3. **`click` 不自动滚动进视口**：元素在视口外时点击静默落空（同样只报 ✓ Done）。
   首页「已归档」区在文档流最底部（绝对 y≈3381），默认视口够不着 →
   先 `set viewport 1280 4000` 让整页可见。
4. **`✓ Done` 不代表命中**：它是命令「已派发」，不是「点中了元素」。
   断言一律以后端 / 数据库的终态为准，UI 读数只作辅助。
5. `.card-archive` 默认 `pointer-events:none`，Playwright 的可点击性检查在移动鼠标
   **之前**做、必然失败 → **必须先 `hover .terminal-card` 再 `click .card-archive`**
   （这也正是真实用户路径：悬停才显形，显形才能点）。
6. 读数块不能用「第 N 个 ✓ Done」定位（`mouse move` / `wait` 不一定输出 ✓ Done）。
   改为按内容特征取：整数块 / 最后一个样式块 / 最后一个文本块。
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import sqlite3
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8805'
URL = BASE + '/#/home'
HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX_DB = os.path.join(HERE, 'sandbox_arch', 'data', 'workbench.db')
REAL_DB = os.path.abspath(os.path.join(HERE, '..', '..', 'data', 'workbench.db'))
REAL_PREFIX = '4f4832aa51d00b51'   # 本次会话开始时真实库的 SHA-256 前缀

PASS = FAIL = 0


def step(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %s' % name)
    else:
        FAIL += 1
        print('  FAIL  %s   %s' % (name, detail))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def ab_prefix():
    """`agent-browser` 是 sh 垫片，Windows 下 Python CreateProcess 找不到它
    （FileNotFoundError WinError 2）。改为直调 node + bin/agent-browser.js。"""
    base = os.path.join(os.path.expanduser('~'), '.workbuddy', 'binaries',
                        'node', 'versions')
    roots = ([os.path.join(base, d) for d in sorted(os.listdir(base))]
             if os.path.isdir(base) else [])
    for root in roots:
        node = os.path.join(root, 'node.exe')
        js = os.path.join(root, 'node_modules', 'agent-browser', 'bin',
                          'agent-browser.js')
        if os.path.exists(node) and os.path.exists(js):
            return [node, js]
    return ['agent-browser']


AB = ab_prefix()


OUTDIR = os.path.join(HERE, 'ab_out')
_AB_N = [0]


def _run_ab(args, timeout):
    """跑一次 agent-browser，输出落盘（**不接管道**），超时按进程树杀。

    这里刻意不用 subprocess.run(capture_output=True, timeout=...)：
    超时时它只 kill 掉直接子进程（node.exe），而 agent-browser 派生的
    agent-browser-win32-x64.exe / chrome 仍持有 stdout 管道句柄，
    于是 communicate() 里的读会**永久阻塞** —— 表现为脚本无声挂死几十分钟。
    落盘 + taskkill /T 可以彻底避免。
    """
    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR, exist_ok=True)
    _AB_N[0] += 1
    path = os.path.join(OUTDIR, 'ab_%03d.txt' % _AB_N[0])
    flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    with open(path, 'wb') as f:
        p = subprocess.Popen(AB + args, stdout=f, stderr=subprocess.STDOUT,
                             creationflags=flags)
    timed_out = False
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)],
                       capture_output=True)
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
    data = open(path, 'rb').read().decode('utf-8', 'replace')
    if timed_out:
        data += '\n__TIMEOUT__'
    return data


def batch(*cmds, timeout=150):
    return _run_ab(['batch'] + list(cmds), timeout)


def close_all():
    """重启浏览器会话。

    **环境陷阱**：agent-browser 的会话跑久了（多次 batch 之后）`:hover` 会失效 ——
    真实鼠标事件不再让 `.terminal-card:hover` 生效，`get styles` 恒读默认态
    （opacity 0 / pointer-events none），「悬停显形」类断言因此**假红**。
    症状具有迷惑性：同一批次的 `click` 仍然成功（Playwright 会给元素自身补 hover），
    只有「悬停后读样式」失败。对策就是关掉重开。
    """
    _run_ab(['close', '--all'], 60)


# ---------- 读数块解析（不依赖 ✓ Done 的序号） ----------
def _bl(out):
    return out.split('✓ Done')[1:]      # 丢掉 open 的横幅块


def ints(out):
    """所有「只含一个整数」的输出块，按出现顺序。"""
    return [int(b.strip()) for b in _bl(out) if b.strip().isdigit()]


def last_int(out):
    v = ints(out)
    return v[-1] if v else None


def last_text(out):
    for b in reversed(_bl(out)):
        s = b.strip()
        if s and not s.isdigit():
            return s
    return ''


def last_style(out):
    sb = style_blocks(out)
    return sb[-1] if sb else {}


def style_blocks(out):
    """按出现顺序返回所有 `get styles` 的读数块。"""
    res = []
    for b in _bl(out):
        if re.search(r'(?m)^opacity:', b):
            d = {}
            for line in b.splitlines():
                line = line.strip()
                if re.match(r'^[a-z][a-z-]*:', line):
                    k, _, v = line.partition(':')
                    d[k.strip()] = v.strip()
            res.append(d)
    return res


def close_all():
    """兼容旧调用点：真正的实现在文件上部（走 _run_ab，避免管道死等）。"""
    _run_ab(['close', '--all'], 60)


# ---------- 服务 / 数据库 ----------
def req(path, method='GET', body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


_TABLES = ('research', 'trade_plans', 'execution_reviews',
           'decision_ledger', 'trades')
# 台账是 append-only：归档 / 恢复各追加 1 条，故往返净零时它**应当**增长
_NONLEDGER = ('research', 'trade_plans', 'execution_reviews', 'trades')


def counts(sid):
    c = sqlite3.connect(SANDBOX_DB)
    c.row_factory = sqlite3.Row
    try:
        return {t: c.execute('SELECT COUNT(*) n FROM %s WHERE security_id=?' % t,
                             (sid,)).fetchone()['n'] for t in _TABLES}
    finally:
        c.close()


def ledger_total():
    c = sqlite3.connect(SANDBOX_DB)
    try:
        return c.execute('SELECT COUNT(*) FROM decision_ledger').fetchone()[0]
    finally:
        c.close()


def archived_rows():
    c = sqlite3.connect(SANDBOX_DB)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(
            'SELECT id,name,code,exchange,status,archived_at FROM securities'
            ' WHERE archived_at IS NOT NULL')]
    finally:
        c.close()


def sec_row(sid):
    c = sqlite3.connect(SANDBOX_DB)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute('SELECT id,name,code,exchange,status,archived_at,'
                      'updated_at FROM securities WHERE id=?', (sid,)).fetchone()
        return dict(r) if r else {}
    finally:
        c.close()


def main():
    print('=' * 78)
    print('真实服务 8805 + 真实 Chromium —— 标的「归档 / 恢复」端到端验证')
    print('=' * 78)

    real_hash0 = sha(REAL_DB)
    print('\n真实库 %s\n  sha256 = %s' % (REAL_DB, real_hash0))
    print('沙箱库 %s' % SANDBOX_DB)

    st, secs = req('/api/securities')
    st2, arch0 = req('/api/securities?archived=only')
    n_all = len(secs) + len(arch0)
    step('§0#1 沙箱服务在线、默认列表可读', st == 200 and st2 == 200,
         'st=%s/%s' % (st, st2))
    step('§0#2 起测为干净态（无归档标的）', len(arch0) == 0,
         'archived=%d' % len(arch0))
    if st != 200 or arch0:
        print('\n沙箱不干净，终止。')
        return 1
    base_ledger = ledger_total()
    print('  标的 %d 只；台账 %d 条' % (n_all, base_ledger))
    # 每进入一个大段都重开会话：会话跑久了 :hover / 点击都会退化（见 close_all 注释）
    close_all()

    # ---------- §1 悬停显形 ----------
    print('\n§1 「鼠标悬停后在右上角出现一个叉」')
    s0 = s1 = {}
    for attempt in (1, 2, 3):
        out = batch('set viewport 1280 720', 'open ' + URL, 'wait 6000',
                    'mouse move 0 0', 'wait 600', 'get styles .card-archive',
                    'hover .terminal-card', 'wait 600', 'get styles .card-archive')
        sbs = style_blocks(out)
        if len(sbs) >= 2:
            s0, s1 = sbs[0], sbs[-1]
        if s1.get('opacity') == '1' and s1.get('pointer-events') == 'auto':
            break
        print('        （第 %d 次悬停读数未生效 → 重启浏览器会话后重试）' % attempt)
        close_all()
    step('§1#1 未悬停时 × 完全不可见（opacity: 0）', s0.get('opacity') == '0',
         'opacity=%r' % s0.get('opacity'))
    step('§1#2 未悬停时 × 不可点（pointer-events: none）',
         s0.get('pointer-events') == 'none', repr(s0.get('pointer-events')))
    step('§1#3 悬停后 × 显形（opacity: 1）', s1.get('opacity') == '1',
         'opacity=%r' % s1.get('opacity'))
    step('§1#4 悬停后可点（pointer-events: auto）',
         s1.get('pointer-events') == 'auto', repr(s1.get('pointer-events')))
    step('§1#5 × 定位在卡片右上角（absolute / top 9px / right 9px / z-index 3）',
         (s1.get('position'), s1.get('top'), s1.get('right'),
          s1.get('z-index')) == ('absolute', '9px', '9px', '3'),
         '%s %s %s %s' % (s1.get('position'), s1.get('top'), s1.get('right'),
                          s1.get('z-index')))
    step('§1#6 × 尺寸恒为 20×20（悬停前后一致，不产生布局抖动）',
         (s0.get('width'), s1.get('width'), s1.get('height')) ==
         ('20px', '20px', '20px'),
         '%s/%s/%s' % (s0.get('width'), s1.get('width'), s1.get('height')))

    # ---------- §2 点 × → 影响面确认弹窗 → 确认归档 ----------
    print('\n§2 点 × → 影响面确认弹窗 → 确认归档')
    # 关键：把「点 × → 读弹窗 → 确认归档」放进**同一批次的同一次点击**。
    # 根因：首页卡片的排序依赖行情（随行情刷新而变），因此 `.terminal-card` 的
    # 「第一张」跨批次并不稳定 —— 实测两次相邻批次点到的是不同的股票
    # （亿联网络 300628.SZ ↔ 宁德时代 300750.SZ）。第一版脚本按 DOM 顺序解出 sid，
    # 结果把断言打到了另一只标的上（§3 全红但产品其实完全正常）。
    # 单批次内完成才是同源；标的身份一律以**库里归档结果**为准。
    n_card = None
    modal_txt = ''
    for attempt in (1, 2, 3):
        close_all()
        out = batch('set viewport 1280 1000', 'open ' + URL, 'wait 5000',
                    'hover .terminal-card', 'click .card-archive', 'wait 1800',
                    'get text .modal',
                    'click .mfoot>button.primary', 'wait 3000',
                    'get count .terminal-card')
        modal_txt = last_text(out)
        n_card = last_int(out)
        if archived_rows():
            print('        （第 %d 次尝试归档成功）' % attempt)
            break
        print('        （第 %d 次尝试未生效，重试）' % attempt)

    rows = archived_rows()
    step('§2#1 点 × 确认后恰好 1 只标的进入归档态', len(rows) == 1, str(rows))
    if not rows:
        print('\n归档未生效，终止。')
        return 1
    tgt = rows[0]
    sid = tgt['id']
    st, imp = req('/api/securities/%d/archive-impact' % sid)
    after = counts(sid)

    m = re.search(r'研究版本\s*(\d+)\s*交易计划\s*(\d+)\s*动态执行\s*(\d+)'
                  r'\s*决策台账\s*(\d+)\s*交易流水\s*(\d+)', modal_txt)
    ui = [int(x) for x in m.groups()] if m else []
    note = re.search(r'共\s*(\d+)\s*条记录不会被删除', modal_txt)

    step('§2#2 弹出的是「归档标的」确认框', '归档标的' in modal_txt,
         repr(modal_txt[:60]))
    step('§2#3 弹窗标的身份 == 实际被归档的标的（同一次点击）',
         tgt['name'] in modal_txt
         and ('%s · %s' % (tgt['code'], tgt['exchange'])) in modal_txt,
         'tgt=%s(%s.%s)' % (tgt['name'], tgt['code'], tgt['exchange']))
    step('§2#4 弹窗列出五类影响面（研究/计划/执行/台账/流水）', len(ui) == 5,
         'ui=%s' % ui)
    step('§2#5 弹窗影响面 == 归档后逐表实测行数（台账多的 1 条即本次留痕）',
         len(ui) == 5 and ui[0] == after['research']
         and ui[1] == after['trade_plans']
         and ui[2] == after['execution_reviews'] and ui[4] == after['trades']
         and ui[3] == after['decision_ledger'] - 1,
         'ui=%s db=%s' % (ui, after))
    step('§2#6 「共 N 条记录不会被删除」== 影响面合计',
         bool(note) and int(note.group(1)) == sum(ui),
         'note=%s sum=%s' % (note.group(1) if note else None, sum(ui)))
    step('§2#7 明说不会被删除、且预告台账追加 1 条',
         '不会被删除' in modal_txt and '追加 1 条' in modal_txt, '')
    step('§2#8 归档后工作台卡片数 17 → 16（UI 实测）', n_card == n_all - 1,
         'ui=%r expect=%d' % (n_card, n_all - 1))
    step('§2#9 研究/计划/执行/流水逐表行数 == 弹窗预告（历史一行不少）',
         len(ui) == 5 and [after[k] for k in _NONLEDGER]
         == [ui[0], ui[1], ui[2], ui[4]], 'db=%s ui=%s' % (after, ui))
    step('§2#10 台账恰好 +1（append-only，不覆盖旧记录）',
         ledger_total() == base_ledger + 1,
         '%d → %d' % (base_ledger, ledger_total()))
    step('§2#11 归档不改变交易状态 status，且写入 archived_at',
         sec_row(sid)['status'] == tgt['status']
         and bool(sec_row(sid)['archived_at']),
         '%s / %r' % (sec_row(sid)['status'], sec_row(sid)['archived_at']))
    step('§2#12 持仓中标的额外给出「不改变状态」警示',
         tgt['status'] != '持仓中' or '不会改变状态' in modal_txt,
         'status=%s' % tgt['status'])
    print('        → %s（%s.%s）研究%d / 计划%d / 执行%d / 台账%d / 流水%d，共 %d 条'
          % (tgt['name'], tgt['code'], tgt['exchange'],
             ui[0] if ui else -1, ui[1] if ui else -1, ui[2] if ui else -1,
             ui[3] if ui else -1, ui[4] if ui else -1, sum(ui) if ui else -1))

    # ---------- §3 「已归档」入口 ----------
    print('\n§3 首页出现「已归档」区，被隐藏的标的仍可找回')
    close_all()
    out = batch('set viewport 1280 4000', 'open ' + URL, 'wait 5000',
                'click .archive-section>details>summary', 'wait 1200',
                'get text .archive-section')
    sec_txt = last_text(out)
    step('§3#1 「已归档」区块已渲染', '已归档' in sec_txt, repr(sec_txt[:40]))
    step('§3#2 区块标出归档数量', re.search(r'1\s*个标的', sec_txt) is not None,
         repr(sec_txt[:120]))
    step('§3#3 展开后列出被隐藏标的的名称与代码',
         tgt['name'] in sec_txt and tgt['code'] in sec_txt,
         repr(sec_txt[:200]))
    step('§3#4 给出「恢复」入口', '恢复' in sec_txt, '')
    step('§3#5 标出归档时间', '归档于' in sec_txt, '')
    step('§3#6 明说历史完整保留', '历史完整保留' in sec_txt, '')

    # ---------- §4 恢复（严格逆操作） ----------
    print('\n§4 从「已归档」恢复 —— 严格逆操作，往返净零')
    close_all()
    out = batch('set viewport 1280 4000', 'open ' + URL, 'wait 5000',
                'click .archive-section>details>summary', 'wait 1200',
                'click .archive-row>button', 'wait 2500', 'get text .modal')
    rst_txt = last_text(out)
    step('§4#1 点「恢复」弹出恢复确认框（标题「恢复标的」）',
         '恢复标的' in rst_txt, repr(rst_txt[:60]))
    step('§4#2 恢复框同样列出影响面，并说明没有任何改动',
         '没有任何改动' in rst_txt, '')
    step('§4#3 恢复框标出原归档时间', '归档于' in rst_txt, '')

    for attempt in (1, 2, 3):
        close_all()
        batch('set viewport 1280 4000', 'open ' + URL, 'wait 5000',
              'click .archive-section>details>summary', 'wait 1200',
              'click .archive-row>button', 'wait 2500',
              'click .mfoot>button.primary', 'wait 3000')
        if not archived_rows():
            print('        （第 %d 次尝试恢复成功）' % attempt)
            break
        print('        （第 %d 次尝试未生效，重试）' % attempt)

    final = counts(sid)
    step('§4#4 恢复后归档归零', archived_rows() == [], str(archived_rows()))
    step('§4#5 工作台重新可见全部 %d 只标的' % n_all,
         len(req('/api/securities')[1]) == n_all,
         str(len(req('/api/securities')[1])))
    step('§4#6 台账再 +1（归档、恢复各留痕一次）',
         ledger_total() == base_ledger + 2,
         '%d → %d' % (base_ledger, ledger_total()))
    step('§4#7 往返净零：研究/计划/执行/流水与归档后逐表相同（恢复未删任何行）',
         [final[k] for k in _NONLEDGER] == [after[k] for k in _NONLEDGER],
         'archived=%s restored=%s' % (after, final))
    step('§4#8 恢复不改变交易状态 status', sec_row(sid)['status'] == tgt['status'],
         sec_row(sid)['status'])
    step('§4#9 恢复后 archived_at 归 NULL', sec_row(sid)['archived_at'] is None,
         repr(sec_row(sid)['archived_at']))

    # ---------- §6 隔离性 ----------
    print('\n§6 隔离性：端到端全程只操作副本')
    real_hash1 = sha(REAL_DB)
    step('§6#1 真实库 data/workbench.db 逐字节未变', real_hash1 == real_hash0,
         '%s → %s' % (real_hash0[:16], real_hash1[:16]))
    step('§6#2 真实库仍等于本次会话开始时的内容',
         real_hash1.startswith(REAL_PREFIX), real_hash1[:16])
    step('§6#3 沙箱库确已演进（证明操作真的落到副本上）',
         sha(SANDBOX_DB) != real_hash1, sha(SANDBOX_DB)[:16])
    print('        真实库 sha256 = %s' % real_hash1)
    print('        沙箱库 sha256 = %s' % sha(SANDBOX_DB))

    print('\n' + '=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
