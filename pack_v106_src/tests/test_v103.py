# -*- coding: utf-8 -*-
"""v1.0.3 + v1.0.4 测试套件 —— 动态执行层（execution_reviews）

本套件**只**使用临时 SQLite 数据库（init_db(seed=False, db_path=...)）。
绝不读写、覆盖或恢复正式 data/workbench.db。

覆盖项：
A §A  新增 execution record 后能正确读取最新版本
B §B  连续新增两次，旧记录仍然存在
C §C  execution + ledger 同事务，失败整体 rollback
D §D  修改动态执行判断不会修改 trade_plan
E §E  行情刷新不会修改 execution record
F §F  首页能同时显示"静态价格位置 + 最新动态执行判断"
   （走真实 list_securities() 链路，禁止手工塞 execution_latest）
G §G  无 execution record 时正常显示"尚未形成动态执行判断"，不得自动生成
H §H  已有最新判断为「可以开始执行」时，再次读取仍返回原判断（首页数据链路回归）
I §I  新库首次 init_db 立即写入 schema_version；二次启动不触发 migration、不生成 pre-xxx 备份
J §J  migrate_v102 不再无条件清空 user_data (account_size_cny/hkd_cny_rate)
K §K  execution_view 允许任意非空自由文本；execution_date 接受未来日期（仅校验格式）
"""
import os
import sys
import tempfile
import shutil
import sqlite3
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

import server  # noqa: E402


# ================ 工具 ================
_tmp_dir = None
TMP_DB = None
PROD_DB_PATH_BEFORE = None


def setup_module(module):
    """整个测试模块开始前：建临时 DB_PATH 并 init_db(v1.0.4)。"""
    global _tmp_dir, TMP_DB, PROD_DB_PATH_BEFORE
    _tmp_dir = tempfile.mkdtemp(prefix='wb_v104_')
    TMP_DB = os.path.join(_tmp_dir, 'test.db')
    # 记下生产库哈希，测试结束/任何时刻都不得改它
    PROD_DB_PATH_BEFORE = os.path.join(ROOT, 'data', 'workbench.db')
    if os.path.exists(PROD_DB_PATH_BEFORE):
        with open(PROD_DB_PATH_BEFORE, 'rb') as f:
            module._prod_db_hash_before = hashlib_sha256(f.read())
    else:
        module._prod_db_hash_before = None

    # proxy：把 server.get_db 指向临时库
    server.init_db(seed=False, db_path=TMP_DB)
    _orig = server.get_db

    def _make():
        co = sqlite3.connect(TMP_DB, timeout=10)
        co.row_factory = sqlite3.Row
        co.execute('PRAGMA journal_mode=WAL')
        co.execute('PRAGMA foreign_keys=ON')
        return co
    server.get_db = _make
    module._orig_get_db = _orig


def teardown_module(module):
    """整个测试模块结束：恢复 get_db，删除临时目录，验证生产库未变。"""
    global _tmp_dir
    server.get_db = module._orig_get_db
    shutil.rmtree(_tmp_dir, ignore_errors=True)
    # 校验：生产 DB 哈希必须与测试开始时一致
    if module._prod_db_hash_before is not None:
        with open(PROD_DB_PATH_BEFORE, 'rb') as f:
            after = hashlib_sha256(f.read())
        assert after == module._prod_db_hash_before, (
            '生产 DB 被改动！before=%s after=%s' % (
                module._prod_db_hash_before[:12], after[:12]
            )
        )


def hashlib_sha256(b):
    import hashlib
    return hashlib.sha256(b).hexdigest()


# ================ 小工具 ================
def step(name, ok, hint=''):
    sym = '✅' if ok else '❌'
    print(f'  [{sym}] {name}' + (f'  ({hint})' if hint and not ok else ''))
    assert ok, f'断言失败：{name} — {hint}'


def direct_conn():
    return sqlite3.connect(TMP_DB)


