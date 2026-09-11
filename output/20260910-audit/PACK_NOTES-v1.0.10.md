# 个股工作台 v1.0.10 —— 交付说明（启动脚本交付修复）

## 项目

- 名称：A/H 投研交易工作台
- 版本：v1.0.10（`TARGET_SCHEMA_VERSION = '1.0.10'`）
- 基线：v1.0.9 → v1.0.10
- 性质：**只修复交付包内启动脚本 `启动工作台.bat` 无法在目标机启动工作台的缺陷**
- 边界：不新增业务功能；不修改研究口径 / 交易计划 / 状态体系；
  **不新增数据库表、列或迁移**；不修改导入 JSON Schema；**服务端与前端零逻辑改动**

---

## 一、缺陷描述（用户实测发现）

v1.0.9 及更早交付包内的 `启动工作台.bat`（388 B）内容是：

```bat
@echo off
rem A/H investment & trading workbench launcher
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python 3 and add it to PATH.
  pause
  exit /b 1
)
echo Starting workbench, browser will open at http://127.0.0.1:8765
echo Close this window or press Ctrl+C to stop.
"%PY%" "app\server.py"
pause
```

**根因：解释器判定方式在目标机上恒为"通过"，但通过的是假解释器。**

| 探测项 | 目标机实测结果 |
|---|---|
| 用户**持久** PATH（`HKCU\Environment`） | **只有** `%USERPROFILE%\AppData\Local\Microsoft\WindowsApps` |
| 系统持久 PATH 中与 python 相关的项 | 只有 `...\systemprofile\...\WindowsApps` |
| 该目录下的 `python.exe` | **Microsoft Store 执行别名存根**，不是解释器 |
| 真正可用的解释器 | 受管运行时目录下的 `python.exe`（**不在持久 PATH 中**） |

因此双击 bat 时：

1. `where python` **命中** Store 存根 → `if errorlevel 1` 永不触发，
   "Python not found" 分支从不执行；
2. `"%PY%" "app\server.py"` 实际拉起的是 Store 存根；
3. 用户现象：**窗口一闪而过 / 弹出应用商店**，工作台从未启动。

**诊断陷阱（值得记录）**：在 agent 自身的 shell 里，
`where python` 与 `python --version` **都正常** —— 因为受管运行时被注入到该**进程**的 PATH
且排在 WindowsApps 之前。只在本机 shell 内验证会得出"bat 没问题"的错误结论；
必须读注册表的**持久** PATH 才能复现用户侧现象。

### 附带问题：历史上还有一份非 ASCII 的 bat

更早的 `audit_pack_src/启动工作台.bat` 直接写死了含中文用户名的绝对路径
（`C:\Users\<中文>\...`），cmd.exe 按控制台代码页逐字节解释该文件时会错位，
路径段被写成乱码字节。本次一并规避（见下）。

---

## 二、修复方案（交付包内 `启动工作台.bat`，3,970 B）

### 要点 1 —— 源码 100% ASCII，路径靠 `%USERPROFILE%` 在运行时展开

受管解释器位于含中文的用户目录下。bat **不写任何非 ASCII 字节**，
统一写成 `%USERPROFILE%\.workbuddy\binaries\python\versions\<ver>\python.exe`，
由 cmd.exe 在运行时展开为正确绝对路径。实测：源码 3,970 B 全 ASCII、105 个 CRLF、0 个裸 LF。

### 要点 2 —— 候选链 + **真执行探测**

按顺序探测 ① 受管固定版本解释器 → ② 受管 `versions` 目录下任意版本
→ ③ `py` 启动器 → ④ PATH 上的 `python`。

每个候选都交给 `:try` 子程序**真实执行一次**并按退出码判定：

```bat
:try
set "T=%~1"
rem  reject the Microsoft Store execution alias outright
if not "%T:WindowsApps=%"=="%T%" goto :eof
rem  must actually run and report version 3.8 or newer
"%T%" -c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PY=%T%"
goto :eof
```

两道闸：**显式拒绝**路径含 `WindowsApps` 的候选；**版本探测**要求
`sys.version_info >= (3,8)`。只"命令存在"不再足以通过。

