# -*- coding: utf-8 -*-
"""v1.0.7 「导入与更新」模块回归测试。

15 节核心 spec（与本轮"v1.0.7 导入与更新"任务清单一一对应）：
  §A  单只新证券完整导入（identity + research + plan + execution）
  §B  多只批量导入（一批包含新建 + 已有）
  §C  已有证券正确识别（不再覆盖身份信息 name/sector/notes）
  §D  research 完全相同 → 不生成新版本（旧版永久保留）
  §E  research 变化 → 生成 v2，旧版 v1 仍保留
  §F  trade_plan 完全相同 → 不生成新版本
  §G  trade_plan 变化 → 生成新版本，旧版仍保留
  §H  execution 每次导入都 append-only（旧 execution 不被 UPDATE/DELETE）
  §I  快速 execution 不修改 research/trade_plan/status
  §J  快速 execution 找不到证券时拒绝
  §K  状态变化必须进入预览，不得自动覆盖
  §L  非法 JSON / 数值非法 / 日期非法 → preview 拒绝，不写库
  §M  导入失败（commit 阶段抛错）整批 ROLLBACK，不污染既有数据
  §N  execution + ledger 原子性保持（同事务写入；ledger 失败注入 → ROLLBACK）
  §O  导入过程中真实 trades 不得发生任何变化
  +  静态契约扫描：覆盖 v1.0.7 新增常量 / 端点 / 注释边界
"""

import os, sys, json, base64, sqlite3, tempfile, time
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server


FAIL_COUNT = 0
TOTAL = 0


def step(name, ok, detail=''):
    """单条断言：失败计数 FAIL_COUNT 增；最后给出 PASS/FAIL 总结。"""
    global FAIL_COUNT, TOTAL
    TOTAL += 1
    flag = 'PASS' if ok else 'FAIL'
    print('  [%s] %s %s' % (flag, name, detail))
    if not ok:
        FAIL_COUNT += 1