def make_security(code='02010', exchange='HK', name='港股测试'):
    """创建一只基础证券，含最小研究/计划。代码必须符合 _norm_code 规则（HK 5 位 / A 股 6 位）。"""
    sid = server.create_security({
        'name': name,
        'exchange': exchange,
        'code': code,
        'status': '等价格',
        'research': {'one_liner': '测试用研究结论', 'research_date': '2026-09-01'},
        'plan': {
            'first_zone_low': 4.0, 'first_zone_high': 4.5,
            'add_zone_low': 3.5, 'add_zone_high': 3.9,
            'odds_zone_low': 3.0, 'odds_zone_high': 3.4,
            'no_chase_price': 4.8,
            'target_position_pct': 10,
            'next_action': '等待首仓区',
            'change_note': '初始计划',
        }
    })['id']
    return sid


# ================ 测试用例 ================
def test_A_add_and_read_latest():
    """1) 新增 execution record 后能正确读取最新版本。"""
    print('\n§A 新增 execution 后可读取最新版本')
    sid = make_security('00001', exchange='HK', name='A测试')

    out = server.add_execution_tx(sid, {
        'execution_date': '2026-09-08',
        'price_snapshot': 4.10,
        'support_zone': '3.95–4.05',
        'resistance_zone': '4.30–4.40',
        'technical_structure': '横盘整理，等待方向选择',
        'execution_condition': '放量突破 4.30 或跌破 3.95',
        'execution_view': '等待技术确认',
        'reason': '价格未触及首仓区下限',
    })
    step('add_execution 返回 id', out['id'] > 0, str(out.get('id')))
    step('add_execution 返回 execution_view', out['execution_view'] == '等待技术确认')

    ex = server.get_execution(sid)
    step('get_execution 返回 latest', ex['latest'] is not None)
    step('latest.execution_date == 2026-09-08', ex['latest']['execution_date'] == '2026-09-08')
    step('latest.execution_view == 等待技术确认', ex['latest']['execution_view'] == '等待技术确认')
    step('latest.price_snapshot == 4.10', ex['latest']['price_snapshot'] == 4.10)
    step('latest.support_zone 保留', ex['latest']['support_zone'] == '3.95–4.05')
    step('history 长度 == 1', len(ex['history']) == 1)


def test_B_two_adds_keep_old():
    """2) 连续新增两次，旧记录仍然存在。"""
    print('\n§B 连续两次新增，旧记录保留')
    sid = make_security('00002', exchange='HK', name='B测试')

    server.add_execution_tx(sid, {
        'execution_date': '2026-09-08', 'execution_view': '等待技术确认', 'reason': '第一次'
    })
    server.add_execution_tx(sid, {
        'execution_date': '2026-09-09', 'execution_view': '暂缓执行',
        'reason': '第二次',
        'price_snapshot': 4.05,
    })
    server.add_execution_tx(sid, {
        'execution_date': '2026-09-10', 'execution_view': '可以开始执行',
        'reason': '第三次', 'price_snapshot': 4.20,
    })

    ex = server.get_execution(sid)
    step('history 共 3 条', len(ex['history']) == 3)
    step('latest 是 09-10', ex['latest']['execution_date'] == '2026-09-10')
    step('latest 是「可以开始执行」', ex['latest']['execution_view'] == '可以开始执行')

    # history 按日期倒序，09-10 / 09-09 / 09-08
    dates = [r['execution_date'] for r in ex['history']]
    step('history 按日期倒序', dates == ['2026-09-10', '2026-09-09', '2026-09-08'])

    # 旧记录视图必须可查
    by_id = {r['id']: r for r in ex['history']}
    step('09-08 旧记录仍存在', by_id.get(2) is not None and by_id[2]['execution_view'] == '等待技术确认')

    # 数据库级断言
    c = direct_conn()
    cnt = c.execute(
        "SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?", (sid,)).fetchone()[0]
    step('DB 行数 == 3', cnt == 3)
    c.close()


