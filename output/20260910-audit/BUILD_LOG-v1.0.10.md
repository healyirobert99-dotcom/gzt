# BUILD LOG —— 个股工作台 v1.0.10

## 版本

- 版本号：**v1.0.10**（`TARGET_SCHEMA_VERSION = '1.0.10'`）
- 基线：v1.0.9 → v1.0.10
- 性质：启动脚本交付修复（不新增业务功能，无数据库 Schema 变化，服务端与前端零逻辑改动）
- 构建日期：2026-09-11

## 版本号同步（4 处 + 前端）

| 位置 | 值 | 校验方式 |
|---|---|---|
| `app/server.py` → `TARGET_SCHEMA_VERSION` | `'1.0.10'` | tests/test_v110.py §A#1 / §A#5 |
| `app/server.py` → `Handler.server_version` | `'Workbench/1.0.10'` | §A#2 / §A#5 + 运行时响应头 |
| `app/server.py` → `argparse` description | `'A/H 投研交易工作台 v1.0.10'` | §A#3 / §A#5 |
| `app/server.py` → 启动 print | `'A/H 投研交易工作台 v1.0.10 已启动: %s'` | §A#4 / §A#5 + 实跑截获 |
| `app/static/app.js` 头部 | `v1.0.10` | §A#6 |

运行时实测响应头：`Server: Workbench/1.0.10 Python/3.13.14`

> **升级过程中的一次真实失误（已修复并机器化防护）**：
> 本轮开始时 4 处版本号只同步了 3 处（`TARGET_SCHEMA_VERSION` / `server_version` /
> `argparse` 已是 1.0.10，而**启动 print 文案仍为 1.0.9**），当时 `app.js` 版本头与
> 三个测试套件的版本契约也都还停在 1.0.9 —— 即套件是**红的**。
> 补齐后在 `test_v110.py` §A#5 增加了一条唯一性断言：用正则抽取 4 处版本号，
> 要求四个值完全一致。这条断言正是为了把"版本号必须同步 4 处"从人工纪律变成机器契约。

## 交付包指纹

- ZIP_PATH: `D:\个股工作台\个股工作台-v1.0.10-20260911.zip`
- ZIP_BYTES: 208012
- ZIP_SHA256: `c55fdc6abfa6d45f4477177f0f3943ff58d85cbe2fb1ea33a867925afd3b3e46`
- ENTRIES: 26（含 `PACK_MANIFEST-v1.0.10.md` 自身）
- UNCOMPRESSED_TOTAL: 660181 B
- 交付内容总字节数（不含 Manifest）: 655376 B
- `zipfile.testzip()`: OK

> BUILD_LOG 含 ZIP 自身 SHA-256，会产生自指矛盾，因此**不进 ZIP**。