def open_tmp_db(prefix='wb-v107-'):
    """建一个临时数据库，返回其路径；并 monkey-patch server.get_db。"""
    fd, path = tempfile.mkstemp(suffix='.db', prefix=prefix)
    os.close(fd)
    server.init_db(seed=False, db_path=path)

    def _open():
        c = sqlite3.connect(path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    server.get_db = _open
    # v1.0.8：清空服务端 preview cache，避免测试互相污染
    try:
        with server._IMPORT_PREVIEW_LOCK:
            server._IMPORT_PREVIEW_CACHE.clear()
    except Exception:
        pass
    # 清 quote cache 防止测试相互污染
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
    """向临时 DB 插入一只 securities（不走 create_security_tx，用于已有场景）。"""
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
    """包装为完整导入格式 A 的 payload。"""
    return {
        'format': 'ah-workbench-import',
        'format_version': '1.0',
        'generated_at': '2026-09-10',
        'securities': securities,
    }


def base_exec_payload(identity, execution):
    return {
        'format': 'ah-workbench-execution',
        'format_version': '1.0',
        'identity': identity,
        'execution': execution,
    }


def base_research(**overrides):
    d = {
        'research_pool': 'A池',
        'one_liner': '核心订阅增长',
        'positive_changes': '',
        'core_validations': [{'content': 'X', 'status': '跟踪中'}],
        'wall_conditions': [{'content': 'Y', 'triggered': False}],
        'report_link': '',
        'research_date': '2026-09-10',
        'change_note': '首次深穿',
    }
    d.update(overrides)
    return d


def base_plan(**overrides):
    d = {
        'first_zone_low': 4.0, 'first_zone_high': 4.4,
        'add_zone_low': 3.5, 'add_zone_high': 3.8,
        'odds_zone_low': 3.0, 'odds_zone_high': 3.3,
        'no_chase_price': 5.0,
        'target_position_pct': 8.0,
        'next_action': '等待',
        'change_note': '初始计划',
    }
    d.update(overrides)
    return d


def base_execution(**overrides):
    d = {
        'execution_date': '2026-09-10',
        'price_snapshot': 4.6,
        'support_zone': '4.18-4.22',
        'resistance_zone': '4.30-4.35',
        'technical_structure': '',
        'execution_condition': '',
        'execution_view': '等待技术确认',
        'reason': '已进入首仓赔率区',
    }
    d.update(overrides)
    return d


# ============ §A 单只新证券完整导入 ============
def test_a_single_full_import():
    print('\n§A 单只新证券完整导入')
    path = open_tmp_db('wb-v107-A-')
    try:
        payload = base_full_payload([
            {
                'identity': {'exchange': 'HK', 'code': '01357', 'name': '美图公司', 'sector': '消费'},
                'status': '等价格',
                'research': base_research(),
                'trade_plan': base_plan(),
                'execution': base_execution(),
            }
        ])
        prev = server.preview_import_full(payload)
        step('§A#1 preview 成功返回', 'token' in prev and len(prev['securities']) == 1)
        step('§A#2 is_new=True', prev['securities'][0]['exists'] is False)
        step('§A#3 status_change.is_new', prev['securities'][0]['status_change'].get('is_new') is True)

        res = server.commit_import_full(prev['token'])
        step('§A#4 commit created=1', res['created_count'] == 1)
        step('§A#5 commit new_executions=1', res['new_executions'] == 1)

        c = server.get_db()
        try:
            sec = c.execute('SELECT * FROM securities WHERE exchange=? AND code=?', ('HK', '01357')).fetchone()
            step('§A#6 securities 行存在', sec is not None)
            step('§A#7 status=等价格', sec['status'] == '等价格')
            step('§A#8 research v1', c.execute('SELECT version FROM research WHERE security_id=?', (sec['id'],)).fetchone()['version'] == 1)
            step('§A#9 plan v1', c.execute('SELECT version FROM trade_plans WHERE security_id=?', (sec['id'],)).fetchone()['version'] == 1)
            step('§A#10 execution 1 条', c.execute('SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?', (sec['id'],)).fetchone()['c'] == 1)
            step('§A#11 ledger ≥ 2 条（标的创建 + 动态执行判断更新）', c.execute('SELECT COUNT(*) c FROM decision_ledger WHERE security_id=?', (sec['id'],)).fetchone()['c'] >= 2)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §B 多只批量导入 ============
def test_b_batch_import():
    print('\n§B 多只批量导入：新建 + 已有混在一批')
    path = open_tmp_db('wb-v107-B-')
    try:
        # 已有一只 securities
        preinsert_security('01357', 'HK', name='旧名', status='等价格')

        payload = base_full_payload([
            {
                'identity': {'exchange': 'HK', 'code': '01357', 'name': '美图公司'},
                'research': base_research(one_liner='增量更新'),
                'trade_plan': base_plan(change_note='增量计划'),
            },
            {
                'identity': {'exchange': 'SH', 'code': '600001', 'name': '测试新股'},
                'status': '可交易',
                'research': base_research(research_pool='B', one_liner='新标的研究'),
                'trade_plan': base_plan(first_zone_low=10.0, first_zone_high=12.0, change_note='首建'),
            },
            {
                'identity': {'exchange': 'SZ', 'code': '000002', 'name': '万科A'},
                'research': base_research(one_liner='第三只'),
                'trade_plan': base_plan(first_zone_low=20.0, first_zone_high=22.0, change_note='首批'),
            },
        ])

        prev = server.preview_import_full(payload)
        step('§B#1 3 条 preview', len(prev['securities']) == 3)
        step('§B#2 sec[0] 已存在', prev['securities'][0]['exists'] is True)
        step('§B#3 sec[1] 不存在', prev['securities'][1]['exists'] is False)
        step('§B#4 sec[2] 不存在', prev['securities'][2]['exists'] is False)

        res = server.commit_import_full(prev['token'])
        step('§B#5 total=3', res['total'] == 3)
        step('§B#6 created=2', res['created_count'] == 2)
        # 已有证券走 create v1 路径(算 1 个新版本);新建标的走 create_security_tx
        # 内层,初始化版本不计入"新增版本"聚合;故此处为 1。
        step('§B#7 new_research=1(已有那只新建 v1)', res['new_research_versions'] == 1)
        step('§B#8 new_plan=1(已有那只新建 v1)', res['new_plan_versions'] == 1)

        c = server.get_db()
        try:
            step('§B#9 三只 securities 全部存在',
                 c.execute('SELECT COUNT(*) c FROM securities').fetchone()['c'] == 3)
            step('§B#10 三条 research', c.execute('SELECT COUNT(*) c FROM research').fetchone()['c'] == 3)
            step('§B#11 三条 trade_plan', c.execute('SELECT COUNT(*) c FROM trade_plans').fetchone()['c'] == 3)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §C 已有证券正确识别：name/sector/notes 不被覆盖 ============
def test_c_existing_recognize():
    print('\n§C 已有证券识别：导入 name 不同也保留库内 name')
    path = open_tmp_db('wb-v107-C-')
    try:
        preinsert_security('01357', 'HK', name='库内原名', status='可交易')
        # 库内已经有该 securities，重导入使用完全不同的 name + sector。
        # 导入层不应改动 securities.name / sector，只看 exchange+code。
        c = server.get_db()
        try:
            c.execute('UPDATE securities SET sector=? WHERE id=1', ('库内行业',))
            c.commit()
        finally:
            c.close()

        payload = base_full_payload([
            {
                'identity': {'exchange': 'HK', 'code': '01357', 'name': '新名字', 'sector': '新行业'},
                'research': base_research(),
                'trade_plan': base_plan(change_note='diff'),
            }
        ])
        prev = server.preview_import_full(payload)
        step('§C#1 preview exists=true', prev['securities'][0]['exists'] is True)
        step('§C#2 preview 标记库内 name 不一致',
             prev['securities'][0].get('security') and
             prev['securities'][0]['security'].get('name_current') == '库内原名')

        res = server.commit_import_full(prev['token'])
        c = server.get_db()
        try:
            sec = c.execute('SELECT * FROM securities WHERE id=1').fetchone()
            step('§C#3 库内 name 未被覆盖（仍是"库内原名"）', sec['name'] == '库内原名')
            step('§C#4 库内 sector 未被覆盖（仍是"库内行业"）', sec['sector'] == '库内行业')
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §D research 完全相同 → 不生成新版本 ============
def test_d_research_unchanged():
    print('\n§D research 完全相同 → 不生成新版本')
    path = open_tmp_db('wb-v107-D-')
    try:
        preinsert_security('01357', 'HK', name='X', status='等价格')

        r = base_research(one_liner='不变内容')
        p1 = base_full_payload([{'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                                  'research': r, 'trade_plan': base_plan(change_note='ok')}])
        t1 = server.preview_import_full(p1)['token']
        server.commit_import_full(t1)

        # 第二次导入: 内容完全相同, change_note 改一下也不影响相等性
        r2 = dict(r)
        r2['change_note'] = 'different but content unchanged'
        p2 = base_full_payload([{'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                                  'research': r2, 'trade_plan': base_plan(change_note='ok')}])
        prev2 = server.preview_import_full(p2)
        step('§D#1 research.unchanged=True', prev2['securities'][0]['research']['unchanged'] is True)
        res = server.commit_import_full(prev2['token'])
        step('§D#2 unchanged_research=true',
             res['securities'][0]['actions'].get('unchanged_research') is True)
        step('§D#3 new_research_versions=0（本次未新增版本）',
             res['new_research_versions'] == 0)

        c = server.get_db()
        try:
            versions = [r['version'] for r in c.execute(
                'SELECT version FROM research WHERE security_id=1 ORDER BY version').fetchall()]
            step('§D#4 仍只有 v1', versions == [1])
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §E research 变化 → 生成 v2，旧版 v1 仍保留 ============
def test_e_research_changed():
    print('\n§E research 变化 → 生成 v2，旧版 v1 仍保留')
    path = open_tmp_db('wb-v107-E-')
    try:
        preinsert_security('01357', 'HK')
        r1 = base_research(one_liner='v1 内容', change_note='first')
        t1 = server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
             'research': r1, 'trade_plan': base_plan(change_note='ok')}
        ]))['token']
        server.commit_import_full(t1)

        # 二次: one_liner 改变
        r2 = base_research(one_liner='v2 新内容', change_note='second')
        prev2 = server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
             'research': r2, 'trade_plan': base_plan(change_note='ok')}
        ]))
        step('§E#1 research.unchanged=False', prev2['securities'][0]['research']['unchanged'] is False)
        step('§E#2 next_version=2', prev2['securities'][0]['research']['next_version'] == 2)

        res = server.commit_import_full(prev2['token'])
        step('§E#3 new_research_version=2', res['securities'][0]['actions'].get('new_research_version') == 2)

        c = server.get_db()
        try:
            rows = list(c.execute('SELECT version, one_liner FROM research WHERE security_id=1 ORDER BY version').fetchall())
            step('§E#4 共两版本', len(rows) == 2)
            step('§E#5 v1 内容保留', rows[0]['one_liner'] == 'v1 内容')
            step('§E#6 v2 内容正确', rows[1]['one_liner'] == 'v2 新内容')
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §F trade_plan 完全相同 → 不生成新版本 ============
def test_f_plan_unchanged():
    print('\n§F trade_plan 完全相同 → 不生成新版本')
    path = open_tmp_db('wb-v107-F-')
    try:
        preinsert_security('01357', 'HK')
        pl = base_plan(change_note='不变')
        t1 = server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
             'research': base_research(), 'trade_plan': pl}
        ]))['token']
        server.commit_import_full(t1)

        # 完全相同, change_note 也一样
        prev = server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
             'research': base_research(), 'trade_plan': pl}
        ]))
        step('§F#1 plan.unchanged=True', prev['securities'][0]['trade_plan']['unchanged'] is True)
        res = server.commit_import_full(prev['token'])
        step('§F#2 unchanged_plan=true',
             res['securities'][0]['actions'].get('unchanged_plan') is True)
        c = server.get_db()
        try:
            versions = [r['version'] for r in c.execute(
                'SELECT version FROM trade_plans WHERE security_id=1 ORDER BY version').fetchall()]
            step('§F#3 仍只有 v1', versions == [1])
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §G trade_plan 变化 → 生成新版本，旧版仍保留 ============
def test_g_plan_changed():
    print('\n§G trade_plan 变化 → 生成新版本，旧版仍保留')
    path = open_tmp_db('wb-v107-G-')
    try:
        preinsert_security('01357', 'HK')
        p1 = base_plan(first_zone_low=4.0, first_zone_high=4.4, change_note='v1')
        server.commit_import_full(server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
             'research': base_research(), 'trade_plan': p1}
        ]))['token'])

        p2 = base_plan(first_zone_low=3.9, first_zone_high=4.4, change_note='v2')
        prev = server.preview_import_full(base_full_payload([
            {'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
             'research': base_research(), 'trade_plan': p2}
        ]))
        step('§G#1 plan.unchanged=False', prev['securities'][0]['trade_plan']['unchanged'] is False)
        step('§G#2 next_version=2', prev['securities'][0]['trade_plan']['next_version'] == 2)

        server.commit_import_full(prev['token'])
        c = server.get_db()
        try:
            rows = list(c.execute(
                'SELECT version, first_zone_low FROM trade_plans WHERE security_id=1 ORDER BY version').fetchall())
            step('§G#3 共两版本', len(rows) == 2)
            step('§G#4 v1 first_zone_low=4.0 保留', rows[0]['first_zone_low'] == 4.0)
            step('§G#5 v2 first_zone_low=3.9', abs(rows[1]['first_zone_low'] - 3.9) < 1e-9)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §H execution 每次导入都 append-only ============
