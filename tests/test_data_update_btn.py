#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""顶栏「数据更新」按钮 —— 功能测试。

被测行为（一次点击的完整语义）
------------------------------
  1. 前端点击 #btn-refresh → refreshQuotes(true, true)
  2. 请求 `/api/quotes?symbols=...&force=1`
  3. 后端 get_quotes(force=True) **忽略 8 秒行情缓存窗口**，对本次请求的全部
     symbol 重新联网拉取
  4. 拉到的新价照常回写 securities.current_price / current_price_updated_at
  5. 60 秒后台轮询不带 force，仍复用缓存

为什么 force 是必须的
---------------------
后端原本对行情做了 8 秒去抖（`stale_window = now - cache_ts > 8`）。没有 force
时，用户点按钮若落在 8 秒窗口内，接口会直接返回缓存，`is_stale=True`，而按钮
提示"已刷新"——按钮就成了没有语义的空壳。force 让"手动更新"名副其实。

测试分层
--------
  §A  后端 force 语义（离线：stub 掉 fetch_tencent，用临时 DB，不联网）
  §B  HTTP 层 force 查询参数解析（真实 ThreadingHTTPServer + stub 上游）
  §C  前端静态契约（可见性 / 文案 / 传参 / 忙碌态 / 轮询不强制）
  §D  真实联网端到端（网络不可达整体 SKIP，不计失败）

