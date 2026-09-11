#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真实腾讯行情 integration test（v1.0.2）。

**与主套件拆分**：
- 测试腾讯免费接口 (https://qt.gtimg.cn/q=...) 的真实响应是否能被解析。
- 网络不可用时本测试整体跳过（不失败），不影响本地账本完整性测试。
- 使用临时 DB，不读写真实 data/workbench.db。

运行：
  python tests/test_integration_quote.py

依赖：app/server.py（仅标准库）、外网（可失败但不致命）
"""
import sys
import os
import json
import sqlite3
import tempfile
import http.client
import threading
import shutil
import urllib.error
import urllib.request
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server  # noqa: E402

PASS = '✅'
FAIL = '❌'
SKIP = '⏭'
results = {'pass': 0, 'fail': 0, 'skip': 0, 'details': []}


def step(name, ok, detail='', skip=False):
    tag = SKIP if skip else (PASS if ok else FAIL)
    print(f'  {tag} {name}{": " + detail if detail else ""}')
    if skip:
        results['skip'] += 1
    elif ok:
        results['pass'] += 1
    else:
        results['fail'] += 1
    results['details'].append((ok, name, detail, skip))


def section(title):
    print()
    print('=== ' + title + ' ===')


# 临时 DB
TMP_ROOT = tempfile.mkdtemp(prefix='wb_intg_')
TMP_DB = os.path.join(TMP_ROOT, 'workbench.db')
server.init_db(seed=False, db_path=TMP_DB)


class _DBProxy:
    def __init__(self, target):
        self.target = target
        self._orig = server.get_db
        server.get_db = lambda: self._make()
    def _make(self):
        c = sqlite3.connect(self.target, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA foreign_keys=ON')
        return c
    def restore(self):
        server.get_db = self._orig

proxy = _DBProxy(TMP_DB)

# 准备一只 A 股 + 一只港股
sid_a = server.create_security({
    'name': '道通集成', 'exchange': 'SH', 'code': '688208',
    'sector': '汽车 / 测试', 'status': '可交易',
    'research': {}, 'plan': {}
})['id']
sid_h = server.create_security({
    'name': '美图集成', 'exchange': 'HK', 'code': '01357',
    'sector': '消费', 'status': '等价格',
    'research': {}, 'plan': {}
})['id']


# ============== 网络可达性检测 ==============
section('0. 网络可达性检测（不可达则整体跳过本套件）')

network_ok = False
try:
    req = urllib.request.Request('https://qt.gtimg.cn/q=sh688208', headers={
        'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'})
    raw = urllib.request.urlopen(req, timeout=5).read()
    if b'v_sh688208' in raw:
        network_ok = True
except Exception as e:
    print(f'  网络不可达：{type(e).__name__}: {e}')
    network_ok = False

step('可达腾讯 qt.gtimg.cn', network_ok, '网络不可达时跳过解析测试', skip=not network_ok)


# ============== §1. A 股真实解析 + 回写 + 端到端 ==============
section('1. A 股真实行情：解析 + securities 回写 + get_detail 端到端')

if network_ok:
    # 先清缓存
    server._quote_cache['ts'] = 0.0
    server._quote_cache['data'] = {}

    # 模拟"完整链路"：调 get_quotes → 触发 fetch + DB 回写
    res = server.get_quotes(['sh688208'])
    sample = res.get('data', {}).get('sh688208', {})
    step('A 股 sh688208 解析含完整字段',
         all(k in sample for k in ('name', 'code', 'current', 'prev_close',
                                    'change_pct', 'market_time')),
         'keys=' + ','.join(sorted(sample.keys())))
    # market_time 格式 YYYY-MM-DD HH:MM:SS
    mt = sample.get('market_time')
    if mt:
        ok_fmt = isinstance(mt, str) and len(mt) == 19 and mt[4] == '-' and mt[10] == ' '
    else:
        ok_fmt = False
    step('A 股 market_time 是 YYYY-MM-DD HH:MM:SS', ok_fmt, 'mt=%r' % mt)

    # 回写 securities
    c = sqlite3.connect(TMP_DB)
    c.row_factory = sqlite3.Row
    r = c.execute('SELECT current_price, current_price_updated_at FROM securities WHERE id=?',
                  (sid_a,)).fetchone()
    c.close()
    step('A 股行情回写 securities.current_price（真实链路）',
         r['current_price'] is not None and abs(r['current_price'] - sample['current']) < 1e-6,
         'cur=%s sample=%s' % (r['current_price'], sample.get('current')))

    # 端到端：get_detail 必须返回正确的 market_value
    server.add_trade(sid_a, {'side': '买入', 'price': sample['current'] - 1,
                             'quantity': 100, 'fee': 0,
                             'trade_date': '2026-09-01'})
    # 再次拉取
    server._quote_cache['ts'] = 0.0
    res2 = server.get_quotes(['sh688208'])
    det = server.get_detail(sid_a)
    mv = det['position']['market_value']
    step('端到端：A 股 get_detail().market_value = 100 * current_price',
         mv is not None and abs(mv - 100 * sample['current']) < 0.01,
         'mv=%s expected=%s' % (mv, 100 * sample.get('current')))


# ============== §2. 港股真实解析 ==============
section('2. 港股真实行情：解析 + 回写（HKD）')

if network_ok:
    server._quote_cache['ts'] = 0.0
    res = server.get_quotes(['hk01357'])
    sample = res.get('data', {}).get('hk01357', {})
    step('港股 hk01357 解析',
         'current' in sample and 'market_time' in sample and 'currency' in sample,
         'currency=%s' % sample.get('currency'))
    step('港股 currency=HKD', sample.get('currency') == 'HKD')

    # 回写
    c = sqlite3.connect(TMP_DB)
    c.row_factory = sqlite3.Row
    r = c.execute('SELECT current_price FROM securities WHERE id=?', (sid_h,)).fetchone()
    c.close()
    step('港股行情回写 securities.current_price',
         r['current_price'] is not None and abs(r['current_price'] - sample['current']) < 1e-6,
         'cur=%s' % r['current_price'])


# ============== §3. 网络故障降级（mock 失败） ==============
section('3. 网络故障降级：第一次失败必须返回 error')

# 用 mock 替代 fetch_tencent 抛错
def fail_fetch(symbols):
    raise urllib.error.URLError('mocked failure')

server.fetch_tencent = fail_fetch
server._quote_cache['ts'] = 0.0
server._quote_cache['last_success_at'] = None
server._quote_cache['last_error'] = ''
server._quote_cache['last_error_at'] = None

res = server.get_quotes(['sh688208'])
step('首次失败时返回 error',
     bool(res.get('error')) and 'mocked failure' in res.get('error', ''),
     'error=%r' % res.get('error'))
step('首次失败时 last_success_at 仍为 NULL',
     res.get('last_success_at') is None)
step('first fail 不影响已有 last_error 维护',
     res.get('last_error_at') is not None)


# ============== §4. 缓存旧价展示 + 时间戳 ==============
section('4. 缓存旧价：标记为"上次成功" + 时间戳')

# 模拟：上次成功过 → 现在失败
server._quote_cache['last_success_at'] = '2026-09-10 10:00:00'
server._quote_cache['data'] = {'sh99999': {
    'symbol': 'sh99999', 'current': 100.0, 'market_time': '2026-09-10 10:00:00'
}}
server.fetch_tencent = fail_fetch
server._quote_cache['ts'] = 0.0

res = server.get_quotes(['sh99999'])
step('曾成功后再次失败：error 字段填上',
     bool(res.get('error')))
step('曾成功后再次失败：last_success_at 仍存在',
     res.get('last_success_at') == '2026-09-10 10:00:00')
step('曾成功后再次失败：data 仍含 sh99999（缓存旧价展示）',
     'sh99999' in res.get('data', {}))

# 还原 fetch_tencent
server.fetch_tencent = server.__dict__.get('_orig_fetch', server.fetch_tencent)


# ============== 总计 + 清理 ==============
print()
print('=' * 60)
print(f'总计: PASS {results["pass"]}    FAIL {results["fail"]}    SKIP {results["skip"]}')
print('=' * 60)

# 还原 server.fetch_tencent（无论是否跳过）
server.fetch_tencent = proxy._orig.__globals__.get('fetch_tencent', server.fetch_tencent)
# 实际上还原是另一回事；monkey-patch 失败便算了（不影响主套件）

proxy.restore()
shutil.rmtree(TMP_ROOT, ignore_errors=True)

sys.exit(0 if results['fail'] == 0 else 1)