### 要点 3 —— 前后置守卫

启动前检查 `app\server.py` 是否存在；找不到任何可用解释器时给出明确指引
（并点明 `WindowsApps` 下那个只是 Store 占位符）。

### 修复后的实际形状

```
   ==============================================
     A/H Workbench
   ==============================================
   Python  : "C:\Users\<用户>\.workbuddy\binaries\python\versions\3.13.12\python.exe"
   Address : http://127.0.0.1:8765

   The browser opens automatically. Keep this window open;
   close it or press Ctrl+C to stop the server.
```

---

## 三、为什么不只是"改一行 `set PY=`"

| 备选写法 | 问题 |
|---|---|
| `set "PY=<绝对路径>"` | 路径含中文用户名 → bat 出现非 ASCII 字节 → cmd 按代码页解释会错位；且换机即失效 |
| `where python` + `python` | 本缺陷本身：命中 Store 存根 |
| `py -3 app\server.py` | 仅当装了官方 Python Launcher 才可用；目标机没有 |
| `if exist <路径> set PY=...` | 只证明"文件在"，不证明"能跑"（路径权限、损坏、架构不符都会漏过） |
| **候选链 + 真执行探测（采用）** | 逐候选真跑一次 + 拒绝 Store 存根，任一环节不成立就换下一个 |

---

## 四、本轮改动范围（服务端与前端零逻辑改动）

| 文件 | 改动 |
|---|---|
| `启动工作台.bat` | **整体替换**为上述候选链版本（388 B → 3,970 B） |
| `app/server.py` | 仅 4 处版本号同步（见第六节）+ 头部增加 v1.0.10 说明注释。**业务逻辑与 v1.0.9 逐字节等价改动为零** |
| `app/static/app.js` | 仅版本号同步 + 头部增加 v1.0.10 说明注释 |
| `README.txt` | 版本号与断言数更新，新增「关于 启动工作台.bat」说明段 |
| `tests/test_v110.py` | **新增**，14 断言（版本同步契约 + 启动脚本契约） |
| `tests/test_v107.py` / `test_v108.py` / `test_v109.py` | 仅版本号契约前移，共 11 条（见第五节），业务语义断言零改动 |

**未改动**：数据库 Schema、迁移逻辑、`TARGET_SCHEMA_VERSION` 以外的一切常量、
所有业务写入函数、行情层、导出层、导入两段式流程、前端全部交互逻辑。

---

## 五、测试结果（本轮实际运行，可复现）

| 套件 | 断言数 | 结果 |
|---|---:|---|
| `tests/test_v102.py` | 38 | PASS |
| `tests/test_v103.py` | 60 | PASS |
| `tests/test_v105.py` | 25 | PASS |
| `tests/test_v106.py` | 28 | PASS |
| `tests/test_v107.py` | 127 | PASS（其中 2 条版本契约前移） |
| `tests/test_v108.py` | 129 | PASS（其中 3 条版本契约前移） |
| `tests/test_v109.py` | 83 | PASS（其中 6 条版本契约前移） |
| `tests/test_v110.py` | 14 | PASS（**本轮新增**） |
| **离线合计** | **504** | **FAIL 0** |
| `tests/test_integration_quote.py` | 14 | PASS（需外网，单独执行） |
| `output/.../smoke_v108_http.py` | 14 | PASS（不得回退） |
| `output/.../smoke_v109_http.py` | 38 | PASS（不得回退） |

离线断言总数由 490 增至 **504（+14）**，净变化来源唯一：新增 `tests/test_v110.py`。

### 既有测试的变更清单（逐条 diff，非按总数反推）

