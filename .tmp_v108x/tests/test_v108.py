# -*- coding: utf-8 -*-
"""v1.0.8 「导入完整性封板修复」回归测试。

本轮 spec 第八节要求至少覆盖 14 项：

  §A#1  不调用 preview，直接 commit → 拒绝
  §A#2  手工构造 base64 token → 拒绝
  §A#3  token 成功 commit 后再次使用 → 拒绝
  §A#4  token 超时 → 拒绝
  §B#1  pasted JSON 自带 status_change_confirmed=true → 初次 preview 仍必须未确认
  §B#2  不勾选（confirmed_status_changes 为空）→ commit 拒绝
  §B#3  勾选后（confirmed_status_changes=[i]）→ commit 成功且 status 真的改变
  §C#1  preview 后 status 改变 → commit 拒绝并要求重新 preview
  §C#2  preview 后 research version 改变 → commit 拒绝
  §C#3  preview 后 trade_plan version 改变 → commit 拒绝
  §C#4  preview 后原本不存在的证券已出现 → commit 拒绝
  §D#1  同一批重复 exchange+code → preview 拒绝
  §E#1  core_validations 为字符串数组 → preview 拒绝
  §E#2  core_validations.status 非法 → preview 拒绝
  §E#3  core_validations 缺 content → preview 拒绝
  §E#4  wall_conditions 为字符串数组 → preview 拒绝
  §E#5  wall_conditions.triggered 非 boolean → preview 拒绝
  §E#6  wall_conditions 缺 content → preview 拒绝
  §F#1  name mismatch → preview 数据显式包含警告
  §F#2  name mismatch → 页面渲染包含警告（静态扫描 app.js）
  §F#3  name mismatch 不自动修改 name（commit 后库内 name 不变）
  §G    静态契约：token 非 base64 / 服务端 cache / TTL 常量 / 版本号
  §H    既有语义不回归（research/plan/execution 版本化 + trades 不变 + 原子性）

所有测试使用临时数据库，不触碰正式 workbench.db。
"""

import os, sys, json, base64, sqlite3, tempfile, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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