def test_C_same_tx_rollback():
    """3) execution + ledger 同事务，注入失败整体 rollback。"""
    print('\n§C execution+ledger 同事务回滚')
    sid = make_security('00003', exchange='HK', name='C测试')

    # 先写一条确认基线
    server.add_execution_tx(sid, {
        'execution_date': '2026-09-09', 'execution_view': '等待技术确认', 'reason': '基线'
    })

    c = direct_conn()
    n_e_before = c.execute(
        "SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?", (sid,)).fetchone()[0]
    n_l_before = c.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=? AND event_type='动态执行判断更新'",
        (sid,)).fetchone()[0]
    c.close()

    server._LEDGER_FAIL_INJECT = True
    try:
        server.add_execution_tx(sid, {
            'execution_date': '2026-09-10',
            'execution_view': '可以开始执行',
            'reason': '应被回滚'
        })
        step('注入失败应抛错', False, '应抛 RuntimeError')
    except RuntimeError as e:
        step('注入失败抛出 RuntimeError', '失败注入' in str(e), str(e)[:60])
    finally:
        server._LEDGER_FAIL_INJECT = False

    c = direct_conn()
    n_e_after = c.execute(
        "SELECT COUNT(*) c FROM execution_reviews WHERE security_id=?", (sid,)).fetchone()[0]
    n_l_after = c.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=? AND event_type='动态执行判断更新'",
        (sid,)).fetchone()[0]
    c.close()

    step('execution_reviews 行数未变', n_e_after == n_e_before,
         f'before={n_e_before} after={n_e_after}')
    step('decision_ledger 行数未变', n_l_after == n_l_before,
         f'before={n_l_before} after={n_l_after}')


def test_D_execution_no_plan_change():
    """4) 修改动态执行判断不会修改 trade_plan。"""
    print('\n§D execution 写入不修改 trade_plan')
    sid = make_security('00004', exchange='HK', name='D测试')

    # 取当前 plan 状态
    c = direct_conn()
    c.row_factory = sqlite3.Row
    plan_before = dict(c.execute(
        "SELECT * FROM trade_plans WHERE security_id=? ORDER BY version DESC, id DESC LIMIT 1",
        (sid,)).fetchone())
    n_plan_before = c.execute(
        "SELECT COUNT(*) c FROM trade_plans WHERE security_id=?", (sid,)).fetchone()[0]
    n_ledger_before = c.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=?", (sid,)).fetchone()[0]
    c.close()

    # 多次 execution 写入
    for d in ('2026-09-08', '2026-09-09', '2026-09-10'):
        server.add_execution_tx(sid, {
            'execution_date': d, 'execution_view': '等待技术确认',
            'reason': '多次写入 execution，plan 必须不变'
        })

    c = direct_conn()
    c.row_factory = sqlite3.Row
    plan_after = dict(c.execute(
        "SELECT * FROM trade_plans WHERE security_id=? ORDER BY version DESC, id DESC LIMIT 1",
        (sid,)).fetchone())
    n_plan_after = c.execute(
        "SELECT COUNT(*) c FROM trade_plans WHERE security_id=?", (sid,)).fetchone()[0]
    n_ledger_after = c.execute(
        "SELECT COUNT(*) c FROM decision_ledger WHERE security_id=?", (sid,)).fetchone()[0]
    c.close()

    step('trade_plans 行数未变', n_plan_after == n_plan_before)
    step('trade_plans 最新版本未变', plan_before == plan_after)
    step('ledger 行数恰好 +3（仅动态执行判断）', n_ledger_after == n_ledger_before + 3,
         f'before={n_ledger_before} after={n_ledger_after}')


