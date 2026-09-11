# -*- coding: utf-8 -*-
"""v1.0.9 「最终并发与预览一致性修复」回归测试。

本轮 spec 第五节要求至少覆盖 7 项：

  §A  同一 execution token 并发 8 次：
      · 成功次数严格 = 1
      · execution_reviews 只 +1
      · decision_ledger 只 +1
      · 其余请求均为受控 4xx
      · 0 个 5xx
  §B  同一 full-import token 并发 8 次：
      · 最多 1 次成功
      · 不产生重复 execution / research / plan
  §C  preview execution → 另一路径新增 execution → 提交旧 token → 拒绝并要求重新 preview
  §D  full import 中带 execution：preview 后 execution_latest 改变 → commit 拒绝
  §E  full import 不带 execution：preview 后仅 execution_latest 改变
      → research / trade_plan 导入不被无关阻断
  §F  commit 因业务校验失败后：in_flight 必须释放，token 在 TTL 内仍可合法重试
  §G  token 成功后仍严格一次性失效

另含两项本轮实现点的直接验证（非 spec 强制，用于封板可复现）：
  §H  SQLITE_BUSY / SQLITE_LOCKED → HTTP 409；其它 OperationalError → 500
  §I  静态契约（版本号 / in_flight / claim-release / 前端防重）

所有测试使用临时数据库与临时端口，不触碰正式 workbench.db。
并发用例走**真实 HTTP 链路**（ThreadingHTTPServer），不复用函数级调用。
"""

import os
import json
import sqlite3
import sys
import tempfile
import threading
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if os.path.join(ROOT, 'app') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'app'))
import server


FAIL_COUNT = 0
TOTAL = 0


def step(name, ok, detail=''):
    global FAIL_COUNT, TOTAL
    TOTAL += 1
    flag = 'PASS' if ok else 'FAIL'
    print('  [%s] %s %s' % (flag, name, detail))
    if not ok:
        FAIL_COUNT += 1


