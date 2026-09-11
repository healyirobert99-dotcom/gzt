# 个股工作台 v1.0.9 —— 交付说明（最终并发与预览一致性修复）

## 项目

- 名称：A/H 投研交易工作台
- 版本：v1.0.9（`TARGET_SCHEMA_VERSION = '1.0.9'`）
- 基线：v1.0.8 → v1.0.9
- 性质：**只修复 v1.0.8 交付后独立验证发现的并发与预览一致性缺陷，不新增业务功能**
- 边界：不修改研究口径 / 交易计划 / 状态体系；**不新增数据库表、列或迁移**；
  不修改导入 JSON Schema

---

## 一、本轮修复清单（对应 spec 六节）

| # | 来源 | 问题 | v1.0.9 处理 |
|---|---|---|---|
| 1 | R-027 | `_import_cache_take()` 只读取 token，commit 成功后才 invalidate，存在 TOCTOU 窗口；同一 token 并发 commit 可重复追加 append-only 的 execution | 改为服务端**原子 claim**：`_IMPORT_PREVIEW_LOCK` 内一次完成「存在 / TTL / kind / in_flight」判定并置位 `in_flight`；失败释放、成功删除；full 与 exec-only 共用同一机制 |
| 2 | 本轮新增 | 前端 commit 按钮无防重 | 点击后按钮立即 disabled 并显示「正在写入…」；请求返回前不再发送第二次；失败恢复、成功进入完成页。**仅为 UI 防误操作**，后端防重独立存在 |
| 3 | spec 第三节 | snapshot 已保存 `execution_latest_id`，却未参与 `_import_snapshot_drift` | 对 execution-only 导入、以及完整导入中**带 execution 块**的证券比对 `execution_latest_id`；不带 execution 块的证券**不被无关 execution 更新阻断** |
| 4 | R-028 | 并发 commit 返回 500「database is locked」而非受控 4xx | 仅 `SQLITE_BUSY` / `SQLITE_LOCKED`（或等价错误文本）→ 受控 **HTTP 409**；其余 `OperationalError` 仍按 500 上报 |

---

## 二、原子 claim 的四条不变式

1. `_import_cache_claim(token, expected_kind)` 在 `_IMPORT_PREVIEW_LOCK` 临界区内
   **一次性**完成四项判定：存在性 → TTL → kind → `in_flight`，并原子置位
   `in_flight = True`。第二个并发 commit 在锁内被拒，而不是等到前一个成功后才
   发现 token 已失效。
2. claim 返回**浅拷贝**，调用方在锁外无法改写 cache 内部状态。
3. commit 成功 → `_import_cache_invalidate(token)` 删除 token（严格一次性）。
4. commit 失败 → `_import_cache_release(token)` 复位 `in_flight`（token 未过期时），
   允许用户修正后重试；覆盖 claim 之后的**所有**异常路径，包括
   `confirmed_status_changes` 参数本身不合法。

token 字面量在 claim / release / invalidate 三处统一经 `_import_token_key()` 规范化（`strip`），
因此「token 前后加空格」不能绕过一次性失效。

**不得只依靠前端按钮防重复**：前端防重（第 2 项）与后端原子防重（第 1 项）是两套独立机制，
任一单独失效都不会导致重复写入。

---

## 三、execution_latest_id 漂移检测的适用范围

| 场景 | `check_execution` | 行为 |
|---|---|---|
| `ah-workbench-execution`（格式 B） | True | `execution_latest_id` 变化 → 拒绝，提示「动态执行判断自预览后已发生变化，请重新解析预览。」 |
| `ah-workbench-import` 含 execution 块的证券 | True | 同上 |
| `ah-workbench-import` 不含 execution 块的证券 | False | **不比对**；即使用别的路径新增了 execution，research / trade_plan 导入照常完成 |

提示语按漂移类型选择：命中 execution 漂移时给出专属文案；status / research / plan /
证券出现消失场景的原文案「工作台数据自预览后已发生变化，请重新解析预览。」
保持**逐字不变**（v1.0.7 / v1.0.8 的测试对该文案有硬断言）。两类同时命中时两条都给出。

漂移检测发生在事务之外、`BEGIN` 之前，因此拒绝时数据库尚未被触碰，不会留下半完成状态。

---