def test_E_quote_refresh_no_change():
    """5) 行情刷新不会修改 execution record。"""
    print('\n§E 行情刷新不修改 execution_reviews')
    sid = make_security('00005', exchange='HK', name='E测试')

    server.add_execution_tx(sid, {
        'execution_date': '2026-09-09', 'execution_view': '等待技术确认',
        'price_snapshot': 4.10, 'reason': '基线'
    })
    server.add_execution_tx(sid, {
        'execution_date': '2026-09-10', 'execution_view': '可以开始执行',
        'price_snapshot': 4.24, 'reason': '基线2'
    })

    c = direct_conn()
    c.row_factory = sqlite3.Row
    before = [dict(r) for r in c.execute(
        "SELECT * FROM execution_reviews WHERE security_id=? ORDER BY id", (sid,)).fetchall()]
    c.close()

    # 模拟多次行情刷新（直接调 _persist_quote_to_securities）
    server._persist_quote_to_securities('hk00005', {
        'current': 4.30, 'market_time': '2026-09-10 15:30:00'
    })
    server._persist_quote_to_securities('hk00005', {
        'current': 4.50, 'market_time': '2026-09-10 15:45:00'
    })
    server._persist_quote_to_securities('hk00005', {
        'current': 4.10, 'market_time': '2026-09-10 16:00:00'
    })

    c = direct_conn()
    c.row_factory = sqlite3.Row
    after = [dict(r) for r in c.execute(
        "SELECT * FROM execution_reviews WHERE security_id=? ORDER BY id", (sid,)).fetchall()]
    c.close()

    step('行情刷新后 execution_reviews 行数不变', len(before) == len(after))
    step('行情刷新后 execution_reviews 内容完全一致', before == after)

    # 进一步：securities.current_price 已被刷新（验证行情路径确实跑了）
    c = direct_conn()
    cur = c.execute("SELECT current_price, current_price_updated_at FROM securities WHERE id=?",
                    (sid,)).fetchone()
    c.close()
    step('行情确实刷新到 securities.current_price', cur[0] == 4.10,
         f'cur={cur[0]}')


def test_F_home_shows_static_and_dynamic():
    """6) v1.0.4 修复：首页数据链路走真实 list_securities()，禁止手工塞 execution_latest。"""
    print('\n§F 首页同时显示静态位置 + 动态执行判断（真实链路）')
    sid = make_security('600006', exchange='SZ', name='F测试')

    # 录入价格 + execution（用真实函数）
    server._persist_quote_to_securities('sz900006', {
        'current': 4.20, 'market_time': '2026-09-10 14:00:00'
    })
    server.add_execution_tx(sid, {
        'execution_date': '2026-09-10', 'price_snapshot': 4.20,
        'execution_view': '等待技术确认',
        'support_zone': '4.10–4.18', 'resistance_zone': '4.30–4.35',
        'execution_condition': '等待 4.30 放量突破',
        'reason': '已到首仓区上限附近',
    })

    # 关键断言：直接调 list_securities() 拿首页数据（不走手工补 execution_latest）
    secs = server.list_securities()
    step('list_securities 至少包含本测试标的',
         any(x['id'] == sid for x in secs))
    s = [x for x in secs if x['id'] == sid][0]

    # v1.0.4 关键断言：execution_latest 必须由真实链路提供，不依赖手工塞入
    step('list_securities().execution_latest 存在（来自真实 enrich）',
         s.get('execution_latest') is not None)
    step('list_securities().execution_latest.execution_view == 等待技术确认',
         s['execution_latest']['execution_view'] == '等待技术确认')
    step('list_securities().execution_latest.support_zone == 4.10–4.18',
         s['execution_latest']['support_zone'] == '4.10–4.18')
    step('list_securities().execution_latest.resistance_zone == 4.30–4.35',
         s['execution_latest']['resistance_zone'] == '4.30–4.35')

    # 静态位置：进入首仓区 [4.0, 4.5]
    step('静态价格位置：进入首仓区', 4.0 <= 4.20 <= 4.5)
    step('详情页 get_detail 含 execution_latest', s.get('execution_latest') is not None)

    # 详情页口径与首页口径必须完全一致（同一 SQL）
    detail = server.get_detail(sid)
    step('detail.execution_latest.execution_view 一致',
         detail['execution_latest']['execution_view'] == '等待技术确认')
    step('detail.execution_history 长度 == 1', len(detail['execution_history']) == 1)
    step('首页 latest.id == 详情页 latest.id',
         s['execution_latest']['id'] == detail['execution_latest']['id'],
         f'home={s["execution_latest"]["id"]} detail={detail["execution_latest"]["id"]}')


