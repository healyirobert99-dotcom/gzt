# A/H 投研交易工作台 —— 长期项目约定

> 只留"不得违反"。细则：环境陷阱 → `ENV-TRAPS.md`；缺陷根因 → `DEFECTS.md`；
> 封板 → 技能 `ah-workbench-release-verify`；改功能 + 六项验证 → 技能
> `ah-workbench-feature-verify`；当日细节 → `YYYY-MM-DD.md`。

## 基本盘
- `D:\个股工作台`；`app/server.py`（纯标准库 http.server+sqlite3）；前端 `app/static/`（hash 路由 + 手写渲染）；库 `data/workbench.db`；端口 **8765**；交付物 `个股工作台-vX.Y.Z-YYYYMMDD.zip`。
- 当前 **v1.0.10**（09-11 封板）；此后 09-14「数据更新」、09-15 卡片「×」两次改动**未升版本号**（用户拍板"只改代码 + 测试"）。
- 离线 **695 断言 / 11 套件全绿**（标的归档 135）。**每次只按批准的 spec 做一件事**。

## 业务口径
- 证券身份只认 **exchange+code**，绝不用 name 匹配。涨 = **红**，跌 = **绿**。
- 导入**两段式**（preview 不写库 + commit 单事务，任一失败整批 ROLLBACK）；**不触碰 trades**；`execution_reviews` / `decision_ledger` **append-only**。
- **归档不是删除**：`archived_at` 是**可见性开关**，与 `status` **正交**（不得混入 STATUSES）；五张子表全 `ON DELETE RESTRICT` → "删除按钮"落地为归档；归档/恢复各追加 1 条台账；**唯一写入口 `_set_archived_at`**（幂等、并发安全已验证）。
- **行情两档**：60 秒轮询走 **8 秒去抖缓存**；「数据更新」带 `&force=1` 强制联网重拉。缺 force = **语义空壳**。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。

## 前端骨架（改前端前必读）
- `render` 在 app.js **末尾被覆盖为 `renderTerminal`**；`renderHome` / `cardHtml` 是**死代码**。
- 「×」= `.card-archive`：默认 `opacity:0 + pointer-events:none`，悬停 / 键盘焦点 / 抽屉选中**三态显形**（`focus-visible` 须同时给 `opacity:1` 与 `pointer-events:auto`；**不得加 `tabindex="-1"`**）；头部预留 24px。
- **`S.secs` 只用于"渲染哪些卡片"**（= 活跃列表）；"按 id 取标的"必须走 `findSec`（活跃 → 已归档两级）；**禁止当"全部标的"用**（09-15 两处真缺陷源于此）。
- `openModal` 宿主 `#modal-root` 是 `#app` 的**兄弟节点**；**无在途守卫**（连点两下双发）。
- 服务端同型铁律：导入按 exchange+code 匹配、**不按归档过滤**；导入 7 个函数体内**不得出现 `archived_at`**。

## 封板硬约束（细则见 release-verify 技能）
1. 版本号同步 **5 处**（TARGET_SCHEMA_VERSION / server_version / argparse / 启动 print / app.js 头部）+ "正则抽 4 处四值一致"唯一性断言。
2. **测试不得回退**：逐标签 diff 出改了哪几条，不得靠断言总数反推。
3. **交付包自洽**：Manifest 条目数 == ZIP 条目数；逐文件字节 + SHA-256 全对；无幽灵条目；只写真跑数；README 端口 == 实际端口。
4. `BUILD_LOG`（含 ZIP 自身 SHA）与构建脚本**不进 ZIP / Manifest**；**交付库 ≠ 工作区库**（空库交付，`SRC_OVERRIDE` 指临时空库，绝不把操作者数据打进包）。
5. 新版必须有契约测试 + **负向验证**（旧产物放回原位须跑红）；校验须在"目标机环境"跑**交付物本身**（读注册表持久 PATH）。

## Git
- `git@github.com:healyirobert99-dotcom/gzt.git`（**公开**，main）；**权威流向：远程 → 本地**（`git ls-remote` 取显式 hash → `git reset --hard`；**不用 `origin/main`**，恒 `[gone]`）。
- "完整留档"含**真实数据库快照**；风险已告知（仓库公开，数据对互联网可见）。

