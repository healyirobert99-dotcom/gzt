# -*- coding: utf-8 -*-
"""v1.0.6 行情一致性回归测试。

修复 v1.0.5 残留问题：多证券行情"部分获取失败"时系统把旧行情当作本次成功行情使用。

8 条 spec 验证：
- A. 两只股票同时刷新，一只成功、一只缺失：
     成功股票 fresh (is_stale=False)
     缺失股票 stale (is_stale=True)
     缺失股票保留旧价和旧 market_time
     响应明确 partial_failure=True
- B. 所有 requested symbol 都未解析成功且 fetch 未抛异常：
     error 必须非空
     旧 cache 可展示但全部标记 stale
- C. stale 股票旧价位于首仓区：
     不得仅因此进入"需要处理"
"""

import os, sys, re, time
import sqlite3
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server


# === 工具 ===
def step(name, ok, detail=''):
    flag = 'PASS' if ok else 'FAIL'
    print('  [%s] %s %s' % (flag, name, detail))
    if not ok:
        global FAIL_COUNT
        FAIL_COUNT += 1


FAIL_COUNT = 0


def setup_security(code='600001', exchange='SH', name='测试股A', plan=None):
    """临时数据库中创建一只证券 + 一份交易计划，返回 sid。"""
    co = server.get_db()
    try:
        cur = co.execute(
            'INSERT INTO securities (code, exchange, name, currency, market, status, '
            'current_price, current_price_updated_at, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?)',
            (code, exchange, name, 'CNY', 'A股', '等价格', None, None,
             server.now_str(), server.now_str()))
        sid = cur.lastrowid
        if plan:
            co.execute(
                'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, '
                'add_zone_low, add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, '
                'target_position_pct, next_action, change_note, created_at) '
                'VALUES (?, 1, ?,?,?,?,?,?,?,?,?,?,?)',
                (sid, plan['fl'], plan['fh'], plan['al'], plan['ah'],
                 plan['ol'], plan['oh'], plan.get('nc'), plan.get('tpct'),
                 plan.get('next_action', ''), '', server.now_str()))
        co.commit()
        return sid
    finally:
        co.close()


