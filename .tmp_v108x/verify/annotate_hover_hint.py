# -*- coding: utf-8 -*-
"""把「悬停前 / 悬停后」对比图做成中文标注版，直接标出鼠标该停在哪、点哪里。

产出：output/20260916-卡片删除按钮确认/09-哪里悬停-中文标注.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

D = r'D:\个股工作台\output\20260916-卡片删除按钮确认'
SRC = os.path.join(D, '03-悬停对比-右上角放大.png')
DST = os.path.join(D, '09-哪里悬停-中文标注.png')

CJK = r'C:\Windows\Fonts\msyh.ttc'
CJK_B = r'C:\Windows\Fonts\msyhbd.ttc'


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(CJK, size)


src = Image.open(SRC).convert('RGB')
W = max(src.width, 1180)
HEAD = 76
FOOT = 74
canvas = Image.new('RGB', (W, HEAD + src.height + FOOT), (8, 12, 18))
dr = ImageDraw.Draw(canvas)

# ---- 标题 ----
dr.text((18, 12), '鼠标悬停 → 卡片右上角出现「×」→ 点它即可删除（归档）该标的',
        font=font(CJK_B, 24), fill=(240, 195, 106))
dr.text((18, 46), '不用精确瞄准角落：鼠标停在卡片上任意位置，× 就出现',
        font=font(CJK, 17), fill=(140, 175, 205))

# ---- 贴原对比图 ----
canvas.paste(src, (0, HEAD))

# ---- 在右图（悬停后）的 × 上画红圈 + 箭头 ----
CX, CY = 1022, HEAD + 130          # × 图心（按原图目测）
R = 44
dr.ellipse((CX - R, CY - R, CX + R, CY + R), outline=(232, 86, 86), width=4)

AX, AY = 930, HEAD + src.height + 8    # 箭头起点（图下方）
BX, BY = CX - 14, CY + R + 4           # 箭头终点
dr.line((AX, AY, BX, BY), fill=(232, 86, 86), width=4)
dr.polygon([(BX, BY), (BX - 6, BY - 18), (BX + 16, BY - 13)], fill=(232, 86, 86))
dr.text((AX - 8, AY + 10), '点这里删除', font=font(CJK_B, 20), fill=(232, 86, 86))

# ---- 底部中文图例 ----
dr.text((18, HEAD + src.height + 36),
        '左：鼠标不在卡片上 → 右上角空着（状态徽章在最右）    '
        '右：鼠标停在卡片上 → 「×」出现',
        font=font(CJK, 18), fill=(170, 195, 215))

canvas.save(DST)
print('已生成', DST, canvas.size)

# 自检：确认红圈内确实有非背景像素（不是画在空白上）
px = canvas.crop((CX - R, CY - R, CX + R, CY + R))
bright = sum(1 for p in px.getdata() if max(p) > 140)
print('红圈内亮像素 =', bright, '（>200 说明圈住的是真实图形，不是空白）')
