# -*- coding: utf-8 -*-
"""独立验证探针（不由交付包提供，仅本轮核验用）。"""
import os, sys, json, base64, time, sqlite3, tempfile, threading, urllib.request, urllib.error
ROOT = r'D:/个股工作台'
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server

P=F=0
def step(n, ok, d=''):
    global P,F
    if ok: P+=1; print('  [PASS]', n, d)
    else: F+=1; print('  [FAIL]', n, d)

fd, db = tempfile.mkstemp(suffix='.db', prefix='probe-'); os.close(fd)
server.init_db(seed=False, db_path=db)
def op():
    c=sqlite3.connect(db, timeout=10); c.row_factory=sqlite3.Row; return c
server.get_db = op
with server._IMPORT_PREVIEW_LOCK: server._IMPORT_PREVIEW_CACHE.clear()
srv = server.ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
srv.daemon_threads=True
port=srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base='http://127.0.0.1:%d'%port

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

def pl(code='600001', exch='SH', name='探针A', status='等价格', cv=None, wc=None):
    return {'format':'ah-workbench-import','format_version':'1.0','generated_at':'2026-09-11',
      'status_change_confirmed': True,
      'securities':[{'identity':{'exchange':exch,'code':code,'name':name},
        'status':status,
        'research':{'one_liner':'探针逻辑','research_date':'2026-09-11',
          'core_validations': cv if cv is not None else [{'content':'v1','status':'跟踪中'}],
          'wall_conditions': wc if wc is not None else [{'content':'w1','triggered':False}],
          'change_note':'探针'},
        'trade_plan':{'first_zone_low':10.0,'first_zone_high':11.0,'change_note':'探针计划'}}]}

def seed(code='600001', exch='SH', name='探针A', status='等价格'):
    c=op()
    c.execute("INSERT INTO securities (code,exchange,name,currency,market,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
              (code,exch,name,'CNY','SH',status,'2026-09-11','2026-09-11'))
    sid=c.execute("SELECT id FROM securities WHERE code=? AND exchange=?",(code,exch)).fetchone()['id']
    c.commit(); c.close(); return sid

print('=== A group: 漂移检测（spec 三）===')
s1=seed('600001')
# A1 research version drift
st,r=http(base+'/api/import/preview', pl('600001'))
tok=r['token']
c=op(); c.execute("UPDATE research SET version=version+1 WHERE security_id=?",(s1,)); c.commit(); c.close()
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('A1 research version 漂移 → 400', st==400, 'status=%s'%st)
step('A1b 文案要求重新预览', '重新解析预览' in str(r.get('error')), str(r.get('error'))[:40])

# A2 trade_plan version drift
st,r=http(base+'/api/import/preview', pl('600001')); tok=r['token']
c=op()
c.execute("UPDATE trade_plans SET version=version+3 WHERE security_id=?",(s1,))
c.commit(); c.close()
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('A2 trade_plan version 漂移 → 400', st==400, 'status=%s'%st)

# A3 new security appeared after preview
st,r=http(base+'/api/import/preview', pl('600099', name='探针B')); tok=r['token']
seed('600099','SH','探针B')
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('A3 原不存在证券预览后出现 → 400', st==400, 'status=%s'%st)
step('A3b 文案要求重新预览', '重新解析预览' in str(r.get('error')), str(r.get('error'))[:40])

print('=== B group: JSON 结构严格校验（spec 五）===')
cases = [
 ('B1 core_validations 为字符串数组', dict(cv=['验证项一','验证项二'])),
 ('B2 core_validations.status 非法', dict(cv=[{'content':'x','status':'已确认'}])),
 ('B3 core_validations 缺 content', dict(cv=[{'status':'跟踪中'}])),
 ('B4 wall_conditions 为字符串数组', dict(wc=['危墙一'])),
 ('B5 wall_conditions.triggered 非布尔(字符串)', dict(wc=[{'content':'x','triggered':'false'}])),
 ('B6 wall_conditions.triggered 数字 0', dict(wc=[{'content':'x','triggered':0}])),
 ('B7 wall_conditions 缺 content', dict(wc=[{'triggered':True}])),
 ('B8 core_validations 含 null', dict(cv=[None])),
 ('B9 core_validations 含数字', dict(cv=[123])),
]
for n,kw in cases:
    st,r=http(base+'/api/import/preview', pl('600002', 'SH', '探针C', **kw))
    step(n+' → 400', st==400, 'status=%s'%st)