## 四、database is locked 的 HTTP 语义

| 判定 | 依据 | 响应 |
|---|---|---|
| `SQLITE_BUSY`（主码 5） | `sqlite_errorcode & 0xFF in (5, 6)` | **409**「数据库正在处理另一项写入，请稍后重试。」 |
| `SQLITE_LOCKED`（主码 6） | 同上 | 409，同一文案 |
| 文本退化路径 | message 含 `database is locked` / `database table is locked` / `database is busy` | 409（仅拿不到 `sqlite_errorcode` 时兜底） |
| 其它 `OperationalError` | `no such table` / `disk I/O error` / malformed … | **500**「服务器错误: …」，不伪装成 4xx |

同时定义 `DbConflictError`（→ 409）供内部主动上报「稍后重试」使用；
`ApiError` 仍映射 400，语义边界不混淆。

注：原子 claim 生效后，进程内并发已不再产生写入冲突（只有一个请求能进入写入路径），
409 主要覆盖「多进程 / 多标签页同时写同一 SQLite 文件」等进程内锁覆盖不到的情形。

---

## 五、测试结果（本轮实际运行，可复现）

| 套件 | 断言数 | 结果 |
|---|---:|---|
| `tests/test_v102.py` | 38 | PASS |
| `tests/test_v103.py` | 60 | PASS |
| `tests/test_v105.py` | 25 | PASS |
| `tests/test_v106.py` | 28 | PASS |
| `tests/test_v107.py` | 127 | PASS（其中 2 条版本契约断言随版本升级前移，见下） |
| `tests/test_v108.py` | 129 | PASS（其中 3 条版本契约断言同步前移，见下） |
| `tests/test_v109.py` | 83 | PASS（**本轮新增**） |
| **离线合计** | **490** | **FAIL 0** |
| `tests/test_integration_quote.py` | 14 | PASS（需外网，单独执行） |
| `output/.../smoke_v108_http.py` | 14 | PASS（v1.0.8 真实 HTTP 冒烟，不得回退） |
| `output/.../smoke_v109_http.py` | 38 | PASS（**本轮新增**，v1.0.9 全部验收点的真实 HTTP 端到端） |

离线断言总数由 407 增至 **490（+83）**，净变化来源唯一且明确：新增 `tests/test_v109.py`。

### 并发用例的可复现性（本版重点）

- 并发用例走**真实 HTTP 链路**（`ThreadingHTTPServer` + 临时端口 + 8 线程 `Barrier` 同时冲闸），
  不是函数级模拟。
- 为排除「数字随调度波动」：`test_v109.py` 连续运行 **5 次**、`smoke_v109_http.py` 连续运行 **3 次**，
  A/B 两组并发用例的成功次数在**每一次运行中都严格为 1**。
  （v1.0.8 该数字在 **2~3** 之间波动——这正是 R-027 的表现。）
- R-027 / R-028 的原始复现探针在 v1.0.9 上的输出：每轮状态码分布 `{400: 7, 200: 1}`，
  `execution_reviews` 0→1，需要人工判定的轮次 **0/3**，即原缺陷已不可复现。

### 既有测试的变更清单（逐条 diff，非按总数反推）

本轮对既有测试套件**只做版本号契约前移**，未改动任何业务语义断言。
对 v1.0.8 交付 ZIP 内文件与当前工作区文件逐行 diff，结果如下：

| 文件 | 断言标签 | v1.0.8 期望 | v1.0.9 期望 |
|---|---|---|---|
| `tests/test_v107.py` | §P#1 | `TARGET_SCHEMA_VERSION = '1.0.8'` | `TARGET_SCHEMA_VERSION = '1.0.9'` |
| `tests/test_v107.py` | §P#2 | `server_version = 'Workbench/1.0.8'` | `server_version = 'Workbench/1.0.9'` |
| `tests/test_v108.py` | §I#1 | `TARGET_SCHEMA_VERSION = '1.0.8'` | `TARGET_SCHEMA_VERSION = '1.0.9'` |
| `tests/test_v108.py` | §I#2 | `server_version = 'Workbench/1.0.8'` | `server_version = 'Workbench/1.0.9'` |
| `tests/test_v108.py` | §I#15 | 前端版本号 v1.0.8 | 前端版本号 v1.0.9 |

