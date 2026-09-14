# -*- coding: utf-8 -*-
"""「数据更新」按钮 —— 真实服务端到端验证。

对**真实运行中的工作台服务**发真实 HTTP 请求（不 stub 任何东西），验证：

  1. force=1 首次请求 → 全部标的都是本次新行情（is_stale=False）
  2. 紧随其后不带 force → 命中后端 8 秒缓存（is_stale=True）
  3. 再打 force=1 → 绕缓存重新拉取（is_stale=False 且 last_success_at 前进）
  4. 服务端下发的 index.html 里按钮可见、文案正确
  5. 服务端下发的 app.js 里确实带 force=1 传参（证明浏览器拿到的是新代码）

用法：
  python .tmp_v108x/verify/e2e_data_update_btn.py [port]

注意：请在**新代码**启动的服务上跑。若对旧进程跑，第 3/5 条会 FAIL ——
这正是本脚本的判别力所在。
"""

import json
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
BASE = 'http://127.0.0.1:%d' % PORT

FAIL = 0
TOTAL = 0


def step(name, ok, detail=''):
    global FAIL, TOTAL
    TOTAL += 1
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAIL += 1


def section(t):
    print('\n=== %s ===' % t)


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def get_text(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.status, r.read().decode('utf-8')


def tx_symbol(s):
    """与前端 txSymbol() 等价。"""
    if s['exchange'] == 'HK':
        return 'hk' + str(s['code']).zfill(5)
    return ('sh' if s['exchange'] == 'SH' else 'sz') + str(s['code']).zfill(6)


def main():
    print('=== 「数据更新」按钮 · 真实服务端到端 (%s) ===' % BASE)

    try:
        st, secs = get_json('/api/securities')
    except Exception as e:
        print('无法连接 %s：%s: %s' % (BASE, type(e).__name__, e))
        return 1

    if not isinstance(secs, list) or not secs:
        print('服务未返回标的列表（%r），无法继续' % type(secs))
        return 1

    syms = ','.join(tx_symbol(s) for s in secs)
    section('0. 前置')
    step('E2E#0 拿到标的列表', True, '%d 只' % len(secs))
    print('       symbols = %s' % (syms if len(syms) <= 100 else syms[:100] + '...'))

    # ---------- 1. force=1 首次 ----------
    section('1. force=1 首次请求（等价于用户第一次点「数据更新」）')
    t0 = time.time()
    st, r1 = get_json('/api/quotes?symbols=' + syms + '&force=1')
    dt1 = time.time() - t0
    t1 = r1.get('last_success_at')
    fresh1 = sum(1 for v in r1['data'].values() if v.get('is_stale') is False)
    step('E2E#1 HTTP 200', st == 200, 'status=%d' % st)
    step('E2E#2 全部标的均为本次新行情（is_stale=False）',
         fresh1 == len(secs), '%d/%d fresh, 耗时 %.1fs' % (fresh1, len(secs), dt1))
    step('E2E#3 last_success_at 有值', bool(t1), 'last_success_at=%r' % t1)
    step('E2E#4 无顶层 error', not r1.get('error'), 'error=%r' % r1.get('error'))

    # ---------- 2. 不带 force 紧随其后：应命中缓存 ----------
    section('2. 紧随其后不带 force（后台轮询路径，应命中 8 秒缓存）')
    t0 = time.time()
    st, r2 = get_json('/api/quotes?symbols=' + syms)
    dt2 = time.time() - t0
    stale2 = sum(1 for v in r2['data'].values() if v.get('is_stale') is True)
    within_window = dt2 < 8.0
    if not within_window:
        step('E2E#5 （本轮耗时超 8 秒，缓存窗口已过，跳过判定）', False,
             'elapsed=%.1fs' % dt2, )
    else:
        step('E2E#5 全部标的命中缓存（is_stale=True）',
             stale2 == len(secs), '%d/%d stale, 耗时 %.2fs' % (stale2, len(secs), dt2))

    # ---------- 3. 再 force=1：绕缓存 ----------
    section('3. 再点一次「数据更新」（force=1 必须绕开 8 秒缓存窗口）')
    time.sleep(1.2)  # 确保 now_str() 秒级时间戳能前进
    t0 = time.time()
    st, r3 = get_json('/api/quotes?symbols=' + syms + '&force=1')
    dt3 = time.time() - t0
    t3 = r3.get('last_success_at')
    fresh3 = sum(1 for v in r3['data'].values() if v.get('is_stale') is False)
    step('E2E#6 全部标的重新变成新行情（is_stale=False）',
         fresh3 == len(secs), '%d/%d fresh, 耗时 %.1fs' % (fresh3, len(secs), dt3))
    step('E2E#7 last_success_at 前进（证明真的重新请求了上游）',
         bool(t3) and bool(t1) and t3 > t1, '%s → %s' % (t1, t3))

    # ---------- 4. 服务端下发的静态资源 ----------
    section('4. 服务端下发的静态资源（浏览器实际拿到的东西）')
    st, html = get_text('/')
    step('E2E#8 首页 200', st == 200)
    btn_ok = False
    if 'id="btn-refresh"' in html:
        frag = html.split('id="btn-refresh"', 1)[1].split('>', 1)[0]
        btn_ok = ('hidden' not in frag.split()) and ('数据更新' in
                  html.split('id="btn-refresh"', 1)[1].split('</button>', 1)[0])
    step('E2E#9 首页按钮存在、可见、文案为「数据更新」', btn_ok)
    step('E2E#10 首页按钮带 title 行为说明',
         'title=' in html and '行情' in html.split('id="btn-refresh"', 1)[1][:300]
         if 'id="btn-refresh"' in html else False)

    st, js = get_text('/static/app.js')
    step('E2E#11 下发的 app.js 200', st == 200)
    step('E2E#12 下发的 app.js 含 force=1 传参（新代码已生效）',
         "force ? '&force=1'" in js,
         '命中' if "force ? '&force=1'" in js else '未命中 —— 服务可能仍跑旧代码')
    step('E2E#13 下发的 app.js 点击绑定为 refreshQuotes(true, true)',
         'refreshQuotes(true, true)' in js)

    print('\n' + '=' * 60)
    print('端到端: PASS %d / FAIL %d （共 %d 断言）' % (TOTAL - FAIL, FAIL, TOTAL))
    print('=' * 60)
    if FAIL:
        print('FAIL_COUNT = %d' % FAIL)
        return 1
    print('FAIL_COUNT = 0')
    print('ALL E2E PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
