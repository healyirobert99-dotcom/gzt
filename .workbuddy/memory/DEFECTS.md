# 已修复缺陷登记（不得回退）—— 细化版

> 由 `MEMORY.md` 拆分而来（MEMORY.md 每次会话都被注入，控制在最小必要量）。
> 每条都被**测试锁定**：回退就会翻红。根因叙述与负向验证证据在每日日志与技能里。
> 约定：不写"某次观测到的数字"、不写无测试支撑的结论。

## 当前版本前后的功能改动（未升版本号，用户拍板"只改代码 + 测试"）

- 2026-09-14 顶栏「数据更新」按钮：`tests/test_data_update_btn.py`（42）+ 负向
  `neg_data_update_btn.py` + 端到端 `e2e_data_update_btn.py`。
- 2026-09-15 卡片右上角「×」归档/恢复：`tests/test_security_archive.py`（133）+
  浏览器 `browser_e2e_archive.py`（38）/ `browser_e2e_archive_edge.py`（37）/
  `browser_e2e_archive_keyboard.py`（24，纯键盘路径）/ `check_ah_link_archive.py`（11）+
  进程内 `check_archive_import.py`（38）+ 并发 `concurrency_archive_probe.py`（12）+
  负向 `neg_security_archive.py` / `neg_archive_import_contract.py`（24，12 次注入）/
  `neg_findsec_browser.py`（6）/ `neg_keyboard_browser.py`（11）。

## v1.0.9（封板，R-027 / R-028）

- **R-027** 同一 preview token 并发 commit 可重复追加 append-only 的 execution。
  修法 = `_import_cache_claim()` 在 `_IMPORT_PREVIEW_LOCK` 内一次完成「存在/TTL/kind/
  in_flight」判定并**原子置位 `in_flight`**。**不得退回"先读校验、成功才失效"。**
- **R-028** 并发写 500「database is locked」。修法 = 仅 `SQLITE_BUSY`(5) / `SQLITE_LOCKED`(6)
  → HTTP 409；**其余 `OperationalError` 必须仍走 500**（不得扩大映射范围）。

## v1.0.10（封板，启动脚本次交付修复）

- **`启动工作台.bat` 曾用 `where python`**（v1.0.9 及更早的 388 B 版本）→ 持久 PATH 只含
  Microsoft Store 存根的机器上双击起不来。v1.0.10 换成 3,970 B 候选链版
  （SHA `65414590…fb93`）。**不得退回 `set "PY=python"` + `where python`。**
  抽 `:try` 子程序做隔离测试，保证被测代码 == 交付代码。

## 2026-09-14 · 「数据更新」按钮的 force 语义

- `get_quotes(symbols, force=True)` 必须 `need_list = list(need)` 绕开 8 秒去抖缓存；
  `/api/quotes` 只认 `force ∈ {1,true,yes,on}`；前端**仅** force 时拼 `&force=1`。
- 缺 force → 按钮在 8 秒窗口内只拿缓存却提示"已更新"，即**语义空壳**。

## 2026-09-15 · 归档功能的缺陷（本次改动）

- **卡片「×」键盘可达性**：页面级 `keydown` 里 `Enter` 会 `preventDefault()` 并跳详情页，
  **吞掉按钮的默认点击** → Tab 聚焦到 × 后按 Enter 变成"想归档却跳去详情页"。
  守卫表达式必须含 `button` 与 `a[href]`（原为 `editing`，现为 `onControl`）。锁 `§D#7`。
- **补列不能依赖 schema_version**：用户库版本已等于 `TARGET_SCHEMA_VERSION`，`init_db` 会
  **整体跳过** `do_migration`，而 `executescript(SCHEMA)` 用的是 `CREATE TABLE IF NOT EXISTS`、
  不补列 → 新增列必须在 `init_db` 里**无条件幂等** `ALTER TABLE ... ADD COLUMN`
  （`_ensure_security_columns`）。另：`_column_exists` 必须兼容未设 `row_factory` 的连接
  （`hasattr(r,'keys')`），否则"启动即失败"。
