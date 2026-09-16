# -*- coding: utf-8 -*-
"""把取证截图裁成「卡片右上角」的放大对比图，并自检坐标正确。

为什么要自检：裁剪坐标来自 `get box .terminal-card`（页面绝对坐标）。
若 DPR ≠ 1（截图被放大 2 倍）而我按 CSS 像素裁，就会裁到空白处 —— 出来的图
"看着没问题"但其实是错的。故本脚本会对比 A/B 两图在**× 槽位**区域的像素差异，
差异过小就报错退出，绝不交付一张假图。
"""
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r'D:\个股工作台\output\20260916-卡片删除按钮确认'
BOXJSON = os.path.join(HERE, 'shot_box.json')

SCALE = 5            # 放大倍数
CROP_W = 112         # 裁剪宽（CSS px）
CROP_H = 48          # 裁剪高（CSS px）
GAP = 18
LABEL_H = 46
SLOT = 20            # × 的边长（style.css: width/height 20px）
SLOT_OFF = 9         # × 距上/右各 9px


def find(*needles):
    for n in sorted(os.listdir(OUT)):
        if n.endswith('.png') and all(x in n for x in needles):
            return os.path.join(OUT, n)
    return None


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def crop_region(img, box, vw):
    """返回卡片右上角的裁剪图 + ×槽位在裁剪图中的矩形。"""
    x, y, w, h = box
    scale = img.width / float(vw)
    right = x + w
    left = right - CROP_W
    top = y + 1
    px = (int(round(left * scale)), int(round(top * scale)),
          int(round((left + CROP_W) * scale)), int(round((top + CROP_H) * scale)))
    tile = img.crop(px)
    tile = tile.resize((tile.width * SCALE, tile.height * SCALE), Image.LANCZOS)
    # ×槽位矩形（相对裁剪图，已按 scale*SCALE 放大）
    k = scale * SCALE
    slot = (int(round((right - SLOT_OFF - SLOT - left) * k)),
            int(round((y + SLOT_OFF - top) * k)),
            int(round((right - SLOT_OFF - left) * k)),
            int(round((y + SLOT_OFF + SLOT - top) * k)))
    return tile, slot, scale


def slot_diff(a, b, slot):
    ca = a.crop(slot).convert('L')
    cb = b.crop(slot).convert('L')
    diff = ImageChops.difference(ca, cb)
    hist = diff.histogram()
    total = sum(hist)
    mean = sum(i * n for i, n in enumerate(hist)) / float(total or 1)
    return mean


def main():
    meta = json.load(open(BOXJSON, encoding='utf-8'))
    box = meta.get('box')
    vw = meta.get('viewport', [1000, 900])[0]
    if not box:
        print('[FAIL] shot_box.json 里没有 box 坐标，无法裁剪'); return 1

    pa = find('01-1')
    pb = find('01-2')
    print('未悬停图 =', os.path.basename(pa or '?'))
    print('悬停图   =', os.path.basename(pb or '?'))
    if not pa or not pb:
        print('[FAIL] 找不到阶段 1 的两张截图'); return 1

    ia, ib = Image.open(pa).convert('RGB'), Image.open(pb).convert('RGB')
    print('截图尺寸 = %s / %s ; 视口宽 = %s' % (ia.size, ib.size, vw))

    ta, slot, scale = crop_region(ia, box, vw)
    tb, _, _ = crop_region(ib, box, vw)
    print('DPR(推导) = %.2f ; 裁剪像素 = %s ; ×槽位(裁剪图内) = %s'
          % (scale, ta.size, slot))

    d = slot_diff(ta, tb, slot)
    print('×槽位区域 A/B 灰度平均差 = %.2f' % d)
    if d < 6:
        print('[FAIL] ×槽位区域几乎无差异 —— 裁剪坐标很可能不对（DPR/坐标系不符），'
              '拒绝交付假图。请检查 shot_box.json 与 screenshot 的实际尺寸。')
        return 1
    print('[OK] 槽位区域差异显著 ⇒ 裁剪坐标正确，A 为空槽、B 有 ×')

    # 单张放大图（在 B 上画出槽位框，便于对照）
    for tag, tile in (('01-未悬停-右上角放大', ta), ('02-悬停后-右上角放大', tb)):
        out = tile.copy()
        dr = ImageDraw.Draw(out)
        dr.rectangle(slot, outline=(64, 184, 239), width=2)
        p = os.path.join(OUT, tag + '.png')
        out.save(p)
        print('   写', p)

    # 并排对比图
    W = ta.width * 2 + GAP
    H = LABEL_H + max(ta.height, tb.height)
    canvas = Image.new('RGB', (W, H), (7, 28, 47))
    canvas.paste(ta, (0, LABEL_H))
    canvas.paste(tb, (ta.width + GAP, LABEL_H))
    dr = ImageDraw.Draw(canvas)
    dr.rectangle((ta.width + GAP - 1, 0, ta.width + GAP, H), fill=(38, 74, 102))
    f = font(26)
    dr.text((10, 10), 'A. NO HOVER  ->  no X in the top-right corner',
            fill=(150, 175, 195), font=f)
    dr.text((ta.width + GAP + 10, 10),
            'B. HOVER  ->  X appears (click it to delete)', fill=(120, 220, 255),
            font=f)
    # 在两张图上都标出槽位
    dr.rectangle((slot[0], LABEL_H + slot[1], slot[2], LABEL_H + slot[3]),
                 outline=(64, 184, 239), width=2)
    dr.rectangle((ta.width + GAP + slot[0], LABEL_H + slot[1],
                  ta.width + GAP + slot[2], LABEL_H + slot[3]),
                 outline=(64, 184, 239), width=2)
    p = os.path.join(OUT, '03-悬停对比-右上角放大.png')
    canvas.save(p)
    print('   写', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
