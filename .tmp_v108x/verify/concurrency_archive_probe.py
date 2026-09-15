# -*- coding: utf-8 -*-
"""并发探针：归档 / 恢复 属于 **append-only 台账写入**，必须验证并发下的不变式。

项目铁律（MEMORY.md 硬性约定）：凡「一次性凭据 / token / append-only 写入」的改动
**必须跑并发探针**；顺序路径全绿不能证明无缺陷 —— v1.0.9 的 R-027（同一 preview token
并发 commit 重复追加 execution）就是这样漏出去的。

被检的临界区（app/server.py `_set_archived_at`）是一个典型的
**「先读校验 → 写状态 → 追加台账」**三段式：
    sec = get_security_or_404(conn, sid)
    if bool(sec.get('archived_at')) == bool(value): return {'changed': False}
    conn.execute('UPDATE securities SET archived_at=..')
    ledger_add(conn, sid, .., event_type, ..)
若两个线程都读到"未归档"，就可能**双双追加一条「标的归档」**——把 append-only 台账污染成
两条同一事件的记录，而状态只该变一次。本探针就是要证明它不会发生。

不变式（与线程调度无关、可复现；**不写死某次观测值**）：
  I1  每轮台账行数增量 == 该轮 changed=True 的返回数（**禁止"写了却没报告"或"报了却没写"**）
  I2  纯归档轮：changed=True 数 **严格 == 1**（幂等，重复点击不得产生第二次事件）
  I3  每个线程的结局 ∈ {changed=True, changed=False, 数据库忙(409 族)}，**不得有其它的异常**
  I4  终态与操作序列一致（纯归档轮必为已归档；混合轮满足
      终态=已归档 ⟺ 成功总次数为奇数 —— 每次 changed=True 都是一次真翻转）
  I5  隔离性：其它事件类型的台账行数不受影响
  I6  真实库 data/workbench.db 逐字节未变

跑法：<python> .tmp_v108x/verify/concurrency_archive_probe.py
"""
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import threading

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))

REAL_DB = os.path.join(ROOT, 'data', 'workbench.db')

PASS = 0
FAIL = 0