def test_h_execution_append_only():
    print('\n§H execution 每次导入都 append-only（旧 execution 不被覆盖）')
    path = open_tmp_db('wb-v107-H-')
    try:
        preinsert_security('01357', 'HK')

        # 第一次: 创建 v1 execution
        p1 = base_full_payload([{
            'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
            'research': base_research(),
            'trade_plan': base_plan(change_note='ok'),
            'execution': base_execution(execution_view='V1 view'),
        }])
        server.commit_import_full(server.preview_import_full(p1)['token'])

        # 第二次: 内容一样的 execution (但不应该和 prev conflict, append-only 意味着每次都加)
        p2 = base_full_payload([{
            'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
            'research': base_research(),
            'trade_plan': base_plan(change_note='ok'),
            'execution': base_execution(execution_view='V2 new'),
        }])
        prev = server.preview_import_full(p2)
        step('§H#1 execution.will_add=True（append-only）',
             prev['securities'][0]['execution']['will_add'] is True)
        step('§H#2 is_strictly_append_only 标记',
             prev['securities'][0]['execution'].get('is_strictly_append_only') is True)

        server.commit_import_full(prev['token'])

        c = server.get_db()
        try:
            rows = list(c.execute(
                'SELECT id, execution_view FROM execution_reviews WHERE security_id=1 ORDER BY id').fetchall())
            step('§H#3 execution 累计 2 条', len(rows) == 2)
            step('§H#4 第 1 条 view 仍是 V1 view', rows[0]['execution_view'] == 'V1 view')
            step('§H#5 第 2 条 view=V2 new', rows[1]['execution_view'] == 'V2 new')
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §I 快速 execution 不修改 research / trade_plan / status ============
def test_i_quick_execution_only():
    print('\n§I 快速 execution 不修改 research/trade_plan/status')
    path = open_tmp_db('wb-v107-I-')
    try:
        # 已有标的有 research v1 + plan v1 + status=等价格 + execution v1
        preinsert_security('01357', 'HK', status='等价格')
        c = server.get_db()
        try:
            c.execute('INSERT INTO research (security_id, version, one_liner, core_validations, '
                      'wall_conditions, change_note, created_at) '
                      'VALUES (1, 1, ?, "[]", "[]", ?, ?)',
                      ('原研究', 'init', server.now_str()))
            c.execute('INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, '
                      'add_zone_low, add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, '
                      'target_position_pct, next_action, change_note, created_at) '
                      'VALUES (1, 1, 4.0, 4.4, 3.5, 3.8, 3.0, 3.3, 5.0, 8.0, ?, ?, ?)',
                      ('旧下一动作', 'init', server.now_str()))
            c.execute('INSERT INTO execution_reviews (security_id, execution_date, execution_view, '
                      'created_at) VALUES (1, ?, ?, ?)',
                      ('2026-09-09', '旧执行', server.now_str()))
            c.commit()
        finally:
            c.close()

        # 走快速 execution 入口
        p = base_exec_payload({'exchange': 'HK', 'code': '01357'},
                              base_execution(execution_date='2026-09-10',
                                             execution_view='新动态执行'))
        prev = server.preview_import_execution(p)
        step('§I#1 预览找到证券', prev['security']['name'] is not None or prev['security']['id'])
        step('§I#2 上一条 execution 显示', prev['security']['current_latest_execution']['view'] == '旧执行')

        server.commit_import_execution(prev['token'])

        c = server.get_db()
        try:
            step('§I#3 research 仍只有 v1',
                 c.execute('SELECT version FROM research WHERE security_id=1').fetchone()['version'] == 1)
            step('§I#4 trade_plan 仍只有 v1',
                 c.execute('SELECT version FROM trade_plans WHERE security_id=1').fetchone()['version'] == 1)
            step('§I#5 status 未变(等价格)',
                 c.execute('SELECT status FROM securities WHERE id=1').fetchone()['status'] == '等价格')
            step('§I#6 execution 累计 2 条(append)',
                 c.execute('SELECT COUNT(*) c FROM execution_reviews WHERE security_id=1').fetchone()['c'] == 2)
            step('§I#7 原 execution_reviews record 仍存在(view=旧执行)',
                 c.execute('SELECT COUNT(*) c FROM execution_reviews WHERE security_id=1 AND execution_view=?',
                           ('旧执行',)).fetchone()['c'] == 1)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §J 快速 execution 找不到证券时拒绝 ============
