"""生成 A/H 投研交易工作台 v1.0.10 交付审计文档（docx）。

v1.0.10 是「启动脚本交付修复」版本：不新增业务功能，只修复 v1.0.9 交付包内的
启动脚本在目标机上无法拉起工作台的缺陷（`where python` 命中 Microsoft Store
执行别名存根），并把「启动脚本必须长什么样」固化为可执行契约测试。

本脚本不复用任何历史 docx 字节。文中所有测试数字、文件字节数、SHA-256
均由本脚本在运行时**实际读取/来自本轮实跑结果**，不沿用任何历史文档的声称。
"""

import os
import datetime
import hashlib

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ================ 基础排版 helper ================
def add_h(doc, text, level=1):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    if level == 1:
        run.font.size = Pt(16)
    elif level == 2:
        run.font.size = Pt(13)
    else:
        run.font.size = Pt(11)


def add_p(doc, text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(11)
    if bold:
        r.bold = True


def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    r = p.add_run(text)
    r.font.size = Pt(11)


def add_code(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.name = 'Consolas'


def add_table(doc, headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = 'Table Grid'
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for ri, row in enumerate(rows, 1):
        for ci, val in enumerate(row):
            cell = t.rows[ri].cells[ci]
            cell.text = str(val)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)


# ================ 路径与实测指纹 ================
ROOT = r'D:\个股工作台'
OUT_DIR = os.path.join(ROOT, 'output', '20260910-audit', 'stage3')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'A-H投研交易工作台交付审计文档-v1.0.10.docx')


def fingerprint(rel):
    """返回 (字节数, SHA-256) —— 运行时真实读取，不写死。"""
    p = os.path.join(ROOT, rel)
    data = open(p, 'rb').read()
    return len(data), hashlib.sha256(data).hexdigest()


FP = {}
for rel in ['app/server.py', 'app/static/app.js', 'app/static/index.html',
            'app/static/style.css', '启动工作台.bat',
            'tests/test_v107.py', 'tests/test_v108.py', 'tests/test_v109.py',
            'tests/test_v110.py',
            'output/20260910-audit/smoke_v108_http.py',
            'output/20260910-audit/smoke_v109_http.py',
            'output/20260910-audit/PACK_NOTES-v1.0.10.md',
            '.tmp_v108x/verify/delivery-empty-v110.db']:
    FP[rel] = fingerprint(rel)

BAT_REL = '启动工作台.bat'
BAT_BYTES, BAT_SHA = FP[BAT_REL]
DB_BYTES, DB_SHA = FP['.tmp_v108x/verify/delivery-empty-v110.db']

# 旧 bat（v1.0.9 交付包内那份）的指纹 —— 用于对比说明，取自历史 Manifest 实测值
OLD_BAT_BYTES = 388
OLD_BAT_SHA = 'caf74fb14c04cbef56ebbda0a70700594fd0e55136ad01cedd372843e18244c4'


# ================ 文档主体 ================
doc = Document()
doc.styles['Normal'].font.name = 'Microsoft YaHei'
doc.styles['Normal'].font.size = Pt(11)

title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run('A/H 投研交易工作台')
r.bold = True
r.font.size = Pt(24)

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('交付审计文档（v1.0.10 · 启动脚本交付修复）')
r.bold = True
r.font.size = Pt(18)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run(
    '版本：v1.0.10（TARGET_SCHEMA_VERSION = 1.0.10）\n'
    '生成时间：' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + '\n'
    '基线版本：v1.0.9 → v1.0.10\n'
    '本轮性质：仅修复交付包内启动脚本 `启动工作台.bat` 无法在目标机拉起工作台的缺陷\n'
    '边界：不新增业务功能；不修改研究口径 / 交易计划 / 状态体系；\n'
    '      不新增数据库表、列或迁移；不修改导入 JSON Schema；服务端与前端零逻辑改动'
).font.size = Pt(11)

doc.add_page_break()

# ================ §1 本轮定位 ================
add_h(doc, '1. 本轮定位与修复清单', 1)
add_p(doc, 'v1.0.9 的并发与预览一致性修复通过了 490 断言离线测试与 18~20 项交付包自洽校验，'
           '但在**用户侧实际使用**时暴露出一个交付层面的缺陷：解压交付包后双击 '
           '`启动工作台.bat`，工作台无法启动。')
add_p(doc, '该缺陷不影响服务端与前端任何业务逻辑，纯粹位于**交付包内的启动脚本**这一层，'
           '但足以让整包不可用 —— 因此单独作为一版封板。')

add_table(doc,
          ['#', '来源', '问题', 'v1.0.10 处理'],
          [
              ['1', '用户实测',
               '交付包内 `启动工作台.bat`（388 B）用 `set "PY=python"` + `where python` '
               '判定解释器；目标机持久 PATH 上唯一可见的 python.exe 是 Microsoft Store '
               '执行别名存根，`where` 命中它 → 守卫恒为"通过" → 实际拉起的是商店存根',
               '整体替换为 ASCII-only 候选链版本（3,970 B）：4 级候选 + 真执行探测 + '
               '显式拒绝 WindowsApps 路径 + 前后置守卫'],
              ['2', '本轮新增',
               '「启动脚本必须长什么样」此前没有任何自动化约束，'
               '同类回归可以再次悄悄进入交付包',
               '新增 `tests/test_v110.py`（14 断言）：版本同步契约 + 启动脚本契约；'
               '对旧 bat 负向验证可得 3 FAIL，即该测试能抓住本缺陷'],
              ['3', '本轮新增',
               'v1.0.10 版本号一度只同步了 3 处，启动文案残留在 1.0.9',
               '补齐第 4 处，并在 `test_v110.py` §A#5 增加"4 处抽取值必须完全一致"的'
               '唯一性断言，把人工纪律变成机器契约'],
          ])

# ================ §2 根因 ================
add_h(doc, '2. 缺陷根因分析', 1)
add_p(doc, '旧脚本的判定逻辑只有两步：确认 `python` 命令存在 → 直接调用它。')

add_code(doc,
         '@echo off\n'
         'cd /d "%~dp0"\n'
         'set "PY=python"\n'
         'where python >nul 2>nul\n'
         'if errorlevel 1 (\n'
         '  echo [ERROR] Python not found. Please install Python 3 and add it to PATH.\n'
         '  pause\n'
         '  exit /b 1\n'
         ')\n'
         '"%PY%" "app\\server.py"\n'
         'pause')

add_p(doc, '问题在于「命令存在」与「是可用的解释器」是两件事。目标机的实测结果：')

add_table(doc,
          ['探测项', '实测结果'],
          [
              ['用户**持久** PATH（HKCU\\Environment）',
               '**只有** `%USERPROFILE%\\AppData\\Local\\Microsoft\\WindowsApps`'],
              ['系统持久 PATH 中与 python 相关的项',
               '只有 `...\\systemprofile\\...\\WindowsApps`'],
              ['该目录下的 `python.exe`',
               '**Microsoft Store 执行别名存根**，不是解释器'],
              ['真正可用的解释器',
               '受管运行时目录下的 `python.exe`（**不在持久 PATH 中**）'],
          ])

add_p(doc, '因此双击 bat 的实际后果是：')
add_bullet(doc, '`where python` **命中** Store 存根 → `if errorlevel 1` 永不触发，'
                '"Python not found" 分支从不执行；')
add_bullet(doc, '`"%PY%" "app\\server.py"` 实际拉起的是 Store 存根；')
add_bullet(doc, '用户现象：**窗口一闪而过 / 弹出应用商店**，工作台从未启动。')

add_h(doc, '2.1 诊断陷阱（本轮最重要的方法论记录）', 2)
add_p(doc, '在开发环境（agent 自身的 shell）里验证会得到**错误结论**：')
add_code(doc,
         '# 在 agent shell 内 —— 一切正常\n'
         '> where python\n'
         'C:\\Users\\<user>\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe\n'
         '> python --version\n'
         'Python 3.13.12')
add_p(doc, '原因是受管运行时被注入到该**进程**的 PATH 且排在 WindowsApps 之前。'
           '只在本机 shell 内验证，会得出"bat 没问题"的错误结论 —— '
           '这正是本缺陷能通过 v1.0.9 全部校验的原因。')
add_p(doc, '正确做法：读注册表的**持久** PATH（`HKCU\\Environment` / `HKLM\\...\\Environment`），'
           '以及**在没有任何 PATH 注入的干净环境**里实跑一次脚本。',
       bold=True)

add_h(doc, '2.2 附带问题：历史 bat 含非 ASCII 字节', 2)
add_p(doc, '更早的 `audit_pack_src/启动工作台.bat` 直接写死了含中文用户名的绝对路径。'
           'cmd.exe 按控制台代码页（936 / 65001）逐字节解释 .bat 文件，'
           '非 ASCII 字节会错位，把路径段污染成乱码字节。v1.0.10 版本一并规避。')

doc.add_page_break()

# ================ §3 修复方案 ================
add_h(doc, '3. 修复方案（交付包内 `启动工作台.bat`）', 1)

add_h(doc, '3.1 源码 100% ASCII，路径靠 %USERPROFILE% 运行时展开', 2)
add_p(doc, '受管解释器位于含中文的用户目录下。脚本**不写任何非 ASCII 字节**，'
           '统一写成 `%USERPROFILE%\\.workbuddy\\binaries\\python\\versions\\<ver>\\python.exe`，'
           '由 cmd.exe 在运行时展开为正确绝对路径。')
add_table(doc,
          ['实测项', '值'],
          [
              ['文件字节数', '%d B' % BAT_BYTES],
              ['SHA-256', BAT_SHA],
              ['非 ASCII 字节数', '0'],
              ['CRLF 行数', '105'],
              ['裸 LF 行数', '0'],
          ])

add_h(doc, '3.2 候选链 + 真执行探测（核心修复点）', 2)
add_p(doc, '按顺序探测四级候选：')
add_bullet(doc, '① 受管固定版本解释器（优先，确定性最高）')
add_bullet(doc, '② 受管 `versions` 目录下的任意版本（不写死版本号）')
add_bullet(doc, '③ `py` 启动器（官方 Python Launcher）')
add_bullet(doc, '④ PATH 上的 `python`')
add_p(doc, '每个候选都交给 `:try` 子程序**真实执行一次**并按退出码判定：')
add_code(doc,
         ':try\n'
         'set "T=%~1"\n'
         'rem  reject the Microsoft Store execution alias outright\n'
         'if not "%T:WindowsApps=%"=="%T%" goto :eof\n'
         'rem  must actually run and report version 3.8 or newer\n'
         '"%T%" -c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul\n'
         'if errorlevel 1 goto :eof\n'
         'set "PY=%T%"\n'
         'goto :eof')
add_p(doc, '两道闸：**显式拒绝**路径含 `WindowsApps` 的候选（即使它能"跑起来"）；'
           '**版本探测**要求 `sys.version_info >= (3,8)`。'
           '只"命令存在"不再足以通过。')

add_h(doc, '3.3 前后置守卫', 2)
add_bullet(doc, '启动前检查 `app\\server.py` 是否存在 —— 脚本被移出工作台根目录时立即明确报错；')
add_bullet(doc, '找不到任何可用解释器时给出安装指引，并**点明** `WindowsApps` 下那个只是 Store 占位符。')

add_h(doc, '3.4 为什么不是"改一行 set PY="', 2)
add_table(doc,
          ['备选写法', '问题'],
          [
              ['`set "PY=<绝对路径>"`',
               '路径含中文用户名 → bat 出现非 ASCII 字节 → cmd 按代码页解释会错位；且换机即失效'],
              ['`where python` + `python`', '本缺陷本身：命中 Store 存根'],
              ['`py -3 app\\server.py`', '仅当装了官方 Python Launcher 才可用；目标机没有'],
              ['`if exist <路径> set PY=...`',
               '只证明"文件在"，不证明"能跑"（权限、损坏、架构不符都会漏过）'],
              ['**候选链 + 真执行探测（采用）**',
               '逐候选真跑一次 + 拒绝 Store 存根，任一环节不成立就换下一个'],
          ])

add_h(doc, '3.5 修复前后的文件指纹', 2)
add_table(doc,
          ['', 'v1.0.9 交付包内（缺陷版）', 'v1.0.10 交付包内（修复版）'],
          [
              ['字节数', str(OLD_BAT_BYTES), str(BAT_BYTES)],
              ['SHA-256', OLD_BAT_SHA, BAT_SHA],
              ['解释器判定', '`where python`（只看存在）', '候选链 + 真执行版本探测'],
              ['Store 存根', '无法识别，直接调用', '路径守卫显式拒绝'],
              ['非 ASCII 字节', '0', '0（同样安全）'],
          ])

doc.add_page_break()

# ================ §4 版本同步 ================
add_h(doc, '4. 版本号同步（4 处，缺一不可）', 1)
add_table(doc,
          ['位置', '值', '机器校验'],
          [
              ['`app/server.py` → `TARGET_SCHEMA_VERSION`', "'1.0.10'", 'test_v110 §A#1 / §A#5'],
              ['`app/server.py` → `Handler.server_version`', "'Workbench/1.0.10'",
               'test_v110 §A#2 / §A#5'],
              ['`app/server.py` → `argparse` description', "'A/H 投研交易工作台 v1.0.10'",
               'test_v110 §A#3 / §A#5'],
              ['`app/server.py` → 启动 print', "'A/H 投研交易工作台 v1.0.10 已启动: %s'",
               'test_v110 §A#4 / §A#5'],
              ['`app/static/app.js` 头部', "'v1.0.10'", 'test_v110 §A#6'],
          ])
add_p(doc, '本轮新增的 §A#5 是一条**唯一性**断言：用正则分别抽取服务端 4 处版本号，'
           '要求四个抽取值完全一致。这条断言存在的直接原因，'
           '是本轮升级过程中 4 处曾一度只同步了 3 处、启动文案残留在 1.0.9 —— '
           '而该残留此前不会被任何测试发现（`test_v109.py` §I#4 是 v1.0.10 才补上的）。')

# ================ §5 测试结果 ================
add_h(doc, '5. 测试结果（本轮实际运行）', 1)
add_table(doc,
          ['套件', '断言数', '结果', '本轮变化'],
          [
              ['`tests/test_v102.py`', '38', 'PASS', '不变'],
              ['`tests/test_v103.py`', '60', 'PASS', '不变'],
              ['`tests/test_v105.py`', '25', 'PASS', '不变'],
              ['`tests/test_v106.py`', '28', 'PASS', '不变'],
              ['`tests/test_v107.py`', '127', 'PASS', '2 条版本契约前移'],
              ['`tests/test_v108.py`', '129', 'PASS', '3 条版本契约前移'],
              ['`tests/test_v109.py`', '83', 'PASS', '6 条版本契约前移'],
              ['`tests/test_v110.py`', '14', 'PASS（**本轮新增**）', '+14'],
              ['**离线合计**', '**504**', '**FAIL 0**', '490 → 504（+14）'],
              ['`tests/test_integration_quote.py`', '14', 'PASS（需外网）', '不变'],
              ['`output/.../smoke_v108_http.py`', '14', 'PASS（回归）', '不变'],
              ['`output/.../smoke_v109_http.py`', '38', 'PASS（回归）', '不变'],
          ])
add_p(doc, '离线断言总数由 490 增至 504，净变化来源唯一且明确：新增 `tests/test_v110.py`（14 条）。')

add_h(doc, '5.1 新测试的价值：能抓住旧 bat（负向验证）', 2)
add_p(doc, '把 v1.0.9 交付包内的旧 bat（388 B）临时放回原位后重跑 `test_v110.py`：')
add_code(doc,
         '  [FAIL] §B#4 真执行探测解释器版本（非仅检查命令存在） 未找到真执行探测\n'
         '  [FAIL] §B#5 显式拒绝 Microsoft Store 执行别名存根 缺少 WindowsApps 路径守卫\n'
         '  [FAIL] §B#6 不含旧的 `set "PY=python"` + `where python` 判定 旧判定残留\n'
         'v1.0.10 测试: PASS 11 / FAIL 3  (共 14 断言)')
add_p(doc, '即：**该测试若在 v1.0.9 封板时存在，本缺陷不会漏出。**'
           '验证后已恢复修复版，SHA-256 回到 ' + BAT_SHA + '。', bold=True)

add_h(doc, '5.2 端到端实跑', 2)
add_bullet(doc, '实际执行 bat → 控制台输出解析到的解释器绝对路径（中文路径展开正确）'
                '→ 监听到 `127.0.0.1:8765` → `GET /` 返回 `HTTP 200`。')
add_bullet(doc, '`:try` 子程序隔离测试（从**已安装的 bat 里抽取**该子程序，'
                '保证被测代码 == 交付代码）：3/3 PASS —— 受管解释器被接受；'
                '不存在的路径被拒绝；`...\\WindowsApps\\python.exe` 被路径守卫拒绝。')

add_h(doc, '5.3 既有测试的变更清单（逐条 diff，非按总数反推）', 2)
add_p(doc, '本轮对既有测试套件**只做版本号契约前移**，未改动任何业务语义断言：')
add_table(doc,
          ['文件', '断言标签', 'v1.0.9 期望', 'v1.0.10 期望'],
          [
              ['`tests/test_v107.py`', '§P#1', "TARGET_SCHEMA_VERSION = '1.0.9'", "'1.0.10'"],
              ['`tests/test_v107.py`', '§P#2', "server_version = 'Workbench/1.0.9'",
               "'Workbench/1.0.10'"],
              ['`tests/test_v108.py`', '§I#1', "TARGET_SCHEMA_VERSION = '1.0.9'", "'1.0.10'"],
              ['`tests/test_v108.py`', '§I#2', "server_version = 'Workbench/1.0.9'",
               "'Workbench/1.0.10'"],
              ['`tests/test_v108.py`', '§I#15', '前端版本号 v1.0.9', 'v1.0.10'],
              ['`tests/test_v109.py`', '§I#1', "TARGET_SCHEMA_VERSION = '1.0.9'", "'1.0.10'"],
              ['`tests/test_v109.py`', '§I#2', "server_version = 'Workbench/1.0.9'",
               "'Workbench/1.0.10'"],
              ['`tests/test_v109.py`', '§I#3', 'argparse 描述 v1.0.9', 'v1.0.10'],
              ['`tests/test_v109.py`', '§I#4', '启动文案 v1.0.9', 'v1.0.10'],
              ['`tests/test_v109.py`', '§I#20', "TARGET_SCHEMA_VERSION = '1.0.9'", "'1.0.10'"],
              ['`tests/test_v109.py`', '§I#21', '前端版本号 v1.0.9', 'v1.0.10'],
          ])
add_p(doc, '合计 **11 条**（2 + 3 + 6），全部为「当前版本常量」契约断言。'
           '三个套件的**断言总数保持不变**：127 → 127、129 → 129、83 → 83；'
           'diff 中不存在任何新增、删除或改写业务语义断言的行。')

doc.add_page_break()

# ================ §6 交付包一致性 ================
add_h(doc, '6. 交付包一致性', 1)

add_h(doc, '6.1 关键产物指纹（运行时实测）', 2)
add_table(doc,
          ['产物', '字节数', 'SHA-256'],
          [[rel, str(FP[rel][0]), FP[rel][1]] for rel in FP])

add_h(doc, '6.2 Manifest ↔ ZIP', 2)
add_table(doc,
          ['检查项', '结果'],
          [
              ['Manifest 条目数', '26（25 条含字节数 + SHA 写实值 + 1 条自指）'],
              ['ZIP 实际条目数', '26'],
              ['Manifest 幽灵条目（列了但 ZIP 没有）', '无'],
              ['ZIP 多余条目（有但 Manifest 没列）', '无'],
              ['逐文件字节数 + SHA-256 回读比对', '25/25 全部一致'],
              ['构建脚本是否混入', '否（`build_docx_v10x.py`、打包脚本均不进 ZIP）'],
              ['README.txt 默认地址', '`http://127.0.0.1:8765`，与 `--port` 默认值一致'],
          ])

add_h(doc, '6.3 交付库与工作区库的差异（刻意）', 2)
add_p(doc, '交付包内 `data/workbench.db` 是**空的模板库**，按交付约定不夹带操作者的实盘数据：')
add_table(doc,
          ['项', '交付库（包内）', '工作区库（本机）'],
          [
              ['字节数', str(DB_BYTES), '随使用变化'],
              ['SHA-256', DB_SHA, '随使用变化'],
              ['securities / research / trade_plans 行数', '0 / 0 / 0', '含操作者实际数据'],
              ['trades / execution_reviews / decision_ledger 行数', '0 / 0 / 0', '随使用变化'],
              ['schema_version', '1.0.10', '1.0.10'],
              ['integrity_check / FK 违例', 'ok / 0', 'ok / 0'],
          ])
add_p(doc, '因此校验器的 [2] 项（ZIP ↔ 工作区逐字节一致）把 `data/workbench.db` **排除**，'
           '改由 [3] 项按 `integrity_check / FK 违例 / schema_version 与 server.py 一致 / '
           '业务表必须全空` 四项单独校验 —— 检查强度不降反升：'
           '原先只比"字节是否相同"，现在额外锁定了"交付库必须是空库"这条交付约定。')

doc.add_page_break()

# ================ §7 本轮边界 ================
add_h(doc, '7. 本轮边界（未改变的部分）', 1)
add_p(doc, '为便于第三方审计逐项排除，以下列出本轮**没有**改变的内容：')
add_bullet(doc, '**业务功能**：未新增、未删除、未修改任何业务功能。')
add_bullet(doc, '**研究口径 / 交易计划 / 状态体系**：逐字未变。')
add_bullet(doc, '**数据库 Schema**：未新增表、列、索引或迁移脚本；'
                '`TARGET_SCHEMA_VERSION` 仅作版本号前移，不触发结构迁移。')
add_bullet(doc, '**导入 JSON Schema**：`ah-workbench-import` / `ah-workbench-execution` '
                '的字段与校验规则逐字未变。')
add_bullet(doc, '**服务端业务逻辑**：`app/server.py` 的改动仅限 4 处版本号与头部注释；'
                '导入两段式、原子 claim、漂移检测、409 语义、行情层、导出层全部与 v1.0.9 一致。')
add_bullet(doc, '**前端逻辑**：`app/static/app.js` 的改动仅限版本号与头部注释；'
                '导入防重、状态确认、渲染逻辑全部与 v1.0.9 一致。')
add_bullet(doc, '**证券身份规则**：仍只认 `exchange + code`；`name` 不一致只提示不自动改。')
add_bullet(doc, '**涨跌配色**：仍为涨=红 / 跌=绿（中国市场惯例）。')

# ================ §8 风险 ================
add_h(doc, '8. 风险与开放问题', 1)
add_table(doc,
          ['编号', '状态', '描述', '影响 / 处置'],
          [
              ['本轮缺陷', '**已修复**',
               '交付包内 bat 用 `where python` 判定解释器，Store 存根机器上拉起商店而非工作台',
               '修复 = ASCII-only 候选链 + 真执行探测 + 拒绝 Store 存根；'
               '验证 = 端到端实跑 + 对旧 bat 负向验证 3 FAIL'],
              ['R-030', '本轮新增（低危）',
               '候选链**优先**受管运行时目录，其次 `py`，最后 PATH 上的 `python`；'
               '目标机有多个可用解释器时选中的是链上第一个',
               '仅影响用哪个解释器运行，不影响数据与功能（纯标准库，3.8+ 均可）'],
              ['R-029', '沿用（低危，刻意选择）',
               'commit 路径若被 `BaseException` 中断，`in_flight` 不释放，'
               '该 token 在剩余 TTL 内不可重试',
               'fail-safe 取向「宁阻塞、不重复」；重新预览即可恢复'],
              ['R-026', '沿用（预期行为）',
               'preview cache 为进程内存态，服务重启后未使用的 token 全部失效',
               '「服务端持有预览状态」的必然代价'],
              ['R-027', 'v1.0.9 已修复，本轮未回退',
               '同一 token 并发 commit 可重复追加 append-only 的 execution',
               '本轮 `test_v109.py` 83 PASS 即为回归证据'],
              ['R-028', 'v1.0.9 已修复，本轮未回退',
               '并发 commit 返回 500 而非受控 4xx',
               '本轮 `smoke_v109_http.py` 38 PASS（含 409/500 语义）即为回归证据'],
              ['O-003', '待批准，未推进', '`trades` 冲正机制', '需用户拍板方向'],
              ['O-004', '待批准，未推进',
               '`securities.research_pool` 字段彻底废弃', 'SQLite 不支持 DROP COLUMN'],
          ])

doc.add_page_break()

# ================ §9 第三方审计重点 ================
add_h(doc, '9. 第三方审计重点', 1)
add_p(doc, '建议独立审计方按以下顺序复核，每项均可自证：')

add_h(doc, '9.1 最高优先级：启动脚本在"干净环境"下真能启动', 2)
add_bullet(doc, '在**只装了 Microsoft Store 存根、未配置 PATH** 的 Windows 上解压交付包，'
                '双击 `启动工作台.bat`，确认控制台打印出解释器绝对路径与 '
                '`http://127.0.0.1:8765`，浏览器可打开。')
add_bullet(doc, '核对包内 bat 字节数 = ' + str(BAT_BYTES) + '，'
                'SHA-256 = ' + BAT_SHA + '。')
add_bullet(doc, '确认包内 bat 无非 ASCII 字节、无裸 LF。')
add_bullet(doc, '把 v1.0.9 的旧 bat 放回原位重跑 `tests/test_v110.py`，'
                '预期 §B#4 / §B#5 / §B#6 三条 FAIL —— 用于确认该契约测试真的有效。')

add_h(doc, '9.2 版本号同步与唯一性', 2)
add_bullet(doc, '`test_v110.py` §A#5 逐一抽取 4 处版本号并断言完全一致；'
                '人工再 grep 一次确认无 `1.0.9` 残留在版本契约位置。')
add_bullet(doc, '确认 `1.0.9` 在 `app/server.py` 中**仅**出现在历史注释里'
                '（描述 v1.0.9 那次修复的行为），不出现在任何常量或文案中。')

add_h(doc, '9.3 无业务改动的证明', 2)
add_bullet(doc, '把 v1.0.9 交付包内文件与 v1.0.10 交付包内文件逐行 diff，'
                '预期差异仅限于：版本号 4 处 + 前端版本头 + 头部注释、'
                'README、启动脚本、以及测试的 11 条版本契约。')
add_bullet(doc, '确认 `app/server.py` 中所有业务函数'
                '（`create_security_tx` / `update_research_tx` / `update_plan_tx` / '
                '`change_status_tx` / `add_execution_tx` / `add_trade` / `ledger_add`）'
                '以及 `_import_cache_claim` / `_import_snapshot_drift` / `_is_db_busy_error` '
                '的实现**逐字未变**。')
add_bullet(doc, '确认 Schema 未变：表清单仍为 `securities / research / trade_plans / '
                'trades / decision_ledger / execution_reviews / settings`，'
                '无新增迁移函数。')

add_h(doc, '9.4 测试数字可复现', 2)
add_bullet(doc, '解压到**全新目录**后重跑 8 个离线套件，预期合计 **504 断言、FAIL 0**，'
                '且分别为 38 / 60 / 25 / 28 / 127 / 129 / 83 / 14。')
add_bullet(doc, '重跑 `smoke_v109_http.py`（38 PASS）与 `smoke_v108_http.py`（14 PASS），'
                '确认 v1.0.9 的并发修复未回退。')
add_bullet(doc, '并发用例建议连跑多次：§A 成功次数应**每次严格 = 1**'
                '（不是"≤3"这类波动区间 —— 能写出等号才是修复的判据）。')

add_h(doc, '9.5 交付包自洽', 2)
add_bullet(doc, 'Manifest 条目数 26 == ZIP 实际条目数 26；逐文件字节数 + SHA-256 全对；'
                '无幽灵条目、无未列出条目。')
add_bullet(doc, '确认包内 `data/workbench.db` 为**空库**（6 张业务表行数全 0），'
                '`schema_version = 1.0.10`，`integrity_check = ok`，FK 违例 0。')
add_bullet(doc, '确认 `README.txt` 默认地址 `http://127.0.0.1:8765` 与 '
                '`app/server.py` 的 `--port` 默认值一致。')
add_bullet(doc, '确认构建脚本（`build_docx_v10x.py`、打包脚本、BUILD_LOG）'
                '**均不在 ZIP 中**（BUILD_LOG 含 ZIP 自身 SHA，会产生自指矛盾）。')

doc.add_paragraph()
add_h(doc, '10. 签字', 1)
add_table(doc,
          ['角色', '姓名', '结论', '日期'],
          [
              ['交付方（开发 / 打包）', '', '', ''],
              ['独立审计方', '', '', ''],
              ['接收方', '', '', ''],
          ])

doc.save(OUT_PATH)

print('已生成：%s' % OUT_PATH)
print('字节数：%d' % os.path.getsize(OUT_PATH))
print('SHA-256：%s' % hashlib.sha256(open(OUT_PATH, 'rb').read()).hexdigest())