## 不得回退（根因/证据见 `DEFECTS.md`）
- **R-027/R-028**：同 token 并发重复追加 execution → claim 须在锁内原子置位 `in_flight`；`_is_db_busy_error` 用 `code & 0xFF` 取主码（不得退化成只比 5/6，否则 WAL 下 517 会变 500）。
- **启动器**：不得退回 `where python`（Store 存根机双击起不来）。**force**：只认 `{1,true,yes,on}`，须绕开 8 秒缓存。
- **归档六条**（锁 `§B#5d §D#7 §D#9~#15b`）：① 补列不依赖 schema_version；② 迁移重建 DDL 列集合 == `INSERT…SELECT` 复制列（漏列 = 静默清空）；③ A/H 下拉须补回已归档关联项；④ 取标的必须走 `findSec`；⑤ 导入不触碰 `archived_at`、行情须「暂无行情」兜底；⑥「×」必须键盘可达且**放大后不得压住徽章**。

## 验证约定（六项）
1. **离线契约** `run_all_tests.py`（必带**基线交叉核对**；断言数净变化须有来源）。
2. **负向验证**：新断言必须"反向打坏"确认会红。
3. **真实浏览器**（沙箱 8805 + 真实 Chromium + 库副本）：archive 38 / edge 37 / keyboard 24（**纯键盘**）/ ah_link 11。**鼠标点击 ≠ 键盘可达** → 每个新交互控件都要单独跑键盘路径。
4. **进程内探针**：monkeypatch `server.DB_PATH` 到库副本。
5. **并发探针**（append-only / token 类必跑）：`Barrier` + **与调度无关的不变式**，禁止写死某次观测值。
6. **「被过滤集合」四问**：① 表单/下拉 → 静默改值 ② 入口查找 → 静默失效 ③ 展示 → 通常正确 ④ **中转层（转发器）也是操作入口**。
7. **隔离性不能用 sha256 判**：8765 自跑时 60 秒行情轮询必改真实库字节 → 只认「**业务数据不变 + 变化只限行情两列**」；收尾还原走 `POST /api/securities/{id}/unarchive`。详见 ENV-TRAPS ⑯⑰⑱⑲。
8. **绝对定位不参与文档流 → 布局耦合须显式断言**（锁 `§D#15`：`38 > 29`）；量几何注意 **border-box ≠ padding-box**，期望值从 DOM 推导、不许写死。

## 待批准 / 开放项（不得自行推进）
- **Ctrl+K 搜不到已归档标的**：① 保持现状 ② 纳入并标注「已归档」。
- **导入对已归档标的"静默成功"**（文案缺口）：preview 不带 `is_archived`；再次「创建」只报"禁止重复创建"。
- **连点两下双写**（09-16 实测：`trades` / `execution_reviews` / `research` / `decision_ledger` 各 **+2**；`trade_plans` 是 UPDATE，安全）：根因 `openModal` **无在途守卫**，**属其它功能、未擅自改**；归档/恢复免疫。
- **交付包 `个股工作台-v1.0.10-20260911.zip` 内 `card-archive` 出现 0 次** —— 若打开的是解压包，拿不到「×」，需重新打包。
- **R-026**（preview cache 内存态，预期）/ **R-029**（commit 中断 `in_flight` 不释放，低危）/ **R-024/R-014/R-015**（大批量导入 / 单一行情源 / HKD 缺汇率）/ **R-030**（启动器优先受管运行时，低危）；`trades` 冲正机制待批。

---
最后更新：2026-09-16 · 离线 695 断言 · 315 跟踪文件 · 同步点 `aea3b4f`
- 卡片「×」= 09-15 已实现（`1829eed`）；09-16 仅**确认**（未改产品代码），改的是验证脚本自身两处探针缺陷。
- `data/workbench.db` 因用户自身实例（行情刷新 + 亲手归档紫金矿业）而改动，**未提交**，待拍板。