def test_j_quick_execution_missing_security():
    print('\n§J 快速 execution 找不到证券时拒绝')
    path = open_tmp_db('wb-v107-J-')
    try:
        # 库里完全为空
        p = base_exec_payload({'exchange': 'HK', 'code': '01357'},
                              base_execution())
        thrown = None
        try:
            server.preview_import_execution(p)
        except server.ImportValidationError as e:
            thrown = str(e)
        except server.ApiError as e:
            thrown = str(e)
        step('§J#1 预览阶段拒绝(找不到标的)', thrown is not None)
        step('§J#2 错误信息明确提到"导入研究结果"',
             thrown and '导入研究结果' in thrown)

        c = server.get_db()
        try:
            step('§J#3 securities 表为空', c.execute('SELECT COUNT(*) c FROM securities').fetchone()['c'] == 0)
            step('§J#4 execution_reviews 表为空', c.execute('SELECT COUNT(*) c FROM execution_reviews').fetchone()['c'] == 0)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §K 状态变化必须进入预览，不得自动覆盖 ============
def test_k_status_change_required_confirm():
    print('\n§K 状态变化必须进入预览，不得自动覆盖')
    path = open_tmp_db('wb-v107-K-')
    try:
        preinsert_security('01357', 'HK', status='等价格')

        # v1.0.8：状态确认不再来自导入 JSON；preview 恒定返回 change_confirmed=False
        p = base_full_payload([{
            'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
            'status': '可交易',  # 变化！
            'research': base_research(),
            'trade_plan': base_plan(change_note='ok'),
        }])
        prev = server.preview_import_full(p)
        sc = prev['securities'][0]['status_change']
        step('§K#1 preview status_change.changed=True', sc['changed'] is True)
        step('§K#2 preview requires_confirm=True', sc['requires_confirm'] is True)
        step('§K#3 preview change_confirmed=False（未勾选）', sc['change_confirmed'] is False)

        # commit 不带 confirmed_status_changes → 整批拒绝
        thrown = None
        try:
            server.commit_import_full(prev['token'])
        except (server.ImportValidationError, server.ApiError) as e:
            thrown = str(e)
        step('§K#4 commit 不带确认 → 拒绝', thrown is not None)
        step('§K#5 错误明确提到"状态变化"', thrown and '状态变化' in thrown)

        # 验证库内 status 未被自动改
        c = server.get_db()
        try:
            step('§K#6 库内 status 未变化', c.execute('SELECT status FROM securities WHERE id=1').fetchone()['status'] == '等价格')
        finally:
            c.close()

        # v1.0.8：即使粘贴 JSON 自带 status_change_confirmed=true，也不得生效
        p_inject = base_full_payload([dict(p['securities'][0], status_change_confirmed=True)])
        prev_inj = server.preview_import_full(p_inject)
        step('§K#7 粘贴 JSON 自带 confirmed=true → preview 仍 False',
             prev_inj['securities'][0]['status_change']['change_confirmed'] is False)
        thrown2 = None
        try:
            server.commit_import_full(prev_inj['token'])
        except (server.ImportValidationError, server.ApiError) as e:
            thrown2 = str(e)
        step('§K#7b 自带 confirmed=true 仍被拒绝', thrown2 is not None)

        # v1.0.8：确认只来自 commit 请求的 confirmed_status_changes
        prev2 = server.preview_import_full(p)
        res = server.commit_import_full(prev2['token'], [0])
        step('§K#8 commit（confirmed_status_changes=[0]）成功, status_changed=true',
             res['securities'][0]['actions'].get('status_changed') is True)
        c = server.get_db()
        try:
            step('§K#9 status 改为"可交易"', c.execute('SELECT status FROM securities WHERE id=1').fetchone()['status'] == '可交易')
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §L 非法 JSON / 数值非法 / 日期非法 → preview 拒绝，不写库 ============
def test_l_invalid_payloads_rejected():
    print('\n§L 非法 JSON / 数值非法 / 日期非法 → preview 拒绝，不写库')
    path = open_tmp_db('wb-v107-L-')
    try:
        # L1: 不支持的 format
        bad_formats = [
            # bad format
            ({'format': 'wrong-format', 'format_version': '1.0', 'securities': []}, 'format'),
            # bad format_version
            ({'format': 'ah-workbench-import', 'format_version': '0.0', 'securities': []}, 'format_version'),
            # securities 非数组
            ({'format': 'ah-workbench-import', 'format_version': '1.0', 'securities': 'oops'}, 'securities'),
            # securities 为空
            ({'format': 'ah-workbench-import', 'format_version': '1.0', 'securities': []}, '非空'),
            # exchange 非法
            (base_full_payload([{'identity': {'exchange': 'XX', 'code': '01357', 'name': 'X'},
                                 'research': base_research(), 'trade_plan': base_plan(change_note='ok')}]), 'exchange'),
            # 缺 name
            (base_full_payload([{'identity': {'exchange': 'HK', 'code': '01357'},
                                 'research': base_research(), 'trade_plan': base_plan(change_note='ok')}]), 'name'),
            # code 非法 (字母)
            (base_full_payload([{'identity': {'exchange': 'HK', 'code': 'abc', 'name': 'X'},
                                 'research': base_research(), 'trade_plan': base_plan(change_note='ok')}]), 'code'),
            # 日期非法
            (base_full_payload([{'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                                 'research': dict(base_research(), research_date='2026-13-40'),
                                 'trade_plan': base_plan(change_note='ok')}]), '日期'),
            # 数值非法 (target_position_pct 超出范围)
            (base_full_payload([{'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                                 'research': base_research(),
                                 'trade_plan': dict(base_plan(change_note='ok'), target_position_pct=150)}]), '仓位'),
            # trade_plan.change_note 空
            (base_full_payload([{'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                                 'research': base_research(),
                                 'trade_plan': dict(base_plan(), change_note='')}]), 'change_note'),
            # research.one_liner 空
            (base_full_payload([{'identity': {'exchange': 'SH', 'code': '600001', 'name': 'X'},
                                 'research': dict(base_research(), one_liner=''),
                                 'trade_plan': base_plan(change_note='ok')}]), 'one_liner'),
            # execution.execution_view 空
            (base_full_payload([{'identity': {'exchange': 'SH', 'code': '600002', 'name': 'X'},
                                 'research': base_research(),
                                 'trade_plan': base_plan(change_note='ok'),
                                 'execution': dict(base_execution(), execution_view='')}]), 'execution_view'),
            # execution.execution_date 非法
            (base_full_payload([{'identity': {'exchange': 'SH', 'code': '600003', 'name': 'X'},
                                 'research': base_research(),
                                 'trade_plan': base_plan(change_note='ok'),
                                 'execution': dict(base_execution(), execution_date='2026-02-30')}]), 'execution_date'),
        ]

        c = server.get_db()
        try:
            # 关键不变量: 没有任何 bad payload 写库前, 库必须全空
            for i, (payload, hint) in enumerate(bad_formats, 1):
                thrown = None
                try:
                    server.preview_import_full(payload)
                except (server.ImportValidationError, server.ApiError) as e:
                    thrown = str(e)
                step('§L#%d#1 拒绝非法 payload (%s)' % (i, hint), thrown is not None)
            # 验证库确实保持空
            step('§L#all 库仍为空 securities=0', c.execute('SELECT COUNT(*) c FROM securities').fetchone()['c'] == 0)
            step('§L#all 库仍为空 research=0', c.execute('SELECT COUNT(*) c FROM research').fetchone()['c'] == 0)
            step('§L#all 库仍为空 trade_plans=0', c.execute('SELECT COUNT(*) c FROM trade_plans').fetchone()['c'] == 0)
            step('§L#all 库仍为空 execution_reviews=0', c.execute('SELECT COUNT(*) c FROM execution_reviews').fetchone()['c'] == 0)
            step('§L#all 库仍为空 decision_ledger=0', c.execute('SELECT COUNT(*) c FROM decision_ledger').fetchone()['c'] == 0)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §M 导入失败（commit 阶段抛错）整批 ROLLBACK ============