- **迁移重建路径的列一致性**：`securities__new` 的 DDL 列集合必须与 `INSERT ... SELECT`
  的复制列集合**完全一致** —— 漏一列会**静默清空**该列（不报错、只回 DEFAULT）。锁 `§B#5d`。
- **归档不得连带丢掉 A/H 关联**：`S.secs` 不含已归档标的，而编辑框的 A/H 下拉只照 `S.secs`
  生成 → 关联标的被归档后下拉里没有它，浏览器回落首项「— 无 —」，用户**只改行业/备注再保存
  就会把 `ah_link_id` 静默清空**（`app.js::openBasicModal`）。修法：候选里补回被归档的关联项
  并标「· 已归档」，**且仅在"当前已关联且该关联不在活跃列表"时补**（不无条件塞入已归档标的）；
  标的库的 A/H 显示同一口径。锁 `§D#9`；端到端负向 `check_ah_link_archive.py`（修正前 4 红 →
  修正后 11 绿）。
- **归档是可见性开关，不是只读开关**：`findSec` 原先只查 `S.secs`，于是从 `#/s/{id}`
  （书签 / 后退 / 标的库的 A/H 链接）打开已归档标的时，详情抽屉的「更新动态执行 / 录入交易 /
  查看研究 / ··· 更多」**全部静默失效**（后端并没有任何 mutation 端点校验 `archived_at`，
  本就允许编辑）。修法：`findSec` 改为**活跃 → 已归档**两级查找（活跃优先）。
  锁 `§D#10`（含 `#10d/e`：抽屉的「··· 更多」必须是**纯 id 转发器**，自己不得查活跃列表，
  否则菜单里 4 项会一并失效）+ 边界 `§E7`（4 项入口）+ `§E8`（「更多」菜单内 4 项）
  + `§E9`（活跃标的对照组）。修正前：边界脚本 3 红、菜单内 4 红，浏览器层负向 7 条全红。
- **导入路径不得触碰归档**（边界检查新增）：导入按 `exchange+code` 匹配，**不按归档过滤**
  （否则归档标的再也导不进来）；但 `preview/commit_import_full`、`_import_apply_one`、
  `_import_full_diff`、`_import_snapshot_for`、`preview/commit_import_execution` 这 **7 个函数体
  内不得出现 `archived_at`**（既不读也不写）—— 归档标的走 `is_new = row is None` 的 UPDATE 路径，
  绝不复活归档、不改写时间戳、不伪造归档/恢复事件。`archived_at` 全项目**只有 1 个写入口**
  `_set_archived_at`。锁 `§D#11`（6 条）；进程内证据 `check_archive_import.py`（38，含真实仓库版
  DB 快照上"init_db 幂等补列且不触发 do_migration"）；负向 `neg_archive_import_contract.py`
  （12 次注入全部按预期翻红，含 §D#10d/e、§D#13~#13c、§D#14/#14b）。
- **归档标的的行情必须走兜底**：行情只对 `S.secs` 拉取 → 已归档标的 `quoteOf()` 返回 null，
  全部渲染点（含详情抽屉）须有「暂无行情」兜底，`uiMiniChart` 须判空（否则整抽屉渲染崩）。
  锁 `§D#12`（3 条）。
- **「×」必须键盘可达**（2026-09-15）：三条只对键盘生效的不变式，缺任一条键盘用户就够不到 ×：
  ① `.card-archive` 默认 `opacity:0 + pointer-events:none`（鼠标路径：悬停才出现）；
  ② `.card-archive:focus-visible` 必须**同时**给出 `opacity:1` 与 `pointer-events:auto`
  （只管 opacity 会让键盘 Tab 到却点不动）；③ × 按钮**不得**带 `tabindex="-1"`。
  锁 `§D#13~#13c`（3 条）+ 浏览器 `browser_e2e_archive_keyboard.py`（24，Tab→Enter→Enter
  纯键盘走完归档+恢复）；负向 `neg_keyboard_browser.py`（11）：删掉 ② → §K3#2/#3 红且
  下面一切照旧；加 `tabindex="-1"` → §K3#1 红且**键盘完全无法归档**（台账一条不动）。