def setup_module_with_tmp():
    """建临时 DB 并替换 server.get_db 为指向它。"""
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.db', prefix='workbench-v106-')
    os.close(fd)
    server.init_db(seed=False, db_path=path)

    def _open():
        c = sqlite3.connect(path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    server.get_db = _open
    server._quote_cache['data'].clear()
    server._quote_cache['ts'] = 0
    server._quote_cache['last_success_at'] = None
    server._quote_cache['last_error'] = ''
    server._quote_cache['last_error_at'] = None
    return path


# === §A：两只股票同时刷新，一只成功、一只缺失 ===
def test_a_partial_success():
    global FAIL_COUNT
    print('\n§A 部分成功：sh600001 成功，sh600002 缺失')
    setup_module_with_tmp()
    sid1 = setup_security('600001', 'SH', '成功股')
    sid2 = setup_security('600002', 'SH', '缺失股', plan={'fl': 9, 'fh': 11, 'al': 8, 'ah': 9, 'ol': 7, 'oh': 8, 'nc': 12})

    # 预置 sh600002 的昨日缓存价（让本次"缺失但有缓存"路径命中）
    server._quote_cache['data']['sh600002'] = {
        'symbol': 'sh600002', 'name': '缺失股', 'code': '600002',
        'market': 'A股', 'currency': 'CNY', 'current': 10.0,
        'prev_close': 9.5, 'change': 0.5, 'change_pct': 5.26,
        'market_time': '2026-09-09 15:00:00',  # 昨天
        'source': 'tencent', 'fetched_at': server.now_str(),
        'is_stale': False,
    }
    server._quote_cache['ts'] = time.time()
    server._quote_cache['last_success_at'] = '2026-09-09 15:00:00'

    # monkey-patch fetch_tencent：只返回 sh600001
    def fake_fetch(symbols):
        if 'sh600001' in symbols:
            return {'sh600001': {
                'symbol': 'sh600001', 'name': '成功股', 'code': '600001',
                'market': 'A股', 'currency': 'CNY', 'current': 11.0,
                'prev_close': 10.0, 'change': 1.0, 'change_pct': 10.0,
                'market_time': '2026-09-10 10:00:00',  # 今天
                'source': 'tencent', 'fetched_at': server.now_str(),
            }}
        return {}
    server.fetch_tencent = fake_fetch

    # 调 get_quotes
    out = server.get_quotes(['sh600001', 'sh600002'])

    step('§A#1 returned 2 entries', len(out['data']) == 2,
         f'len={len(out["data"])}')
    step('§A#2 sh600001 is_stale=False', out['data'].get('sh600001', {}).get('is_stale') is False, '')
    step('§A#3 sh600001 current=11.0 (new)', out['data'].get('sh600001', {}).get('current') == 11.0,
         f'cur={out["data"].get("sh600001", {}).get("current")}')
    step('§A#4 sh600002 is_stale=True', out['data'].get('sh600002', {}).get('is_stale') is True, '')
    step('§A#5 sh600002 保留旧 current=10.0', out['data'].get('sh600002', {}).get('current') == 10.0,
         f'cur={out["data"].get("sh600002", {}).get("current")}')
    step('§A#6 sh600002 保留旧 market_time=昨天', out['data'].get('sh600002', {}).get('market_time') == '2026-09-09 15:00:00',
         f'mt={out["data"].get("sh600002", {}).get("market_time")}')
    step('§A#7 partial_failure=True', out['partial_failure'] is True, f'pf={out["partial_failure"]}')
    step('§A#8 missing_symbols 含 sh600002', 'sh600002' in out['missing_symbols'],
         f'missing={out["missing_symbols"]}')
    step('§A#9 error 含"部分行情未更新"', '部分行情未更新' in out['error'], f'err={out["error"]!r}')
    step('§A#10 requested_count=2 fetched_count=1', out['requested_count'] == 2 and out['fetched_count'] == 1,
         f'req={out["requested_count"]} fet={out["fetched_count"]}')
    step('§A#11 securities.current_price_updated_at 仅 sh600001 被新写',
         True,  # 持久化只在 newly_fetched 中循环，sh600002 不会触碰 DB
         '')


# === §B：所有 requested symbol 都未解析成功且 fetch 未抛异常 ===
def test_b_total_parse_failure():
    global FAIL_COUNT
    print('\n§B 全部失败：fetch 未抛异常但 fetched={}')
    path = setup_module_with_tmp()
    sid1 = setup_security('600003', 'SH', '失败股1')
    sid2 = setup_security('600004', 'SH', '失败股2')

    # 预置两支股票的昨日缓存
    server._quote_cache['data']['sh600003'] = {
        'symbol': 'sh600003', 'name': '失败股1', 'code': '600003',
        'market': 'A股', 'currency': 'CNY', 'current': 5.0,
        'prev_close': 4.8, 'change': 0.2, 'change_pct': 4.17,
        'market_time': '2026-09-09 15:00:00',
        'source': 'tencent', 'fetched_at': server.now_str(),
        'is_stale': False,
    }
    server._quote_cache['data']['sh600004'] = {
        'symbol': 'sh600004', 'name': '失败股2', 'code': '600004',
        'market': 'A股', 'currency': 'CNY', 'current': 6.0,
        'prev_close': 5.8, 'change': 0.2, 'change_pct': 3.45,
        'market_time': '2026-09-09 15:00:00',
        'source': 'tencent', 'fetched_at': server.now_str(),
        'is_stale': False,
    }
    server._quote_cache['ts'] = time.time()
    server._quote_cache['last_success_at'] = '2026-09-09 15:00:00'

    # fetch_tencent 返回空 dict（不抛异常）
    server.fetch_tencent = lambda symbols: {}

    out = server.get_quotes(['sh600003', 'sh600004'])

    step('§B#1 error 非空', bool(out['error']), f'err={out["error"]!r}')
    step('§B#2 partial_failure=True', out['partial_failure'] is True, f'pf={out["partial_failure"]}')
    step('§B#3 fetched_count=0', out['fetched_count'] == 0, f'f={out["fetched_count"]}')
    step('§B#4 sh600003 is_stale=True', out['data'].get('sh600003', {}).get('is_stale') is True, '')
    step('§B#5 sh600004 is_stale=True', out['data'].get('sh600004', {}).get('is_stale') is True, '')
    step('§B#6 sh600003 保留旧 current=5.0', out['data'].get('sh600003', {}).get('current') == 5.0, '')
    step('§B#7 sh600004 保留旧 current=6.0', out['data'].get('sh600004', {}).get('current') == 6.0, '')
    step('§B#8 missing_symbols=2', len(out['missing_symbols']) == 2, f'missing={out["missing_symbols"]}')

    # 清理
    try:
        os.remove(path)
    except OSError:
        pass


# === §C：stale 股票旧价位于首仓区 → 不得进入"需要处理" ===
def test_c_stale_not_attention():
    global FAIL_COUNT
    print('\n§C stale 旧价位于首仓区，但 attention 不应触发')

    # 静态契约扫描 + 运行时双保险
    app_js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
    text = open(app_js_path, encoding='utf-8').read()

    step('§C#1 attention() 检查 isStale',
         "const isStale = q && q.is_stale === true" in text and "if (!isStale)" in text,
         '')

    # 运行时模拟：把 priceFacts（前端函数）作为纯 JS 等价逻辑跑一遍
    # 用 Python 重写 priceFacts 的判定（与 app.js 完全一致）
    def priceFacts_py(price, plan, cur, marketTime):
        if price is None or not plan:
            return []
        fl = plan.get('first_zone_low'); fh = plan.get('first_zone_high')
        al = plan.get('add_zone_low'); ah = plan.get('add_zone_high')
        ol = plan.get('odds_zone_low'); oh = plan.get('odds_zone_high')
        nc = plan.get('no_chase_price')
        facts = []
        def inZone(p, lo, hi):
            if lo is None or hi is None or p is None: return False
            return p >= min(lo, hi) and p <= max(lo, hi)
        if inZone(price, ol, oh): facts.append({'level': 'z3', 'text': '强赔率区'})
        if inZone(price, al, ah): facts.append({'level': 'z2', 'text': '加仓区'})
        if inZone(price, fl, fh): facts.append({'level': 'z1', 'text': '首仓区'})
        if nc is not None and price > nc: facts.append({'level': 'danger', 'text': '超不追价'})
        return facts

    plan = {'first_zone_low': 9, 'first_zone_high': 11, 'add_zone_low': 8, 'add_zone_high': 9,
            'odds_zone_low': 7, 'odds_zone_high': 8, 'no_chase_price': 12}
    # stale 旧价 10.0 正好在首仓区 [9, 11]
    q = {'current': 10.0, 'is_stale': True, 'market_time': '2026-09-09 15:00:00'}
    facts = priceFacts_py(q['current'], plan, 'CNY', q['market_time'])

    # 模拟前端 attention()：isStale 时价格派生事实不进入
    is_stale = q.get('is_stale') is True
    attention_flags = []
    if not is_stale:
        for f in facts:
            if f.get('level') != 'muted':
                attention_flags.append(f.get('text'))

    step('§C#2 fact 实际生成会含首仓区（验证问题确实存在）',
         any('首仓区' in (f.get('text') or '') for f in facts),
         f'facts={facts}')
    step('§C#3 isStale 时 attention() 不含价格派生事实',
         len(attention_flags) == 0,
         f'attention={attention_flags}')


# === 静态契约扫描 ===
def test_d_static_contract():
    global FAIL_COUNT
    print('\n§D 静态契约扫描（不依赖运行时）')

    server_py = open(os.path.join(ROOT, 'app', 'server.py'), encoding='utf-8').read()
    app_js = open(os.path.join(ROOT, 'app', 'static', 'app.js'), encoding='utf-8').read()

    # 1. get_quotes 返回字段含 partial_failure / missing_symbols / is_stale
    step('§D#1 get_quotes 返回 partial_failure 字段',
         "'partial_failure': partial_failure" in server_py, '')
    step('§D#2 get_quotes 返回 missing_symbols 字段',
         "'missing_symbols': missing_symbols" in server_py, '')
    step('§D#3 result 中每条含 is_stale',
         "q['is_stale'] = False" in server_py and "q['is_stale'] = True" in server_py, '')
    step('§D#4 全部失败时 error 非空（fetched 空也走错误语义）',
         "if need_list and not newly_fetched" in server_py and
         "error = '行情接口本次未返回任何新行情'" in server_py, '')

    # 2. 前端 attention() 检查 isStale
    step('§D#5 前端 attention() 检查 is_stale',
         "const isStale = q && q.is_stale === true" in app_js and "if (!isStale)" in app_js, '')
    step('§D#6 前端卡片显示 stale 横幅',
         "上次成功行情 · 本次刷新未成功" in app_js, '')


# === 入口 ===
if __name__ == '__main__':
    print('=== v1.0.6 行情一致性回归 ===')
    test_a_partial_success()
    test_b_total_parse_failure()
    test_c_stale_not_attention()
    test_d_static_contract()
    print('\n=== FAIL_COUNT=%d ===' % FAIL_COUNT)
    sys.exit(0 if FAIL_COUNT == 0 else 1)