# -*- coding: utf-8 -*-
"""为「卡片右上角 × 删除按钮」拍一组取证截图。

产出（落到 output/<日期>-卡片删除按钮确认/）：
  01 未悬停（卡片右上角无 ×）
  02 悬停后（右上角出现 ×）
  03 点击 × 后的确认弹窗
  04 确认归档后：卡片消失 + 首页出现「已归档」区
  05 恢复后回到原状（顺便把沙箱库还原，供后续脚本重跑）

并把第一张卡的 `get box` 坐标写进 shot_box.json，供 crop_shots.py 裁放大图。
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'browser_e2e_archive.py')
SHOT_DIR = os.path.join(os.path.expanduser('~'), '.agent-browser', 'tmp',
                        'screenshots')
OUT = r'D:\个股工作台\output\20260916-卡片删除按钮确认'


def load():
    spec = importlib.util.spec_from_file_location('e2e_mod', TARGET)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def snap_names():
    try:
        return set(os.listdir(SHOT_DIR))
    except FileNotFoundError:
        return set()


def run_batch(m, tag, cmds):
    """跑一个批次，返回 (新截图路径列表[按 mtime 升序], 原始输出文本)。"""
    before = snap_names()
    out = m.batch(*cmds)
    time.sleep(0.6)
    new = sorted(snap_names() - before,
                 key=lambda n: os.path.getmtime(os.path.join(SHOT_DIR, n)))
    paths = []
    for i, n in enumerate(new):
        dst = os.path.join(OUT, '%s-%s.png' % (tag, i + 1 if len(new) > 1 else '1'))
        shutil.copy2(os.path.join(SHOT_DIR, n), dst)
        paths.append(dst)
        print('    [shot] %s → %s' % (n, os.path.basename(dst)))
    return paths, out


def first_card_box(m, raw):
    """从 `get box .terminal-card` 的原始输出里抠出坐标。

    `get box` 的输出形如（**带标签、每行一项**）：
        x:      106
        y:      194.34375
        width:  419
        height: 401.53125
    绝不能直接 `re.findall(r'\\d+')` —— 那会把页面标题 / URL 里的 `8805` 也吃进来
    （上一版实测拿到 `width=8805.0`，若照着裁剪必然裁到空白）。
    """
    d = {}
    for k in ('x', 'y', 'width', 'height'):
        mm = re.search(r'(?m)^%s:\s*(-?[\d.]+)' % k, raw)
        if mm:
            d[k] = float(mm.group(1))
    if len(d) == 4:
        return [d['x'], d['y'], d['width'], d['height']]
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    m = load()

    print('== 阶段 1/3：未悬停 → 悬停（同一批次，页面状态才保持）==')
    m.close_all()
    _, out1 = run_batch(m, '01', [
        'set viewport 1000 900', 'open ' + m.URL, 'wait 8000',
        'get box .terminal-card',
        'screenshot',                     # 未悬停
        'hover .terminal-card', 'wait 900',
        'get styles .card-archive',
        'screenshot',                     # 悬停后
    ])
    with open(os.path.join(HERE, 'shot_raw_1.txt'), 'w', encoding='utf-8') as f:
        f.write(out1)
    box = first_card_box(m, out1)
    print('    第一张卡的 box =', box)
    with open(os.path.join(HERE, 'shot_box.json'), 'w', encoding='utf-8') as f:
        json.dump({'box': box, 'viewport': [1000, 900]}, f)

    print('== 阶段 2/3：点 × → 确认弹窗 ==')
    _, out2 = run_batch(m, '02', [
        'set viewport 1000 900', 'open ' + m.URL, 'wait 8000',
        'hover .terminal-card', 'wait 900',
        'click .card-archive', 'wait 2600',
        'screenshot', 'get text .modal',
    ])
    with open(os.path.join(HERE, 'shot_raw_2.txt'), 'w', encoding='utf-8') as f:
        f.write(out2)

    print('== 阶段 3/3：确认归档 → 卡片消失 + 已归档区 → 恢复 ==')
    m.close_all()
    done = False
    for attempt in (1, 2, 3):
        _, out3 = run_batch(m, '03', [
            'set viewport 1000 4000', 'open ' + m.URL, 'wait 8000',
            'hover .terminal-card', 'wait 900',
            'click .card-archive', 'wait 2600',
            'click .mfoot>button.primary', 'wait 3500',
            'screenshot',
        ])
        if m.archived_rows():
            done = True
            break
        print('    （第 %d 次归档未生效，重试）' % attempt)
    print('    归档已生效 =', done)
    with open(os.path.join(HERE, 'shot_raw_3.txt'), 'w', encoding='utf-8') as f:
        f.write(out3)

    # 收尾：恢复沙箱库到干净态，便于脚本重复运行
    for attempt in (1, 2, 3):
        m.close_all()
        m.batch('set viewport 1000 4000', 'open ' + m.URL, 'wait 6000',
                'click .archive-section>details>summary', 'wait 1300',
                'click .archive-row>button', 'wait 2600',
                'click .mfoot>button.primary', 'wait 3500')
        if not m.archived_rows():
            print('    沙箱库已恢复干净态（第 %d 次尝试）' % attempt)
            break
    m.close_all()

    print('\n截图目录：', OUT)
    for n in sorted(os.listdir(OUT)):
        print('   ', n, os.path.getsize(os.path.join(OUT, n)), 'bytes')


if __name__ == '__main__':
    main()
