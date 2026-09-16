# -*- coding: utf-8 -*-
"""把沙箱库还原成干净态（无归档标的），供后续脚本重复运行。

为什么用接口而不是浏览器点击：截图脚本里三轮「点恢复」都没生效
（浏览器点击受 60 秒行情重渲染影响，DOM 可能在两次点击之间被替换），
而收尾还原是**纯清理**动作，走接口确定、可重复。
"""
import json
import sqlite3
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://127.0.0.1:8805'
DB = r'D:\个股工作台\.tmp_v108x\verify\sandbox_arch\data\workbench.db'


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body or {}).encode(), method='POST',
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def archived():
    c = sqlite3.connect(DB)
    try:
        return c.execute('SELECT id,code,name FROM securities'
                         ' WHERE archived_at IS NOT NULL').fetchall()
    finally:
        c.close()


rows = archived()
print('还原前归档标的：', rows)
for sid, code, name in rows:
    st, res = post('/api/securities/%d/unarchive' % sid, {})
    print('  unarchive id=%d %s.%s → HTTP %s changed=%s'
          % (sid, code, name, st, res.get('changed')))
print('还原后归档标的：', archived())
