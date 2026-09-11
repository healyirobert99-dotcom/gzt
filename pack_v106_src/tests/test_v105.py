# -*- coding: utf-8 -*-
"""v1.0.5 封板准确性修复测试 —— 交易流水账准 + 前端契约。

本套件只使用临时 SQLite 数据库，绝不读写或覆盖正式 data/workbench.db。

覆盖项：
A §A  历史补录非法案例：先买后卖合法基线
B §B  非法案例拒绝：补录卖在买之前 → ApiError，trades 行数不变
C §C  失败零污染：拒绝后数据库中 trades 数量 = 调用前，compute_position 仍正常
D §D  同日先买后卖合法：candidate.id=INF 排在同日末位
E §E  前端契约：execution_view 不再使用 <select>，改为 <input list="execution-view-suggest">
F §F  前端契约：包含 <datalist id="execution-view-suggest">，4 个建议项
G §G  前端契约：自定义 execution_view（白名单外文本）可作为 input value 原样预填
H §H  前端契约：execution_date 默认 = today()，不继承 prev.execution_date
"""
import os
import sys
import re
import tempfile
import shutil
import sqlite3
import hashlib


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))

import server  # noqa: E402


# ================ 工具 ================
_tmp_dir = None
_SEC_ID = None
TMP_DB = None
PROD_DB_PATH_BEFORE = None
RESULTS = []  # [(label, ok, detail)]


def step(label, ok, detail=''):
    RESULTS.append((label, bool(ok), detail))
    mark = '✅' if ok else '❌'
    print(f'  [{mark}] {label}' + (f'  —— {detail}' if detail else ''))


def setup_module(module):
    """整个测试模块开始前：建临时 DB，proxy get_db() 指向它。"""
    global _tmp_dir, TMP_DB
    _tmp_dir = tempfile.mkdtemp(prefix='wb_v105_')
    TMP_DB = os.path.join(_tmp_dir, 'test.db')

    # 记下生产库哈希，测试期间任何时刻都不得改它
    prod_path = os.path.join(ROOT, 'data', 'workbench.db')
    if os.path.exists(prod_path):
        with open(prod_path, 'rb') as f:
            module._prod_db_hash_before = hashlib.sha256(f.read()).hexdigest()
    else:
        module._prod_db_hash_before = None

    # 初始化临时库
    server.init_db(seed=False, db_path=TMP_DB)

    # 把全局 get_db 转向临时库（不污染生产）
    _orig_get_db = server.get_db

    def _make():
        co = sqlite3.connect(TMP_DB, timeout=10)
        co.row_factory = sqlite3.Row
        co.execute('PRAGMA journal_mode=WAL')
        co.execute('PRAGMA foreign_keys=ON')
        return co

    server.get_db = _make

    # 记一个 security_id 复用
    co = _make()
    co.execute(
        "INSERT INTO securities (code, exchange, name, currency, market, status, created_at, updated_at) "
        "VALUES ('01357','HK','美图公司','HKD','港股','等价格',?,?)",
        (server.now_str(), server.now_str())
    )
    co.commit()
    row = co.execute("SELECT id FROM securities WHERE code='01357'").fetchone()
    module.SEC_ID = row['id']
    globals()['_SEC_ID'] = module.SEC_ID
    co.close()