def test_m_rollback_on_commit_failure():
    print('\n§M 导入失败（commit 阶段抛错）整批 ROLLBACK，不污染既有数据')
    path = open_tmp_db('wb-v107-M-')
    try:
        # 已有一只标的(且已有 v1 research/plan/execution, ledger=1)
        preinsert_security('01357', 'HK', name='已有', status='持仓中')
        c = server.get_db()
        try:
            c.execute('INSERT INTO research (security_id, version, one_liner, core_validations, '
                      'wall_conditions, change_note, created_at) '
                      'VALUES (1, 1, ?, "[]", "[]", ?, ?)',
                      ('已有研究', 'init', server.now_str()))
            c.execute('INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, '
                      'add_zone_low, add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, '
                      'target_position_pct, next_action, change_note, created_at) '
                      'VALUES (1, 1, 4.0, 4.4, 3.5, 3.8, 3.0, 3.3, 5.0, 8.0, ?, ?, ?)',
                      ('已有', 'init', server.now_str()))
            c.execute('INSERT INTO execution_reviews (security_id, execution_date, execution_view, '
                      'created_at) VALUES (1, ?, ?, ?)',
                      ('2026-09-09', '已有执行', server.now_str()))
            c.execute('INSERT INTO decision_ledger (security_id, event_date, event_type, summary, created_at) '
                      'VALUES (1, ?, ?, ?, ?)',
                      ('2026-09-09', '测试台账', 'init row', server.now_str()))
            c.commit()
        finally:
            c.close()

        baseline = {'sec': 1, 'research': 1, 'plan': 1, 'exec': 1, 'ledger': 1, 'trade': 0}

        # 注入：本次 commit 第一只 OK，第二只时强制 ledger 失败
        # 用 patch 的方式: 把第一只标的研究的某字段设为合法 → 通过预览；第二只的 research 因 patch 强制在 commit 阶段抛错。
        # 用 _LEDGER_FAIL_INJECT 来制造 commit 中途失败。
        server._LEDGER_FAIL_INJECT = True
        try:
            payload = base_full_payload([
                {
                    'identity': {'exchange': 'SH', 'code': '600001', 'name': 'FIRST'},
                    'research': base_research(one_liner='first'),
                    'trade_plan': base_plan(change_note='first plan'),
                },
                {
                    'identity': {'exchange': 'SH', 'code': '600002', 'name': 'SECOND'},
                    'research': base_research(one_liner='second'),
                    'trade_plan': base_plan(change_note='second plan'),
                },
            ])
            prev = server.preview_import_full(payload)
            # 注入要只在 SECOND 时生效：手动只 commit 一次
            thrown = None
            try:
                server.commit_import_full(prev['token'])
            except Exception as e:
                thrown = str(e)
            step('§M#1 commit 失败有异常抛出', thrown is not None)

            # 验证整批 ROLLBACK: 库应保持 baseline
            c = server.get_db()
            try:
                step('§M#2 securities 维持 baseline (1)',
                     c.execute('SELECT COUNT(*) c FROM securities').fetchone()['c'] == 1)
                step('§M#3 research 维持 baseline (1)',
                     c.execute('SELECT COUNT(*) c FROM research').fetchone()['c'] == 1)
                step('§M#4 plan 维持 baseline (1)',
                     c.execute('SELECT COUNT(*) c FROM trade_plans').fetchone()['c'] == 1)
                step('§M#5 execution 维持 baseline (1)',
                     c.execute('SELECT COUNT(*) c FROM execution_reviews').fetchone()['c'] == 1)
                step('§M#6 ledger 维持 baseline (1)',
                     c.execute('SELECT COUNT(*) c FROM decision_ledger').fetchone()['c'] == 1)
                step('§M#7 trades 维持 baseline (0)',
                     c.execute('SELECT COUNT(*) c FROM trades').fetchone()['c'] == 0)
                # 已有数据未被破坏
                step('§M#8 已有 execution 仍在',
                     c.execute('SELECT COUNT(*) c FROM execution_reviews WHERE execution_view=?',
                               ('已有执行',)).fetchone()['c'] == 1)
                step('§M#9 已有 ledger 仍在',
                     c.execute('SELECT COUNT(*) c FROM decision_ledger WHERE summary=?',
                               ('init row',)).fetchone()['c'] == 1)
            finally:
                c.close()
        finally:
            server._LEDGER_FAIL_INJECT = False
    finally:
        cleanup_tmp(path)