| 文件 | 断言标签 | v1.0.9 期望 | v1.0.10 期望 |
|---|---|---|---|
| `tests/test_v107.py` | §P#1 | `TARGET_SCHEMA_VERSION = '1.0.9'` | `'1.0.10'` |
| `tests/test_v107.py` | §P#2 | `server_version = 'Workbench/1.0.9'` | `'Workbench/1.0.10'` |
| `tests/test_v108.py` | §I#1 | `TARGET_SCHEMA_VERSION = '1.0.9'` | `'1.0.10'` |
| `tests/test_v108.py` | §I#2 | `server_version = 'Workbench/1.0.9'` | `'Workbench/1.0.10'` |
| `tests/test_v108.py` | §I#15 | 前端版本号 v1.0.9 | v1.0.10 |
| `tests/test_v109.py` | §I#1 | `TARGET_SCHEMA_VERSION = '1.0.9'` | `'1.0.10'` |
| `tests/test_v109.py` | §I#2 | `server_version = 'Workbench/1.0.9'` | `'Workbench/1.0.10'` |
| `tests/test_v109.py` | §I#3 | argparse 描述 v1.0.9 | v1.0.10 |
| `tests/test_v109.py` | §I#4 | 启动文案 v1.0.9 | v1.0.10 |
| `tests/test_v109.py` | §I#20 | `TARGET_SCHEMA_VERSION = '1.0.9'` | `'1.0.10'` |
| `tests/test_v109.py` | §I#21 | 前端版本号 v1.0.9 | v1.0.10 |

合计 **11 条**（2 + 3 + 6），全部为「当前版本常量」契约断言。
三个套件的**断言总数保持不变**：127 → 127、129 → 129、83 → 83；
diff 中不存在任何新增、删除或改写业务语义断言的行。

### 新测试的价值：能抓住旧 bat（负向验证）

`tests/test_v110.py` §B 把"启动脚本必须长什么样"固化为契约。
把 v1.0.9 交付包内的旧 bat（388 B）临时放回原位重跑，结果：

```
  [FAIL] §B#4 真执行探测解释器版本（非仅检查命令存在） 未找到真执行探测
  [FAIL] §B#5 显式拒绝 Microsoft Store 执行别名存根 缺少 WindowsApps 路径守卫
  [FAIL] §B#6 不含旧的 `set "PY=python"` + `where python` 判定 旧判定残留
v1.0.10 测试: PASS 11 / FAIL 3  (共 14 断言)
```

即：**该测试若在 v1.0.9 封板时存在，本缺陷不会漏出**。验证后已恢复修复版
（SHA-256 回到 `65414590d0804b255830ce6b489e384db7501659ccb50b9ebf8c0dc64f70fb93`）。

### 端到端实跑

- 实际执行 bat → 输出 `Python : "<受管解释器绝对路径>"`（中文路径展开正确）
  → 监听到 `127.0.0.1:8765` → `GET /` 返回 `HTTP 200`。
- `:try` 子程序隔离测试（从**已安装的 bat 里抽取**该子程序，保证被测代码 == 交付代码）：
  3/3 PASS —— 受管解释器被接受；不存在的路径被拒绝；`...\WindowsApps\python.exe` 被路径守卫拒绝。

---

## 六、版本号同步位置（4 处，缺一不可）

| 位置 | 值 |
|---|---|
| `app/server.py` → `TARGET_SCHEMA_VERSION` | `'1.0.10'` |
| `app/server.py` → `Handler.server_version` | `'Workbench/1.0.10'` |
| `app/server.py` → `argparse` description | `'A/H 投研交易工作台 v1.0.10'` |
| `app/server.py` → 启动 print | `'A/H 投研交易工作台 v1.0.10 已启动: %s'` |

另：`app/static/app.js` 头部注释版本号同步为 `v1.0.10`。

> 本版 4 处版本号曾一度只同步了 3 处（启动文案留在 1.0.9）。
> `tests/test_v110.py` §A#5 因此增加了一条**唯一性**断言：
> 用正则抽取 4 处版本号，要求四个值完全一致。这条断言把
> "版本号必须同步 4 处" 从人工纪律变成机器契约。

---

## 七、数据库状态（未变更）

- 本版**无 Schema 变化**：不新增表、列、索引或迁移脚本。
- `TARGET_SCHEMA_VERSION` 仅作版本号前移，用于版本识别，不触发任何结构迁移。
- **交付库为空的模板库**：`data/workbench.db`，6 张业务表行数均为 0，
  `schema_version = 1.0.10`，`integrity_check = ok`，`PRAGMA foreign_key_check` 违例 0。
