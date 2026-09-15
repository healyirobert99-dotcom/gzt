# A/H 投研交易工作台 —— 长期项目约定

> 环境陷阱/命令细节 → `ENV-TRAPS.md`；缺陷根因与证据 → `DEFECTS.md`；
> 封板流程 → 技能 `ah-workbench-release-verify`；功能增改 + 四级验证 →
> 技能 `ah-workbench-feature-verify`；当日细节 → `YYYY-MM-DD.md`。
> 本文件只留"不得违反"的口径，细则全部在这四处 + 每日日志里。

## 基本盘

- `D:\个股工作台`；`app/server.py`（纯标准库 `http.server`+`sqlite3`）；前端
  `app/static/{index.html,app.js,style.css}`（hash 路由 + 手写渲染）；库 `data/workbench.db`；
  端口 **8765**；交付物 `个股工作台-vX.Y.Z-YYYYMMDD.zip`。
- **当前版本 v1.0.10**（2026-09-11 封板）。此后两次**未升版本号**的功能改动（用户拍板
  "只改代码 + 测试"）：09-14 顶栏「数据更新」；09-15 卡片右上角「×」归档/恢复。
- **离线断言 682 / 11 套件全绿**：v102 38、v103 60、v105 25、v106 28、v107 127、v108 129、
  v109 83、v110 14、行情集成 14、数据更新按钮 42、标的归档 **122**。
- 节奏：**每次只按用户批准的 spec 做一件事**，不擅自加规则、不扩任务、不改研究口径。

## 硬性约定（封板必满足；细则见 release-verify 技能）

1. 版本号同步 **5 处**（`TARGET_SCHEMA_VERSION`/`Handler.server_version`/`argparse`
   description/启动 `print`/`app.js` 头部）+ 契约测试硬断言；新版必须有"正则抽 4 处 + 断言
   四值一致"的唯一性断言（v1.0.10 真漏过第 4 处）。
2. **测试不得回退**：改既有套件要逐标签 diff 出改了哪几条、为什么，**不能靠断言总数反推**。
3. **交付包自洽**：Manifest 条目数 == ZIP 条目数；逐文件字节 + SHA-256 全对；无幽灵条目；
   审计文档只写真跑出来的数字；README 端口 == 实际端口；打包后解压到全新目录重跑全套再记 SHA。
4. `BUILD_LOG`（含 ZIP 自身 SHA）与 `build_docx_*.py` 等构建脚本**不进 ZIP / Manifest**。
5. 审计文档章节：定位与修复清单 → 逐条展开 → 测试结果 → 交付包一致性 → 本轮边界 →
   风险与开放问题 → 第三方审计重点 + 签字栏。
6. **交付库 ≠ 工作区库**：交付是**空库**（业务表全 0 行）；**绝不把操作者数据打进包**；打包用
   `SRC_OVERRIDE` 指临时空库，不覆盖工作区库；`verify_pack.py` 的 `[2]` 改由 `[3]` 按
   integrity=ok / FK 违例=0 / schema_version 对齐 / 业务表全 0 行校验。
7. **新版必须有契约测试 + 负向验证**：不变式固化成 `tests/test_vXYY.py`，并把**修复前的旧产物
   放回原位跑一次确认它会红**（做法见 `.tmp_v108x/verify/neg_*.py`）。
8. **校验必须在"目标机环境"下做**：读注册表持久 PATH 跑**交付物本身**；开发 shell 的 PATH
   被注入过，在里面验证"能不能跑起来"无效。

## 业务口径（不得擅改）

- 证券唯一身份只认 **`exchange + code`**，绝不用 `name` 匹配；name 不一致只提示、不自动改。
- 行情涨 = **红**，跌 = **绿**（中国市场惯例）。
- 导入**两段式**：preview 不写库 + commit 单一事务（任一只失败整批 ROLLBACK）；导入路径
  **不触碰 `trades`**；execution 与 `decision_ledger` 均 **append-only**。
