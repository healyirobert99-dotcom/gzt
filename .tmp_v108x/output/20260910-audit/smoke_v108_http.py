# -*- coding: utf-8 -*-
"""v1.0.8 导入完整性封板 —— 真实 HTTP 端到端冒烟脚本（审计证据）。

与 tests/test_v108.py 的区别：
  test_v108.py 在函数级直接调用 preview_import_full / commit_import_full；
  本脚本启动真实 HTTP 服务（127.0.0.1，临时端口 + 临时数据库），
  通过 POST /api/import/preview、POST /api/import/commit 走完整网络链路，
  用于证明"两段式导入"在真实交付形态下同样成立。

运行：
    python output/20260910-audit/smoke_v108_http.py

结果可复现：脚本自带随机端口与临时库，不触碰 data/workbench.db。
"""

import os
import sys
import json
import base64
import time
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
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw}


def payload():
    return {
        'format': 'ah-workbench-import',
        'format_version': '1.0',
        'generated_at': '2026-09-11',
        # 恶意声明：即便客户端声称已确认，preview 也必须返回未确认
        'status_change_confirmed': True,
        'securities': [{
            'identity': {'exchange': 'SZ', 'code': '000001', 'name': '冒烟标的'},
            'status': '等价格',
            'research': {
                'one_liner': '冒烟测试用一句话逻辑',
                'core_validations': [
                    {'content': '冒烟验证项', 'status': '跟踪中'}],
                'wall_conditions': [
                    {'content': '冒烟危墙条件', 'triggered': False}],
                'research_date': '2026-09-11',
                'change_note': '冒烟',
            },
            'trade_plan': {
                'first_zone_low': 10.0, 'first_zone_high': 11.0,
                'change_note': '冒烟初始计划',
            },
        }],
    }


def main():
    fd, db_path = tempfile.mkstemp(suffix='.db', prefix='wb-smoke108-')
    os.close(fd)
    server.init_db(seed=False, db_path=db_path)

    def _open():
        c = sqlite3.connect(db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    server.get_db = _open
    with server._IMPORT_PREVIEW_LOCK:
        server._IMPORT_PREVIEW_CACHE.clear()

    srv = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    srv.daemon_threads = True
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = 'http://127.0.0.1:%d' % port
    print('冒烟服务已启动: %s（临时库 %s）' % (base, os.path.basename(db_path)))

    try:
        # --- 1) 未 preview 直接 commit → 拒绝
        st, res = http(base + '/api/import/commit', {'token': '', 'confirmed_status_changes': []})
        step('HTTP#1 未 preview 直接 commit → 400', st == 400, 'status=%s' % st)

        # --- 2) 手工构造 base64(JSON) token → 拒绝
        fake = base64.b64encode(json.dumps(payload()).encode('utf-8')).decode('ascii')
        st, res = http(base + '/api/import/commit', {'token': fake, 'confirmed_status_changes': []})
        step('HTTP#2 手工 base64 token → 400', st == 400,
             'status=%s msg=%s' % (st, str(res.get('error'))[:46]))

        # --- 3) 真实 preview
        st, res = http(base + '/api/import/preview', payload())
        step('HTTP#3 preview → 200', st == 200, 'status=%s' % st)
        token = res.get('token')
        step('HTTP#3b token 非空且非 base64(JSON)',
             bool(token) and token != fake, 'token=%s' % (str(token)[:16] + '…'))
        sc = (res.get('securities') or [{}])[0].get('status_change') or {}
        step('HTTP#3c 导入 JSON 自带 status_change_confirmed=true → 初次仍为 False',
             sc.get('change_confirmed') is False, 'change_confirmed=%r' % sc.get('change_confirmed'))
        step('HTTP#3d preview 未写库（库内 securities 仍为 0）',
             _count(db_path) == 0, 'securities=%d' % _count(db_path))

        # --- 4) 用真 token commit → 成功
        st, res = http(base + '/api/import/commit',
                       {'token': token, 'confirmed_status_changes': []})
        step('HTTP#4 真 token commit → 200', st == 200,
             'status=%s created=%s' % (st, res.get('created_count')))
        step('HTTP#4b 库内已创建 1 只', _count(db_path) == 1, 'securities=%d' % _count(db_path))

        # --- 5) 同一 token 再次使用 → 拒绝（一次性）
        st, res = http(base + '/api/import/commit',
                       {'token': token, 'confirmed_status_changes': []})
        step('HTTP#5 token 复用 → 400', st == 400, 'status=%s' % st)

        # --- 6) 真实预览后过期 → 拒绝
        st, res = http(base + '/api/import/preview', payload())
        token2 = res.get('token')
        with server._IMPORT_PREVIEW_LOCK:
            entry = server._IMPORT_PREVIEW_CACHE.get(token2)
            if entry:
                entry['expires_at'] = time.time() - 1  # 人为置为已过期
        st, res = http(base + '/api/import/commit',
                       {'token': token2, 'confirmed_status_changes': []})
        step('HTTP#6 token 超时 → 400', st == 400, 'status=%s' % st)

        # --- 7) preview 之后库内发生变化 → 漂移拒绝
        st, res = http(base + '/api/import/preview', payload())
        token3 = res.get('token')
        # preview 之后，外部把该证券 status 改掉
        c = _open()
        c.execute("UPDATE securities SET status='可交易' WHERE code='000001'")
        c.commit()
        c.close()
        st, res = http(base + '/api/import/commit',
                       {'token': token3, 'confirmed_status_changes': []})
        err = str(res.get('error') or '')
        step('HTTP#7 preview 后 status 漂移 → 400', st == 400, 'status=%s' % st)
        step('HTTP#7b 错误文案要求重新解析预览',
             '重新解析预览' in err, 'error=%s' % err[:52])

        # --- 8) 同一批重复 exchange+code → preview 拒绝
        p = payload()
        p['securities'].append(json.loads(json.dumps(p['securities'][0])))
        st, res = http(base + '/api/import/preview', p)
        step('HTTP#8 同批重复 SZ+000001 → 400', st == 400, 'status=%s' % st)

        # --- 9) wall_conditions.triggered 非布尔 → preview 拒绝
        p = payload()
        p['securities'][0]['research']['wall_conditions'] = [
            {'content': '结构错误', 'triggered': 'false'}]
        st, res = http(base + '/api/import/preview', p)
        step('HTTP#9 triggered 为字符串 → 400', st == 400, 'status=%s' % st)
    finally:
        srv.shutdown()

    print('\n' + '=' * 58)
    print('HTTP 端到端冒烟: PASS %d / FAIL %d' % (PASS, FAIL))
    print('=' * 58)
    return 1 if FAIL else 0


def _count(db_path):
    c = sqlite3.connect(db_path)
    try:
        return c.execute('SELECT COUNT(*) FROM securities').fetchone()[0]
    finally:
        c.close()


if __name__ == '__main__':
    sys.exit(main())
