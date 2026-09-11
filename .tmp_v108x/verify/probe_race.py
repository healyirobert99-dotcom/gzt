# -*- coding: utf-8 -*-
"""对抗性探针：同一 token 并发 commit（TOCTOU）是否会双写。"""
import os, sys, json, sqlite3, tempfile, threading, urllib.request, urllib.error, time
ROOT = r'D:/个股工作台'
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server

fd, db = tempfile.mkstemp(suffix='.db', prefix='race-'); os.close(fd)
server.init_db(seed=False, db_path=db)
def op():
    c=sqlite3.connect(db, timeout=30); c.row_factory=sqlite3.Row; return c
server.get_db = op
with server._IMPORT_PREVIEW_LOCK: server._IMPORT_PREVIEW_CACHE.clear()
srv = server.ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
srv.daemon_threads=True
threading.Thread(target=srv.serve_forever, daemon=True).start()
base='http://127.0.0.1:%d'%srv.server_address[1]

def http(url, body):
    req=urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                               headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: return e.code, json.loads(raw)
        except ValueError: return e.code, {'raw':raw}

def pl():
    return {'format':'ah-workbench-import','format_version':'1.0','generated_at':'2026-09-11',
      'securities':[{'identity':{'exchange':'SH','code':'600777','name':'竞态标的'},
        'status':'等价格',
        'research':{'one_liner':'竞态逻辑','research_date':'2026-09-11',
          'core_validations':[{'content':'c1','status':'跟踪中'}],
          'wall_conditions':[{'content':'w1','triggered':False}],'change_note':'race'},
        'trade_plan':{'first_zone_low':10.0,'first_zone_high':11.0,'change_note':'race'}}]}

st, r = http(base+'/api/import/preview', pl())
tok = r['token']
print('preview ok, token =', tok[:14], '...')

results = []
barrier = threading.Barrier(4)
def worker():
    barrier.wait()                      # 4 个线程同时冲闸
    results.append(http(base+'/api/import/commit', {'token': tok, 'confirmed_status_changes': []}))

ts = [threading.Thread(target=worker) for _ in range(4)]
for t in ts: t.start()
for t in ts: t.join()

ok = [s for s,_ in results if s == 200]
print('并发 4 次 commit 状态码:', sorted(s for s,_ in results))
print('其中 200（成功）次数 =', len(ok))

c = op()
n_sec = c.execute("SELECT COUNT(*) FROM securities WHERE code='600777'").fetchone()[0]
sid_rows = c.execute("SELECT id FROM securities WHERE code='600777'").fetchall()
n_res = c.execute("SELECT COUNT(*) FROM research").fetchone()[0]
n_plan = c.execute("SELECT COUNT(*) FROM trade_plans").fetchone()[0]
n_led = c.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
c.close()
print('库内 securities 行数 =', n_sec, '| research 行数 =', n_res,
      '| trade_plans 行数 =', n_plan, '| decision_ledger 行数 =', n_led)
print()
if len(ok) > 1:
    print('>>> 结论：同一 token 被并发消费成功 %d 次 —— TOCTOU 竞态存在' % len(ok))
else:
    print('>>> 结论：同一 token 仅成功 1 次，竞态未触发（或已被兜住）')

srv.shutdown()