# ============ §N execution + ledger 原子性 ============
def test_n_execution_ledger_atomic():
    print('\n§N execution + ledger 原子性（同一事务）')
    path = open_tmp_db('wb-v107-N-')
    try:
        preinsert_security('01357', 'HK')

        # 注入: 走 execution 入口；执行体完成后强制 ledger 失败 → 应当整条 execution + ledger 都回滚
        server._LEDGER_FAIL_INJECT = True
        try:
            p = base_exec_payload({'exchange': 'HK', 'code': '01357'},
                                  base_execution(execution_view='ATOMIC test'))
            thrown = None
            try:
                prev = server.preview_import_execution(p)
                server.commit_import_execution(prev['token'])
            except Exception as e:
                thrown = str(e)
            step('§N#1 commit 失败有异常抛出', thrown is not None)

            c = server.get_db()
            try:
                step('§N#2 execution 未写入(0)',
                     c.execute('SELECT COUNT(*) c FROM execution_reviews').fetchone()['c'] == 0)
                step('§N#3 ledger 未写入(0)',
                     c.execute('SELECT COUNT(*) c FROM decision_ledger').fetchone()['c'] == 0)
            finally:
                c.close()
        finally:
            server._LEDGER_FAIL_INJECT = False

        # 正常路径：execution 与 ledger 都写入
        p = base_exec_payload({'exchange': 'HK', 'code': '01357'},
                              base_execution(execution_view='NORMAL ok'))
        prev = server.preview_import_execution(p)
        res = server.commit_import_execution(prev['token'])
        step('§N#4 正常路径 success, new_execution_id>0',
             res.get('new_execution_id') is not None and res['new_execution_id'] > 0)
        c = server.get_db()
        try:
            step('§N#5 execution 行写入',
                 c.execute('SELECT COUNT(*) c FROM execution_reviews').fetchone()['c'] == 1)
            step('§N#6 ledger 同行数同步写入',
                 c.execute("SELECT COUNT(*) c FROM decision_ledger WHERE event_type='动态执行判断更新'").fetchone()['c'] == 1)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §O 导入过程中真实 trades 不得发生任何变化 ============