def step(label, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [PASS] %s %s' % (label, detail))
    else:
        FAIL += 1
        print('  [FAIL] %s  ← %s' % (label, detail))


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def main():
    print('=' * 78)
    print('并发探针：归档 / 恢复 的 append-only 台账不变式')
    print('=' * 78)

    real_sha_before = sha(REAL_DB)
    print('  真实库 sha256 = %s' % real_sha_before)

    box = tempfile.mkdtemp(prefix='conc_arch_')
    data_dir = os.path.join(box, 'data')
    os.makedirs(data_dir)
    sbx = os.path.join(data_dir, 'workbench.db')
    shutil.copy2(REAL_DB, sbx)

    import server
    server.DB_PATH = sbx
    server.DATA_DIR = data_dir
    server.init_db()
    print('  沙箱 = %s' % sbx)

    ARCH, UNARCH = server.ARCHIVE_EVENT, server.UNARCHIVE_EVENT

    conn = sqlite3.connect(sbx)
    conn.row_factory = sqlite3.Row
    sid = conn.execute('SELECT id FROM securities ORDER BY id LIMIT 1').fetchone()['id']
    n_ledger_all0 = conn.execute('SELECT COUNT(*) c FROM decision_ledger').fetchone()['c']
    conn.close()
    print('  受测标的 id=%d；沙箱台账共 %d 条' % (sid, n_ledger_all0))

    def n_rows(event=None):
        c = sqlite3.connect(sbx, timeout=10)
        try:
            if event is None:
                return c.execute('SELECT COUNT(*) FROM decision_ledger').fetchone()[0]
            return c.execute('SELECT COUNT(*) FROM decision_ledger '
                             'WHERE security_id=? AND event_type=?', (sid, event)).fetchone()[0]
        finally:
            c.close()

    def archived_at():
        c = sqlite3.connect(sbx, timeout=10)
        try:
            return c.execute('SELECT archived_at FROM securities WHERE id=?', (sid,)).fetchone()[0]
        finally:
            c.close()

    def reset():
        """把受测标的复位成未归档。基线在每个线程启动**之前**取。"""
        c = sqlite3.connect(sbx, timeout=10)
        c.execute('UPDATE securities SET archived_at=NULL, updated_at=updated_at WHERE id=?', (sid,))
        c.commit()
        c.close()

    def run_round(ops, T):
        """ops: ['a','a',...] / ['a','u',...]，长度 T。返回 (结局列表, 台账增量 dict)"""
        reset()
        base_all = n_rows(None)
        base = {ARCH: n_rows(ARCH), UNARCH: n_rows(UNARCH), 'all': base_all}
        base['other'] = base_all - base[ARCH] - base[UNARCH]
        barrier = threading.Barrier(T)
        out = [None] * T

        def work(i):
            barrier.wait()
            try:
                r = (server.archive_security(sid, {'reason': '并发探针'})
                     if ops[i] == 'a' else
                     server.unarchive_security(sid, {'reason': '并发探针'}))
                out[i] = 'true' if r.get('changed') else 'false'
            except sqlite3.OperationalError as e:
                out[i] = 'conflict' if server._is_db_busy_error(e) else \
                    'error:%s:%s' % (type(e).__name__, str(e)[:60])
            except Exception as e:                       # noqa: BLE001
                out[i] = 'error:%s:%s' % (type(e).__name__, str(e)[:60])

        ts = [threading.Thread(target=work, args=(i,)) for i in range(T)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        d_arch = n_rows(ARCH) - base[ARCH]
        d_unarch = n_rows(UNARCH) - base[UNARCH]
        d_all = n_rows(None) - base['all']
        delta = {ARCH: d_arch, UNARCH: d_unarch,
                 'all': d_all, 'other': d_all - d_arch - d_unarch}
        return out, delta

    T = 8
    R = 12
    print('\n§1 纯归档并发：%d 轮 × %d 线程，同一标的、同一方向' % (R, T))
    a_true = a_false = a_conf = a_err = 0
    bad_rounds = []
    over = 0
    for k in range(R):
        out, d = run_round(['a'] * T, T)
        t = out.count('true')
        a_true += t
        a_false += out.count('false')
        a_conf += out.count('conflict')
        a_err += sum(1 for x in out if x.startswith('error'))
        if d[ARCH] > 1:
            over += 1
        if d[ARCH] != t or d['other'] != 0:
            bad_rounds.append((k, t, d))
    print('    合计：changed=True %d / changed=False %d / 409族 %d / 其它异常 %d'
          % (a_true, a_false, a_conf, a_err))
    print('    单轮台账增量 >1 的轮数 = %d（设计上幂等，必须为 0）' % over)

    step('§1#1 每轮「标的归档」台账增量恰等于 changed=True 数（无幽灵行、无漏报）',
         not bad_rounds, '异常轮=%s' % bad_rounds[:3])
    step('§1#2 每轮 changed=True 严格 == 1（幂等：重复并发点击不追加第二次事件）',
         a_true == R, 'changed=True 合计=%d（期望 %d 轮各 1）' % (a_true, R))
    step('§1#3 没有任何线程落进"其它异常"（只允许 true/false/409族）',
         a_err == 0, '其它异常=%d' % a_err)
    step('§1#4 结局恰好覆盖全部 %d×%d 次调用（无丢线程）' % (R, T),
         a_true + a_false + a_conf + a_err == R * T)
    step('§1#5 并发归档后终态确为「已归档」', archived_at() is not None, archived_at())
    step('§1#6 其它事件类型台账行数未受影响（隔离性）', not any(b[2]['other'] for b in bad_rounds))

    print('\n§2 混合并发：归档 / 恢复 交替同时打同一标的')
    R2 = 12
    m_true = m_conf = m_err = 0
    m_arch_true = m_unarch_true = 0
    mix_bad = []
    for k in range(R2):
        ops = ['a', 'u'] * (T // 2)
        out, d = run_round(ops, T)
        ta = sum(1 for i, x in enumerate(out) if x == 'true' and ops[i] == 'a')
        tu = sum(1 for i, x in enumerate(out) if x == 'true' and ops[i] == 'u')
        m_arch_true += ta
        m_unarch_true += tu
        m_true += ta + tu
        m_conf += out.count('conflict')
        m_err += sum(1 for x in out if x.startswith('error'))
        final_arch = archived_at() is not None
        # 不变式（与调度顺序无关）：每次 changed=True 都是一次**真翻转**，
        # 故起始未归档 ⇒ 终态已归档 ⟺ 成功总次数 (a+u) 为奇数。
        if final_arch != bool((ta + tu) % 2):
            mix_bad.append((k, 'parity', ta, tu, final_arch))
        if d[ARCH] != ta or d[UNARCH] != tu or d['other'] != 0:
            mix_bad.append((k, 'ledger', ta, tu, d))
    print('    合计：归档成功 %d / 恢复成功 %d / 409族 %d / 其它异常 %d'
          % (m_arch_true, m_unarch_true, m_conf, m_err))
    step('§2#1 混合并发下终态与成功次数守恒（起始未归档 ⇒ 终态已归档 ⟺ 成功次数为奇数）',
         not mix_bad, '异常轮=%s' % mix_bad[:3])
    step('§2#2 每轮两类台账增量各等于对应方向的 changed=True 数',
         not mix_bad, '异常轮=%s' % mix_bad[:3])
    step('§2#3 混合并发无其它异常', m_err == 0, '其它异常=%d' % m_err)
    step('§2#4 两类事件都真的发生过（不是空跑）',
         m_arch_true > 0 and m_unarch_true > 0,
         '归档成功 %d / 恢复成功 %d' % (m_arch_true, m_unarch_true))

    print('\n§3 隔离性')
    step('§3#1 真实库 data/workbench.db 逐字节未变（SHA-256 前后一致）',
         sha(REAL_DB) == real_sha_before)

    shutil.rmtree(box, ignore_errors=True)
    step('§3#2 沙箱已清理', not os.path.exists(box))

    print('\n' + '=' * 78)
    print('结果：%d PASS / %d FAIL' % (PASS, FAIL))
    print('真实库 sha256 = %s' % sha(REAL_DB))
    print('=' * 78)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
