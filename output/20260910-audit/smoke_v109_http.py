# -*- coding: utf-8 -*-
"""v1.0.9 最终并发与预览一致性修复 —— 真实 HTTP 端到端冒烟脚本（审计证据）。

与 tests/test_v109.py 的区别：
  test_v109.py 中的并发用例走真实 HTTP，其余在函数级直接调用；
  本脚本把 **v1.0.9 的全部验收点** 都放到真实 HTTP 链路（127.0.0.1，临时端口 +
  临时数据库）上再跑一遍，用于证明修复在真实交付形态下同样成立。

覆盖（对应 spec 第一 ~ 五节）：
  HTTP#1-3  同一 execution token 并发 8 次：成功严格 = 1、其余 4xx、0 个 5xx、
            execution_reviews 只 +1、decision_ledger 只 +1
  HTTP#4-5  同一 full-import token 并发 8 次：最多 1 次成功、无重复
            securities / research / trade_plans / execution_reviews
  HTTP#6-7  preview execution → 另一路径新增 execution → 旧 token 拒绝 + 专属文案
  HTTP#8-9  full import 带 execution：execution_latest 改变 → 拒绝
  HTTP#10   full import 不带 execution：execution_latest 改变 → 不被阻断（导入成功）
  HTTP#11   commit 业务校验失败 → in_flight 释放 → 同一 token 修正后可重试成功
  HTTP#12   成功后 token 严格一次性失效
  HTTP#13   SQLITE_BUSY → 409；no such table → 500（不伪装成用户输入错误）

运行：
    python output/20260910-audit/smoke_v109_http.py

结果可复现：脚本自带随机端口与临时库，不触碰 data/workbench.db。
"""

import os
import sys
import json
import sqlite3
import tempfile
import threading
import urllib.request
import urllib.error

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server  # noqa: E402

PASS = 0
FAIL = 0


def step(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  [FAIL] %s %s' % (name, detail))


def http(url, body=None, method='POST'):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw}


EXEC_BODY = {
    'execution_date': '2026-09-11',
    'price_snapshot': 10.5,
    'support_zone': '10.0-10.2',
    'resistance_zone': '11.0-11.2',
    'technical_structure': '冒烟结构',
    'execution_condition': '冒烟条件',
    'execution_view': '等待技术确认',
    'reason': '冒烟依据',
}


def exec_payload(code='600001', view=None):
    body = dict(EXEC_BODY)
    if view:
        body['execution_view'] = view
    return {
        'format': 'ah-workbench-execution',
        'format_version': '1.0',
        'identity': {'exchange': 'SH', 'code': code},
        'execution': body,
    }


def full_sec(code, one_liner='冒烟逻辑', with_execution=False, plan=None):
    sec = {
        'identity': {'exchange': 'SH', 'code': code, 'name': '冒烟标的'},
        'status': '等价格',
        'research': {
            'one_liner': one_liner,
            'research_date': '2026-09-11',
            'core_validations': [{'content': '冒烟验证项', 'status': '跟踪中'}],
            'wall_conditions': [{'content': '冒烟危墙条件', 'triggered': False}],
            'change_note': '冒烟',
        },
        'trade_plan': {
            'first_zone_low': 10.0, 'first_zone_high': 11.0,
            'no_chase_price': 12.0, 'target_position_pct': 5.0,
            'next_action': '等待首仓区', 'change_note': '冒烟初始计划',
        },
    }
    if plan:
        sec['trade_plan'].update(plan)
    if with_execution:
        sec['execution'] = dict(EXEC_BODY)
    return sec


def full_payload(securities):
    return {
        'format': 'ah-workbench-import',
        'format_version': '1.0',
        'generated_at': '2026-09-11',
        'securities': securities,
    }


def preinsert(exchange, code, name='冒烟标的', status='等价格'):
    conn = server.get_db()
    try:
        cur = conn.execute(
            'INSERT INTO securities (code, exchange, name, currency, market, status, '
            'created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)',
            (code, exchange, name,
             'HKD' if exchange == 'HK' else 'CNY',
             '港股' if exchange == 'HK' else 'A股',
             status, server.now_str(), server.now_str()))
        sid = cur.lastrowid
        conn.commit()
        return sid
    finally:
        conn.close()


