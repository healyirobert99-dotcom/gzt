# -*- coding: utf-8 -*-
"""§6 隔离性两条断言的**负向验证**：证明它们不是装饰品。

做法（不碰真实库、不碰正式脚本）：把 browser_e2e_archive.py 当模块载入，
只把 `real_snapshot` 的**第二次调用**（即 §6 的 T1 读数）打桩成"被改坏"的形态，
然后跑完整的 main()。要求目标断言翻红、另一条保持绿 —— 这样才能证明
两条断言各自守住了不同的东西，而不是"恒真"或"恒假"。

变体 A：业务指纹被改（台账 +1）      → 期望 §6#1 FAIL、§6#2 PASS
变体 B：securities 改了非行情列(name)，而业务指纹不变 → 期望 §6#2 FAIL、§6#1 PASS
"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'browser_e2e_archive.py')

VARIANT = sys.argv[1] if len(sys.argv) > 1 else 'A'


def load():
    spec = importlib.util.spec_from_file_location('e2e_mod', TARGET)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)      # __name__ != '__main__'，故不会自动跑 main()
    return m


def main():
    m = load()
    orig = m.real_snapshot
    state = {'n': 0}

    def tampered():
        state['n'] += 1
        biz, secs, tally = orig()
        if state['n'] < 2:          # 第一次（T0）原样返回
            return biz, secs, tally
        if VARIANT == 'A':
            t2 = dict(tally)
            t2['decision_ledger'] += 1          # 伪造"业务表被改了一行"
            return (biz[0], tuple(sorted(t2.items()))), secs, t2
        # 变体 B：securities 的 name 变了（非行情列），但业务指纹**保持原样**，
        # 以精确隔离出 §6#2 的比较逻辑
        secs2 = [dict(s) for s in secs]
        if secs2:
            secs2[0]['name'] = '注入变体B'
        return biz, secs2, tally

    m.real_snapshot = tampered
    print('### 负向变体 %s ###' % VARIANT)
    return m.main()


if __name__ == '__main__':
    sys.exit(main())