- **归档（软删除）不是删除**：`archived_at` 是**可见性开关**，与 `status` **正交**（不得混入
  `STATUSES`）。五张子表全 `ON DELETE RESTRICT` → 任何 DELETE 都永久抹掉历史，故"删除按钮"
  落地为归档；归档/恢复各追加 1 条台账，其余行不动；`?archived=` 只认白名单（非法值 400）；
  **归档唯一写入口 = `_set_archived_at`**。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。
- **行情刷新分两档**：60 秒轮询走 **8 秒去抖缓存**；「数据更新」按钮带 `&force=1` 强制联网
  全量重拉并回写 `current_price`。缺 force 则按钮拿缓存却提示"已更新" = **语义空壳**。

## 前端骨架（改前端前必读）

- `render` 在 `app.js` **末尾被覆盖为 `renderTerminal`**；home → `renderTerminalHome` →
  `uiCardHtml`。**`renderHome` / `cardHtml` 是死代码，别改错地方。**
- 状态白名单 `STATUSES` 5 项（前后端各一份）；`EXECUTION_VIEWS` 仅 datalist 建议。
- 悬停先例：`.terminal-card:hover .quick-actions`；「×」= `.card-archive`（默认
  `opacity:0 + pointer-events:none`，悬停/键盘焦点/抽屉选中三态显形；头部**永久预留 24px**防抖动）。
  入口：`openArchiveModal(id)` / `openRestoreModal(id)`。弹窗 `openModal(title, body, onSubmit, label)`；
  **宿主 `#modal-root` 是 `#app` 的兄弟节点**，重渲染不会冲掉已打开的弹窗。
- **`S.secs` 只用于"渲染哪些卡片"**（= 活跃列表）。一切"按 id 取标的"必须走 `findSec`
  （活跃 → 已归档两级，活跃优先）；**禁止把 `S.secs.find(...)` 当"全部标的"用** —— 09-15 两处
  真缺陷（A/H 下拉静默清空、详情页入口静默失效）都源于此。全项目**只有 1 个下拉**（A/H）
  由标的列表动态生成，其余 5 个是固定枚举。
- **服务端同型铁律**：导入按 `exchange+code` 匹配、**不按归档过滤**，且导入的 7 个函数体内
  **不得出现 `archived_at`**（既不读也不写）；归档标的一律走 `is_new = row is None` 的 UPDATE 路径。

## Git 与远程仓库

- `git@github.com:healyirobert99-dotcom/gzt.git`，**公开仓库**，分支 `main`；local 身份
  `healyirobert99-dotcom`；`core.autocrlf=false`、`core.quotepath=false`、`core.sshCommand`
  指 Windows 原生 OpenSSH；密钥 `~/.ssh/id_ed25519_gzt`。
- **权威流向：远程 → 本地**（用户在 GitHub 网页端维护）。同步标准操作：`git fetch origin` →
  `git ls-remote origin refs/heads/main` 拿显式 hash → `git reset --hard <完整hash>`。
  **不要用 `origin/main` 引用**（环境会清除 `.git/refs/remotes/` 新建引用，恒显示 `[gone]`）。
- 内容策略"完整留档"（用户拍板）：源码、测试、样例、审计材料、**真实数据库快照**、
  验证脚本、记忆文件全部入库。
- **当前同步点 `a5b009c`**（2026-09-15，本地 = 远程，244 个跟踪文件）。**风险已当面告知**：
  仓库公开，真实标的数据对互联网可见；日后转私有/撤下要提醒"可能已被 fork / 缓存"。

## 已修复缺陷（不得回退；根因与证据 → `DEFECTS.md`，每条都被测试锁定）

- **R-027/R-028（v1.0.9）**：同 token 并发重复追加 append-only execution → claim 必须在锁内
  一次判定并原子置位；并发锁只把 `SQLITE_BUSY`(5)/`SQLITE_LOCKED`(6) 转 409，其余仍 500。