## 关键产物指纹

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `app/server.py` | 149287 | `6d29e63f177afa3b965f5929bb498970f8235185901afd2884b759e38b97d322` |
| `app/static/app.js` | 84687 | `e5e62b8e186c2f29b46cece98f6323927afd31ee1d58ca4aed06b451595e7bf6` |
| `app/static/index.html` | 995 | `0d376a2ea40b78512de91e625262c5b01b43384f813c73236adca989a3ce634a` |
| `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| `启动工作台.bat` | 3970 | `65414590d0804b255830ce6b489e384db7501659ccb50b9ebf8c0dc64f70fb93` |
| `tests/test_v107.py` | 46147 | `ec87013675b077057554b64267d79360828914eb10e3f0fb3b77073a534252af` |
| `tests/test_v108.py` | 44466 | `e6ede997c0ddcddc0b47406f41f5a174d5bc2141e8297062c436b2f824a5e960` |
| `tests/test_v109.py` | 31676 | `d63d4692ebee355256c8402483648dc875789c2a128ab0de1deeeddd7c0dab85` |
| `tests/test_v110.py` | 7430 | `14aea424b2eb7c25232854f8a50bea4fb80f9cf75b5b7f86e378a32aba7f3406` |
| `output/.../smoke_v108_http.py` | 7908 | `71826c8eed949d535fb80d34026e8e9d465f1fda59c9ea9b6228f1a6a7479a1f` |
| `output/.../smoke_v109_http.py` | 17684 | `ada790c5d7d1a96b2539539a525a9af0779d220d26191c2975190e8f30ff5956` |
| `output/.../PACK_NOTES-v1.0.10.md` | 14444 | `5a5255c86475fc74002e08040cdd24963078c5bfcb932f623811af116d6b5319` |
| `output/.../PACK_MANIFEST-v1.0.10.md` | 4805 | `6545f608c67378bd42545cf3593471e0e39cf5ac7869a1d16cc129a70a565908` |
| `output/.../A-H投研交易工作台交付审计文档-v1.0.10.docx` | 47806 | `5952d1ca3ca17d1525c8c393555d3b73f91163cc48a098fb7ec62da1e8c2e45a` |

对比 v1.0.9 交付包内的同两项：

| 产物 | v1.0.9（包内） | v1.0.10（包内） |
|---|---|---|
| `启动工作台.bat` | 388 B / `caf74fb14c04cbef56ebbda0a70700594fd0e55136ad01cedd372843e18244c4` | 3970 B / `65414590d0804b255830ce6b489e384db7501659ccb50b9ebf8c0dc64f70fb93` |

## 本轮改动（3 个源文件 + 2 个测试文件 + 3 份文档）

### `启动工作台.bat`（整体替换，388 B → 3970 B）

| 关注点 | 旧版 | 新版 |
|---|---|---|
| 解释器判定 | `set "PY=python"` + `where python` | 4 级候选链 + **真执行探测** |
| 是否验证"能跑" | 否，只看命令存在 | 是，`sys.version_info >= (3,8)` 实跑一次 |
| Store 存根 | 无法识别，直接调用 | 路径守卫 `%T:WindowsApps=%` 显式拒绝 |
| 非 ASCII 字节 | 0 | 0（路径用 `%USERPROFILE%` 运行时展开） |
| 前置守卫 | 无 | 检查 `app\server.py` 是否存在 |
| 找不到解释器时 | 一句 "Python not found" | 给出安装指引并点明 Store 占位符 |

### `app/server.py`

| 位置 | 改动 |
|---|---|
| 头部注释 | 新增 v1.0.10 边界说明（含根因、修复要点、零逻辑改动声明） |
| `TARGET_SCHEMA_VERSION` | `'1.0.9'` → `'1.0.10'` |
| `Handler.server_version` | `'Workbench/1.0.9'` → `'Workbench/1.0.10'` |
| `argparse` description | `v1.0.9` → `v1.0.10` |
| 启动 print 文案 | `v1.0.9` → `v1.0.10` |

**未改动**：Schema、迁移逻辑、所有业务写入函数（`create_security_tx` /
`update_research_tx` / `update_plan_tx` / `change_status_tx` / `add_execution_tx` /
`add_trade` / `ledger_add`）、v1.0.9 引入的 `_import_cache_claim` /
`_import_cache_release` / `_import_snapshot_drift` / `_is_db_busy_error`、
行情层、导出层。

### `app/static/app.js`

仅版本号 `v1.0.9` → `v1.0.10` 与头部说明。**交互逻辑零改动。**

### `tests/test_v110.py`（新增，14 断言）

- §A 版本同步契约（6 条，含 §A#5 四值唯一性）
- §B 启动脚本契约（8 条：存在 / 纯 ASCII / 全 CRLF / 真执行探测 / 拒绝 Store 存根 /
  不含旧判定 / 前置守卫 / 端口一致）

**负向验证**：把 v1.0.9 包内旧 bat 放回原位重跑 → §B#4 / §B#5 / §B#6 三条 FAIL。
验证后恢复，SHA-256 回到 `65414590…`。

### `tests/test_v107.py` / `test_v108.py` / `test_v109.py`

仅版本号契约前移，共 11 条（2 + 3 + 6），详见 PACK_NOTES §五。

### 本轮修复的一个自身缺陷

`build_docx_v110.py` 首次写入头部注释时使用了 `%LOCALAPPDATA%\Microsoft\WindowsApps`
与 `versions\*`，Python 对模块 docstring 中的 `\M`、`\*` 抛出
`SyntaxWarning: invalid escape sequence`。已改为 `%LOCALAPPDATA%\\Microsoft\\WindowsApps`
与「遍历受管 versions 目录」。用 `py_compile(doraise=True)` + `-W error::SyntaxWarning`
复验：编译无告警。

## 本轮测试执行记录（全部真实运行）

### 工作区侧

| 命令 | 结果 |
|---|---|
| `python tests/test_v102.py` | `总计: PASS 38  FAIL 0` |
| `python tests/test_v103.py` | exit 0（60 断言全过） |
| `python tests/test_v105.py` | `PASS 25 / FAIL 0 (共 25 断言)` |
| `python tests/test_v106.py` | `FAIL_COUNT=0`（28 断言全过） |
| `python tests/test_v107.py` | `TOTAL = 127  FAIL_COUNT = 0  ALL TESTS PASS` |
| `python tests/test_v108.py` | `TOTAL = 129  FAIL_COUNT = 0  ALL TESTS PASS` |
| `python tests/test_v109.py` | `PASS 83 / FAIL 0 (共 83 断言)` |
| `python tests/test_v110.py` | `PASS 14 / FAIL 0 (共 14 断言)` |
| **离线合计** | **504 断言，FAIL 0** |
| `python tests/test_integration_quote.py` | `PASS 14  FAIL 0  SKIP 0` |
| `python output/20260910-audit/smoke_v109_http.py` | `PASS 38 / FAIL 0` |
| `python output/20260910-audit/smoke_v108_http.py` | `PASS 14 / FAIL 0` |

### 交付包端到端验收（本轮最强证据）

`\.tmp_v108x\verify\e2e_launcher_v110.py` —— 解压到**全新临时目录**，
用它自己那份 bat，在**真实持久 PATH**（读注册表得到，只含
`%USERPROFILE%\AppData\Local\Microsoft\WindowsApps`，**不含任何受管运行时**）下实跑：

```
[C] 旧 bat 守卫为何恒不触发
  [PASS] C#1 含 WindowsApps 时 `where python` exit=0（守卫不触发）
                                          C:\...\Microsoft\WindowsApps\python.exe
  [PASS] C#2 不含 WindowsApps 时 `where python` 失败（说明旧 bat 只认 PATH） rc=1