def open_tmp_db(prefix='wb-v108-'):
    fd, path = tempfile.mkstemp(suffix='.db', prefix=prefix)
    os.close(fd)
    server.init_db(seed=False, db_path=path)

    def _open():
        c = sqlite3.connect(path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    server.get_db = _open
    # v1.0.8：清空服务端 preview cache，避免测试互相污染
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


def base_full_payload(securities):
    return {
        'format': 'ah-workbench-import',
        'format_version': '1.0',
        'generated_at': '2026-09-11',
        'securities': securities,
    }


def sec_new(exchange='HK', code='00700', name='腾讯控股', status='等价格',
            one_liner='游戏+广告+云', plan=None, execution=None, extra=None):
    d = {
        'identity': {'exchange': exchange, 'code': code, 'name': name},
        'status': status,
        'research': {
            'research_pool': '核心池',
            'one_liner': one_liner,
            'positive_changes': '海外扩张',
            'core_validations': [{'content': '游戏流水同比', 'status': '跟踪中'}],
            'wall_conditions': [{'content': '广告增速转负', 'triggered': False}],
            'report_link': '',
            'research_date': '2026-09-11',
            'change_note': '首次深穿',
        },
    }
    if plan is not None:
        d['trade_plan'] = plan
    if execution is not None:
        d['execution'] = execution
    if extra:
        d.update(extra)
    return d


DEFAULT_PLAN = {
    'first_zone_low': 300.0, 'first_zone_high': 320.0,
    'add_zone_low': 280.0, 'add_zone_high': 290.0,
    'odds_zone_low': 260.0, 'odds_zone_high': 270.0,
    'no_chase_price': 360.0, 'target_position_pct': 5.0,
    'next_action': '等待首仓区', 'change_note': '初始计划',
}


def expect_reject(fn, label, must_contain=None):
    """断言 fn() 抛异常；可选要求错误文本包含某段。返回错误文本。"""
    try:
        fn()
    except Exception as e:
        msg = str(e)
        if must_contain is not None:
            ok = must_contain in msg
            step(label, ok, '' if ok else '错误文本未包含 %r，实际=%r' % (must_contain, msg[:120]))
        else:
            step(label, True)
        return msg
    step(label, False, '预期抛异常但正常返回')
    return ''


def expect_ok(fn, label):
    """断言 fn() 不抛异常，返回结果。"""
    try:
        r = fn()
        step(label, True)
        return r
    except Exception as e:
        step(label, False, '预期成功但抛异常：%s' % str(e)[:140])
        return None


# ==================== §A preview token 机制 ====================

def test_a_token_mechanism():
    print('\n=== §A preview token 机制（真正两段式） ===')
    path = open_tmp_db('wb-v108-a-')
    try:
        payload = base_full_payload([sec_new()])

        # §A#1 不 preview 直接 commit
        expect_reject(lambda: server.commit_import_full('whatever-not-previewed'),
                      '§A#1 未 preview 直接 commit → 拒绝',
                      must_contain='token 无效')

        # §A#2 手工构造 base64(JSON) token —— v1.0.7 的老做法
        fake = base64.b64encode(json.dumps({
            'kind': 'ah-workbench-import',
            'payload': payload,
            'validated': [],
        }, ensure_ascii=False).encode('utf-8')).decode('ascii')
        expect_reject(lambda: server.commit_import_full(fake),
                      '§A#2 手工构造 base64 token → 拒绝',
                      must_contain='token 无效')

        # token 本身不再是 base64(JSON)：合法 token 不应能 base64 解出 JSON
        prev = server.preview_import_full(payload)
        tok = prev['token']
        looks_like_b64json = False
        try:
            decoded = base64.b64decode(tok, validate=True).decode('utf-8')
            json.loads(decoded)
            looks_like_b64json = True
        except Exception:
            looks_like_b64json = False
        step('§A#2b token 不再是 base64(JSON)', not looks_like_b64json,
             'token 前缀=%r' % tok[:8])
        step('§A#2c preview 返回 token_ttl_seconds=300',
             prev.get('token_ttl_seconds') == 300,
             '实际=%r' % prev.get('token_ttl_seconds'))
        step('§A#2d token 存在于服务端 cache',
             tok in server._IMPORT_PREVIEW_CACHE)

        # §A#3 commit 成功后 token 立即失效，再次使用 → 拒绝
        res = expect_ok(lambda: server.commit_import_full(tok),
                        '§A#3a 首次 commit 成功')
        if res:
            step('§A#3b 首次 commit 创建 1 只',
                 res.get('created_count') == 1, 'created=%r' % res.get('created_count'))
        step('§A#3c commit 后 token 已从 cache 移除',
             tok not in server._IMPORT_PREVIEW_CACHE)
        expect_reject(lambda: server.commit_import_full(tok),
                      '§A#3d token 复用 → 拒绝',
                      must_contain='token 无效')

        # §A#4 token 超时 → 拒绝
        prev2 = server.preview_import_full(base_full_payload([
            sec_new(code='00001', exchange='HK', name='长和')]))
        tok2 = prev2['token']
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE[tok2]['expires_at'] = time.time() - 1
        expect_reject(lambda: server.commit_import_full(tok2),
                      '§A#4 token 超时 → 拒绝',
                      must_contain='已过期')
        step('§A#4b 超时 token 被清理',
             tok2 not in server._IMPORT_PREVIEW_CACHE)

        # 空 token / 非字符串 token
        expect_reject(lambda: server.commit_import_full(''),
                      '§A#5 空 token → 拒绝')
        expect_reject(lambda: server.commit_import_full(None),
                      '§A#6 None token → 拒绝')
        expect_reject(lambda: server.commit_import_full(12345),
                      '§A#7 非字符串 token → 拒绝')
    finally:
        cleanup_tmp(path)


# ==================== §B 状态确认不得来自导入 JSON ====================

def test_b_status_confirmation():
    print('\n=== §B 状态确认不得来自导入 JSON ===')
    path = open_tmp_db('wb-v108-b-')
    try:
        preinsert_security('00700', 'HK', name='腾讯控股', status='等价格')
        payload = base_full_payload([
            sec_new(status='可交易', extra={'status_change_confirmed': True}),
        ])

        # §B#1 粘贴 JSON 自带 status_change_confirmed=true → 初次 preview 仍未确认
        prev = server.preview_import_full(payload)
        sc = prev['securities'][0]['status_change']
        step('§B#1a status 变化被识别', sc['changed'] is True)
        step('§B#1b requires_confirm=True', sc['requires_confirm'] is True)
        step('§B#1c 初次 preview 的 change_confirmed 必须为 False',
             sc['change_confirmed'] is False,
             '实际=%r（粘贴 JSON 自带 true 也必须被忽略）' % sc['change_confirmed'])

        # §B#2 不勾选 → commit 拒绝
        expect_reject(lambda: server.commit_import_full(prev['token'], []),
                      '§B#2 未勾选状态变化 → commit 拒绝',
                      must_contain='状态变化未在预览中确认')

        # §B#2b 即使传其它下标也不行
        prev_b = server.preview_import_full(payload)
        expect_reject(lambda: server.commit_import_full(prev_b['token'], [5]),
                      '§B#2b 勾选了不存在的下标 → commit 拒绝',
                      must_contain='状态变化未在预览中确认')

        # §B#3 勾选后 commit 成功，status 确实改变
        prev2 = server.preview_import_full(payload)
        res = expect_ok(lambda: server.commit_import_full(prev2['token'], [0]),
                        '§B#3a 勾选后 commit 成功')
        if res:
            step('§B#3b status_changed_count=1',
                 res.get('status_changed_count') == 1,
                 '实际=%r' % res.get('status_changed_count'))
        conn = server.get_db()
        try:
            st = conn.execute(
                "SELECT status FROM securities WHERE exchange='HK' AND code='00700'"
            ).fetchone()['status']
            step('§B#3c 库内 status 已变为「可交易」', st == '可交易', '实际=%r' % st)
            led = conn.execute(
                "SELECT summary FROM decision_ledger WHERE event_type='状态变更'"
            ).fetchall()
            step('§B#3d 状态变化已写入 decision_ledger', len(led) == 1,
                 'ledger 行数=%d' % len(led))
        finally:
            conn.close()

        # §B#4 以身份字典形式提交也支持
        prev3 = server.preview_import_full(base_full_payload([
            sec_new(code='00005', exchange='HK', name='汇丰控股',
                    status='等价格')]))
        server.commit_import_full(prev3['token'], [])
        prev4 = server.preview_import_full(base_full_payload([
            sec_new(code='00005', exchange='HK', name='汇丰控股',
                    status='持仓中')]))
        res4 = expect_ok(
            lambda: server.commit_import_full(
                prev4['token'], [{'exchange': 'HK', 'code': '00005'}]),
            '§B#4 以 {exchange,code} 形式确认状态变化 → commit 成功')
        if res4:
            step('§B#4b status_changed_count=1',
                 res4.get('status_changed_count') == 1)

        # §B#5 新建标的的初始状态不要求确认（不是"状态变化"）
        prev5 = server.preview_import_full(base_full_payload([
            sec_new(code='00388', exchange='HK', name='香港交易所', status='等价格')]))
        sc5 = prev5['securities'][0]['status_change']
        step('§B#5a 新建标的 status_change.is_new=True', sc5.get('is_new') is True)
        step('§B#5b 新建标的 requires_confirm=False',
             sc5.get('requires_confirm') is False)
        expect_ok(lambda: server.commit_import_full(prev5['token'], []),
                  '§B#5c 新建标的无需状态确认即可 commit')
    finally:
        cleanup_tmp(path)


# ==================== §C preview snapshot 漂移检测 ====================

def test_c_snapshot_drift():
    print('\n=== §C 提交前验证 preview snapshot 未漂移 ===')
    path = open_tmp_db('wb-v108-c-')
    try:
        # ---- §C#1 preview 后 status 改变 → commit 拒绝
        preinsert_security('00700', 'HK', name='腾讯控股', status='等价格')
        payload = base_full_payload([sec_new(status='等价格')])
        prev = server.preview_import_full(payload)
        conn = server.get_db()
        conn.execute("UPDATE securities SET status='暂不参与' "
                     "WHERE exchange='HK' AND code='00700'")
        conn.commit()
        conn.close()
        msg = expect_reject(lambda: server.commit_import_full(prev['token']),
                            '§C#1 preview 后 status 改变 → commit 拒绝',
                            must_contain='请重新解析预览')
        step('§C#1b 错误信息指明 status 漂移',
             'status' in msg, 'msg=%r' % msg[:120])
        step('§C#1c 漂移后 token 未被消费（仍在 cache）',
             prev['token'] in server._IMPORT_PREVIEW_CACHE)

        # ---- §C#2 preview 后 research version 改变 → commit 拒绝
        path2 = open_tmp_db('wb-v108-c2-')
        sid = preinsert_security('00700', 'HK', name='腾讯控股', status='等价格')
        payload2 = base_full_payload([
            sec_new(one_liner='新的研究结论（会被漂移阻止）')])
        prev2 = server.preview_import_full(payload2)
        conn = server.get_db()
        conn.execute(
            'INSERT INTO research (security_id, version, research_pool, one_liner, '
            'positive_changes, core_validations, wall_conditions, report_link, '
            'research_date, change_note, created_at) '
            "VALUES (?, 9, 'X', '手工插入', '', '[]', '[]', '', '', '手工', ?)",
            (sid, server.now_str()))
        conn.commit()
        conn.close()
        msg2 = expect_reject(lambda: server.commit_import_full(prev2['token']),
                             '§C#2 preview 后 research version 改变 → commit 拒绝',
                             must_contain='请重新解析预览')
        step('§C#2b 错误信息指明 research 版本漂移',
             'research' in msg2, 'msg=%r' % msg2[:140])
        cleanup_tmp(path2)
        # 恢复 get_db 指向原 path（后续断言用）
        def _open_1():
            c = sqlite3.connect(path, timeout=10)
            c.row_factory = sqlite3.Row
            return c
        server.get_db = _open_1
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE.clear()

        # ---- §C#3 preview 后 trade_plan version 改变 → commit 拒绝
        preinsert_security('00005', 'HK', name='汇丰控股', status='等价格')
        payload3 = base_full_payload([
            sec_new(code='00005', exchange='HK', name='汇丰控股', plan=DEFAULT_PLAN)])
        prev3 = server.preview_import_full(payload3)
        conn = server.get_db()
        sid3 = conn.execute(
            "SELECT id FROM securities WHERE exchange='HK' AND code='00005'"
        ).fetchone()['id']
        conn.execute(
            'INSERT INTO trade_plans (security_id, version, first_zone_low, '
            'first_zone_high, add_zone_low, add_zone_high, odds_zone_low, '
            'odds_zone_high, no_chase_price, target_position_pct, next_action, '
            'change_note, created_at) VALUES (?, 7, 1,2,0.5,0.9,0.3,0.4,3,5,?,?,?)',
            (sid3, '手工', '手工插入', server.now_str()))
        conn.commit()
        conn.close()
        msg3 = expect_reject(lambda: server.commit_import_full(prev3['token']),
                             '§C#3 preview 后 trade_plan version 改变 → commit 拒绝',
                             must_contain='请重新解析预览')
        step('§C#3b 错误信息指明 trade_plan 版本漂移',
             'trade_plan' in msg3, 'msg=%r' % msg3[:140])

        # ---- §C#4 preview 后原本不存在的证券已出现 → commit 拒绝
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE.clear()
        payload4 = base_full_payload([
            sec_new(code='00388', exchange='HK', name='香港交易所')])
        prev4 = server.preview_import_full(payload4)
        step('§C#4a preview 时该证券标记为不存在',
             prev4['securities'][0]['exists'] is False)
        preinsert_security('00388', 'HK', name='香港交易所', status='等价格')
        msg4 = expect_reject(lambda: server.commit_import_full(prev4['token']),
                             '§C#4 preview 后原不存在的证券已出现 → commit 拒绝',
                             must_contain='请重新解析预览')
        step('§C#4b 错误信息指明"预览时尚不存在"',
             '尚不存在' in msg4, 'msg=%r' % msg4[:140])

        # ---- §C#5 漂移后重新 preview → 正常提交
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE.clear()
        payload5 = base_full_payload([
            sec_new(code='00388', exchange='HK', name='香港交易所')])
        prev5 = server.preview_import_full(payload5)
        res5 = expect_ok(lambda: server.commit_import_full(prev5['token']),
                         '§C#5 重新 preview 后 commit 成功（learning 路径可走通）')
        if res5:
            step('§C#5b 已存在证券被正确识别（不重复创建）',
                 res5.get('created_count') == 0
                 and res5['securities'][0]['is_new'] is False)

        # ---- §C#6 未漂移时正常提交（对照组）
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE.clear()
        payload6 = base_full_payload([
            sec_new(code='01299', exchange='HK', name='友邦保险')])
        prev6 = server.preview_import_full(payload6)
        res6 = expect_ok(lambda: server.commit_import_full(prev6['token']),
                         '§C#6 无漂移 → commit 正常成功')
        if res6:
            step('§C#6b 新建 1 只', res6.get('created_count') == 1)
    finally:
        cleanup_tmp(path)


# ==================== §D 同一批禁止重复证券 ====================

def test_d_duplicate_in_batch():
    print('\n=== §D 同一批禁止重复 (exchange, code) ===')
    path = open_tmp_db('wb-v108-d-')
    try:
        # §D#1 同批两条 SZ 000001 → preview 整体拒绝
        payload = base_full_payload([
            sec_new(exchange='SZ', code='000001', name='平安银行A', one_liner='A 逻辑'),
            sec_new(exchange='SZ', code='000001', name='平安银行B', one_liner='B 逻辑'),
        ])
        expect_reject(lambda: server.preview_import_full(payload),
                      '§D#1 同批重复 SZ.000001 → preview 整体拒绝',
                      must_contain='重复出现')

        # §D#2 错误信息包含两个下标
        try:
            server.preview_import_full(payload)
        except Exception as e:
            m = str(e)
            step('§D#2 错误信息标注 securities[0] 与 securities[1]',
                 'securities[0]' in m and 'securities[1]' in m, 'msg=%r' % m[:140])

        # §D#3 不同 exchange 相同 code 允许（HK 00001 与 SZ 000001 是不同标的）
        payload3 = base_full_payload([
            sec_new(exchange='HK', code='00001', name='长和'),
            sec_new(exchange='SZ', code='000001', name='平安银行'),
        ])
        prev3 = expect_ok(lambda: server.preview_import_full(payload3),
                          '§D#3 不同 exchange 同 code → 允许')
        if prev3:
            step('§D#3b preview 返回 2 条',
                 len(prev3['securities']) == 2)
            expect_ok(lambda: server.commit_import_full(prev3['token']),
                      '§D#3c commit 成功创建 2 只')

        # §D#4 禁止"预览两只均显示新建 → commit 后第二只变更新"
        #      —— 因为 preview 阶段就整体拒绝了，不可能进入 commit
        conn = server.get_db()
        try:
            n = conn.execute(
                "SELECT COUNT(*) c FROM securities WHERE exchange='SZ' AND code='000001'"
            ).fetchone()['c']
            step('§D#4 被拒批次未写入任何 SZ.000001', n == 1,
                 '（应仅 §D#3 写入的 1 行）实际=%d' % n)
        finally:
            conn.close()
    finally:
        cleanup_tmp(path)


# ==================== §E 研究数组结构严格校验 ====================

def test_e_kv_list_schema():
    print('\n=== §E core_validations / wall_conditions 固定 Schema ===')

    def fresh(payload):
        path = open_tmp_db('wb-v108-e-')
        return path, payload

    # ---- §E#1 core_validations 为字符串数组 → 拒绝
    path = open_tmp_db('wb-v108-e1-')
    try:
        s = sec_new()
        s['research']['core_validations'] = ['纯字符串', '第二条']
        expect_reject(lambda: server.preview_import_full(base_full_payload([s])),
                      '§E#1 core_validations 为字符串数组 → preview 拒绝',
                      must_contain='必须是对象')
    finally:
        cleanup_tmp(path)

    # ---- §E#2 core_validations.status 非法 → 拒绝
    path = open_tmp_db('wb-v108-e2-')
    try:
        s = sec_new()
        s['research']['core_validations'] = [{'content': 'C', 'status': '瞎写'}]
        expect_reject(lambda: server.preview_import_full(base_full_payload([s])),
                      '§E#2 core_validations.status 非法 → preview 拒绝',
                      must_contain='必须是')
    finally:
        cleanup_tmp(path)

    # ---- §E#2b status 缺失 → 拒绝
    path = open_tmp_db('wb-v108-e2b-')
    try:
        s = sec_new()
        s['research']['core_validations'] = [{'content': 'C'}]
        expect_reject(lambda: server.preview_import_full(base_full_payload([s])),
                      '§E#2b core_validations 缺 status → preview 拒绝')
    finally:
        cleanup_tmp(path)

    # ---- §E#3 core_validations 缺 content / content 为空 → 拒绝
    path = open_tmp_db('wb-v108-e3-')
    try:
        s = sec_new()
        s['research']['core_validations'] = [{'status': '跟踪中'}]
        expect_reject(lambda: server.preview_import_full(base_full_payload([s])),
                      '§E#3a core_validations 缺 content → preview 拒绝',
                      must_contain='content')
        s2 = sec_new()
        s2['research']['core_validations'] = [{'content': '   ', 'status': '跟踪中'}]
        expect_reject(lambda: server.preview_import_full(base_full_payload([s2])),
                      '§E#3b core_validations.content 全空白 → preview 拒绝',
                      must_contain='content')
        s3 = sec_new()
        s3['research']['core_validations'] = [{'content': 123, 'status': '跟踪中'}]
        expect_reject(lambda: server.preview_import_full(base_full_payload([s3])),
                      '§E#3c core_validations.content 是数字 → preview 拒绝',
                      must_contain='content')
    finally:
        cleanup_tmp(path)

    # ---- §E#4 wall_conditions 为字符串数组 → 拒绝
    path = open_tmp_db('wb-v108-e4-')
    try:
        s = sec_new()
        s['research']['wall_conditions'] = ['危墙字符串']
        expect_reject(lambda: server.preview_import_full(base_full_payload([s])),
                      '§E#4 wall_conditions 为字符串数组 → preview 拒绝',
                      must_contain='必须是对象')
    finally:
        cleanup_tmp(path)

    # ---- §E#5 wall_conditions.triggered 非 boolean → 拒绝
    path = open_tmp_db('wb-v108-e5-')
    try:
        for bad in ['false', 'true', 0, 1, None]:
            s = sec_new()
            s['research']['wall_conditions'] = [{'content': 'W', 'triggered': bad}]
            try:
                server.preview_import_full(base_full_payload([s]))
                step('§E#5 triggered=%r → preview 拒绝' % (bad,), False,
                     '预期拒绝但通过')
            except Exception:
                step('§E#5 triggered=%r → preview 拒绝' % (bad,), True)
    finally:
        cleanup_tmp(path)

    # ---- §E#6 wall_conditions 缺 content → 拒绝
    path = open_tmp_db('wb-v108-e6-')
    try:
        s = sec_new()
        s['research']['wall_conditions'] = [{'triggered': False}]
        expect_reject(lambda: server.preview_import_full(base_full_payload([s])),
                      '§E#6 wall_conditions 缺 content → preview 拒绝',
                      must_contain='content')
    finally:
        cleanup_tmp(path)

    # ---- §E#7 合法结构通过（对照组）
    path = open_tmp_db('wb-v108-e7-')
    try:
        s = sec_new()
        s['research']['core_validations'] = [
            {'content': 'A 项', 'status': '跟踪中'},
            {'content': 'B 项', 'status': '已验证'},
            {'content': 'C 项', 'status': '已恶化'},
        ]
        s['research']['wall_conditions'] = [
            {'content': 'W1', 'triggered': True},
            {'content': 'W2', 'triggered': False},
        ]
        prev = expect_ok(lambda: server.preview_import_full(base_full_payload([s])),
                         '§E#7 三种合法 status + 布尔 triggered → preview 通过')
        if prev:
            expect_ok(lambda: server.commit_import_full(prev['token']),
                      '§E#7b 合法结构 commit 成功')
    finally:
        cleanup_tmp(path)

    # ---- §E#8 错误结构不得部分入库（拒绝即不写库）
    path = open_tmp_db('wb-v108-e8-')
    try:
        s = sec_new()
        s['research']['core_validations'] = [{'content': 'C', 'status': '瞎写'}]
        try:
            server.preview_import_full(base_full_payload([s]))
        except Exception:
            pass
        conn = server.get_db()
        try:
            n = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c']
            step('§E#8 非法结构被拒后 securities 表为空', n == 0,
                 '实际=%d' % n)
        finally:
            conn.close()
    finally:
        cleanup_tmp(path)


# ==================== §F name 不一致提示 ====================

def test_f_name_mismatch():
    print('\n=== §F 已有证券名称不一致必须显式提示（不自动改名） ===')
    path = open_tmp_db('wb-v108-f-')
    try:
        preinsert_security('00700', 'HK', name='腾讯控股有限公司', status='等价格')
        payload = base_full_payload([
            sec_new(name='腾讯控股')])   # 导入 name 与库内不同

        prev = server.preview_import_full(payload)
        sv = prev['securities'][0]

        # §F#1 preview 数据显式包含警告
        step('§F#1a name_mismatch=True', sv.get('name_mismatch') is True)
        notice = sv.get('name_mismatch_notice') or ''
        step('§F#1b notice 包含"名称不一致"', '名称不一致' in notice,
             'notice=%r' % notice[:80])
        step('§F#1c notice 含工作台名称', '腾讯控股有限公司' in notice)
        step('§F#1d notice 含导入名称', '导入块：腾讯控股' in notice)
        step('§F#1e notice 说明仍按 exchange+code 识别',
             'exchange+code' in notice)
        step('§F#1f notice 要求人工核对', '人工核对' in notice)
        step('§F#1g 顶层 warnings 也带出该提示',
             any('名称不一致' in w for w in prev.get('warnings', [])),
             'warnings=%r' % (prev.get('warnings') or [])[:1])
        step('§F#1h security.name_current 仍可读',
             (sv.get('security') or {}).get('name_current') == '腾讯控股有限公司')

        # §F#2 页面渲染包含警告（静态扫描 app.js）
        js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
        js = open(js_path, encoding='utf-8').read()
        step('§F#2a 前端读取 s.name_mismatch', 's.name_mismatch' in js)
        step('§F#2b 前端渲染"名称不一致"横幅', '名称不一致' in js)
        step('§F#2c 前端显式告知不自动改名',
             '不会' in js and '自动修改' in js)

        # §F#3 commit 后库内 name 不被修改
        prev2 = server.preview_import_full(payload)
        expect_ok(lambda: server.commit_import_full(prev2['token'], []),
                  '§F#3a 名称不一致不阻止 commit（仅提示）')
        conn = server.get_db()
        try:
            nm = conn.execute(
                "SELECT name FROM securities WHERE exchange='HK' AND code='00700'"
            ).fetchone()['name']
            step('§F#3b 库内 name 保持"腾讯控股有限公司"（未被自动改写）',
                 nm == '腾讯控股有限公司', '实际=%r' % nm)
            rv = conn.execute(
                'SELECT version FROM research WHERE security_id='
                "(SELECT id FROM securities WHERE exchange='HK' AND code='00700')"
            ).fetchall()
            step('§F#3c 研究仍按版本化追加', len(rv) >= 1, '版本数=%d' % len(rv))
        finally:
            conn.close()

        # §F#4 名称一致时无警告（对照组）
        path2 = open_tmp_db('wb-v108-f2-')
        try:
            preinsert_security('01299', 'HK', name='友邦保险', status='等价格')
            prev4 = server.preview_import_full(base_full_payload([
                sec_new(code='01299', exchange='HK', name='友邦保险')]))
            step('§F#4 名称一致 → name_mismatch=False',
                 prev4['securities'][0].get('name_mismatch') is False)
            step('§F#4b 名称一致 → warnings 为空',
                 (prev4.get('warnings') or []) == [],
                 'warnings=%r' % prev4.get('warnings'))
        finally:
            cleanup_tmp(path2)
    finally:
        cleanup_tmp(path)


# ==================== §G execution-only 入口的 token 一致性 ====================

def test_g_exec_only_token():
    print('\n=== §G 快速更新动态执行：token 机制与漂移检测 ===')
    path = open_tmp_db('wb-v108-g-')
    try:
        preinsert_security('00700', 'HK', name='腾讯控股', status='等价格')
        p = {
            'format': 'ah-workbench-execution',
            'format_version': '1.0',
            'identity': {'exchange': 'HK', 'code': '00700'},
            'execution': {
                'execution_date': '2026-09-11',
                'price_snapshot': 400.0,
                'execution_view': '等待技术确认',
                'reason': '测试',
            },
        }
        # 未 preview 直接 commit → 拒绝
        expect_reject(lambda: server.commit_import_execution('bogus'),
                      '§G#1 exec-only 未 preview 直接 commit → 拒绝',
                      must_contain='token 无效')

        prev = server.preview_import_execution(p)
        tok = prev['token']
        step('§G#2 exec-only token 也在服务端 cache',
             tok in server._IMPORT_PREVIEW_CACHE)
        step('§G#2b exec-only preview 同样返回 ttl',
             prev.get('token_ttl_seconds') == 300)

        res = expect_ok(lambda: server.commit_import_execution(tok),
                        '§G#3 exec-only commit 成功')
        if res:
            step('§G#3b 新增 execution id 存在',
                 res.get('new_execution_id') is not None)
        expect_reject(lambda: server.commit_import_execution(tok),
                      '§G#4 exec-only token 复用 → 拒绝',
                      must_contain='token 无效')

        # 漂移：preview 后 status 改变 → commit 拒绝
        prev2 = server.preview_import_execution(p)
        conn = server.get_db()
        conn.execute("UPDATE securities SET status='暂不参与' "
                     "WHERE exchange='HK' AND code='00700'")
        conn.commit()
        conn.close()
        expect_reject(lambda: server.commit_import_execution(prev2['token']),
                      '§G#5 exec-only preview 后 status 漂移 → 拒绝',
                      must_contain='请重新解析预览')

        # 找不到证券 → 拒绝
        p_bad = json.loads(json.dumps(p))
        p_bad['identity'] = {'exchange': 'SH', 'code': '999999'}
        expect_reject(lambda: server.preview_import_execution(p_bad),
                      '§G#6 找不到证券 → 拒绝',
                      must_contain='尚未进入工作台')
    finally:
        cleanup_tmp(path)


# ==================== §H 既有语义不回归 ====================

def test_h_no_regression():
    print('\n=== §H 既有语义不回归（版本化 / append-only / 原子性 / trades 不变） ===')
    path = open_tmp_db('wb-v108-h-')
    try:
        # 导入一只新标的（完整）
        exec_block = {
            'execution_date': '2026-09-11',
            'price_snapshot': 410.0,
            'support_zone': '400-405',
            'resistance_zone': '430-435',
            'technical_structure': '结构说明',
            'execution_condition': '等待确认',
            'execution_view': '等待技术确认',
            'reason': '测试依据',
        }
        payload = base_full_payload([sec_new(plan=DEFAULT_PLAN, execution=exec_block)])
        prev = server.preview_import_full(payload)
        res = expect_ok(lambda: server.commit_import_full(prev['token']),
                        '§H#1 新证券完整导入成功')
        if res:
            step('§H#1b created=1', res.get('created_count') == 1)
            step('§H#1c 新增 execution=1', res.get('new_executions') == 1)

        conn = server.get_db()
        try:
            sid = conn.execute(
                "SELECT id FROM securities WHERE exchange='HK' AND code='00700'"
            ).fetchone()['id']
            rv = [r['version'] for r in conn.execute(
                'SELECT version FROM research WHERE security_id=? ORDER BY version',
                (sid,)).fetchall()]
            pv = [r['version'] for r in conn.execute(
                'SELECT version FROM trade_plans WHERE security_id=? ORDER BY version',
                (sid,)).fetchall()]
            ev = conn.execute(
                'SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?',
                (sid,)).fetchone()['c']
            step('§H#2a research v1 建立', rv == [1], '实际=%r' % rv)
            step('§H#2b trade_plan v1 建立', pv == [1], '实际=%r' % pv)
            step('§H#2c execution 1 条', ev == 1, '实际=%d' % ev)
        finally:
            conn.close()

        # research 无变化 → 不生成新版本
        prev2 = server.preview_import_full(
            base_full_payload([sec_new(plan=DEFAULT_PLAN)]))
        step('§H#3a research 内容相同 → unchanged=True',
             prev2['securities'][0]['research']['unchanged'] is True)
        step('§H#3b trade_plan 内容相同 → unchanged=True',
             prev2['securities'][0]['trade_plan']['unchanged'] is True)
        server.commit_import_full(prev2['token'], [])
        conn = server.get_db()
        try:
            rv = [r['version'] for r in conn.execute(
                'SELECT version FROM research WHERE security_id=? ORDER BY version',
                (sid,)).fetchall()]
            pv = [r['version'] for r in conn.execute(
                'SELECT version FROM trade_plans WHERE security_id=? ORDER BY version',
                (sid,)).fetchall()]
            step('§H#3c research 仍只有 v1', rv == [1], '实际=%r' % rv)
            step('§H#3d trade_plan 仍只有 v1', pv == [1], '实际=%r' % pv)
        finally:
            conn.close()

        # research 变化 → 新增 v2，旧版保留
        prev3 = server.preview_import_full(
            base_full_payload([sec_new(one_liner='新的核心逻辑', plan=DEFAULT_PLAN)]))
        step('§H#4a research 变化 → unchanged=False',
             prev3['securities'][0]['research']['unchanged'] is False)
        step('§H#4b next_version=2',
             prev3['securities'][0]['research']['next_version'] == 2)
        server.commit_import_full(prev3['token'], [])
        conn = server.get_db()
        try:
            rv = [r['version'] for r in conn.execute(
                'SELECT version FROM research WHERE security_id=? ORDER BY version',
                (sid,)).fetchall()]
            step('§H#4c research 版本=[1,2]（旧版永久保留）', rv == [1, 2],
                 '实际=%r' % rv)
        finally:
            conn.close()

        # execution append-only：再追加一条
        ex2 = json.loads(json.dumps(exec_block))
        ex2['execution_date'] = '2026-09-12'
        ex2['execution_view'] = '继续观察'
        prev5 = server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '00700', 'name': '腾讯控股'},
             'execution': ex2}]))
        server.commit_import_full(prev5['token'], [])
        conn = server.get_db()
        try:
            rows = conn.execute(
                'SELECT execution_date, execution_view FROM execution_reviews '
                'WHERE security_id=? ORDER BY id', (sid,)).fetchall()
            step('§H#5a execution 追加为 2 条（append-only）', len(rows) == 2,
                 '实际=%d' % len(rows))
            step('§H#5b 第一条未被改写',
                 rows[0]['execution_view'] == '等待技术确认',
                 '第一条=%r' % rows[0]['execution_view'])
            step('§H#5c 第二条为新判断',
                 rows[1]['execution_view'] == '继续观察')
        finally:
            conn.close()

        # trades 始终不变
        conn = server.get_db()
        try:
            n = conn.execute('SELECT COUNT(*) c FROM trades').fetchone()['c']
            step('§H#6 导入全程 trades 行数=0', n == 0, '实际=%d' % n)
        finally:
            conn.close()

        # 原子性：ledger 失败注入 → 整批 ROLLBACK
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE.clear()
        prev7 = server.preview_import_full(base_full_payload([
            sec_new(code='01299', exchange='HK', name='友邦保险',
                    plan=DEFAULT_PLAN)]))
        conn = server.get_db()
        try:
            before_sec = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c']
            before_led = conn.execute('SELECT COUNT(*) c FROM decision_ledger').fetchone()['c']
        finally:
            conn.close()
        server._LEDGER_FAIL_INJECT = True
        try:
            server.commit_import_full(prev7['token'], [])
            step('§H#7a ledger 失败注入 → commit 应抛错', False, '未抛错')
        except Exception:
            step('§H#7a ledger 失败注入 → commit 抛错', True)
        finally:
            server._LEDGER_FAIL_INJECT = False
        conn = server.get_db()
        try:
            after_sec = conn.execute('SELECT COUNT(*) c FROM securities').fetchone()['c']
            after_led = conn.execute('SELECT COUNT(*) c FROM decision_ledger').fetchone()['c']
            step('§H#7b securities 未变化（整批 ROLLBACK）',
                 after_sec == before_sec, '%d → %d' % (before_sec, after_sec))
            step('§H#7c ledger 未变化（整批 ROLLBACK）',
                 after_led == before_led, '%d → %d' % (before_led, after_led))
        finally:
            conn.close()
    finally:
        cleanup_tmp(path)