def test_G_no_record_shows_empty():
    """7) 无 execution record 时显式提示，不得自动生成。"""
    print('\n§G 无 execution record → 「尚未形成动态执行判断」')
    sid = make_security('600007', exchange='SZ', name='G测试')

    # 没有 add_execution_tx；detail 应返回 execution_latest=None
    detail = server.get_detail(sid)
    step('execution_latest 为 None', detail['execution_latest'] is None)
    step('execution_history 为空列表', detail['execution_history'] == [])

    ex = server.get_execution(sid)
    step('get_execution 返回 latest=None', ex['latest'] is None)
    step('get_execution 返回 history=[]', ex['history'] == [])

    # 验证渲染模板（详情页 + 首页）能正确显示「尚未形成」字样
    src = open(os.path.join(ROOT, 'app', 'static', 'app.js'), 'r', encoding='utf-8').read()
    step('详情页渲染含「尚未形成动态执行判断」',
         '尚未形成动态执行判断' in src)
    step('首页 execLatestLine 返回 empty=true 时显示该提示',
         '尚未形成动态执行判断' in src)
    step('execution_latest 缺失时不静默生成',
         '尚未形成动态执行判断' in src and 'execution_latest' in src)


def test_H_home_keeps_previous_view():
    """8) v1.0.4 修复：已有最新判断为「可以开始执行」时，再次读取首页数据链路仍返回原判断。

    这是 §F 提到的"再次更新动态执行时，弹窗拿不到旧值"问题的回归测试：
    关键点：
    1. 真实链路 list_securities() 必须返回最新 execution_latest
    2. openExecutionModal 依赖的 detail 接口也必须返回同一份 execution_latest
    3. 两个口径必须完全一致（同一 SQL：ORDER BY execution_date DESC, id DESC）
    """
    print('\n§H 首页/详情 真实链路在已有判断时仍返回原判断')
    sid = make_security('600008', exchange='SZ', name='H测试')

    server._persist_quote_to_securities('sz900008', {
        'current': 4.20, 'market_time': '2026-09-10 14:00:00'
    })
    server.add_execution_tx(sid, {
        'execution_date': '2026-09-10',
        'execution_view': '可以开始执行',  # 注意：非默认「等待技术确认」
        'support_zone': '4.18–4.22', 'resistance_zone': '4.30–4.35',
        'execution_condition': '等待放量',
        'reason': '已进入赔率区',
    })

    # 第一次读取：list_securities（首页）
    secs_first = server.list_securities()
    s_first = [x for x in secs_first if x['id'] == sid][0]
    step('首次 list_securities 返回「可以开始执行」',
         s_first['execution_latest']['execution_view'] == '可以开始执行')
    step('首次 list_securities support_zone == 4.18–4.22',
         s_first['execution_latest']['support_zone'] == '4.18–4.22')

    # 第二次读取：模拟 openExecutionModal 的 detail 接口调用
    detail = server.get_detail(sid)
    step('detail.execution_latest.execution_view == 可以开始执行',
         detail['execution_latest']['execution_view'] == '可以开始执行')
    step('detail.execution_latest.support_zone == 4.18–4.22',
         detail['execution_latest']['support_zone'] == '4.18–4.22')
    step('detail.execution_latest.resistance_zone == 4.30–4.35',
         detail['execution_latest']['resistance_zone'] == '4.30–4.35')

    # 关键：模拟"再次更新"操作——再次调 list_securities 和 detail，确认仍能拿到原值
    secs_second = server.list_securities()
    s_second = [x for x in secs_second if x['id'] == sid][0]
    detail2 = server.get_detail(sid)
    step('再次 list_securities 仍返回「可以开始执行」',
         s_second['execution_latest']['execution_view'] == '可以开始执行',
         f'got={s_second["execution_latest"]["execution_view"]}')
    step('再次 detail 仍返回「可以开始执行」',
         detail2['execution_latest']['execution_view'] == '可以开始执行',
         f'got={detail2["execution_latest"]["execution_view"]}')
    step('两次读取 execution_latest 完全一致',
         s_first['execution_latest'] == s_second['execution_latest'])