- **连点两下提交不得谎报、不得双写**（2026-09-15）：`openModal` 的提交回调**没有在途守卫**
  （不 disable 提交按钮、无 in-flight 标志）→ 连点两下会派发两次请求。归档/恢复因**后端幂等**
  （`_set_archived_at` 的 `changed` 守卫）+ **前端按 `changed` 分流文案**而免疫：
  第一次「已归档 · X」、第二次「X 本就处于归档状态」；恢复侧则在弹窗**打开前**先查
  `im.is_archived`，不成立只提示、不发请求。锁 `§D#14`（toast 按 changed 分流）
  + `§D#14b`（恢复弹窗前提守卫）；负向 M11/M12 两次注入均按预期翻红。
  - **探针副产物（不属本功能，未擅自改）**：`openModal` 提交回调无在途守卫 —— 实测的
    **真实影响半径**（`probe_double_submit_radius.py`，09-16 补完）：

    | 弹窗 | 表 | 连点两下增量 | 判定 |
    |---|---|---|---|
    | 录入交易流水 | `trades` | **+2** | ✗ **业务表重复** |
    | 更新动态执行判断 | `execution_reviews` | **+2** | ✗ |
    | 更新研究结论 | `research` | **+2** | ✗ |
    | 添加决策记录 | `decision_ledger` | **+2** | ✗ |
    | 修改交易计划 | `trade_plans` | **0** | ✅ 是 UPDATE，安全 |

    服务端这 5 条**全无去重 / 唯一约束**；`create_security` 有查重、`archive` 有幂等守卫
    → 二者免疫。已记入 `MEMORY.md` 开放项，待用户拍板。
    测法铁律：**必须发两次独立 `click`** —— `dblclick` 会被 Playwright 合成**单个** click
    事件（`detail=2`），实测只 +1，会把真缺陷误判成"无缺陷"。
  - **交付包可能不含新功能**（09-16）：根目录 `个股工作台-v1.0.10-20260911.zip`（09-11 打）
    里 `card-archive` 出现 **0 次** —— 包早于 09-15 的功能。用户说"界面上没有"时，
    **先确认他跑的是源码目录还是解压出来的交付包**，别急着改代码。

## 已**验证为安全**、并锁成不变式（不是缺陷，但回退就会翻红）

- **归档 / 恢复在并发下不污染 append-only 台账**（2026-09-15）：`_set_archived_at` 是
  「读校验 → 写状态 → 追加台账」三段式，天然有 TOCTOU 嫌疑，故按铁律跑了并发探针
  （`concurrency_archive_probe.py`，12 断言：12 轮×8 线程纯归档 + 12 轮×8 线程混合）。
  实测 192 次调用：**每轮 changed=True 严格 == 1**、台账增量 == changed=True 数、
  无幽灵行、无其它异常、终态与成功次数奇偶守恒。锁 `§C#15~#15d`（4 条，真实
  ThreadingHTTPServer + 真 HTTP 并发）。
  - **并发冲突必须走 409 而不是 500**：192 次里真的撞上 SQLITE_BUSY 32 次（~17%）。
    归档路由走统一的 `_mut`，`_is_db_busy_error` 用 `code & 0xFF` 取主码，
    故 `SQLITE_BUSY_SNAPSHOT`(517) 也被正确归入 409 族 —— **不得退回"只比对 5/6"**。
  - 负向证据：去掉幂等守卫（M7）→ 单轮 6 个 changed=True、并出现 409；写了台账却报
    `changed=False`（M8）→ 台账增量与 changed 数不一致。两次都按预期翻红。
