# BUILD LOG —— 个股工作台 v1.0.9

## 版本

- 版本号：**v1.0.9**（`TARGET_SCHEMA_VERSION = '1.0.9'`）
- 基线：v1.0.8 → v1.0.9
- 性质：最终并发与预览一致性修复（不新增业务功能，无数据库 Schema 变化）
- 构建日期：2026-09-11

## 版本号同步（4 处 + 前端）

| 位置 | 值 | 校验方式 |
|---|---|---|
| `app/server.py` → `TARGET_SCHEMA_VERSION` | `'1.0.9'` | tests/test_v109.py §I#1 |
| `app/server.py` → `Handler.server_version` | `'Workbench/1.0.9'` | §I#2 + 运行时响应头 |
| `app/server.py` → `argparse` description | `'A/H 投研交易工作台 v1.0.9'` | §I#3 |
| `app/server.py` → 启动 print | `'A/H 投研交易工作台 v1.0.9 已启动: %s'` | §I#4 + 实跑截获 |
| `app/static/app.js` 头部 | `v1.0.9` | §I#21 |

运行时实测响应头：`Server: Workbench/1.0.9 Python/3.13.14`

## 交付包指纹

- ZIP_PATH: `D:\个股工作台\个股工作台-v1.0.9-20260911.zip`
- ZIP_BYTES: 201357
- ZIP_SHA256: `7cc93181516a40fc34c8fcf99cb8bccc5c230f25029bdbd11a72808bb3e60aa3`
- ENTRIES: 25（含 `PACK_MANIFEST-v1.0.9.md` 自身）
- UNCOMPRESSED_TOTAL: 648091 B
- 交付内容总字节数（不含 Manifest）: 643803 B
- `zipfile.testzip()`: OK

> BUILD_LOG 含 ZIP 自身 SHA-256，会产生自指矛盾，因此**不进 ZIP**。

### 重建记录（同一工作日内一次措辞修正，替换前一版 ZIP）

初版 v1.0.9 ZIP（`7287ff33…`，201363 B）内容完整、校验全过，唯一问题出在
`PACK_MANIFEST-v1.0.9.md` 的一句**否定式免责声明**：

- 初版措辞：`不列出任何 ZIP 中不存在的构建脚本（build_docx_v10x.py 等不进交付包）。`
- 第三方按"文本中出现构建脚本文件名即视为违规"的粗粒度扫描会误报。
  为消除歧义，改为：`不列出任何 ZIP 中不存在的构建脚本（文档生成脚本一律不进交付包）。`

| 项 | 初版（已作废） | 本版（有效） |
|---|---|---|
| Manifest 字节 / SHA | 4286 / `badedfb6…` | 4288 / `2c6946f8bc89e214b7f7a01583e7cca7a0f5c48bda7c4441eab11ea2b0cab6ec` |
| UNCOMPRESSED_TOTAL | 648089 B | 648091 B |
| ZIP 字节 / SHA | 201363 / `7287ff33…` | 201357 / `7cc93181…` |

**除 Manifest 的该句措辞外，其余 23 个条目逐字节未变**（`app/`、`tests/`、`samples/`、
`data/`、两份冒烟脚本、`PACK_NOTES`、审计 docx 的 SHA 均与初版一致）。
审计 docx 与 PACK_NOTES 因此**无需重建**。

> 初版 ZIP 未单独留档（仅 Manifest 一句话不同，其余条目字节完全一致）；
> 其 SHA-256 `7287ff334630b552686e3ab6b82aa9b1a40decabbbae5311f4a362e0da67dccc`
> 记录于此备查。

同时修正了自研校验器 `verify_pack.py` 的该项检查：由"整份文本正则匹配"收敛为
"只检查清单条目行（`| 序号 | \`路径\` | … |`）"，避免否定句被误报为违规。