def teardown_module(module):
    # 还原 get_db
    try:
        server.get_db = _orig_get_db
    except Exception:
        pass

    # 删除临时库
    try:
        shutil.rmtree(_tmp_dir, ignore_errors=True)
    except Exception:
        pass

    # 检查生产库未被改
    prod_path = os.path.join(ROOT, 'data', 'workbench.db')
    if module._prod_db_hash_before is not None and os.path.exists(prod_path):
        with open(prod_path, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        if h != module._prod_db_hash_before:
            print(f'\n!!! 生产库哈希变化：{module._prod_db_hash_before} -> {h}  测试污染 !!!\n')


_orig_get_db = server.get_db


# ============================================================================
# §A 历史补录非法案例 1：先有 09-10 买 100，补录 09-01 卖 50
# ============================================================================
def test_a_baseline_buy_only():
    print('\n§A 历史补录非法案例（先有合法买入，再补录更早的卖）')
    sid = _SEC_ID
    # 先录入一笔合法的「2026-09-10 买入 100」——通过 add_trade_tx
    server.add_trade(sid, {
        'side': '买入', 'price': 4.20, 'quantity': 100, 'fee': 0,
        'trade_date': '2026-09-10', 'note': '基线买入'
    })
    co = server.get_db()
    rows = co.execute('SELECT trade_date, side, quantity FROM trades WHERE security_id=? ORDER BY trade_date, id',
                      (sid,)).fetchall()
    co.close()
    step('基线 1 笔 trades（2026-09-10 买入 100）', len(rows) == 1, f'rows={len(rows)}')
    step('基线 row[0] = (2026-09-10, 买入, 100)', (rows[0]['trade_date'] == '2026-09-10'
                                                   and rows[0]['side'] == '买入'
                                                   and float(rows[0]['quantity']) == 100.0),
         f'actual={dict(rows[0])}')


def test_b_reject_earlier_sell():
    print('\n§B 拒绝"补录更早日期的卖出"，且零数据污染')
    sid = _SEC_ID
    # 当前已有 1 笔 buy：2026-09-10 买 100
    co = server.get_db()
    before_count = co.execute('SELECT COUNT(*) c FROM trades WHERE security_id=?', (sid,)).fetchone()['c']
    co.close()

    # 现在尝试补录「2026-09-01 卖出 50」——按真实时序会先 -50 再 +100，违反
    try:
        server.add_trade(sid, {
            'side': '卖出', 'price': 4.30, 'quantity': 50, 'fee': 0,
            'trade_date': '2026-09-01', 'note': '补录卖在买之前，应被拒绝'
        })
        # 不应到达这里
        err = None
    except Exception as e:
        err = e

    step('补录卖在买之前应抛 ApiError', err is not None and 'ApiError' in type(err).__name__,
         f'err type={type(err).__name__ if err else None}, msg={str(err)[:80] if err else None}')
    step('错误消息提到累计持仓变负', err is not None and ('累计持仓' in str(err) or '负' in str(err)),
         f'msg={str(err)[:80] if err else None}')

    co = server.get_db()
    after_count = co.execute('SELECT COUNT(*) c FROM trades WHERE security_id=?', (sid,)).fetchone()['c']
    rows = co.execute('SELECT trade_date, side, quantity FROM trades WHERE security_id=? ORDER BY trade_date, id',
                      (sid,)).fetchall()
    co.close()

    step(f'trades 行数 = 调用前（{before_count}）', after_count == before_count,
         f'before={before_count} after={after_count}')
    step('拒绝后数据库只剩基线买入',
         len(rows) == 1 and rows[0]['trade_date'] == '2026-09-10' and rows[0]['side'] == '买入',
         f'rows={[(r["trade_date"], r["side"]) for r in rows]}')

    # compute_position 仍能正常跑通（证明数据库仍是自洽的合法账本）
    co = server.get_db()
    pos = server.compute_position(co, sid)
    co.close()
    step('compute_position 在拒绝后仍可正常计算（quantity=100）',
         abs(pos.get('quantity', 0) - 100) < 1e-9, f'pos={pos.get("quantity")}')


def test_c_after_rejection_get_detail_works():
    print('\n§C 拒绝后 get_detail 不报错（账本仍自洽）')
    sid = _SEC_ID
    try:
        d = server.get_detail(sid)
        step('get_detail 不抛错', True, f'qty={d.get("position", {}).get("quantity")}')
    except Exception as e:
        step('get_detail 不抛错', False, f'异常: {e}')


# ============================================================================
# §D 同日先买后卖合法：candidate.id=INF 排在同日末位
# ============================================================================
def test_d_same_day_buy_then_sell_legal():
    print('\n§D 同日先买后卖合法（candidate.id=INF 排在同日末位）')
    sid = _SEC_ID
    server.add_trade(sid, {
        'side': '买入', 'price': 4.20, 'quantity': 50, 'fee': 0,
        'trade_date': '2026-09-15', 'note': '同日补仓'
    })
    # 现在已存在 2026-09-10 买 100 + 2026-09-15 买 50 = 150
    co = server.get_db()
    rows = co.execute('SELECT trade_date, side, quantity FROM trades WHERE security_id=? ORDER BY trade_date, id',
                      (sid,)).fetchall()
    co.close()
    step('§D#1 已有 2 笔 buy（合计 150）', len(rows) == 2
         and float(rows[0]['quantity']) == 100 and float(rows[1]['quantity']) == 50,
         f'rows={[(r["trade_date"], r["side"], r["quantity"]) for r in rows]}')

    # 在 09-15 后卖 50 = 合法（150-50=100）
    err = None
    try:
        server.add_trade(sid, {
            'side': '卖出', 'price': 4.25, 'quantity': 50, 'fee': 0,
            'trade_date': '2026-09-15', 'note': '同日卖'
        })
    except Exception as e:
        err = e
    step('§D#2 同日买入后再卖 50 合法', err is None, f'err={err}')

    co = server.get_db()
    rows = co.execute('SELECT trade_date, side, quantity FROM trades WHERE security_id=? ORDER BY trade_date, id',
                      (sid,)).fetchall()
    co.close()
    step('§D#3 现在有 3 笔 trades', len(rows) == 3,
         f'rows={[(r["trade_date"], r["side"], r["quantity"]) for r in rows]}')


# ============================================================================
# §E-H 前端契约（静态扫描 app.js）
# ============================================================================
def test_e_no_select_for_execution_view():
    print('\n§E 前端契约：execution_view 不再是 <select>')
    app_js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
    text = open(app_js_path, encoding='utf-8').read()

    # 在 openExecutionModal 内必须用 <input list="execution-view-suggest"> + <datalist>
    has_select = re.search(
        r'<select[^>]*name="execution_view"[^>]*>',
        text
    )
    step('execution_view 不再使用 <select>', has_select is None,
         f'匹配到 {"=>"+has_select.group(0) if has_select else ""}')

    has_input_list = re.search(
        r'<input[^>]*name="execution_view"[^>]*list="execution-view-suggest"[^>]*>',
        text
    )
    step('execution_view 改用 <input list="execution-view-suggest">', has_input_list is not None,
         f'{"命中" if has_input_list else "未命中"}')

    has_datalist = re.search(
        r'<datalist\s+id="execution-view-suggest">',
        text
    )
    step('存在 <datalist id="execution-view-suggest">', has_datalist is not None,
         f'{"命中" if has_datalist else "未命中"}')


def test_f_datalist_contains_4_suggestions():
    print('\n§F 4 个常用建议项存在于 EXECUTION_VIEWS 数组（渲染为 datalist <option>）')
    app_js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
    text = open(app_js_path, encoding='utf-8').read()

    # EXECUTION_VIEWS 数组是模板的数据源；datalist 通过 EXECUTION_VIEWS.map(v => `<option value="${esc(v)}">`) 渲染。
    # 因此静态扫描只需验证：(1) EXECUTION_VIEWS 数组包含 4 个值；(2) datalist 渲染模板通过 map+esc 引用该数组。
    m = re.search(
        r'const\s+EXECUTION_VIEWS\s*=\s*\[([^\]]+)\]',
        text
    )
    arr_text = m.group(1) if m else ''
    suggestions = ['等待技术确认', '可以开始执行', '暂缓执行', '继续观察']
    for s in suggestions:
        step(f'EXECUTION_VIEWS 含 "{s}"', s in arr_text, '')

    # datalist 模板是否通过 EXECUTION_VIEWS.map 渲染
    has_map_usage = re.search(
        r'<datalist[^>]*>\$\{EXECUTION_VIEWS\.map',
        text
    )
    step('<datalist>...</datalist> 内通过 EXECUTION_VIEWS.map 渲染 <option>', has_map_usage is not None,
         f'{"命中" if has_map_usage else "未命中"}')


def test_g_custom_execution_view_preserved():
    print('\n§G 自定义 execution_view（白名单外）作为 input value 原样预填')
    app_js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
    text = open(app_js_path, encoding='utf-8').read()

    # openExecutionModal 中读取 detail.execution_view（任意值）→ 写入 input 的 value
    has_prevView = re.search(r'prevViewRaw\s*=\s*prev\.execution_view\s*\|\|\s*[\'"]?[\'"]?', text)
    step('openExecutionModal 包含 prevViewRaw = prev.execution_view || ""', has_prevView is not None,
         f'{"命中" if has_prevView else "未命中"}')

    has_input_value = re.search(r'value="\$\{esc\(prevViewRaw\)\}"', text)
    step('execution_view input value=${esc(prevViewRaw)} 继承上一条原样', has_input_value is not None,
         f'{"命中" if has_input_value else "未命中"}')

    # 不允许给 execution_view input 一个硬编码的 default 文本（如 prev.execution_view || '等待技术确认'）
    has_hardcoded_default = re.search(
        r'<input[^>]*name="execution_view"[^>]*value="\$\{prev\.execution_view\s*\|\|\s*[\'"][^\'"]+[\'"][^}]*\}',
        text
    )
    step('execution_view input 不再使用 prev.execution_view || "等待技术确认" 硬编码默认',
         has_hardcoded_default is None,
         f'{"违规命中" if has_hardcoded_default else "OK"}')


def test_h_execution_date_default_today():
    print('\n§H execution_date 默认 today()，不继承 prev.execution_date')
    app_js_path = os.path.join(ROOT, 'app', 'static', 'app.js')
    text = open(app_js_path, encoding='utf-8').read()

    # 在 openExecutionModal 内必须使用 value="${esc(todayVal)}"
    has_todayVal_assignment = re.search(r'const\s+todayVal\s*=\s*today\(\)', text)
    step('openExecutionModal 内部 const todayVal = today()', has_todayVal_assignment is not None,
         f'{"命中" if has_todayVal_assignment else "未命中"}')

    has_execution_date_todayVal = re.search(
        r'<input[^>]*name="execution_date"[^>]*type="date"[^>]*value="\$\{esc\(todayVal\)\}"',
        text
    )
    step('execution_date input 使用 value="${esc(todayVal)}"', has_execution_date_todayVal is not None,
         f'{"命中" if has_execution_date_todayVal else "未命中"}')

    # 不允许出现 prev.execution_date || today() 这种继承写法
    has_inherit = re.search(r'<input[^>]*name="execution_date"[^>]*value="\$\{\s*prev\.execution_date\s*\|\|\s*today\(\)\s*\}', text)
    step('execution_date input 不再使用 prev.execution_date || today()',
         has_inherit is None,
         f'{"违规命中" if has_inherit else "OK"}')


# ============== Run all ==============
if __name__ == '__main__':
    setup_module(sys.modules[__name__])
    try:
        test_a_baseline_buy_only()
        test_b_reject_earlier_sell()
        test_c_after_rejection_get_detail_works()
        test_d_same_day_buy_then_sell_legal()
        test_e_no_select_for_execution_view()
        test_f_datalist_contains_4_suggestions()
        test_g_custom_execution_view_preserved()
        test_h_execution_date_default_today()
    finally:
        teardown_module(sys.modules[__name__])

    total = len(RESULTS)
    ok_n = sum(1 for _, ok, _ in RESULTS if ok)
    print(f'\n=================================================')
    print(f'v1.0.5 测试: PASS {ok_n} / FAIL {total - ok_n}  (共 {total} 断言)')
    print('=' * 50)
    if ok_n != total:
        print('FAIL 列表:')
        for label, ok, detail in RESULTS:
            if not ok:
                print(f'  - {label}  {detail}')
        sys.exit(1)
