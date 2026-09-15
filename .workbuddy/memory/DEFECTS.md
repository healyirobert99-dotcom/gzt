# 已修复缺陷登记（不得回退）—— 细化版

> 由 `MEMORY.md` 拆分而来（MEMORY.md 每次会话都被注入，控制在最小必要量）。
> 每条都被**测试锁定**：回退就会翻红。根因叙述与负向验证证据在每日日志与技能里。
> 约定：不写"某次观测到的数字"、不写无测试支撑的结论。

## 当前版本前后的功能改动（未升版本号，用户拍板"只改代码 + 测试"）

- 2026-09-14 顶栏「数据更新」按钮：`tests/test_data_update_btn.py`（42）+ 负向
  `neg_data_update_btn.py` + 端到端 `e2e_data_update_btn.py`。
- 2026-09-15 卡片右上角「×」归档/恢复：`tests/test_security_archive.py`（122）+
  浏览器 `browser_e2e_archive.py`（38）/ `browser_e2e_archive_edge.py`（32）/
  `check_ah_link_archive.py`（11）+ 进程内 `check_archive_import.py`（38）+
  负向 `neg_security_archive.py` / `neg_archive_import_contract.py`。

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
  锁 `§D#10` + 边界 `§E7`（修正前 3 红，对照组「··· 更多」绿）。
- **导入路径不得触碰归档**（边界检查新增）：导入按 `exchange+code` 匹配，**不按归档过滤**
  （否则归档标的再也导不进来）；但 `preview/commit_import_full`、`_import_apply_one`、
  `_import_full_diff`、`_import_snapshot_for`、`preview/commit_import_execution` 这 **7 个函数体
  内不得出现 `archived_at`**（既不读也不写）—— 归档标的走 `is_new = row is None` 的 UPDATE 路径，
  绝不复活归档、不改写时间戳、不伪造归档/恢复事件。`archived_at` 全项目**只有 1 个写入口**
  `_set_archived_at`。锁 `§D#11`（6 条）；进程内证据 `check_archive_import.py`（38，含真实仓库版
  DB 快照上"init_db 幂等补列且不触发 do_migration"）；负向 `neg_archive_import_contract.py`
  （4 次注入全部按预期翻红）。
- **归档标的的行情必须走兜底**：行情只对 `S.secs` 拉取 → 已归档标的 `quoteOf()` 返回 null，
  全部渲染点（含详情抽屉）须有「暂无行情」兜底，`uiMiniChart` 须判空（否则整抽屉渲染崩）。
  锁 `§D#12`（3 条）。