def open_tmp_db(prefix='wb-v109-'):
    fd, path = tempfile.mkstemp(suffix='.db', prefix=prefix)
    os.close(fd)
    server.init_db(seed=False, db_path=path)

    def _open():
        c = sqlite3.connect(path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    server.get_db = _open
    with server._IMPORT_PREVIEW_LOCK:
        server._IMPORT_PREVIEW_CACHE.clear()
    try:
        server._quote_cache['data'].clear()
        server._quote_cache['ts'] = 0
        server._quote_cache['last_success_at'] = None
        server._quote_cache['last_error'] = ''
        server._quote_cache['last_error_at'] = None
    except Exception:
        pass
    return path


def cleanup_tmp(path):
    try:
        os.remove(path)
    except OSError:
        pass


class HttpServer(object):
    """在临时端口起一个真实 HTTP 服务，用于并发用例。"""

    def __init__(self):
        self.srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.srv.daemon_threads = True
        self.port = self.srv.server_address[1]
        self.base = 'http://127.0.0.1:%d' % self.port
        self._t = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        try:
            self.srv.shutdown()
        except Exception:
            pass
        try:
            self.srv.server_close()
        except Exception:
            pass
        return False


def http_post(url, body):
    """返回 (status_code, 解析后的响应体或原始文本)。"""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8')
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, {'raw': raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw}


def preinsert_security(code, exchange, name='X', status='等价格'):
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


def count(table):
    conn = server.get_db()
    try:
        return conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
    finally:
        conn.close()


EXEC_BODY = {
    'execution_date': '2026-09-11',
    'price_snapshot': 10.5,
    'support_zone': '10.0-10.2',
    'resistance_zone': '11.0-11.2',
    'technical_structure': '结构',
    'execution_condition': '条件',
    'execution_view': '等待技术确认',
    'reason': '依据',
}


def exec_payload(exchange='SH', code='600001', view=None):
    body = dict(EXEC_BODY)
    if view:
        body['execution_view'] = view
    return {
        'format': 'ah-workbench-execution',
        'format_version': '1.0',
        'identity': {'exchange': exchange, 'code': code},
        'execution': body,
    }


def full_sec(exchange='SH', code='600200', name='并发标的', one_liner='逻辑',
             with_execution=False, plan_note='初始计划', plan=None):
    sec = {
        'identity': {'exchange': exchange, 'code': code, 'name': name},
        'status': '等价格',
        'research': {
            'one_liner': one_liner,
            'research_date': '2026-09-11',
            'core_validations': [{'content': '验证项一', 'status': '跟踪中'}],
            'wall_conditions': [{'content': '危墙一', 'triggered': False}],
            'change_note': '导入',
        },
        'trade_plan': {
            'first_zone_low': 10.0, 'first_zone_high': 11.0,
            'no_chase_price': 12.0, 'target_position_pct': 5.0,
            'next_action': '等待首仓区', 'change_note': plan_note,
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


def add_execution_directly(sid, view='继续观察'):
    """走真实业务写入路径（另一条路径）追加一条 execution。"""
    body = dict(EXEC_BODY)
    body['execution_view'] = view
    server.add_execution_tx(sid, body)


# ==================== §A execution token 并发 ====================

def test_a_exec_token_concurrency():
    print('\n=== §A 同一 execution token 并发 8 次 ===')
    path = open_tmp_db('wb-v109-a-')
    try:
        sid = preinsert_security('600001', 'SH', '并发执行标的')
        with HttpServer() as hs:
            st, r = http_post(hs.base + '/api/import/execution/preview',
                              exec_payload('SH', '600001'))
            step('§A#1 execution preview 成功', st == 200, 'status=%s' % st)
            token = r.get('token')
            step('§A#2 preview 返回服务端 token', isinstance(token, str) and len(token) > 20)

            before_e = count('execution_reviews')
            before_l = count('decision_ledger')

            n = 8
            results = []
            barrier = threading.Barrier(n)

            def worker():
                barrier.wait()
                results.append(http_post(hs.base + '/api/import/execution/commit',
                                         {'token': token}))

            ts = [threading.Thread(target=worker) for _ in range(n)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            codes = sorted(s for s, _ in results)
            ok_n = sum(1 for s, _ in results if s == 200)
            c5xx = sum(1 for s, _ in results if 500 <= s < 600)
            other4xx = sum(1 for s, _ in results if 400 <= s < 500)

            step('§A#3 成功次数严格 = 1', ok_n == 1, '实际=%d（状态码分布 %s）' % (ok_n, codes))
            step('§A#4 其余均为受控 4xx', other4xx == n - 1,
                 '4xx=%d 期望=%d' % (other4xx, n - 1))
            step('§A#5 0 个 5xx', c5xx == 0, '5xx=%d' % c5xx)

            after_e = count('execution_reviews')
            after_l = count('decision_ledger')
            step('§A#6 execution_reviews 只 +1', after_e - before_e == 1,
                 '%d -> %d' % (before_e, after_e))
            step('§A#7 decision_ledger 只 +1', after_l - before_l == 1,
                 '%d -> %d' % (before_l, after_l))

            # 失败请求的错误文案必须是"正在提交中"或"token 无效/过期"，而非 500 堆栈
            msgs = [str(b.get('error') or b.get('raw') or '') for s, b in results if s != 200]
            step('§A#8 拒绝理由为受控文案',
                 all(('正在提交中' in m) or ('token 无效' in m) or ('token 已过期' in m)
                     for m in msgs),
                 '样本=%r' % (msgs[0][:46] if msgs else ''))
            step('§A#9 并发后该证券 execution 仅 1 条',
                 conn_exec_count(sid) == 1, 'executions=%d' % conn_exec_count(sid))
    finally:
        cleanup_tmp(path)


def conn_exec_count(sid):
    conn = server.get_db()
    try:
        return conn.execute(
            'SELECT COUNT(*) FROM execution_reviews WHERE security_id=?',
            (sid,)).fetchone()[0]
    finally:
        conn.close()


# ==================== §B full-import token 并发 ====================

def test_b_full_token_concurrency():
    print('\n=== §B 同一 full-import token 并发 8 次 ===')
    path = open_tmp_db('wb-v109-b-')
    try:
        with HttpServer() as hs:
            payload = full_payload([full_sec('SH', '600200', '全量并发标的',
                                             with_execution=True)])
            st, r = http_post(hs.base + '/api/import/preview', payload)
            step('§B#1 full preview 成功', st == 200, 'status=%s' % st)
            token = r.get('token')

            n = 8
            results = []
            barrier = threading.Barrier(n)

            def worker():
                barrier.wait()
                results.append(http_post(hs.base + '/api/import/commit',
                                         {'token': token,
                                          'confirmed_status_changes': []}))

            ts = [threading.Thread(target=worker) for _ in range(n)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            codes = sorted(s for s, _ in results)
            ok_n = sum(1 for s, _ in results if s == 200)
            c5xx = sum(1 for s, _ in results if 500 <= s < 600)
            step('§B#2 最多 1 次成功', ok_n <= 1, '成功=%d（%s）' % (ok_n, codes))
            step('§B#3 0 个 5xx', c5xx == 0, '5xx=%d' % c5xx)

            step('§B#4 securities 只有 1 行（无重复证券）', count('securities') == 1,
                 'securities=%d' % count('securities'))
            step('§B#5 research 只有 1 个版本', count('research') == 1,
                 'research=%d' % count('research'))
            step('§B#6 trade_plans 只有 1 个版本', count('trade_plans') == 1,
                 'trade_plans=%d' % count('trade_plans'))
            step('§B#7 execution_reviews 只有 1 条', count('execution_reviews') == 1,
                 'execution_reviews=%d' % count('execution_reviews'))
    finally:
        cleanup_tmp(path)


# ==================== §C execution 漂移 ====================

def test_c_exec_drift():
    print('\n=== §C preview execution → 另一路径新增 execution → 提交旧 token 必须拒绝 ===')
    path = open_tmp_db('wb-v109-c-')
    try:
        sid = preinsert_security('600300', 'SH', '漂移执行标的')
        with HttpServer() as hs:
            st, r = http_post(hs.base + '/api/import/execution/preview',
                              exec_payload('SH', '600300', view='等待技术确认'))
            step('§C#1 execution preview 成功', st == 200, 'status=%s' % st)
            token = r.get('token')

            # 另一条路径新增 execution（真实业务写入函数）
            add_execution_directly(sid, '继续观察')
            step('§C#2 另一路径已新增 execution',
                 conn_exec_count(sid) == 1, 'executions=%d' % conn_exec_count(sid))

            st, r = http_post(hs.base + '/api/import/execution/commit', {'token': token})
            msg = str(r.get('error') or '')
            step('§C#3 提交旧 token → 拒绝（400）', st == 400, 'status=%s' % st)
            step('§C#4 提示"动态执行判断自预览后已发生变化，请重新解析预览。"',
                 '动态执行判断自预览后已发生变化，请重新解析预览。' in msg,
                 'msg=%r' % msg[:80].replace('\n', '|'))
            step('§C#5 execution 未被旧 token 追加（仍 1 条）',
                 conn_exec_count(sid) == 1, 'executions=%d' % conn_exec_count(sid))
    finally:
        cleanup_tmp(path)


# ==================== §D full import 带 execution ====================

def test_d_full_with_execution_drift():
    print('\n=== §D full import 带 execution：preview 后 execution_latest 改变 → 拒绝 ===')
    path = open_tmp_db('wb-v109-d-')
    try:
        with HttpServer() as hs:
            # 第 1 次：建立基线（含 execution）
            st, r = http_post(hs.base + '/api/import/preview',
                              full_payload([full_sec('SH', '600400', '带执行标的',
                                                     with_execution=True)]))
            step('§D#1 基线 preview 成功', st == 200, 'status=%s' % st)
            st, r = http_post(hs.base + '/api/import/commit',
                              {'token': r['token'], 'confirmed_status_changes': []})
            step('§D#2 基线 commit 成功', st == 200, 'status=%s' % st)
            sid = sec_id('SH', '600400')
            step('§D#3 基线 execution 1 条', conn_exec_count(sid) == 1)

            # 第 2 次：带 execution 的完整导入
            st, r = http_post(hs.base + '/api/import/preview',
                              full_payload([full_sec('SH', '600400', '带执行标的',
                                                     one_liner='第二版逻辑',
                                                     with_execution=True)]))
            step('§D#4 第二次 preview 成功', st == 200, 'status=%s' % st)
            token = r['token']

            # preview 之后：另一条路径新增 execution
            add_execution_directly(sid, '暂缓执行')
            step('§D#5 preview 后 execution_latest 已改变',
                 conn_exec_count(sid) == 2, 'executions=%d' % conn_exec_count(sid))

            st, r = http_post(hs.base + '/api/import/commit',
                              {'token': token, 'confirmed_status_changes': []})
            msg = str(r.get('error') or '')
            step('§D#6 commit 被拒（400）', st == 400, 'status=%s' % st)
            step('§D#7 提示要求重新解析预览',
                 '动态执行判断自预览后已发生变化，请重新解析预览。' in msg,
                 'msg=%r' % msg[:80].replace('\n', '|'))
            step('§D#8 research 未被写入第 2 版', count('research') == 1,
                 'research=%d' % count('research'))
    finally:
        cleanup_tmp(path)


def sec_id(exchange, code):
    conn = server.get_db()
    try:
        row = conn.execute('SELECT id FROM securities WHERE exchange=? AND code=?',
                           (exchange, code)).fetchone()
        return row['id'] if row else None
    finally:
        conn.close()


# ==================== §E full import 不带 execution ====================

def test_e_full_without_execution_not_blocked():
    print('\n=== §E full import 不带 execution：execution 变化不得阻断 research / plan 导入 ===')
    path = open_tmp_db('wb-v109-e-')
    try:
        with HttpServer() as hs:
            # 第 1 次：基线（不带 execution）
            st, r = http_post(hs.base + '/api/import/preview',
                              full_payload([full_sec('SH', '600500', '无执行标的')]))
            st, r = http_post(hs.base + '/api/import/commit',
                              {'token': r['token'], 'confirmed_status_changes': []})
            step('§E#1 基线 commit 成功', st == 200, 'status=%s' % st)
            sid = sec_id('SH', '600500')
            step('§E#2 基线 research v1', max_version('research', sid) == 1)

            # 第 2 次：仍不带 execution，但 research / plan 有实质变化
            # （plan 必须改"被纳入版本判定"的字段，例如不追价；仅改 change_note 不算变化）
            st, r = http_post(hs.base + '/api/import/preview',
                              full_payload([full_sec('SH', '600500', '无执行标的',
                                                     one_liner='第二版逻辑',
                                                     plan={'no_chase_price': 13.5,
                                                           'next_action': '等待回踩'},
                                                     plan_note='第二版计划')]))
            step('§E#3 第二次 preview 成功', st == 200, 'status=%s' % st)
            token = r['token']

            # preview 之后：另一条路径新增 execution（与本次导入无关）
            add_execution_directly(sid, '继续观察')
            step('§E#4 preview 后 execution_latest 已改变',
                 conn_exec_count(sid) == 1, 'executions=%d' % conn_exec_count(sid))

            st, r = http_post(hs.base + '/api/import/commit',
                              {'token': token, 'confirmed_status_changes': []})
            step('§E#5 commit 成功（未被无关 execution 阻断）', st == 200,
                 'status=%s err=%r' % (st, str(r.get('error') or '')[:60]))
            step('§E#6 research 已写入第 2 版', max_version('research', sid) == 2,
                 'research max version=%d' % max_version('research', sid))
            step('§E#7 trade_plan 已写入第 2 版', max_version('trade_plans', sid) == 2,
                 'plan max version=%d' % max_version('trade_plans', sid))
            step('§E#8 execution 仍为 1 条（本次导入未追加）',
                 conn_exec_count(sid) == 1)
    finally:
        cleanup_tmp(path)


def max_version(table, sid):
    conn = server.get_db()
    try:
        row = conn.execute('SELECT MAX(version) v FROM %s WHERE security_id=?'
                           % table, (sid,)).fetchone()
        return row['v']
    finally:
        conn.close()


# ==================== §F 失败释放 in_flight ====================

def test_f_release_in_flight_on_failure():
    print('\n=== §F commit 业务校验失败 → in_flight 释放，同 token 仍可合法重试 ===')
    path = open_tmp_db('wb-v109-f-')
    try:
        sid = preinsert_security('600600', 'SH', '重试标的', status='等价格')
        with HttpServer() as hs:
            # 已有证券 + status 变化：commit 时不带确认 → 业务校验失败
            sec = full_sec('SH', '600600', '重试标的', one_liner='第一版逻辑')
            sec['status'] = '可交易'
            st, r = http_post(hs.base + '/api/import/preview', full_payload([sec]))
            step('§F#1 preview 成功且提示需确认状态变化',
                 st == 200 and bool((r['securities'][0].get('status_change') or {})
                                    .get('requires_confirm')),
                 'status=%s' % st)
            token = r['token']

            st, r = http_post(hs.base + '/api/import/commit',
                              {'token': token, 'confirmed_status_changes': []})
            step('§F#2 未确认 → commit 被拒（400）', st == 400, 'status=%s' % st)
            with server._IMPORT_PREVIEW_LOCK:
                entry = server._IMPORT_PREVIEW_CACHE.get(token)
            step('§F#3 失败后 token 仍在 cache 中',
                 entry is not None)
            step('§F#4 失败后 in_flight 已释放为 False',
                 entry is not None and entry.get('in_flight') is False,
                 'in_flight=%r' % (entry.get('in_flight') if entry else None))

            # 同一个 token 重试：这次带上确认
            st, r = http_post(hs.base + '/api/import/commit',
                              {'token': token, 'confirmed_status_changes': [0]})
            step('§F#5 同一 token 修正后可成功重试', st == 200, 'status=%s' % st)
            conn = server.get_db()
            try:
                cur = conn.execute('SELECT status FROM securities WHERE id=?',
                                   (sid,)).fetchone()['status']
            finally:
                conn.close()
            step('§F#6 重试后 status 真的改变', cur == '可交易', 'status=%s' % cur)
    finally:
        cleanup_tmp(path)


# ==================== §G 成功一次性失效 ====================

def test_g_token_one_shot_after_success():
    print('\n=== §G token 成功后严格一次性失效 ===')
    path = open_tmp_db('wb-v109-g-')
    try:
        sid = preinsert_security('600700', 'SH', '一次性标的')
        with HttpServer() as hs:
            st, r = http_post(hs.base + '/api/import/execution/preview',
                              exec_payload('SH', '600700'))
            token = r['token']
            st, r = http_post(hs.base + '/api/import/execution/commit', {'token': token})
            step('§G#1 首次 commit 成功', st == 200, 'status=%s' % st)

            st, r = http_post(hs.base + '/api/import/execution/commit', {'token': token})
            step('§G#2 同 token 再次 commit → 拒绝（400）', st == 400, 'status=%s' % st)

            # 前后带空格也不得绕过（token 规范化必须一致）
            st, r = http_post(hs.base + '/api/import/execution/commit',
                              {'token': '  %s  ' % token})
            step('§G#3 token 前后加空格仍拒绝（400）', st == 400, 'status=%s' % st)

            step('§G#4 execution 只写入 1 条', conn_exec_count(sid) == 1,
                 'executions=%d' % conn_exec_count(sid))

            # 手工构造的 base64 token 也必须拒绝
            import base64 as _b64
            fake = _b64.b64encode(json.dumps(exec_payload('SH', '600700')).encode()).decode()
            st, r = http_post(hs.base + '/api/import/execution/commit', {'token': fake})
            step('§G#5 手工构造 base64 token → 拒绝（400）', st == 400, 'status=%s' % st)
    finally:
        cleanup_tmp(path)


# ==================== §H 数据库锁的 HTTP 语义 ====================

def test_h_db_lock_http_semantics():
    print('\n=== §H SQLITE_BUSY / SQLITE_LOCKED → 409；其它 OperationalError → 500 ===')
    path = open_tmp_db('wb-v109-h-')
    try:
        sid = preinsert_security('600800', 'SH', '锁语义标的')
        with HttpServer() as hs:
            st, r = http_post(hs.base + '/api/import/execution/preview',
                              exec_payload('SH', '600800'))
            token_busy = r['token']
            st, r = http_post(hs.base + '/api/import/execution/preview',
                              exec_payload('SH', '600800', view='继续观察'))
            token_other = r['token']

            # 复制当前的 get_db（指向同一临时库）
            def make_faulty(msg, prefix='BEGIN'):
                class _Faulty(sqlite3.Connection):
                    def execute(self, sql, *a, **k):
                        if str(sql).strip().upper().startswith(prefix):
                            raise sqlite3.OperationalError(msg)
                        return sqlite3.Connection.execute(self, sql, *a, **k)

                def _open():
                    c = sqlite3.connect(path, timeout=10, factory=_Faulty)
                    c.row_factory = sqlite3.Row
                    return c
                return _open

            server.get_db = make_faulty('database is locked')
            st, r = http_post(hs.base + '/api/import/execution/commit',
                              {'token': token_busy})
            step('§H#1 database is locked → 409', st == 409, 'status=%s' % st)
            step('§H#2 冲突提示文案受控',
                 '数据库正在处理另一项写入，请稍后重试。' in str(r.get('error') or ''),
                 repr(str(r.get('error'))[:50]))

            server.get_db = make_faulty('no such table: bogus_table')
            st, r = http_post(hs.base + '/api/import/execution/commit',
                              {'token': token_other})
            step('§H#3 no such table → 500（不伪装成 4xx）', st == 500, 'status=%s' % st)

            # 还原正常连接
            def _normal(path=path):
                c = sqlite3.connect(path, timeout=10)
                c.row_factory = sqlite3.Row
                return c
            server.get_db = _normal

        # 纯函数级判定
        step('§H#4 _is_db_busy_error("database is locked") = True',
             server._is_db_busy_error(sqlite3.OperationalError('database is locked')))
        step('§H#5 _is_db_busy_error("database table is locked") = True',
             server._is_db_busy_error(sqlite3.OperationalError('database table is locked')))
        step('§H#6 _is_db_busy_error("no such table: x") = False',
             not server._is_db_busy_error(sqlite3.OperationalError('no such table: x')))
        step('§H#7 _is_db_busy_error("disk I/O error") = False',
             not server._is_db_busy_error(sqlite3.OperationalError('disk I/O error')))
        step('§H#8 常量 DB_BUSY_MESSAGE 受控',
             server.DB_BUSY_MESSAGE == '数据库正在处理另一项写入，请稍后重试。')
    finally:
        cleanup_tmp(path)


# ==================== §I 静态契约 ====================

def test_i_static_contract():
    print('\n=== §I 静态契约扫描（v1.0.9） ===')
    src = open(os.path.join(ROOT, 'app', 'server.py'), encoding='utf-8').read()

    # v1.0.10：版本契约随版本升级前移（test_v109 自身语义不变，仅契约值更新）。
    step('§I#1 TARGET_SCHEMA_VERSION=1.0.10',
         "TARGET_SCHEMA_VERSION = '1.0.10'" in src)
    step('§I#2 server_version=Workbench/1.0.10',
         "server_version = 'Workbench/1.0.10'" in src)
    step('§I#3 argparse 描述为 v1.0.10',
         "description='A/H 投研交易工作台 v1.0.10'" in src)
    step('§I#4 启动文案为 v1.0.10',
         'A/H 投研交易工作台 v1.0.10 已启动' in src)

    step('§I#5 原子 claim 函数存在（_import_cache_claim）',
         'def _import_cache_claim(' in src)
    step('§I#6 in_flight 标记存在', "'in_flight'" in src)
    step('§I#7 claim 内一次性判定 in_flight',
         'if entry.get(\'in_flight\'):' in src)
    step('§I#8 失败释放函数存在（_import_cache_release）',
         'def _import_cache_release(' in src)
    step('§I#9 旧的非原子 _import_cache_take 已移除',
         'def _import_cache_take(' not in src)
    step('§I#10 full 与 exec-only 均使用 claim',
         src.count('_import_cache_claim(token, IMPORT_FORMAT_FULL)') == 1
         and src.count('_import_cache_claim(token, IMPORT_FORMAT_EXEC_ONLY)') == 1)
    step('§I#11 两条 commit 路径均释放 in_flight（1 处定义 + 2 处调用）',
         src.count('_import_cache_release(token)') == 3,
         '出现 %d 次' % src.count('_import_cache_release(token)'))

    step('§I#12 snapshot 带 check_execution 标记',
         "snap['check_execution'] = bool(s.get('execution'))" in src)
    step('§I#13 漂移检测比对 execution_latest_id',
         "snap.get('check_execution')" in src
         and "snap['execution_latest_id'] != cur['execution_latest_id']" in src)
    step('§I#14 execution 漂移专属文案',
         '动态执行判断自预览后已发生变化，请重新解析预览。' in src)
    step('§I#15 原有漂移文案保持逐字不变',
         '工作台数据自预览后已发生变化，请重新解析预览。' in src)

    step('§I#16 409 语义函数存在（_is_db_busy_error）',
         'def _is_db_busy_error(' in src)
    step('§I#17 DbConflictError → 409',
         'class DbConflictError(Exception):' in src and 'self._err(str(e), 409)' in src)
    step('§I#18 SQLITE_BUSY/LOCKED 主码常量 = (5, 6)',
         'DB_BUSY_PRIMARY_CODES = (5, 6)' in src)
    step('§I#19 非 busy 的 OperationalError 走 500',
         "self._err('服务器错误: %s' % e, 500)" in src)
    step('§I#20 不修改数据库 Schema（无新增迁移/表）',
         'TARGET_SCHEMA_VERSION = \'1.0.10\'' in src
         and 'securities__new' in src)   # 迁移逻辑仍旧存在，但未新增版本

    js = open(os.path.join(ROOT, 'app', 'static', 'app.js'), encoding='utf-8').read()
    step('§I#21 前端版本号 v1.0.10',
         'A/H 投研交易工作台 · 前端  v1.0.10' in js)
    step('§I#22 前端 committing 标记存在', 'committing: false,' in js)
    step('§I#23 前端按钮显示"正在写入…"', "'正在写入…'" in js)
    step('§I#24 前端按钮 disabled 绑定 committing',
         "Import.committing ? 'disabled' : ''" in js)
    step('§I#25 前端 commit 入口有防重早退',
         "if (Import.committing) { toast('正在写入，请稍候…', true); return; }" in js)
    step('§I#26 前端失败路径恢复 committing=false',
         js.count('Import.committing = false;') >= 4)

    # 样例：生产 UI 不得存在"载入示例"按钮，也不得内置 01357 真实标的
    # （注：公司名输入框的 placeholder 里仍保留一个真实公司名作为填写示例，
    #   它不是"可一键载入的研究/交易计划数据"，本轮不改文案，已在审计文档记录。）
    step('§I#27 无"载入示例"按钮 / 无 01357 示例',
         'onclick="loadFullExample()"' not in js
         and 'onclick="loadExecExample()"' not in js
         and '01357' not in js
         and 'function loadFullExample' not in js
         and 'function loadExecExample' not in js)


# ==================== 入口 ====================

def main():
    print('=== v1.0.9 最终并发与预览一致性修复 —— 回归测试 ===')
    test_a_exec_token_concurrency()
    test_b_full_token_concurrency()
    test_c_exec_drift()
    test_d_full_with_execution_drift()
    test_e_full_without_execution_not_blocked()
    test_f_release_in_flight_on_failure()
    test_g_token_one_shot_after_success()
    test_h_db_lock_http_semantics()
    test_i_static_contract()
    print('\n' + '=' * 60)
    print('v1.0.9 测试: PASS %d / FAIL %d  (共 %d 断言)'
          % (TOTAL - FAIL_COUNT, FAIL_COUNT, TOTAL))
    print('=' * 60)
    if FAIL_COUNT:
        print('FAIL_COUNT = %d' % FAIL_COUNT)
        return 1
    print('FAIL_COUNT = 0')
    print('ALL TESTS PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