print('=== C group: 同批重复（spec 四）===')
p=pl('600003','SH','探针D'); p['securities'].append(json.loads(json.dumps(p['securities'][0])))
st,r=http(base+'/api/import/preview', p)
step('C1 同批重复 SH+600003 → 400', st==400, 'status=%s'%st)
step('C2 错误信息点出重复', '重复' in str(r.get('error')), str(r.get('error'))[:56])

print('=== D group: 确认机制（spec 二）===')
p=pl('600004','SH','探针E'); st,r=http(base+'/api/import/preview', p); tok=r['token']
secs=r['securities']
step('D1 新建证券 change_confirmed 为 False', (secs[0].get('status_change') or {}).get('change_confirmed') is False,
     'change_confirmed=%r'%((secs[0].get('status_change') or {}).get('change_confirmed'),))
# 已有证券：status 变化必须确认
st,r=http(base+'/api/import/preview', pl('600001','SH','探针A', status='可交易')); tok=r['token']
sc=r['securities'][0].get('status_change') or {}
step('D2 已有证券 status 变化 → requires_confirm=True', sc.get('requires_confirm') is True, str(sc)[:60])
step('D3 初次 change_confirmed=False（JSON 声称 true 也被忽略）', sc.get('change_confirmed') is False)
st,r=http(base+'/api/import/commit', {'token':tok,'confirmed_status_changes':[]})
step('D4 未勾选 → commit 拒绝', st==400, 'status=%s'%st)
st,r2=http(base+'/api/import/preview', pl('600001','SH','探针A', status='可交易')); tok2=r2['token']
st,r=http(base+'/api/import/commit', {'token':tok2,'confirmed_status_changes':[0]})
step('D5 勾选后 → commit 成功', st==200, 'status=%s'%st)
c=op(); cur=c.execute("SELECT status FROM securities WHERE code='600001'").fetchone()['status']; c.close()
step('D6 status 真的改为 可交易', cur=='可交易', 'status=%s'%cur)

print('=== E group: name mismatch（spec 六）===')
st,r=http(base+'/api/import/preview', pl('600001','SH','工作台里叫别的名字'))
s=r['securities'][0]
step('E1 name_mismatch=True', s.get('name_mismatch') is True, str(s.get('name_mismatch')))
step('E2 name_mismatch_notice 含"名称不一致"', '名称不一致' in str(s.get('name_mismatch_notice')), str(s.get('name_mismatch_notice'))[:60].replace('\n','|'))
step('E3 notice 同时给出工作台名与导入名', '探针A' in str(s.get('name_mismatch_notice')) and '工作台里叫别的名字' in str(s.get('name_mismatch_notice')))
step('E4 warnings 里也带该提示', any('名称不一致' in w for w in (r.get('warnings') or [])))
step('E5 页面渲染代码引用 name_mismatch', 'name_mismatch' in open(os.path.join(ROOT,'app/static/app.js'),encoding='utf-8').read())

print('=== F group: 身份只认 exchange+code ===')
st,r=http(base+'/api/import/preview', pl('600001','SH','完全不同的名字'))
step('F1 同名不同 code 视为不同证券', r['securities'][0].get('exists') is True, 'exists=%s'%r['securities'][0].get('exists'))

srv.shutdown()
print('\n'+'='*56)
print('独立探针结果: PASS %d / FAIL %d'%(P,F))
print('='*56)
sys.exit(1 if F else 0)
