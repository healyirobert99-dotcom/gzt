# -*- coding: utf-8 -*-
import os, sys, json, sqlite3, tempfile, threading, urllib.request, urllib.error
ROOT = r'D:/个股工作台'
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server
P=F=0
def step(n, ok, d=''):
    global P,F
    if ok: P+=1; print('  [PASS]', n, d)
    else: F+=1; print('  [FAIL]', n, d)

fd, db = tempfile.mkstemp(suffix='.db', prefix='probeA1-'); os.close(fd)
server.init_db(seed=False, db_path=db)
def op():
    c=sqlite3.connect(db, timeout=10); c.row_factory=sqlite3.Row; return c
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
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: return e.code, json.loads(raw)
        except ValueError: return e.code, {'raw':raw}

def pl(code, status='等价格', one_liner='第一版逻辑'):
    return {'format':'ah-workbench-import','format_version':'1.0','generated_at':'2026-09-11',
      'securities':[{'identity':{'exchange':'SH','code':code,'name':'漂移标的'},
        'status':status,
        'research':{'one_liner':one_liner,'research_date':'2026-09-11',
          'core_validations':[{'content':'v1','status':'跟踪中'}],
          'wall_conditions':[{'content':'w1','triggered':False}],'change_note':'init'},
        'trade_plan':{'first_zone_low':10.0,'first_zone_high':11.0,'change_note':'init'}}]}

# 先建立基线：真实 preview + commit 让 research v1 / trade_plan v1 落库
st,r=http(base+'/api/import/preview', pl('600010')); tok=r['token']
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('基线 commit → 200', st==200, 'status=%s'%st)
c=op()
sid=c.execute("SELECT id FROM securities WHERE code='600010'").fetchone()['id']
rv=c.execute("SELECT MAX(version) v FROM research WHERE security_id=?",(sid,)).fetchone()['v']
pv=c.execute("SELECT MAX(version) v FROM trade_plans WHERE security_id=?",(sid,)).fetchone()['v']
c.close()
step('基线 research v1 已落库', rv==1, 'research_version=%s'%rv)
step('基线 trade_plan v1 已落库', pv==1, 'plan_version=%s'%pv)

# --- A1: preview 后 research 最新 version 变化 → commit 拒绝
st,r=http(base+'/api/import/preview', pl('600010', one_liner='第二版逻辑', status='等价格'))
tok=r['token']
step('A1 preview 时 snapshot.research_version=1', r['securities'][0].get('research',{}).get('current_version')==1,
     str(r['securities'][0].get('research'))[:80])
c=op()
c.execute("UPDATE research SET version=version+1 WHERE security_id=? AND version=?",(sid,1))
c.commit()
nv=c.execute("SELECT MAX(version) v FROM research WHERE security_id=?",(sid,)).fetchone()['v']
c.close()
step('A1b 外部将 research version 改为 2', nv==2, 'now=%s'%nv)
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('A1c research version 漂移 → commit 400', st==400, 'status=%s'%st)
step('A1d 文案要求重新解析预览', '重新解析预览' in str(r.get('error')), str(r.get('error'))[:60].replace('\n','|'))

# --- 反向：漂移后 token 仍可被再次正确使用？（token 未失效，重新 preview 才可）
st,r=http(base+'/api/import/preview', pl('600010', one_liner='第三版逻辑'))
tok=r['token']
c=op(); c.execute("UPDATE trade_plans SET version=version+2 WHERE security_id=? AND version=1",(sid,)); c.commit(); c.close()
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('A2 trade_plan version 漂移 → commit 400', st==400, 'status=%s'%st)

# --- 重新 preview（未漂移）应可成功
st,r=http(base+'/api/import/preview', pl('600010', one_liner='第四版逻辑'))
tok=r['token']
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('A3 重新 preview 后 commit → 200', st==200, 'status=%s'%st)
step('A3b 未根据新库状态直接续跑（是重新 preview 才成功）', st==200)

srv.shutdown()
print('\n'+'='*56); print('A1/A2/A3 专项: PASS %d / FAIL %d'%(P,F)); print('='*56)
sys.exit(1 if F else 0)