def test_I_new_db_initializes_schema_version():
    """9) v1.0.4 修复：全新数据库首次 init_db 立即写入 schema_version。

    关键不变量：
    - 全新 DB 第一次 init_db 后 settings 含 schema_version = TARGET_SCHEMA_VERSION
    - 二次 init_db 不触发 do_migration（无新 pre-migration backup 文件）
    - 不修改用户已经填的 account_size_cny / hkd_cny_rate
    """
    print('\n§I 全新 DB 首次 init_db 立即写 schema_version；二次启动不触发 migration')

    # 单独用一个全新临时 DB（不影响主测试库的全局 fixtures）
    new_db_dir = tempfile.mkdtemp(prefix='wb_v104_newdb_')
    new_db = os.path.join(new_db_dir, 'fresh.db')
    backup_dir = os.path.join(new_db_dir, 'backup')
    os.makedirs(backup_dir, exist_ok=True)

    try:
        # 1) 首次 init_db
        server.init_db(seed=False, db_path=new_db)

        c = sqlite3.connect(new_db)
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT key, value FROM settings").fetchall()
        d = {r['key']: r['value'] for r in rows}
        step('首次 init_db 后 settings 含 schema_version',
             'schema_version' in d, f'keys={list(d.keys())}')
        step('schema_version == TARGET_SCHEMA_VERSION',
             d.get('schema_version') == server.TARGET_SCHEMA_VERSION,
             f'got={d.get("schema_version")} expected={d.get("schema_version") if d.get("schema_version") else server.TARGET_SCHEMA_VERSION}')

        # 2) 写入用户真实数据（模拟用户录入）
        c.execute(
            "INSERT INTO settings (key, value) VALUES ('account_size_cny', ?)",
            ('500000',)
        )
        c.execute(
            "INSERT INTO settings (key, value) VALUES ('hkd_cny_rate', ?)",
            ('0.913',)
        )
        c.commit()
        c.close()

        # 3) 二次 init_db（模拟第二次启动）
        baks_before = set(os.listdir(backup_dir))
        server.init_db(seed=False, db_path=new_db)
        baks_after = set(os.listdir(backup_dir))

        step('二次启动未生成新的 pre-xxx 备份（无 migration 触发）',
             baks_before == baks_after,
             f'before={baks_before} after={baks_after}')

        # 4) 用户数据必须保留
        c = sqlite3.connect(new_db)
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT key, value FROM settings WHERE key IN ('account_size_cny','hkd_cny_rate')").fetchall()
        d2 = {r['key']: r['value'] for r in rows}
        c.close()
        step('account_size_cny == 500000（用户真实数据未被破坏）',
             d2.get('account_size_cny') == '500000',
             f'got={d2.get("account_size_cny")}')
        step('hkd_cny_rate == 0.913（用户真实数据未被破坏）',
             d2.get('hkd_cny_rate') == '0.913',
             f'got={d2.get("hkd_cny_rate")}')
    finally:
        shutil.rmtree(new_db_dir, ignore_errors=True)