本文件是功能测试，不是版本交付契约测试；不写真实 data/workbench.db。
"""

import os
import re
import sys
import json
import http.client
import shutil
import sqlite3
import tempfile
import threading

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server  # noqa: E402

FAIL = 0
TOTAL = 0
SKIPPED = 0


def step(name, ok, detail='', skip=False):
    global FAIL, TOTAL, SKIPPED
    if skip:
        SKIPPED += 1
        print('  [SKIP] %s %s' % (name, detail))
        return
    TOTAL += 1
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAIL += 1


def section(title):
    print('\n=== %s ===' % title)


def read_text(rel):
    with open(os.path.join(ROOT, *rel.split('/')), encoding='utf-8') as f:
        return f.read()


# ==================== 隔离环境：临时 DB + stub 上游 ====================

TMP_ROOT = tempfile.mkdtemp(prefix='wb_updbtn_')
TMP_DB = os.path.join(TMP_ROOT, 'workbench.db')
server.init_db(seed=False, db_path=TMP_DB)

_ORIG_GET_DB = server.get_db


def _tmp_db():
    c = sqlite3.connect(TMP_DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
    return c


server.get_db = _tmp_db

SID = server.create_security({
    'name': '测试标的', 'exchange': 'SH', 'code': '600000',
    'sector': '测试', 'status': '等价格', 'research': {}, 'plan': {},
})['id']

_CALLS = []          # 记录每次上游调用收到的 symbol 列表
_PRICE = {'v': 10.0}  # 可变的"最新价"


def _make_quote(sym, cur, mt='2026-09-14 10:00:00'):
    return {
        'symbol': sym, 'name': '测试标的', 'code': '600000',
        'market': 'A股', 'currency': 'CNY',
        'current': cur, 'prev_close': round(cur - 0.1, 4),
        'change': 0.1, 'change_pct': 1.0,
        'market_time': mt, 'source': 'tencent',
        'fetched_at': '2026-09-14 10:00:00',
    }


def stub_fetch(symbols):
    _CALLS.append(list(symbols))
    return {s: _make_quote(s, _PRICE['v']) for s in symbols}


_ORIG_FETCH_TENCENT = server.fetch_tencent
server.fetch_tencent = stub_fetch


def reset_cache():
    server._quote_cache.update({
        'ts': 0.0, 'data': {}, 'last_success_at': None,
        'last_error': '', 'last_error_at': None})


def db_price():
    c = sqlite3.connect(TMP_DB)
    c.row_factory = sqlite3.Row
    row = c.execute('SELECT current_price FROM securities WHERE id=?',
                    (SID,)).fetchone()
    c.close()
    return None if row is None else row['current_price']


# ==================== §A 后端 force 语义 ====================

def test_a_backend_force():
    section('§A 后端 get_quotes(force=) 语义（离线）')

    # A1：冷缓存首次必然联网
    reset_cache()
    _CALLS.clear()
    r1 = server.get_quotes(['sh600000'])
    step('§A#1 冷缓存首次调用 → 联网 1 次',
         len(_CALLS) == 1, 'upstream_calls=%d' % len(_CALLS))
    step('§A#2 首次结果 is_stale=False',
         r1['data']['sh600000'].get('is_stale') is False)

    # A3：8 秒窗口内 force 默认 → 命中缓存，不再联网
    r2 = server.get_quotes(['sh600000'])
    step('§A#3 缓存窗口内再调（force=False）→ 不再联网',
         len(_CALLS) == 1, 'upstream_calls=%d' % len(_CALLS))
    step('§A#4 缓存命中标记 is_stale=True（不伪装成本次新行情）',
         r2['data']['sh600000'].get('is_stale') is True)

    # A5：force=True 必须绕缓存重拉（这是按钮的核心）
    r3 = server.get_quotes(['sh600000'], force=True)
    step('§A#5 force=True 绕缓存强制联网（上游 +1）',
         len(_CALLS) == 2, 'upstream_calls=%d' % len(_CALLS))
    step('§A#6 force=True 的结果 is_stale=False',
         r3['data']['sh600000'].get('is_stale') is False)

    # A7：force 时携带全部请求 symbol，而不是只带"过期的"
    reset_cache()
    _CALLS.clear()
    server.get_quotes(['sh600000', 'sz000001'], force=True)
    step('§A#7 force=True 时全部 symbol 一起重拉',
         bool(_CALLS) and sorted(_CALLS[0]) == ['sh600000', 'sz000001'],
         'CALLS[0]=%s' % (_CALLS[0] if _CALLS else None))

    # A8：force 拉到的新价必须回写 DB（行情→持仓链路）
    reset_cache()
    _PRICE['v'] = 12.34
    server.get_quotes(['sh600000'], force=True)
    step('§A#8 force 拉到的新价回写 securities.current_price',
         db_price() is not None and abs(db_price() - 12.34) < 1e-9,
         'db=%s expected=12.34' % db_price())

    # A9：缓存命中时不得拿旧缓存改写 DB
    _PRICE['v'] = 99.99
    server.get_quotes(['sh600000'])  # 缓存仍新鲜 → 命中
    step('§A#9 缓存命中时不用旧价改写 DB',
         abs(db_price() - 12.34) < 1e-9, 'db=%s' % db_price())

    # A10：force 也不能凭空空转（无 symbol 就不该打上游）
    _CALLS.clear()
    server.get_quotes([], force=True)
    step('§A#10 symbols 为空时 force 也不打上游',
         len(_CALLS) == 0, 'upstream_calls=%d' % len(_CALLS))

    # A11：force 撞上上游故障，必须如实报错（不许骗用户"已更新"）
    reset_cache()

    def boom(symbols):
        _CALLS.append(list(symbols))
        raise RuntimeError('mocked network down')

    server.fetch_tencent = boom
    r = server.get_quotes(['sh600000'], force=True)
    step('§A#11 force 时上游故障 → error 非空',
         bool(r.get('error')), 'error=%r' % r.get('error'))
    server.fetch_tencent = stub_fetch


# ==================== §B HTTP 层 force 参数 ====================

def test_b_http_force_param():
    section('§B HTTP 层 /api/quotes?force= 解析（真实 server + stub 上游）')

    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    srv.daemon_threads = True
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(path):
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        c.request('GET', path)
        resp = c.getresponse()
        body = resp.read().decode('utf-8')
        c.close()
        return resp.status, json.loads(body)

    try:
        reset_cache()
        _CALLS.clear()

        st, body = get('/api/quotes?symbols=sh600000')
        step('§B#1 GET /api/quotes → 200', st == 200, 'status=%d' % st)
        step('§B#1b 响应含 data / last_success_at 字段',
             'data' in body and 'last_success_at' in body,
             'keys=%s' % sorted(body.keys()))
        n1 = len(_CALLS)
        step('§B#1c 冷缓存首请求联网 1 次', n1 == 1, 'calls=%d' % n1)

        get('/api/quotes?symbols=sh600000')
        step('§B#2 无 force + 缓存新鲜 → 不联网',
             len(_CALLS) == n1, 'calls=%d' % len(_CALLS))

        st, body = get('/api/quotes?symbols=sh600000&force=1')
        step('§B#3 force=1 → 强制联网（上游 +1）',
             len(_CALLS) == n1 + 1, 'calls=%d' % len(_CALLS))
        step('§B#4 force=1 响应中 is_stale=False',
             body['data']['sh600000']['is_stale'] is False)

        n2 = len(_CALLS)
        get('/api/quotes?symbols=sh600000&force=0')
        step('§B#5 force=0 → 不强制（仍走缓存）',
             len(_CALLS) == n2, 'calls=%d' % len(_CALLS))

        get('/api/quotes?symbols=sh600000&force=yes')
        step('§B#6 force=yes → 视为强制',
             len(_CALLS) == n2 + 1, 'calls=%d' % len(_CALLS))

        n3 = len(_CALLS)
        get('/api/quotes?symbols=sh600000&force=true')
        step('§B#7 force=true → 视为强制',
             len(_CALLS) == n3 + 1, 'calls=%d' % len(_CALLS))

        n4 = len(_CALLS)
        get('/api/quotes?symbols=sh600000&force=abc')
        step('§B#8 force=abc → 不强制（只认白名单取值）',
             len(_CALLS) == n4, 'calls=%d' % len(_CALLS))

        st, body = get('/api/quotes?symbols=sh600000&force=1')
        step('§B#9 强制更新仍返回 200（不因 force 改变状态码）',
             st == 200, 'status=%d' % st)
    finally:
        srv.shutdown()
        srv.server_close()


# ==================== §C 前端静态契约 ====================

def test_c_frontend_contract():
    section('§C 前端静态契约')

    html = read_text('app/static/index.html')
    js = read_text('app/static/app.js')

    m = re.search(r'<button id="btn-refresh"([^>]*)>([^<]*)</button>', html)
    step('§C#1 顶栏存在 #btn-refresh 按钮', m is not None,
         (m.group(0) if m else '未找到'))
    attrs = m.group(1) if m else ''
    label = (m.group(2) if m else '').strip()

    step('§C#2 按钮对用户可见（不带 hidden）',
         'hidden' not in attrs.split(), 'attrs=%r' % attrs.strip())
    step('§C#3 按钮文案为「数据更新」', label == '数据更新', 'label=%r' % label)
    step('§C#4 按钮带 title 说明其行为',
         'title=' in attrs and '行情' in attrs, 'attrs=%r' % attrs.strip())

    step('§C#5 点击绑定为「手动 + 强制」refreshQuotes(true, true)',
         'refreshQuotes(true, true)' in js)
    step('§C#6 refreshQuotes 接受 (manual, force) 两个形参',
         'function refreshQuotes(manual, force)' in js)
    step('§C#7 仅 force 时拼接 &force=1',
         "force ? '&force=1'" in js)
    step('§C#8 force=1 出现在请求 URL 构造中',
         "'/api/quotes?symbols=' + encodeURIComponent(symbols)" in js
         and '&force=1' in js)
    step('§C#9 60 秒后台轮询不带 force（不强制联网）',
         'setInterval(() => refreshQuotes(), 60000)' in js)
    step('§C#10 手动点击有忙碌态并禁用（防重复点击）',
         'setRefreshBusy' in js and 'btn.disabled' in js)
    step('§C#11 忙碌态文案为「更新中…」', '更新中…' in js)
    step('§C#12 无标的时给提示而非静默返回', '当前没有标的' in js)
    step('§C#13 手动成功提示含最后成功时间',
         "'数据已更新 · '" in js)
    step('§C#14 手动失败提示明确区分成功文案',
         '数据更新失败' in js)
    step('§C#15 轮询仍复用既有 updateQuoteStatus 反馈',
         'updateQuoteStatus()' in js)


# ==================== §D 真实联网端到端 ====================

def test_d_live_end_to_end():
    section('§D 真实联网端到端（不可达则 SKIP）')

    import urllib.request

    net_ok = False
    net_err = ''
    try:
        req = urllib.request.Request('https://qt.gtimg.cn/q=sh600000', headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://gu.qq.com/'})
        raw = urllib.request.urlopen(req, timeout=6).read()
        net_ok = b'v_sh600000' in raw
    except Exception as e:
        net_err = '%s: %s' % (type(e).__name__, e)

    if not net_ok:
        for i in range(1, 6):
            step('§D#%d 真实联网' % i, False, '网络不可达：%s' % net_err, skip=True)
        return

    server.fetch_tencent = _ORIG_FETCH_TENCENT
    try:
        reset_cache()
        r = server.get_quotes(['sh600000'], force=True)
        q = r['data'].get('sh600000', {})
        step('§D#1 force=True 真实联网拿到行情',
             isinstance(q.get('current'), (int, float)) and q.get('current') > 0,
             'current=%s' % q.get('current'))
        step('§D#2 is_stale=False（确属本次新行情）',
             q.get('is_stale') is False)
        step('§D#3 market_time 为 YYYY-MM-DD HH:MM:SS',
             isinstance(q.get('market_time'), str) and len(q['market_time']) == 19,
             'market_time=%r' % q.get('market_time'))
        step('§D#4 真实新价已回写 DB',
             db_price() is not None and abs(db_price() - q['current']) < 1e-6,
             'db=%s quote=%s' % (db_price(), q.get('current')))

        # 紧接着的非 force 请求应命中缓存（省流量路径同样真实可用）
        r2 = server.get_quotes(['sh600000'])
        step('§D#5 force 之后普通请求回到缓存路径',
             r2['data']['sh600000'].get('is_stale') is True,
             'is_stale=%s' % r2['data']['sh600000'].get('is_stale'))
    finally:
        server.fetch_tencent = stub_fetch


# ==================== 入口 ====================

def main():
    print('=== 顶栏「数据更新」按钮 —— 功能测试 ===')
    try:
        test_a_backend_force()
        test_b_http_force_param()
        test_c_frontend_contract()
        test_d_live_end_to_end()
    finally:
        server.fetch_tencent = _ORIG_FETCH_TENCENT
        server.get_db = _ORIG_GET_DB
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    print('\n' + '=' * 60)
    print('数据更新按钮测试: PASS %d / FAIL %d / SKIP %d  (共 %d 断言)'
          % (TOTAL - FAIL, FAIL, SKIPPED, TOTAL))
    print('=' * 60)
    if FAIL:
        print('FAIL_COUNT = %d' % FAIL)
        return 1
    print('FAIL_COUNT = 0')
    print('ALL TESTS PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