# ==================== §I 静态契约 ====================

def test_i_static_contract():
    print('\n=== §I 静态契约扫描 ===')
    src_path = os.path.join(ROOT, 'app', 'server.py')
    src = open(src_path, encoding='utf-8').read()

    step('§I#1 TARGET_SCHEMA_VERSION=1.0.8',
         "TARGET_SCHEMA_VERSION = '1.0.8'" in src)
    step('§I#2 server_version=Workbench/1.0.8',
         "server_version = 'Workbench/1.0.8'" in src)
    step('§I#3 不再 import base64', 'import base64' not in src)
    step('§I#4 引入 secrets 模块', 'import secrets' in src)
    step('§I#5 secrets.token_urlsafe 生成 token',
         'secrets.token_urlsafe' in src)
    step('§I#6 服务端 preview cache 存在',
         '_IMPORT_PREVIEW_CACHE = {}' in src)
    step('§I#7 TTL 常量=300',
         'IMPORT_PREVIEW_TTL_SECONDS = 300' in src)
    step('§I#8 validations status 白名单常量',
         "VALIDATION_STATUSES = ['跟踪中', '已验证', '已恶化']" in src)
    step('§I#9 commit 接收 confirmed_status_changes',
         'def commit_import_full(token, confirmed_status_changes=None)' in src)
    step('§I#10 漂移检测函数存在',
         'def _import_snapshot_drift(' in src)
    step('§I#11 漂移提示文案一致',
         '工作台数据自预览后已发生变化，请重新解析预览。' in src)
    step('§I#12 同批去重实现',
         'seen_identity' in src)
    step('§I#13 kv_list 校验函数存在',
         'def _import_validate_kv_list(' in src)
    step('§I#14 status_change_confirmed 不再写入 validated',
         "'status_change_confirmed': scc" not in src)

    # 前端契约
    js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
    js = open(js_path, encoding='utf-8').read()
    step('§I#15 前端版本号 v1.0.8',
         'A/H 投研交易工作台 · 前端  v1.0.8' in js)
    step('§I#16 前端 confirmed_status_changes 提交',
         'confirmed_status_changes' in js)
    step('§I#17 前端不再出现"载入示例"按钮（仅注释说明）',
         'onclick="loadFullExample()"' not in js
         and 'onclick="loadExecExample()"' not in js)
    step('§I#18 前端不再内置美图 01357 示例',
         '01357' not in js)
    step('§I#19 前端 confirmedStatus 状态存在',
         'confirmedStatus' in js)
    step('§I#20 前端不再写回 status_change_confirmed 到 payload',
         'sec.status_change_confirmed = true' not in js)

    # index.html
    idx = open(os.path.join(ROOT, 'app', 'static', 'index.html'),
               encoding='utf-8').read()
    step('§I#21 导航含「导入与更新」', '导入与更新' in idx)


# ==================== main ====================

def main():
    print('=' * 66)
    print('v1.0.8 导入完整性封板 —— 回归测试')
    print('=' * 66)
    test_a_token_mechanism()
    test_b_status_confirmation()
    test_c_snapshot_drift()
    test_d_duplicate_in_batch()
    test_e_kv_list_schema()
    test_f_name_mismatch()
    test_g_exec_only_token()
    test_h_no_regression()
    test_i_static_contract()
    print()
    print('=' * 66)
    print('TOTAL = %d' % TOTAL)
    print('FAIL_COUNT = %d' % FAIL_COUNT)
    print('ALL TESTS PASS' if FAIL_COUNT == 0 else '*** 有测试失败 ***')
    print('=' * 66)
    return 0 if FAIL_COUNT == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