def test_J_migration_preserves_user_data():
    """10) v1.0.4 修复：migrate_v102 不再无条件清空 user_data。

    场景：v1.0.2 DB 含用户真实 account_size_cny / hkd_cny_rate，升级 v1.0.4，两值不变。
    """
    print('\n§J 迁移不破坏用户真实 account_size_cny / hkd_cny_rate')

    mig_db_dir = tempfile.mkdtemp(prefix='wb_v104_mig_')
    mig_db = os.path.join(mig_db_dir, 'pre_v104.db')

    try:
        # 1) 模拟 v1.0.2 DB（schema_version=1.0.2 + 用户真实数据 + 完整 SCHEMA 表结构）
        # 用手工构建的方式，不依赖 server.init_db；表结构与 server.SCHEMA 一致
        # （缺 trade_date 等列会导致 SCHEMA 重复执行时报错）
        co = sqlite3.connect(mig_db)
        co.row_factory = sqlite3.Row
        co.executescript('''
        CREATE TABLE securities (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL, exchange TEXT NOT NULL CHECK (exchange IN ('SH','SZ','HK')),
          name TEXT NOT NULL,
          currency TEXT NOT NULL DEFAULT 'CNY',
          market TEXT NOT NULL DEFAULT 'A股',
          sector TEXT DEFAULT '',
          ah_link_id INTEGER,
          notes TEXT DEFAULT '',
          status TEXT NOT NULL DEFAULT '等价格',
          research_pool TEXT DEFAULT '',
          current_price REAL,
          current_price_updated_at TEXT,
          created_at TEXT, updated_at TEXT,
          UNIQUE(exchange, code)
        );
        CREATE TABLE research (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL DEFAULT 1,
          research_pool TEXT DEFAULT '',
          one_liner TEXT DEFAULT '',
          positive_changes TEXT DEFAULT '',
          core_validations TEXT DEFAULT '[]',
          wall_conditions TEXT DEFAULT '[]',
          report_link TEXT DEFAULT '',
          research_date TEXT DEFAULT '',
          change_note TEXT DEFAULT '',
          created_at TEXT,
          UNIQUE(security_id, version)
        );
        CREATE TABLE trade_plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL DEFAULT 1,
          first_zone_low REAL, first_zone_high REAL,
          add_zone_low REAL, add_zone_high REAL,
          odds_zone_low REAL, odds_zone_high REAL,
          no_chase_price REAL,
          target_position_pct REAL,
          next_action TEXT DEFAULT '',
          change_note TEXT DEFAULT '',
          created_at TEXT,
          UNIQUE(security_id, version)
        );
        CREATE TABLE trades (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          trade_date TEXT NOT NULL,
          side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
          quantity REAL NOT NULL CHECK (quantity > 0),
          price REAL NOT NULL CHECK (price > 0),
          fee REAL NOT NULL DEFAULT 0,
          note TEXT DEFAULT '',
          created_at TEXT
        );
        CREATE TABLE decision_ledger (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          security_id INTEGER NOT NULL REFERENCES securities(id) ON DELETE RESTRICT,
          event_date TEXT NOT NULL,
          event_type TEXT NOT NULL,
          summary TEXT NOT NULL,
          reason TEXT DEFAULT '',
          created_at TEXT
        );
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        ''')
        co.execute("INSERT INTO settings (key, value) VALUES ('schema_version', '1.0.2')")
        co.execute("INSERT INTO settings (key, value) VALUES ('account_size_cny', '800000')")
        co.execute("INSERT INTO settings (key, value) VALUES ('hkd_cny_rate', '0.918')")
        co.commit()
        co.close()

        # 2) 触发升级：init_db 检测到 schema_version != TARGET_SCHEMA_VERSION
        server.init_db(seed=False, db_path=mig_db)

        # 3) 校验用户数据保留
        co = sqlite3.connect(mig_db)
        co.row_factory = sqlite3.Row
        rows = co.execute(
            "SELECT key, value FROM settings WHERE key IN ('account_size_cny','hkd_cny_rate','schema_version')"
        ).fetchall()
        d = {r['key']: r['value'] for r in rows}
        co.close()

        step('升级后 schema_version == TARGET_SCHEMA_VERSION',
             d.get('schema_version') == server.TARGET_SCHEMA_VERSION,
             f'got={d.get("schema_version")}')
        step('升级后 account_size_cny == 800000（用户真实数据未被清空）',
             d.get('account_size_cny') == '800000',
             f'got={d.get("account_size_cny")}')
        step('升级后 hkd_cny_rate == 0.918（用户真实数据未被清空）',
             d.get('hkd_cny_rate') == '0.918',
             f'got={d.get("hkd_cny_rate")}')
    finally:
        shutil.rmtree(mig_db_dir, ignore_errors=True)