## 关键产物指纹

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `app/server.py` | 148060 | `be8dd23fbaf5fe7de84af2b00e962f57d56db419bf5393aaec9fb73bc044ece2` |
| `app/static/app.js` | 84469 | `9855a8893e440d8ba0b2badeff31a440681d6bba83462855bc8e42bd18afc459` |
| `app/static/index.html` | 995 | `0d376a2ea40b78512de91e625262c5b01b43384f813c73236adca989a3ce634a` |
| `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| `tests/test_v109.py` | 31557 | `bd9a25a1a9ec170235d7ba840d775ae1408a833c4d0f104c09142f14c04c5ba6` |
| `output/.../smoke_v109_http.py` | 17684 | `ada790c5d7d1a96b2539539a525a9af0779d220d26191c2975190e8f30ff5956` |
| `output/.../PACK_NOTES-v1.0.9.md` | 11248 | `1aa650c5bc1b934de7d33604b412c288da81cacdd272687505c8d9e640d9fadf` |
| `output/.../PACK_MANIFEST-v1.0.9.md` | 4288 | `2c6946f8bc89e214b7f7a01583e7cca7a0f5c48bda7c4441eab11ea2b0cab6ec` |
| `output/.../A-H投研交易工作台交付审计文档-v1.0.9.docx` | 47227 | `7f26486eda0478c6dcf692e49e092d65b54f76fb5f0bb2682b738022089a6389` |

## 本轮代码改动（仅 2 个源文件）

### `app/server.py`

| 位置 | 改动 |
|---|---|
| 头部注释 | 新增 v1.0.9 边界说明；导入区注释新增 3 条修复记录 |
| 常量区 | 新增 `DB_BUSY_PRIMARY_CODES = (5, 6)`、`DB_BUSY_MESSAGE`；TTL 注释补充 in_flight |
| 异常类 | 新增 `DbConflictError`（→ 409）与 `_is_db_busy_error()` |
| cache 生命周期 | `_import_cache_take()` → 移除；新增 `_import_token_key()`、`_import_cache_claim()`、`_import_cache_release()`；`_import_cache_put()` 条目新增 `in_flight: False` |
| 漂移检测 | `_import_snapshot_drift()` 返回值由 `list[str]` 改为 `list[(kind, str)]`，新增 execution 分支；`_import_require_no_drift()` 按 kind 选择提示语 |
| snapshot 构建 | `preview_import_full()` 为每条 snapshot 打 `check_execution`；`preview_import_execution()` 置 True |
| commit 路径 | 两条 commit 均改为 claim + 全异常释放（`conn = None` 保护，覆盖 `get_db()` 自身失败） |
| HTTP 错误映射 | `_mut()` 新增 `DbConflictError → 409`、`sqlite3.OperationalError` 分支（busy → 409，其余 → 500） |

**未改动**：SCHEMA、迁移逻辑、所有业务写入函数（`create_security_tx` / `update_research_tx` /
`update_plan_tx` / `change_status_tx` / `add_execution_tx` / `add_trade` / `ledger_add`）
的 SQL 与语义、行情层、导出层。

### `app/static/app.js`

| 位置 | 改动 |
|---|---|
| 头部 | 版本号 → v1.0.9；新增前端侧边界说明 |
| `Import` 状态 | 新增 `committing: false` |
| `renderImportFullPreview()` / `renderImportExecPreview()` | 按钮绑定 `disabled` + 文案切换「正在写入…」；「返回修改」在写入中同样 disabled |
| `commitFull()` / `commitExec()` | 入口防重早退；发请求前置位并重绘；成功/失败均复位 |
| 两处 preview 成功分支 | `Import.committing = false` 复位 |

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
| **离线合计** | **490 断言，FAIL 0** |
| `python tests/test_integration_quote.py` | `PASS 14  FAIL 0  SKIP 0` |
| `python output/20260910-audit/smoke_v109_http.py` | `PASS 38 / FAIL 0` |
| `python output/20260910-audit/smoke_v108_http.py` | `PASS 14 / FAIL 0` |

### 稳定性复跑（排除"数字不可复现"）

| 命令 | 次数 | 结果 |
|---|---|---|
| `tests/test_v109.py` | 连续 5 次 | 每次 `PASS 83 / FAIL 0`；§A 并发成功次数**每次严格 = 1**、§B 每次 ≤ 1 |
| `smoke_v109_http.py` | 连续 3 次 | 每次 `PASS 38 / FAIL 0`，状态码分布恒为 `{400×7, 200×1}` |

### R-027 / R-028 原始复现探针（修复验证）

`ah-workbench-release-verify` 技能的 `concurrency_probe.py --n 8 --trials 3`：

```
trial0 n=8 | 状态码 {400: 7, 200: 1} | execution_reviews 0 -> 1 (应+1) | OK
trial1 n=8 | 状态码 {400: 7, 200: 1} | execution_reviews 0 -> 1 (应+1) | OK
trial2 n=8 | 状态码 {400: 7, 200: 1} | execution_reviews 0 -> 1 (应+1) | OK