[A] 新 bat + 真实持久 PATH（无受管运行时）
  [PASS] A#1 工作台被拉起（8765 监听中）
  [PASS] A#2 GET / 返回 200 status=200
  [PASS] A#3 Server 头为 Workbench/1.0.10  Workbench/1.0.10 Python/3.13.14
  [PASS] A#4 收尾：端口已彻底释放（按端口属主杀进程树）

[B] v1.0.9 交付包内旧 bat + 不含真 Python 的 PATH
  [PASS] B#1 旧 bat 无法启动（报 Python not found）
  [PASS] B#2 旧 bat 未留下监听端口

交付包端到端验收: PASS 11 / FAIL 0
```

即：**新 bat 在用户机器那样的 PATH 下能起来，旧 bat 在同一环境下起不来** ——
差异确实来自本次修复，而非开发环境的 PATH 注入。

> 探针自身的一次修正：`proc.kill()` 只杀 `cmd.exe`，其子进程 `python.exe` 会存活并
> 继续监听 8765，导致实验 B 误判"旧 bat 也留下了监听端口"。改为用
> `netstat -ano` 找到端口属主后 `taskkill /F /T`，并新增 A#4 断言"端口已彻底释放"。

### 交付包自洽校验（自研校验器）

```
--rerun:                  PASS 24 / FAIL 0  （离线断言合计 504）
--port-probe:             PASS 17 / FAIL 0
  [PASS] GET / 返回 200 status=200
  [PASS] Server 头带版本号 Workbench/1.0.10 Python/3.13.14
```

`--rerun` 明细：8 个套件 38/60/25/28/127/129/83/14 = **504 断言**，全部 rc=0。

## 交付包一致性校验

| 项 | 结果 |
|---|---|
| Manifest 条目数 | 26（25 条含字节数+SHA + 1 条自指） |
| ZIP 实际条目数 | 26 |
| Manifest 幽灵条目（列了但 ZIP 没有） | 无 |
| ZIP 多余条目（有但 Manifest 没列） | 无 |
| 逐文件字节数 + SHA-256 回读比对 | 25/25 全部一致 |
| 构建脚本是否混入 | 否（`build_docx_v110.py`、打包脚本、本 BUILD_LOG 均不进 ZIP） |
| README.txt 默认地址 | `http://127.0.0.1:8765`，与 `app/server.py` 的 `--port` 默认值一致 |
| 启动器 bat 卫生 | 纯 ASCII / 无裸 LF / 不依赖裸 `where python` |
| 根目录残留 `README.txt` | 否（打包后按约定移除，副本在 ZIP 内） |

## 数据库

- 本版**无 Schema 变化**：不新增表、列、索引或迁移脚本。
- `TARGET_SCHEMA_VERSION` 由 1.0.9 前移至 1.0.10 触发既有 `do_migration()` 流程，
  迁移后表结构与业务数据均无变化。
- 表清单未变：`securities / research / trade_plans / trades / decision_ledger /
  execution_reviews / settings`（+ SQLite 内建 `sqlite_sequence`）。

