# -*- coding: utf-8 -*-
"""几何探针：卡片右上角「×」与状态徽章到底有没有挤在一起。

背景
----
截至 2026-09-16，归档按钮的浏览器验证只断言过 `opacity` / `pointer-events`
（"悬停才显形"），**从没量过它的几何位置**。
而 CSS 里 `.terminal-card-head { padding-right: 24px; }` 正是为 × 预留槽位的
—— 但那是**推导**，不是**测量**。用户的原始诉求恰恰是"右上角出现一个叉"，
所以这个角落值得实测一次。

本探针回答四个问题（在多个视口宽度下）：
  ① × 是否完整落在卡片内部（不被 `overflow:hidden` 裁掉）
  ② × 与卡片上/右边缘的距离是否稳定（不因视口变化而漂移）
  ③ **× 与状态徽章是否重叠**（徽章文案变长时会不会顶到 × 底下）
  ④ × 的点击热区尺寸是否仍是 20×20（不被 flex 挤压变形）

铁律遵守
--------
- `eval` 参数里**不写任何引号**（本环境 CLI 会把引号吃掉）→ 选择器一律用
  `String.fromCharCode(...)` 构造；返回值也不含引号（用 `,` / `;` 拼串）。
- 一次 batch ≤ 7 条命令，避免输出块被合并导致读数丢失。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import browser_e2e_archive as B   # noqa: E402  公共 batch / step / URL

TOL = 0.75          # px 容差：亚像素布局
CSS_OFFSET = 9.0    # style.css: .card-archive { top:9px; right:9px }
EXPECT_SIZE = 20.0  # style.css: .card-archive { width/height: 20px }
# 注意：getBoundingClientRect() 量的是 **border-box**，而 position:absolute 的
# top/right 是相对包含块的 **padding box**。卡片有 `border: 1px solid`，
# 所以实测偏移 = CSS_OFFSET + border-width。**不要写死 9.0**（这是首跑 8 条假红的根因），
# 改成从 DOM 读 border-width 推导 —— 属于"探针自身缺陷"，见 ENV-TRAPS ⑯ 的同类教训。


def cp(s):
    """把字符串转成 String.fromCharCode(...) 用的码点串（绕开引号被吃）。"""
    return ','.join(str(ord(ch)) for ch in s)


CP_CARD = cp('terminal-card')
CP_HEAD = cp('terminal-card-head')
CP_BTN = cp('card-archive')
CP_BADGE = cp('badge')

# 全卡片遍历：每行 i,card(l,t,r,b),btn(l,t,r,b),badge(l,t,r,b)
# 字段用 ',' 分隔、行用 ';' 分隔 —— 结果串里没有任何引号，正则好取。
EXPR = (
    'String((function(){'
    'var cards=document.getElementsByClassName(String.fromCharCode(' + CP_CARD + '));'
    'var R=function(e){if(!e)return[-1,-1,-1,-1];var r=e.getBoundingClientRect();'
    'return[Math.round(r.left*10)/10,Math.round(r.top*10)/10,'
    'Math.round(r.right*10)/10,Math.round(r.bottom*10)/10];};'
    'var rows=[];'
    'for(var i=0;i<cards.length;i++){'
    'var c=cards[i];'
    'var btn=c.getElementsByClassName(String.fromCharCode(' + CP_BTN + '))[0];'
    'var head=c.getElementsByClassName(String.fromCharCode(' + CP_HEAD + '))[0];'
    'var bdg=head?head.getElementsByClassName(String.fromCharCode(' + CP_BADGE + '))[0]:null;'
    'rows.push([i].concat(R(c)).concat(R(btn)).concat(R(bdg))'
    '.join(String.fromCharCode(44)));'
    '}'
    'rows.push(window.innerWidth+String.fromCharCode(44)'
    '+parseFloat(getComputedStyle(cards[0]).borderTopWidth));'
    'return rows.join(String.fromCharCode(59));'
    '})())'
)


def main():
    print('=' * 74)
    print('几何探针：卡片右上角「×」× 状态徽章（多视口实测）')
    print('  期望：× 距上/右边缘 = %gpx(CSS) + border-width、尺寸 %.0fx%.0fpx、与徽章不重叠'
          % (CSS_OFFSET, EXPECT_SIZE, EXPECT_SIZE))
    print('=' * 74)

    widths = [1440, 1000, 768, 560]
    all_rows = {}

    for w in widths:
        print('\n--- 视口 %dpx ---' % w)
        out = B.batch('set viewport %d 1000' % w, 'open ' + B.URL, 'wait 6000',
                      'eval ' + EXPR)
        vals = re.findall(r'"([^"\n]*)"', out)
        payload = ''
        for v in vals:
            if ';' in v or re.match(r'^\d+(\.\d+)?$', v):
                payload = v
                break
        if not payload:
            B.step('视口 %d：拿到几何读数' % w, False, '输出=%r' % out[:200])
            all_rows[w] = []
            continue

        rows = []
        for chunk in payload.split(';'):
            nums = [float(x) for x in chunk.split(',') if x not in ('', '-')]
            if len(nums) == 13:
                rows.append(nums)
        all_rows[w] = rows

        if not rows:
            B.step('视口 %d：解析出卡片几何' % w, False, 'payload=%r' % payload[:200])
            continue

        meta = [c for c in payload.split(';')][-1]
        meta_nums = [float(x) for x in meta.split(',') if x not in ('', '-')]
        vw = meta_nums[0] if meta_nums else 0
        border = meta_nums[1] if len(meta_nums) > 1 else -1
        if border < 0:
            B.step('视口 %d：读到卡片 border-width' % w, False, 'meta=%r' % meta)
            continue
        expect_edge = CSS_OFFSET + border
        B.step('视口 %d：实测 viewport=%s，解析到 %d 张卡片（border-width=%gpx → 期望偏移 %gpx）'
               % (w, vw, len(rows), border, expect_edge),
               abs(vw - w) <= 20 and len(rows) > 0, 'innerWidth=%s' % vw)

        # ① × 完整落在卡片内
        escape = [r[0] for r in rows
                  if not (r[5] >= r[1] - TOL and r[7] <= r[3] + TOL
                          and r[6] >= r[2] - TOL and r[8] <= r[4] + TOL)]
        B.step('① × 完整落在卡片内部（不被 overflow:hidden 裁切）%d/%d'
               % (len(rows) - len(escape), len(rows)), not escape,
               '越界卡片=%s' % escape)

        # ② 距上/右边缘稳定（期望值由 DOM 的 border-width 推导，非魔数）
        dr = [round(r[3] - r[7], 1) for r in rows]     # card.right - btn.right
        dt = [round(r[6] - r[2], 1) for r in rows]     # btn.top - card.top
        off_r = [v for v in dr if abs(v - expect_edge) > TOL]
        off_t = [v for v in dt if abs(v - expect_edge) > TOL]
        B.step('② × 距卡片右边缘恒为 %gpx（实测 %s）' % (expect_edge, sorted(set(dr))),
               not off_r, '偏离=%s' % off_r)
        B.step('②b × 距卡片上边缘恒为 %gpx（实测 %s）' % (expect_edge, sorted(set(dt))),
               not off_t, '偏离=%s' % off_t)

        # ③ 与状态徽章不重叠
        pairs = [r for r in rows if r[9] >= 0]
        gaps = [round(r[5] - r[11], 1) for r in pairs]   # btn.left - badge.right
        overlap = [(r[0], g) for r, g in zip(pairs, gaps) if g < -TOL]
        B.step('③ × 与状态徽章不重叠（%d/%d 张有徽章，最小间隙 %.1fpx）'
               % (len(pairs) - len(overlap), len(pairs), min(gaps) if gaps else -999),
               not overlap, '重叠=%s' % overlap)

        # ④ 热区尺寸
        ws = [round(r[7] - r[5], 1) for r in rows]
        hs = [round(r[8] - r[6], 1) for r in rows]
        bad = [(w_, h_) for w_, h in zip(ws, hs) if abs(w_ - EXPECT_SIZE) > TOL
               or abs(h - EXPECT_SIZE) > TOL]
        B.step('④ × 热区恒为 %.0fx%.0fpx（实测 %s × %s）'
               % (EXPECT_SIZE, EXPECT_SIZE, sorted(set(ws)), sorted(set(hs))),
               not bad, '异常=%s' % bad)

        sample = rows[0]
        print('        首卡几何 card=(%.1f,%.1f,%.1f,%.1f) btn=(%.1f,%.1f,%.1f,%.1f) '
              'badge=(%.1f,%.1f,%.1f,%.1f)'
              % (sample[1], sample[2], sample[3], sample[4],
                 sample[5], sample[6], sample[7], sample[8],
                 sample[9], sample[10], sample[11], sample[12]))

    # ⑤ 卡片数量随视口变化（确认布局真的响应了，否则前面几组是同一个布局）
    counts = {w: len(all_rows.get(w, [])) for w in widths}
    print('\n各视口卡片数：%s' % counts)

    # ⑥ 跨视口的**不变量**：× 与徽章的间隙不随视口漂移（这才是真正要守的东西）
    gaps_by_w = {}
    for w in widths:
        rs = [r for r in all_rows.get(w, []) if r[9] >= 0]
        if rs:
            gaps_by_w[w] = min(round(r[5] - r[11], 1) for r in rs)
    uniq = sorted(set(gaps_by_w.values()))
    B.step('⑥ × 与徽章的间隙跨视口恒定（1440→560px 实测 %s）' % uniq,
           len(uniq) == 1 and uniq[0] > 0, 'gaps=%s' % gaps_by_w)

    # ⑦ 卡片宽度确实随视口变化（证明 ⑥ 不是"布局根本没动"的假绿）
    widths_seen = set()
    for w in widths:
        for r in all_rows.get(w, []):
            widths_seen.add(round(r[3] - r[1], 0))
    B.step('⑦ 卡片宽度确实随视口变化（%d 种，证明布局真的重排过）' % len(widths_seen),
           len(widths_seen) >= 3, 'card widths=%s' % sorted(widths_seen))

    B.close_all()
    print('\n' + '=' * 74)
    print('汇总：TOTAL=%d PASS=%d FAIL=%d SKIP=0'
          % (B.PASS + B.FAIL, B.PASS, B.FAIL))
    return 0 if B.FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