并发探针：0/3 次试验需要人工判定
```

对比 v1.0.8 交付时的同一探针输出（`3/3 需要人工判定`，成功 2~3 次、execution 多写 1~2 条、
并伴随 4~5 次 500）——**两个缺陷均已不可复现**。

### 解压到全新目录后复跑（最强证据）

1. `zipfile.extractall('.tmp_v108x/final-v109')` 解压交付 ZIP。
2. 在该目录内重跑 7 个离线套件：全部 `exit=0`，
   断言数 38 / 60 / 25 / 28 / 127 / 129 / 83 = **490**。
3. 包内 `smoke_v109_http.py` → 38 PASS；`smoke_v108_http.py` → 14 PASS。
4. 包内 `test_integration_quote.py` → 14 PASS。
5. 包内真实启动：`python app/server.py --port 8795 --no-browser`
   → 输出 `A/H 投研交易工作台 v1.0.9 已启动: http://127.0.0.1:8795`；
   `GET /` → 200，`Server: Workbench/1.0.9`；未预览直接 commit → 400 受控文案。

## 交付包一致性校验

| 项 | 结果 |
|---|---|
| Manifest 条目数 | 25（24 条含字节数+SHA + 1 条自指） |
| ZIP 实际条目数 | 25 |
| Manifest 幽灵条目（列了但 ZIP 没有） | 无 |
| ZIP 多余条目（有但 Manifest 没列） | 无 |
| 逐文件字节数 + SHA-256 回读比对 | 24/24 全部一致 |
| 构建脚本是否混入 | 否（`build_docx_v10x.py`、本打包脚本均不进 ZIP） |
| README.txt 默认地址 | `http://127.0.0.1:8765`，与 `app/server.py` 的 `--port` 默认值一致 |
| 根目录残留 `README.txt` | 否（打包后已移除） |

## 数据库

- `data/workbench.db`：`schema_version = 1.0.9`、`integrity_check = ok`、
  `PRAGMA foreign_key_check` 违例 0。
- 表清单未变：`securities / research / trade_plans / trades / decision_ledger /
  execution_reviews / settings`（+ SQLite 内建 `sqlite_sequence`）。
- 行数：全部为 0（空库交付）。
- 迁移说明：`TARGET_SCHEMA_VERSION` 由 1.0.8 前移至 1.0.9 触发了既有的
  `do_migration()` 流程；本版**未新增任何迁移代码、表或列**，迁移后表结构与行数均无变化。
- 迁移前的工作区库留档：`.tmp_v108x/verify/wsdb-before-109.db`。

## 既有测试变更（逐条列明）

对 v1.0.8 交付 ZIP 内文件与工作区文件逐行 diff：

| 文件 | 变更条数 | 断言标签 | 变更内容 |
|---|---:|---|---|
| `tests/test_v107.py` | 2 | §P#1、§P#2 | 版本契约 `1.0.8` → `1.0.9` |
| `tests/test_v108.py` | 3 | §I#1、§I#2、§I#15 | 版本契约 `1.0.8` → `1.0.9`（含前端版本号） |

- 合计 5 条，**全部为版本号契约断言**，无任何业务语义断言被新增、删除或改写。
- 断言总数不变：`test_v107.py` 127 → 127；`test_v108.py` 129 → 129。
- 离线断言总数 407 → 490（+83），净变化来源唯一：新增 `tests/test_v109.py`。

## 遗留与开放项

- **R-029（本轮新增，低危）**：commit 路径被 `BaseException` 中断时 `in_flight` 不释放，
  该 token 在剩余 TTL 内不可重试（需重新 preview）。刻意选择「宁阻塞、不重复」。
- **R-026（沿用）**：preview cache 为进程内存态，服务重启后未使用 token 全部失效。
- **R-024 / R-014 / R-015**：沿用，未处理。
- **O-003 / O-004**：待批准功能，未推进。
- 工作区临时目录（`archive/`、`audit_pack_src/`、`pack_v106_src/`、`.tmp_v108x/`、
  根目录旧版 `PACK_MANIFEST.md` / `PACK_NOTES.md`）仍在，如需清理请单独指示。
- 仓库仍未初始化 git。