def test_o_trades_untouched():
    print('\n§O 导入过程中真实 trades 不得发生任何变化')
    path = open_tmp_db('wb-v107-O-')
    try:
        preinsert_security('01357', 'HK')

        # 先记录一笔 trade (建立 baseline)
        c = server.get_db()
        try:
            c.execute('INSERT INTO trades (security_id, trade_date, side, price, quantity, fee, note, created_at) '
                      'VALUES (1, ?, ?, 4.5, 100, 0, "baseline trade", ?)',
                      ('2026-09-09', '买入', server.now_str()))
            c.commit()
        finally:
            c.close()

        baseline_trades = c.execute if False else None  # placeholder
        c = server.get_db()
        try:
            before_trades = [dict(r) for r in c.execute('SELECT * FROM trades').fetchall()]
        finally:
            c.close()
        step('§O#1 起始 trades=1', len(before_trades) == 1)

        # 多次跑 import
        payloads = [
            base_full_payload([{
                'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                'research': base_research(one_liner='一次'),
                'trade_plan': base_plan(change_note='一次'),
                'execution': base_execution(execution_view='一次'),
            }]),
            base_full_payload([{
                'identity': {'exchange': 'HK', 'code': '01357', 'name': 'X'},
                'research': base_research(one_liner='二次'),
                'trade_plan': base_plan(change_note='二次'),
                'execution': base_execution(execution_view='二次'),
            }]),
            base_exec_payload({'exchange': 'HK', 'code': '01357'},
                              base_execution(execution_view='快速更新')),
        ]
        for i, pl in enumerate(payloads, 1):
            if 'securities' in pl:
                server.commit_import_full(server.preview_import_full(pl)['token'])
            else:
                server.commit_import_execution(server.preview_import_execution(pl)['token'])

        c = server.get_db()
        try:
            after_trades = [dict(r) for r in c.execute('SELECT * FROM trades').fetchall()]
            step('§O#2 多次导入后 trades 仍=1', len(after_trades) == 1)
            step('§O#3 trade 内容未变化 (price=4.5)', after_trades[0]['price'] == 4.5)
            step('§O#4 trade 内容未变化 (note 原文)', after_trades[0]['note'] == 'baseline trade')
            step('§O#5 execution 累计 ≥ 3 条',
                 c.execute('SELECT COUNT(*) c FROM execution_reviews').fetchone()['c'] >= 3)
        finally:
            c.close()
    finally:
        cleanup_tmp(path)


