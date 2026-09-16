# A/H 投研交易工作台 —— 长期项目约定

> 细则分离，本文件只留"不得违反"：环境陷阱 → `ENV-TRAPS.md`；缺陷根因/证据 → `DEFECTS.md`；
> 封板流程 → 技能 `ah-workbench-release-verify`；功能增改 + 六项验证 → 技能
> `ah-workbench-feature-verify`；当日细节 → `YYYY-MM-DD.md`。

## 基本盘
- `D:\个股工作台`；`app/server.py`（纯标准库 http.server+sqlite3）；前端 `app/static/`（hash 路由 + 手写渲染）；库 `data/workbench.db`；端口 **8765**；交付物 `个股工作台-vX.Y.Z-YYYYMMDD.zip`。
- 当前 **v1.0.10**（09-11 封板）。此后两次**未升版本号**的功能改动（用户拍板"只改代码+测试"）：09-14「数据更新」；09-15 卡片「×」归档/恢复。
- 离线 **693 断言 / 11 套件全绿**（标的归档 133）。节奏：**每次只按用户批准的 spec 做一件事**。

## 硬性约定（封板必满足；细则见 release-verify 技能）
1. 版本号同步 **5 处**（TARGET_SCHEMA_VERSION / server_version / argparse description / 启动 print / app.js 头部）+ 契约硬断言 + "正则抽 4 处四值一致"唯一性断言。
2. **测试不得回退**：改既有套件逐标签 diff 出改了哪几条，不得靠断言总数反推。
3. **交付包自洽**：Manifest 条目数 == ZIP 条目数；逐文件字节 + SHA-256 全对；无幽灵条目；只写真跑数；README 端口 == 实际端口；打包后解压到全新目录重跑全套再记 SHA。
4. `BUILD_LOG`（含 ZIP 自身 SHA）与构建脚本**不进 ZIP / Manifest**。
5. 审计文档章节：定位与修复清单 → 逐条展开 → 测试结果 → 交付包一致性 → 本轮边界 → 风险与开放问题 → 第三方审计重点 + 签字栏。
6. **交付库 ≠ 工作区库**：交付是**空库**（业务表全 0 行），绝不把操作者数据打进包；`SRC_OVERRIDE` 指临时空库。
7. **新版必须有契约测试 + 负向验证**（旧产物放回原位须跑红）。
8. **校验必须在"目标机环境"下做**：读注册表持久 PATH 跑**交付物本身**。

## 业务口径
- 证券身份只认 **exchange+code**，绝不用 name 匹配。涨 = **红**，跌 = **绿**。
- 导入**两段式**：preview 不写库 + commit 单一事务（任一只失败整批 ROLLBACK）；导入**不触碰 trades**；`execution_reviews` / `decision_ledger` **append-only**。
- **归档不是删除**：`archived_at` 是**可见性开关**，与 `status` **正交**（不得混入 STATUSES）；子表全 `ON DELETE RESTRICT` → "删除按钮"落地为归档；归档/恢复各追加 1 条台账；`?archived=` 只认白名单；**唯一写入口 `_set_archived_at`**（幂等，并发安全已验证）。
- **行情两档**：60 秒轮询走 **8 秒去抖缓存**；「数据更新」带 `&force=1` 强制联网全量重拉。缺 force = **语义空壳**。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。

## 前端骨架（改前端前必读）
- `render` 在 app.js **末尾被覆盖为 `renderTerminal`**（home → renderTerminalHome → uiCardHtml）；`renderHome` / `cardHtml` 是**死代码**。
- 「×」= `.card-archive`：默认 `opacity:0 + pointer-events:none`，悬停 / 键盘焦点 / 抽屉选中**三态显形**（`:focus-visible` 须同时给 `opacity:1` 与 `pointer-events:auto`，**不得加 `tabindex="-1"`**）；头部预留 24px。
- **`S.secs` 只用于"渲染哪些卡片"**（= 活跃列表）；"按 id 取标的"必须走 `findSec`（活跃 → 已归档两级）；**禁止把 `S.secs.find(...)` 当"全部标的"用**（09-15 两处真缺陷源于此）。全项目**只有 1 个下拉**（A/H）由标的列表动态生成。
- `openModal` 宿主 `#modal-root` 是 `#app` 的**兄弟节点**；**无在途守卫**（连点两下双发，见开放项）。
- **服务端同型铁律**：导入按 exchange+code 匹配、**不按归档过滤**；导入 7 个函数体内**不得出现 `archived_at`**。