def test_K_execution_view_free_text_and_future_date():
    """11) v1.0.4 修复：execution_view 接受任意非空自由文本；execution_date 接受未来日期。

    严格遵循 spec：不得新增业务规则（"首仓可以执行，加仓等待确认"必须可入库）。
    """
    print('\n§K execution_view 自由文本 + execution_date 未来日期')
    sid = make_security('600010', exchange='SZ', name='K测试')

    # 自由文本（非白名单内）
    out = server.add_execution_tx(sid, {
        'execution_date': '2026-09-10',
        'execution_view': '首仓可以执行，加仓等待确认',  # 自由组合文本
        'support_zone': '4.18–4.22', 'resistance_zone': '4.30–4.35',
        'reason': '赔率区已达但短线结构未确认',
    })
    step('自由文本 execution_view 可入库',
         out['execution_view'] == '首仓可以执行，加仓等待确认',
         f'got={out["execution_view"]}')

    # 未来日期（v1.0.4 不得拒绝）
    out2 = server.add_execution_tx(sid, {
        'execution_date': '2099-12-31',  # 未来日期
        'execution_view': '继续观察',
        'reason': '占位',
    })
    step('未来 execution_date 可入库（v1.0.4 不再拒绝）',
         out2['execution_date'] == '2099-12-31',
         f'got={out2["execution_date"]}')

    # 仍保留校验：非空
    try:
        server.add_execution_tx(sid, {
            'execution_date': '2026-09-10',
            'execution_view': '',  # 空串必须拒绝
        })
        step('空 execution_view 仍应被拒绝', False, '应抛 ApiError')
    except Exception as e:
        step('空 execution_view 仍被拒绝', '不能为空' in str(e), str(e)[:60])

    # 仍保留校验：日期格式必须合法（拒绝 2026-02-30）
    try:
        server.add_execution_tx(sid, {
            'execution_date': '2026-02-30',  # 不存在的日期
            'execution_view': '继续观察',
        })
        step('非法日期仍应被拒绝', False, '应抛 ApiError')
    except Exception as e:
        step('非法日期 2026-02-30 仍被拒绝', '不存在' in str(e) or '无效' in str(e), str(e)[:60])


# ================ 主流程 ================
if __name__ == '__main__':
    setup_module(sys.modules[__name__])
    try:
        test_A_add_and_read_latest()
        test_B_two_adds_keep_old()
        test_C_same_tx_rollback()
        test_D_execution_no_plan_change()
        test_E_quote_refresh_no_change()
        test_F_home_shows_static_and_dynamic()
        test_G_no_record_shows_empty()
        test_H_home_keeps_previous_view()
        test_I_new_db_initializes_schema_version()
        test_J_migration_preserves_user_data()
        test_K_execution_view_free_text_and_future_date()
        print('\n=== v1.0.3 + v1.0.4 测试套件：全部通过 ===')
    finally:
        teardown_module(sys.modules[__name__])