合计 **5 条**（2 + 3），全部为「当前版本常量」契约断言。两个套件的**断言总数保持不变**：
`test_v107.py` 127 → 127，`test_v108.py` 129 → 129；diff 中不存在任何新增、删除或
改写业务语义断言的行。

---

## 六、版本号同步位置（4 处，缺一不可）

| 位置 | 值 |
|---|---|
| `app/server.py` → `TARGET_SCHEMA_VERSION` | `'1.0.9'` |
| `app/server.py` → `Handler.server_version` | `'Workbench/1.0.9'` |
| `app/server.py` → `argparse` description | `'A/H 投研交易工作台 v1.0.9'` |
| `app/server.py` → 启动 print | `'A/H 投研交易工作台 v1.0.9 已启动: %s'` |

另：`app/static/app.js` 头部注释版本号同步为 `v1.0.9`。

---

## 七、数据库状态（未变更）

- 本版**无 Schema 变化**：不新增表、列、索引或迁移脚本。
- `TARGET_SCHEMA_VERSION` 仅作版本号前移，用于版本识别，不触发任何结构迁移。
- `data/workbench.db`：`schema_version = 1.0.9`、`integrity_check = ok`、
  `PRAGMA foreign_key_check` 违例 0。

---

## 八、启动方式

```bash
# Windows
启动工作台.bat

# 命令行
python app/server.py
# 默认地址 http://127.0.0.1:8765
```

---

## 九、验收清单（接收方）

1. 解压到**全新目录**（不要覆盖旧目录），核对 Manifest 条目数与 ZIP 实际条目数一致。
2. `python app/server.py`，确认启动文案为 `v1.0.9` 且地址为 `http://127.0.0.1:8765`。
3. 跑离线套件 7 个：`test_v102/v103/v105/v106/v107/v108/v109` → 合计 **490 断言，FAIL 0**。
4. 跑 `python output/20260910-audit/smoke_v109_http.py` → **38 PASS / FAIL 0**。
5. 跑 `python output/20260910-audit/smoke_v108_http.py` → **14 PASS / FAIL 0**（确认无回退）。
6. 联网可选：`python tests/test_integration_quote.py` → **14 PASS / FAIL 0**。
7. 并发复现（可选）：同一 preview token 并发 8 次 POST `/api/import/execution/commit`，
   预期**恰好 1 次 200、7 次 400、0 次 5xx**，且 `execution_reviews` 只 +1。
8. 确认 `README.txt` 默认地址为 `http://127.0.0.1:8765`。

---

## 十、风险与开放问题

- **R-027（已修复）**：同一 token 并发 commit 可重复追加 execution。
  修复 = 服务端原子 claim + `in_flight`；验证 = 并发 8 次成功严格 = 1，
  原复现探针 3/3 轮不再复现。
- **R-028（已修复）**：并发返回 500 而非受控 4xx。
  修复 = 仅 BUSY/LOCKED → 409，其余 `OperationalError` → 500。
- **R-026（沿用，预期行为）**：preview cache 为进程内存态，服务重启后未使用的 token
  全部失效（需重新预览）。这是「服务端持有预览状态」的必然代价。
- **R-029（本轮新增，低危，刻意选择）**：commit 路径若被 `BaseException`
  （如 `KeyboardInterrupt`、进程被强杀）中断，`in_flight` 不会被释放，
  该 token 在剩余 TTL 内不可重试（需重新 preview）。
  选择「宁阻塞、不重复」是刻意的 fail-safe 取向；影响面为单用户本机操作，
  重新预览即可恢复。
- **O-003 / O-004（待批准，未推进）**：`trades` 冲正机制；`securities.research_pool`
  字段彻底废弃（SQLite 不支持 DROP COLUMN）。

---

## 十一、继续生效的既有约束

- 证券唯一身份只认 `exchange + code`；不用 `name` 匹配，`name` 不一致只提示不自动改。
- 行情涨 = **红**，跌 = **绿**（中国市场惯例）。
- 导入两段式：preview 不写库 + commit 单一 SQLite 事务（任一只失败整批 ROLLBACK）。
- 导入路径不触碰 `trades`；execution 为 append-only；本次也未新增任何写入函数。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。
- 未经用户明确批准，不得新增规则、扩展任务或改变研究口径。