## Git
- `git@github.com:healyirobert99-dotcom/gzt.git`（**公开**，main）；身份 `healyirobert99-dotcom`；`core.autocrlf=false`、`quotepath=false`、`core.sshCommand` 指 Windows 原生 OpenSSH；密钥 `~/.ssh/id_ed25519_gzt`。
- **权威流向：远程 → 本地**：`git fetch origin` → `git ls-remote origin refs/heads/main` 取显式 hash → `git reset --hard <hash>`；**不要用 `origin/main` 引用**（恒 `[gone]`）。
- "完整留档"（用户拍板），含**真实数据库快照**。风险已告知：仓库公开，真实标的数据对互联网可见。

## 已修复缺陷（不得回退；详见 `DEFECTS.md`）
- **R-027/R-028**：同 token 并发重复追加 execution → claim 须在锁内原子置位 `in_flight`；并发锁只把 `SQLITE_BUSY`(5)/`SQLITE_LOCKED`(6) 转 409，其余仍 500。
- **启动器**：不得退回 `where python`（Store 存根机双击起不来）。**force**：只认 `force ∈ {1,true,yes,on}`，须绕开 8 秒缓存。
- **归档六条**（锁 `§B#5d §D#7 §D#9 §D#10 §D#11 §D#12 §D#13~#13c §D#14/#14b`）：① 补列不依赖 schema_version；② 迁移重建 DDL 列集合 == `INSERT…SELECT` 复制列（漏列 = 静默清空）；③ A/H 下拉须补回已归档关联项；④ 取标的必须走 `findSec`；⑤ 导入不触碰 `archived_at`、行情须「暂无行情」兜底；⑥「×」必须键盘可达。

## 验证约定（六项；命令与陷阱见 ENV-TRAPS.md / feature-verify 技能）
1. **离线契约** `run_all_tests.py`（必带**基线交叉核对**；断言数净变化必须有来源）。
2. **负向验证**：新断言必须"反向打坏"确认会红。
3. **真实浏览器**（沙箱 8805 + 真实 Chromium + 库副本）：archive 38 / edge 37 / keyboard 24（**纯键盘**）/ ah_link 11；起 `sandbox_server.py 8805`（**后台任务**），收尾 `kill_port.py 8805`。**先读 ENV-TRAPS 陷阱，别先怀疑产品。** **鼠标点击 ≠ 键盘可达** → 每个新交互控件都要单独跑键盘路径。
4. **进程内探针**：monkeypatch `server.DB_PATH` 到库副本，**真实库 SHA 前后必须一致**（`4f4832aa51d00b51…`）。
5. **并发探针**（append-only / token 类改动必跑）：线程池 + `Barrier`，断言为**与调度无关的不变式**，禁止写死某次观测值。
6. **「被过滤集合」四问**：① 表单/下拉 → 静默改值 ② 入口查找 → 静默失效 ③ 展示 → 通常正确 ④ **中转层（转发器）也是操作入口**。能加对照组就加。
7. **真实库隔离性不能用 sha256 判**（09-16 更新）：8765 上自己的实例在跑时，60 秒行情轮询必然改真实库字节。只认「**业务数据不变 + 字节变化只限行情两列**」（业务指纹必须排除行情两列），并记录写者 PID。**收尾还原走 `POST /api/securities/{id}/unarchive` 接口，不用浏览器点击**。`get box` 读数带标签，禁止 `findall` 抓数字。详见 ENV-TRAPS ⑯⑰⑱。

## 待批准 / 开放项（不得自行推进）
- **Ctrl+K 搜不到已归档标的**：① 保持现状 ② 纳入搜索并标注「已归档」。
- **导入对已归档标的"静默成功"**（文案缺口，未擅自改）：① preview 载荷不带 `is_archived`；② 再次「创建」只报"禁止重复创建"。
- **连点两下提交向 append-only 表双写**（实测台账 +2；同构有录交易/执行）：根因 `openModal` **无在途守卫**，**属其它功能、未擅自改**；归档/恢复免疫。
- **R-026** preview cache 进程内存态（预期）；**R-029** commit 被 BaseException 中断时 `in_flight` 不释放（低危）；**R-024/R-014/R-015** 大批量导入耗时 / 单一行情源 / HKD 缺汇率；**R-030** 启动器优先受管运行时（低危）。
- `trades` 冲正机制待批；`securities.research_pool` 废弃（SQLite 不支持 DROP COLUMN）。
- 工作区临时目录已改判「一并入库」；但**删除或整理工作区文件仍需单独批准**。

---
最后更新：2026-09-16 · 离线 693 断言 · 275 个跟踪文件 · 卡片「×」= 09-15 已实现（09-16 仅确认 + 修探针）