# ============ §P 静态契约：常量 / 端点 / 注释边界 ============
def test_p_static_contract():
    print('\n§P 静态契约扫描（v1.0.7 边界 / 路由 / 常量）')
    server_py = open(os.path.join(ROOT, 'app', 'server.py'), encoding='utf-8').read()
    app_js = open(os.path.join(ROOT, 'app', 'static', 'app.js'), encoding='utf-8').read()
    index_html = open(os.path.join(ROOT, 'app', 'static', 'index.html'), encoding='utf-8').read()

    # v1.0.10：当前版本号契约随版本升级前移（test_v107 自身语义不变，仅契约值更新）。
    step('§P#1 TARGET_SCHEMA_VERSION=1.0.10',
         "'1.0.10'" in server_py and "TARGET_SCHEMA_VERSION = '1.0.10'" in server_py)
    step('§P#2 server_version 头=1.0.10',
         "server_version = 'Workbench/1.0.10'" in server_py)
    step('§P#3 IMPORT_FORMAT_FULL 常量',
         "IMPORT_FORMAT_FULL = 'ah-workbench-import'" in server_py)
    step('§P#4 IMPORT_FORMAT_EXEC_ONLY 常量',
         "IMPORT_FORMAT_EXEC_ONLY = 'ah-workbench-execution'" in server_py)
    step('§P#5 preview_import_full 函数',
         "def preview_import_full(payload):" in server_py)
    # v1.0.8：commit 必须携带服务端 preview token，并单独接收状态确认参数。
    step('§P#6 commit_import_full 函数（token + confirmed_status_changes）',
         "def commit_import_full(token, confirmed_status_changes=None):" in server_py)
    step('§P#7 preview_import_execution 函数',
         "def preview_import_execution(payload):" in server_py)
    step('§P#8 commit_import_execution 函数',
         "def commit_import_execution(token):" in server_py)

    step('§P#9 路由 /api/import/preview',
         "['api', 'import', 'preview']" in server_py)
    step('§P#10 路由 /api/import/commit',
         "['api', 'import', 'commit']" in server_py)
    step('§P#11 路由 /api/import/execution/preview',
         "['api', 'import', 'execution', 'preview']" in server_py)
    step('§P#12 路由 /api/import/execution/commit',
         "['api', 'import', 'execution', 'commit']" in server_py)

    # 边界注释
    step('§P#13 注释明确"不修改数据库结构"',
         '不修改数据库结构' in server_py or '不允许 importer 触发' in server_py)
    step('§P#14 注释明确 "append-only" 与 "不修改历史"',
         'append-only' in server_py and '不留半完成状态' in server_py)
    step('§P#15 注释明确"不在导入层修改 trades"',
         'trades' in server_py and '不在导入层修改' in server_py)

    # 前端
    step('§P#16 index.html 包含"导入与更新"导航',
         '导入与更新' in index_html and 'data-nav="import"' in index_html)
    step('§P#17 app.js 含 renderImportLanding',
         'function renderImportLanding(' in app_js)
    step('§P#18 app.js 含 renderImportFullPreview',
         'function renderImportFullPreview(' in app_js)
    step('§P#19 app.js 含 routeInfo 识别 import',
         "'#/import'" in app_js and "'#/import/research'" in app_js and "'#/import/execution'" in app_js)


# ============ 入口 ============
if __name__ == '__main__':
    print('=== v1.0.7 导入与更新 ===')
    test_a_single_full_import()
    test_b_batch_import()
    test_c_existing_recognize()
    test_d_research_unchanged()
    test_e_research_changed()
    test_f_plan_unchanged()
    test_g_plan_changed()
    test_h_execution_append_only()
    test_i_quick_execution_only()
    test_j_quick_execution_missing_security()
    test_k_status_change_required_confirm()
    test_l_invalid_payloads_rejected()
    test_m_rollback_on_commit_failure()
    test_n_execution_ledger_atomic()
    test_o_trades_untouched()
    test_p_static_contract()
    print()
    print('=== 总结 ===')
    print('FAIL_COUNT =', FAIL_COUNT)
    print('TOTAL =', TOTAL)
    if FAIL_COUNT == 0:
        print('ALL TESTS PASS')
    else:
        print('FAILED')