### 交付库 vs 工作区库（本版新出现的分离，须记录）

| 项 | 交付库（包内） | 工作区库（本机 `data/workbench.db`） |
|---|---|---|
| 字节数 | 73728 | 90112 |
| SHA-256 | `cce3b15e10e4fb08183f7f640c82255085a46ca570039e61391e5a0781421ec4` | 随使用变化 |
| securities / research / trade_plans | 0 / 0 / 0 | 7 / 7 / 7 |
| trades / execution_reviews / decision_ledger | 0 / 0 / 0 | 0 / 0 / 7 |
| schema_version | 1.0.10 | 1.0.10 |
| integrity / FK 违例 | ok / 0 | ok / 0 |

原因：v1.0.9 打包时（11:32）工作区库是空的（`.tmp_v108x/verify/wsdb-before-109.db`
实测 0 行 / schema_version 1.0.8），打包与工作区两份天然一致；此后用户启动了工作台
并导入了 7 只真实标的，工作区库不再是空库。

处置：**打包脚本按交付约定使用空库模板，不夹带操作者数据**
（`build_pack_v110.py` 的 `SRC_OVERRIDE`）。工作区库未被修改、未被清空；
打包前另存了一份到 `.tmp_v108x/verify/wsdb-live-v110.db` 备查。

配套修改：自研校验器 `verify_pack.py` 的 [2] 项（ZIP ↔ 工作区逐字节一致）
把 `data/workbench.db` 排除，改由 [3] 项按
`integrity_check / FK 违例 / schema_version 与 server.py 一致 / 业务表必须全空`
四项单独校验 —— **检查强度不降反升**（原先只比"字节是否相同"，现在额外锁定了
"交付库必须是空库"这条此前只写在文档里的交付约定）。

## 本轮改动的工作区外文件（不进 ZIP）

| 文件 | 说明 |
|---|---|
| `.tmp_v108x/verify/build_pack_v110.py` | v1.0.10 打包脚本 |
| `.tmp_v108x/verify/e2e_launcher_v110.py` | 交付包端到端验收探针（11 断言） |
| `.tmp_v108x/verify/delivery-empty-v110.db` | 交付用空库模板 |
| `.tmp_v108x/verify/wsdb-live-v110.db` | 打包前的工作区库备份 |
| `output/20260910-audit/build_docx_v110.py` | 审计文档生成脚本 |
| 本文件 | BUILD_LOG |

## 遗留与开放项

- **R-030（本轮新增，低危）**：候选链**优先**受管运行时目录，其次 `py`，最后 PATH 上的
  `python`。目标机存在多个可用解释器时选中的是链上第一个，与"系统默认 Python"的直觉
  可能不一致。仅影响用哪个解释器运行，不影响数据与功能（纯标准库，3.8+ 均可）。
- **R-029（沿用，低危，刻意选择）**：commit 路径被 `BaseException` 中断时
  `in_flight` 不释放，该 token 在剩余 TTL 内不可重试。
- **R-026（沿用）**：preview cache 为进程内存态，服务重启后未使用 token 全部失效。
- **R-027 / R-028（v1.0.9 已修复，本轮未回退）**：由 `test_v109.py` 83 PASS 与
  `smoke_v109_http.py` 38 PASS 作为回归证据。
- **O-003 / O-004**：待批准功能，未推进。
- 工作区临时目录（`archive/`、`audit_pack_src/`、`pack_v106_src/`、`.tmp_v108x/`、
  根目录旧版 `PACK_MANIFEST.md` / `PACK_NOTES.md`）仍在，如需清理请单独指示。
- 仓库仍未初始化 git。

## 与前序版本的关系

| 版本 | 主题 | 离线断言 | 来源 |
|---|---|---:|---|
| v1.0.7 | 导入与更新交互层 | —（历史日志未记合计） | — |
| v1.0.8 | 导入完整性封板（token / 同批去重 / 漂移检测） | 407 | `BUILD_LOG-v1.0.8.md` §实测 |
| v1.0.9 | 最终并发与预览一致性修复（R-027 / R-028） | 490 | `BUILD_LOG-v1.0.9.md` §实测 |
| **v1.0.10** | **启动脚本交付修复** | **504** | 本文件 §实测 |

> v1.0.8 的 407 = 38 + 60 + 25 + 28 + 127 + 129；v1.0.10 的 504 = 407 + 83（v1.0.9 新增）
> + 14（v1.0.10 新增）。v1.0.7 的历史日志中没有记录离线合计，故此处不填数字 ——
> 不沿用未经核对的声称。