def count(table, sid=None):
    conn = server.get_db()
    try:
        if sid is None:
            return conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
        return conn.execute('SELECT COUNT(*) FROM %s WHERE security_id=?'
                            % table, (sid,)).fetchone()[0]
    finally:
        conn.close()


def max_version(table, sid):
    conn = server.get_db()
    try:
        return conn.execute('SELECT MAX(version) v FROM %s WHERE security_id=?'
                            % table, (sid,)).fetchone()['v']
    finally:
        conn.close()


def sec_id(exchange, code):
    conn = server.get_db()
    try:
        row = conn.execute('SELECT id FROM securities WHERE exchange=? AND code=?',
                           (exchange, code)).fetchone()
        return row['id'] if row else None
    finally:
        conn.close()


def concurrent_post(base, url, body, n=8):
    """n 个线程同时冲同一个端点，返回 [(status, body), ...]。"""
    results = []
    barrier = threading.Barrier(n)

    def worker():
        barrier.wait()
        results.append(http(base + url, body))

    ts = [threading.Thread(target=worker) for _ in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return results


def main():
    fd, db_path = tempfile.mkstemp(suffix='.db', prefix='wb-smoke109-')
    os.close(fd)
    server.init_db(seed=False, db_path=db_path)

    def _normal():
        c = sqlite3.connect(db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    server.get_db = _normal
    with server._IMPORT_PREVIEW_LOCK:
        server._IMPORT_PREVIEW_CACHE.clear()

    # 预置两只标的，供 execution-only 用例使用
    preinsert('SH', '600001', '冒烟执行标的')
    preinsert('SH', '600002', '冒烟漂移标的')

    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    srv.daemon_threads = True
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d' % port
    print('冒烟服务已启动: %s（临时库 %s，v%s）'
          % (base, os.path.basename(db_path), server.TARGET_SCHEMA_VERSION))

    try:
        # ---------- HTTP#1-3 execution token 并发 8 次 ----------
        sid1 = sec_id('SH', '600001')
        st, res = http(base + '/api/import/execution/preview', exec_payload('600001'))
        step('HTTP#1 execution preview → 200', st == 200, 'status=%s' % st)
        token = res.get('token')
        be, bl = count('execution_reviews'), count('decision_ledger')

        results = concurrent_post(base, '/api/import/execution/commit', {'token': token}, 8)
        codes = sorted(s for s, _ in results)
        ok_n = sum(1 for s, _ in results if s == 200)
        c5xx = sum(1 for s, _ in results if 500 <= s < 600)
        c4xx = sum(1 for s, _ in results if 400 <= s < 500)
        step('HTTP#2 并发 8 次：成功严格 = 1', ok_n == 1, '成功=%d 分布=%s' % (ok_n, codes))
        step('HTTP#2b 其余均为受控 4xx', c4xx == 7, '4xx=%d' % c4xx)
        step('HTTP#2c 0 个 5xx', c5xx == 0, '5xx=%d' % c5xx)
        step('HTTP#3 execution_reviews 只 +1', count('execution_reviews') - be == 1,
             '%d -> %d' % (be, count('execution_reviews')))
        step('HTTP#3b decision_ledger 只 +1', count('decision_ledger') - bl == 1,
             '%d -> %d' % (bl, count('decision_ledger')))
        step('HTTP#3c 该证券 execution 恰 1 条', count('execution_reviews', sid1) == 1)

        # ---------- HTTP#4-5 full-import token 并发 8 次 ----------
        st, res = http(base + '/api/import/preview',
                       full_payload([full_sec('600100', with_execution=True)]))
        step('HTTP#4 full preview → 200', st == 200, 'status=%s' % st)
        ftoken = res.get('token')

        results = concurrent_post(base, '/api/import/commit',
                                  {'token': ftoken, 'confirmed_status_changes': []}, 8)
        codes = sorted(s for s, _ in results)
        ok_n = sum(1 for s, _ in results if s == 200)
        c5xx = sum(1 for s, _ in results if 500 <= s < 600)
        step('HTTP#4b 并发 8 次：最多 1 次成功', ok_n <= 1, '成功=%d 分布=%s' % (ok_n, codes))
        step('HTTP#4c 0 个 5xx', c5xx == 0, '5xx=%d' % c5xx)
        sidx = sec_id('SH', '600100')
        step('HTTP#5 securities 无重复', count('securities') == 3,
             'securities=%d（2 预置 + 1 新建）' % count('securities'))
        step('HTTP#5b research 无重复版本', max_version('research', sidx) == 1,
             'research max=%s' % max_version('research', sidx))
        step('HTTP#5c trade_plans 无重复版本', max_version('trade_plans', sidx) == 1,
             'plan max=%s' % max_version('trade_plans', sidx))
        step('HTTP#5d execution 无重复追加', count('execution_reviews', sidx) == 1,
             'executions=%d' % count('execution_reviews', sidx))

        # ---------- 为 600002 建立基线（research v1 / plan v1） ----------
        sid2 = sec_id('SH', '600002')
        st, res = http(base + '/api/import/preview',
                       full_payload([full_sec('600002', one_liner='基线逻辑')]))
        st, res = http(base + '/api/import/commit',
                       {'token': res['token'], 'confirmed_status_changes': []})
        step('HTTP#5e 600002 基线导入成功（research/plan 均为 v1）',
             st == 200 and max_version('research', sid2) == 1
             and max_version('trade_plans', sid2) == 1,
             'status=%s research_max=%s plan_max=%s'
             % (st, max_version('research', sid2), max_version('trade_plans', sid2)))

        # ---------- HTTP#6-7 execution 漂移 ----------
        st, res = http(base + '/api/import/execution/preview', exec_payload('600002'))
        step('HTTP#6 execution preview → 200', st == 200, 'status=%s' % st)
        etok = res.get('token')
        server.add_execution_tx(sid2, dict(EXEC_BODY, execution_view='继续观察'))
        st, res = http(base + '/api/import/execution/commit', {'token': etok})
        err = str(res.get('error') or '')
        step('HTTP#6b preview 后另一路径新增 execution → 旧 token 被拒 400',
             st == 400, 'status=%s' % st)
        step('HTTP#6c 专属文案正确',
             '动态执行判断自预览后已发生变化，请重新解析预览。' in err,
             'error=%s' % err[:56].replace('\n', '|'))
        step('HTTP#6d 旧 token 未追加 execution', count('execution_reviews', sid2) == 1)

        # ---------- HTTP#8-9 full import 带 execution → 漂移拒绝 ----------
        st, res = http(base + '/api/import/preview',
                       full_payload([full_sec('600002', one_liner='第二版逻辑',
                                              with_execution=True)]))
        step('HTTP#7 full(带 execution) preview → 200', st == 200, 'status=%s' % st)
        dtok = res.get('token')
        server.add_execution_tx(sid2, dict(EXEC_BODY, execution_view='暂缓执行'))
        st, res = http(base + '/api/import/commit',
                       {'token': dtok, 'confirmed_status_changes': []})
        err = str(res.get('error') or '')
        step('HTTP#8 preview 后 execution_latest 改变 → 拒绝 400', st == 400, 'status=%s' % st)
        step('HTTP#8b 专属文案正确',
             '动态执行判断自预览后已发生变化，请重新解析预览。' in err,
             'error=%s' % err[:56].replace('\n', '|'))
        step('HTTP#9 research 未被写入（无半完成状态）',
             max_version('research', sid2) == 1,
             'research max=%s' % max_version('research', sid2))

        # ---------- HTTP#10 full import 不带 execution → 不被无关阻断 ----------
        st, res = http(base + '/api/import/preview',
                       full_payload([full_sec('600002', one_liner='第三版逻辑',
                                              plan={'no_chase_price': 13.5})]))
        step('HTTP#9b full(不带 execution) preview → 200', st == 200, 'status=%s' % st)
        ntok = res.get('token')
        # preview 之后：仅 execution_latest 变化（与本次导入无关）
        server.add_execution_tx(sid2, dict(EXEC_BODY, execution_view='继续观察'))
        st, res = http(base + '/api/import/commit',
                       {'token': ntok, 'confirmed_status_changes': []})
        step('HTTP#10 仅 execution 变化不阻断 research / plan 导入 → 200',
             st == 200, 'status=%s err=%s' % (st, str(res.get('error') or '')[:40]))
        step('HTTP#10b research 已写入第 2 版', max_version('research', sid2) == 2,
             'research max=%s' % max_version('research', sid2))
        step('HTTP#10c trade_plan 已写入第 2 版', max_version('trade_plans', sid2) == 2,
             'plan max=%s' % max_version('trade_plans', sid2))

        # ---------- HTTP#11 失败释放 in_flight → 同 token 可重试 ----------
        conn = server.get_db()
        try:
            conn.execute("UPDATE securities SET status='等价格' WHERE id=?", (sid2,))
            conn.commit()
        finally:
            conn.close()
        sec = full_sec('600002', one_liner='第四版逻辑')
        sec['status'] = '可交易'
        st, res = http(base + '/api/import/preview', full_payload([sec]))
        step('HTTP#11 preview 提示需确认状态变化', st == 200 and bool(
            (res['securities'][0].get('status_change') or {}).get('requires_confirm')),
            'status=%s' % st)
        rtok = res['token']
        st, res = http(base + '/api/import/commit',
                       {'token': rtok, 'confirmed_status_changes': []})
        step('HTTP#11b 未确认 → 400', st == 400, 'status=%s' % st)
        with server._IMPORT_PREVIEW_LOCK:
            entry = server._IMPORT_PREVIEW_CACHE.get(rtok)
        step('HTTP#11c 失败后 in_flight 已释放', entry is not None
             and entry.get('in_flight') is False,
             'in_flight=%r' % (entry.get('in_flight') if entry else None))
        st, res = http(base + '/api/import/commit',
                       {'token': rtok, 'confirmed_status_changes': [0]})
        step('HTTP#11d 同一 token 修正后重试成功 → 200', st == 200, 'status=%s' % st)

        # ---------- HTTP#12 成功后一次性失效 ----------
        st, res = http(base + '/api/import/execution/preview', exec_payload('600002'))
        step('HTTP#12 preview → 200', st == 200, 'status=%s' % st)
        otok = res['token']
        st, res = http(base + '/api/import/execution/commit', {'token': otok})
        step('HTTP#12 首次 commit → 200', st == 200, 'status=%s' % st)
        st, res = http(base + '/api/import/execution/commit', {'token': otok})
        step('HTTP#12b 同 token 复用 → 400', st == 400, 'status=%s' % st)
        st, res = http(base + '/api/import/execution/commit', {'token': '  %s  ' % otok})
        step('HTTP#12c 前后加空格仍 → 400', st == 400, 'status=%s' % st)

        # ---------- HTTP#13 数据库锁的 HTTP 语义 ----------
        st, res = http(base + '/api/import/execution/preview', exec_payload('600002'))
        busy_tok = res['token']
        st, res = http(base + '/api/import/execution/preview', exec_payload('600002'))
        other_tok = res['token']

        def _faulty(msg):
            class _F(sqlite3.Connection):
                def execute(self, sql, *a, **k):
                    if str(sql).strip().upper().startswith('BEGIN'):
                        raise sqlite3.OperationalError(msg)
                    return sqlite3.Connection.execute(self, sql, *a, **k)

            def _open():
                c = sqlite3.connect(db_path, timeout=10, factory=_F)
                c.row_factory = sqlite3.Row
                return c
            return _open

        server.get_db = _faulty('database is locked')
        st, res = http(base + '/api/import/execution/commit', {'token': busy_tok})
        step('HTTP#13 database is locked → 409', st == 409, 'status=%s' % st)
        step('HTTP#13b 受控冲突文案',
             '数据库正在处理另一项写入，请稍后重试。' in str(res.get('error') or ''),
             repr(str(res.get('error'))[:36]))

        server.get_db = _faulty('no such table: bogus_table')
        st, res = http(base + '/api/import/execution/commit', {'token': other_tok})
        step('HTTP#13c no such table → 500（不伪装成 4xx）', st == 500, 'status=%s' % st)

        server.get_db = _normal
    finally:
        srv.shutdown()

    print('\n' + '=' * 58)
    print('v1.0.9 HTTP 端到端冒烟: PASS %d / FAIL %d' % (PASS, FAIL))
    print('=' * 58)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