- 交付库与工作区库**按设计不是同一份文件**：工作区那份含操作者的实际标的与研究数据，
  按交付约定不夹带进交付包。校验器的 [2] 项因此把 `data/workbench.db` 排除在
  "ZIP ↔ 工作区逐字节一致" 之外，改由 [3] 项按
  `integrity / FK / schema_version 一致 / 必须为空库` 四项单独校验，检查强度不降反升。

---

## 八、启动方式

```bash
# Windows（推荐，双击）
启动工作台.bat

# 命令行
python app/server.py
# 默认地址 http://127.0.0.1:8765
```

运行环境：Python 3.8+（3.13 已验证），**纯标准库，无第三方依赖**。

---

## 九、验收清单（接收方）

1. 解压到**全新目录**（不要覆盖旧目录），核对 Manifest 条目数与 ZIP 实际条目数一致（26）。
2. **双击 `启动工作台.bat`**，确认控制台打印出解析到的 Python 绝对路径与
   `http://127.0.0.1:8765`，浏览器自动打开且页面可用。
   （此步是本版的核心验收点：在只装了 Store 存根、没配 PATH 的机器上也必须能起来。）
3. `python app/server.py`，确认启动文案为 `v1.0.10`、地址为 `http://127.0.0.1:8765`。
4. 跑离线套件 8 个：`test_v102/v103/v105/v106/v107/v108/v109/v110`
   → 合计 **504 断言，FAIL 0**。
5. 跑 `python output/20260910-audit/smoke_v109_http.py` → **38 PASS / FAIL 0**。
6. 跑 `python output/20260910-audit/smoke_v108_http.py` → **14 PASS / FAIL 0**（确认无回退）。
7. 联网可选：`python tests/test_integration_quote.py` → **14 PASS / FAIL 0**。
8. 确认 `README.txt` 默认地址为 `http://127.0.0.1:8765`。
9. 确认包内 `data/workbench.db` 为空库（6 张业务表行数均为 0）。

---

## 十、风险与开放问题

- **本轮修复的缺陷（已修复）**：交付包内 `启动工作台.bat` 用 `where python` 判定解释器，
  在持久 PATH 只含 Microsoft Store 存根的机器上会拉起商店而非工作台。
  修复 = ASCII-only 候选链 + 真执行探测 + 拒绝 Store 存根；
  验证 = 端到端实跑可启动 + `test_v110.py` 对旧 bat 负向验证 3 FAIL。
- **R-030（本轮新增，低危）**：`启动工作台.bat` 的候选链**优先**受管运行时目录，
  其次 `py`，最后 PATH 上的 `python`。若目标机同时存在多个可用解释器，
  实际选中的是链上第一个 —— 这与使用者"系统默认 Python"的直觉可能不一致。
  影响面：仅影响用哪个解释器运行，不影响数据与功能（纯标准库，3.8+ 均可）。
- **R-026（沿用，预期行为）**：preview cache 为进程内存态，服务重启后未使用的 token
  全部失效（需重新预览）。
- **R-029（沿用，低危，刻意选择）**：commit 路径若被 `BaseException` 中断，
  `in_flight` 不会释放，该 token 在剩余 TTL 内不可重试（需重新 preview）。
- **R-027 / R-028（v1.0.9 已修复，本轮未回退）**：原子 claim + 409 语义；
  本轮 `smoke_v109_http.py` 38 PASS、`test_v109.py` 83 PASS 即为回归证据。
- **O-003 / O-004（待批准，未推进）**：`trades` 冲正机制；
  `securities.research_pool` 字段彻底废弃（SQLite 不支持 DROP COLUMN）。

---

## 十一、继续生效的既有约束

- 证券唯一身份只认 `exchange + code`；不用 `name` 匹配，`name` 不一致只提示不自动改。
- 行情涨 = **红**，跌 = **绿**（中国市场惯例）。
- 导入两段式：preview 不写库 + commit 单一 SQLite 事务（任一只失败整批 ROLLBACK）。
- 导入路径不触碰 `trades`；execution 为 append-only。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。
- 未经用户明确批准，不得新增规则、扩展任务或改变研究口径。