- **启动器**（v1.0.10）：不得退回 `where python`（Store 存根机上双击起不来）。
- **force 语义**（09-14）：`/api/quotes` 只认 `force ∈ {1,true,yes,on}`，且必须绕开 8 秒缓存。
- **归档相关五条**（09-15，详见 `DEFECTS.md`）：① 补列不得依赖 schema_version；② 迁移重建的
  DDL 列集合必须与 `INSERT…SELECT` 复制列一致（漏列=静默清空）；③ A/H 下拉须补回已归档关联项；
  ④ 取标的必须走 `findSec`（两级查找）；⑤ 导入不得触碰 `archived_at`、行情须有「暂无行情」兜底。
  锁：`§B#5d §D#7 §D#9 §D#10 §D#11 §D#12`。

## 验证约定（四级，命令与陷阱见 ENV-TRAPS.md / feature-verify 技能）

1. **离线契约**：`python .tmp_v108x/verify/run_all_tests.py`（必带**基线交叉核对**；铁律：断言数
   净变化必须有来源）。
2. **负向验证**：新断言必须"反向打坏"确认会红（`.tmp_v108x/verify/neg_*.py`）。
3. **真实浏览器**（真实服务 + 真实 Chromium，沙箱端口 8805，库用副本）：
   `browser_e2e_archive.py`（38）+ `browser_e2e_archive_edge.py`（37）+
   `check_ah_link_archive.py`（11）；起服务 `sandbox_server.py 8805`（后台任务），收尾
   `kill_port.py 8805` 按端口杀进程树。**先读 `ENV-TRAPS.md` ⑪⑩⑦⑤④，别先怀疑产品。**
4. **进程内探针**（不起服务）：monkeypatch `server.DB_PATH` 到真实库副本，**真实库 SHA-256
   前后必须一致**（当前 `4f4832aa51d00b51…`）。

- 凡「一次性凭据 / token / append-only 写入」改动**必须跑并发探针**；顺序路径全绿不能证明无缺陷。
  并发数字要可复现：恒定写「严格 = 1」，波动写区间 + 不变式，**禁止写死某次观测值**。
- 交付包自洽一条命令：`scripts/verify_pack.py <zip> --workspace . --rerun [--port-probe]`。
- **「被过滤集合」三问检查法**（09-15 立，已揪出 2 个真缺陷）：凡有一个被过滤过的集合（`S.secs`），
  就问 ① 表单/下拉/多选（→ 静默改值）② 操作入口的查找（→ 静默失效）③ 展示/统计（→ 通常正确）；
  能加对照组就加。

## 待批准 / 开放项（不得自行推进）

- **命令面板（Ctrl+K）搜不到已归档标的**：两条路待拍板 ① 保持现状（用首页「已归档」区）
  ② 纳入搜索并标注「已归档」。
- **导入对已归档标的"静默成功"**（09-15 记录的文案缺口，**未擅自改**，数据完整性已验证无误）：
  ① preview 载荷不带 `is_archived`，看不出"该标的已归档、导入后仍隐藏"；② 对已归档标的再次
  「创建」只报"禁止重复创建"，未提示可到「已归档」区恢复。
- **R-026** preview cache 是进程内存态，重启后未用 token 全失效（预期）。**R-029** commit 被
  `BaseException` 中断时 `in_flight` 不释放（低危，取舍"宁阻塞不重复"）。**R-024/R-014/R-015**
  大批量导入单事务耗时 / 单一行情源（Tencent）/ HKD 缺汇率手工录入。**R-030** 启动器候选链优先
  受管运行时，与"系统默认 Python"直觉可能不一致（低危）。
- `trades` 冲正机制（A/B/C 三方向待批）；`securities.research_pool` 字段废弃（SQLite 不支持
  DROP COLUMN）。
- 工作区临时目录（`archive/`、`audit_pack_src/`、`pack_v106_src/`、`.tmp_v108x/`、旧版
  `PACK_MANIFEST.md`/`PACK_NOTES.md`）已被用户改判为「一并入库」；但**删除或整理工作区文件
  仍需单独批准**。
