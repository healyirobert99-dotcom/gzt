# A/H 投研交易工作台 —— 长期项目约定

> 环境陷阱明细 → 同目录 `ENV-TRAPS.md`；封板流程 → 技能 `ah-workbench-release-verify`；
> 功能增改与三层验证 → 技能 `ah-workbench-feature-verify`。

## 基本盘

- 目录 `D:\个股工作台`；应用 `app/server.py`（纯标准库 `http.server`+`sqlite3`，无第三方依赖）；
  前端 `app/static/{index.html,app.js,style.css}`（hash 路由 + 手写渲染）；库 `data/workbench.db`；
  默认端口 **8765**；交付物 `个股工作台-vX.Y.Z-YYYYMMDD.zip`
- **当前版本仍 v1.0.10**（2026-09-11 封板）。此后两次**未升版本号**的功能改动（用户拍板
  "只改代码 + 测试"）：2026-09-14 顶栏「数据更新」按钮；2026-09-15 卡片右上角「×」归档/恢复。
  版本史：v1.0.7 导入交互 → v1.0.8 导入完整性 → v1.0.9 并发与预览一致性 → v1.0.10 启动脚本
- **离线断言 665 / 11 套件全绿**：v102 38、v103 60、v105 25、v106 28、v107 127、v108 129、
  v109 83、v110 14、行情集成 14、数据更新按钮 42、标的归档 105
- 节奏：**每次只按用户批准的 spec 做一件事**，不擅自加规则、不扩展任务、不改研究口径

## 硬性约定（封板必满足）

1. **版本号同步 5 处**：`TARGET_SCHEMA_VERSION`、`Handler.server_version`、`argparse`
   description、启动 `print`、`app/static/app.js` 头部；外加各 `tests/test_v1xx.py` 的版本契约
   硬断言。**新版契约测试必须有"正则抽 4 处 + 断言四值完全一致"的唯一性断言**
   —— v1.0.10 真漏过第 4 处且当时无测试能发现。
2. **测试不得回退**：改既有套件必须逐标签 diff 出改了哪几条、为什么，
   **不能靠断言总数反推**"其余未改"。
3. **交付包必须自洽**：Manifest 条目数 == ZIP 条目数；逐文件字节 + SHA-256 全对；无幽灵条目；
   审计文档**只写真跑出来的数字**；README 默认地址 == `server.py` 实际端口；
   打包后**解压到全新目录重跑全套**再记 SHA。
4. **归档 vs 交付**：`BUILD_LOG`（含 ZIP 自身 SHA）与 `build_docx_*.py` 等构建脚本
   **不进 ZIP / Manifest**。
5. **审计文档章节**：定位与修复清单 → 逐条修复展开 → 测试结果 → 交付包一致性 →
   本轮边界 → 风险与开放问题 → 第三方审计重点 + 签字栏。
6. **交付库 ≠ 工作区库**：交付约定是**空库**（6 张业务表全 0 行的模板库）。
   **绝不把操作者数据打进交付包**；打包脚本用 `SRC_OVERRIDE` 指临时空库，
   **不覆盖、不清空工作区库**；Manifest 的字节/SHA 取**实际写进 ZIP 的那份**；
   `verify_pack.py` 的 `[2]` 排除它，改由 `[3]` 按 `integrity_check=ok / FK 违例=0 /
   schema_version==server.py / 业务表全 0 行` 四项校验。
7. **新版本必须有交付契约测试 + 负向验证**：把修复依赖的不变式固化成 `tests/test_vXYY.py`；
   **把修复前的旧产物放回原位跑一次确认它会红**，再恢复并核对 SHA。
8. **校验必须在"目标机环境"下做**：读注册表持久 PATH（`python -c "import winreg; ..."`）
   作为环境，跑**交付物本身**；开发 shell 的 PATH 被注入过，在里面验证"能不能跑起来"无效。

## 业务口径（不得擅改）

- 证券唯一身份只认 **`exchange + code`**，绝不用 `name` 匹配；name 不一致只提示、不自动改。
- 行情涨 = **红**，跌 = **绿**（中国市场惯例）。
- 导入为**两段式**：preview 不写库 + commit 单一 SQLite 事务（任一只失败整批 ROLLBACK）；
  导入路径**不触碰 `trades`**；execution 为 append-only。
- **`decision_ledger` 是 append-only**，保留"当时的判断"，不可被事后改写。
- **归档（软删除）不是删除**：`securities.archived_at` 是**可见性开关**，与交易状态 `status`
  **正交**。五张子表全部 `ON DELETE RESTRICT` 引用 securities，任何 DELETE 都会永久抹掉历史
  —— 故卡片上的"删除按钮"落地为**归档**。归档/恢复各追加 1 条台账（`标的归档`/`标的恢复`），
  其余子表一行不动；`GET /api/securities?archived=` 只认白名单（非法值 400，不静默兜底）。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。
- **行情刷新分两档**（不得回退）：60 秒后台轮询走后端 **8 秒去抖缓存**；「数据更新」按钮带
  `&force=1` **强制联网全量重拉**并回写 `securities.current_price`。缺 force 则按钮在 8 秒
  窗口内只拿缓存却提示"已更新"，即**语义空壳**。

## 前端骨架（改前端前必读）

- `render` 在 `app.js` **末尾被覆盖为 `renderTerminal`**；home → `renderTerminalHome` →
  `uiCardHtml`（`.terminal-card`）。**`renderHome` / `cardHtml` 是死代码，别改错地方。**
- 状态白名单 `STATUSES = ['可交易','等价格','等证据','持仓中','暂不参与']`（前后端各一份）；
  `EXECUTION_VIEWS` 仅作 datalist 建议，后端只校验非空。
- 悬停机制已有先例：`.terminal-card:hover .quick-actions { opacity: 1 }`；
  卡片右上角「×」归档按钮同法（`.card-archive` 默认 `opacity:0 + pointer-events:none`，
  悬停/键盘焦点/抽屉选中三态显形；卡片头部**永久预留 24px 槽位**防悬停抖动）。
- 归档交互入口：`uiCardHtml` 里的 `.card-archive` → `openArchiveModal(id)`；
  首页底部「已归档」区 `uiArchivedSection()` → `openRestoreModal(id)`。
- 重绘用 `render()`；提示 `.toast`；弹窗 `openModal(title, body, onSubmit, label)`。**宿主
  `#modal-root` 是 `#app` 的兄弟节点，重渲染不会冲掉已打开的弹窗。**

## Git 与远程仓库

- `git@github.com:healyirobert99-dotcom/gzt.git`，**公开仓库**，默认分支 `main`；
  local 身份 `healyirobert99-dotcom`；`core.autocrlf=false`、`core.quotepath=false`、
  `core.sshCommand` 指 Windows 原生 OpenSSH；密钥 `~/.ssh/id_ed25519_gzt`（项目专用）。
- **权威流向：远程 → 本地**（用户会在 GitHub 网页端直接维护）。本地改动前先对齐。
  **同步标准操作**：`git fetch origin` → `git ls-remote origin refs/heads/main` 拿显式 hash
  → `git reset --hard <完整hash>`。**不要用 `origin/main` 引用**（环境会清除
  `.git/refs/remotes/` 下新建引用，`git status` 恒显示 `[gone]`）。
- 内容策略"完整留档"（用户拍板）：源码、测试、样例、审计材料、**真实数据库快照**全部入库。
- **当前同步点 `10c6466`**（2026-09-14，本地 = 远程），200 个跟踪文件。
- **风险已当面告知**：仓库公开，真实标的数据对互联网可见；日后转私有或撤下要提醒
  "可能已被 fork / 缓存，删除不等于消失"。

## 已修复缺陷登记（不得回退）

- **R-027（v1.0.9）**：同一 preview token 并发 commit 可重复追加 append-only 的 execution。
  修法 = `_import_cache_claim()` 在 `_IMPORT_PREVIEW_LOCK` 内一次完成
  「存在/TTL/kind/in_flight」判定并**原子置位 `in_flight`**；**不得退回"先读校验、成功才失效"。**
- **R-028（v1.0.9）**：并发写 500「database is locked」。修法 = 仅 `SQLITE_BUSY`(5) /
  `SQLITE_LOCKED`(6) → HTTP 409；**其余 `OperationalError` 必须仍走 500**。
- **`启动工作台.bat` 曾用 `where python`**（v1.0.9 及更早的 388 B 版本）→ 持久 PATH 只含
  Microsoft Store 存根的机器上双击起不来。v1.0.10 换成 3,970 B 候选链版
  （SHA `65414590…fb93`）。**不得退回 `set "PY=python"` + `where python`。**
- **「数据更新」按钮的 force 语义**（2026-09-14）：`get_quotes(symbols, force=True)` 必须
  `need_list = list(need)` 绕开 8 秒缓存；`/api/quotes` 只认 `force ∈ {1,true,yes,on}`；
  前端**仅** force 时拼 `&force=1`，自动轮询不带。契约测试 `tests/test_data_update_btn.py`
  （42 断言）；负向验证与端到端脚本见 `.tmp_v108x/verify/`。
- **卡片「×」的键盘可达性**（2026-09-15）：页面级 `keydown` 里 `Enter` 会 `preventDefault()`
  并跳详情页，**吞掉按钮的默认点击** → Tab 聚焦到 × 后按 Enter 变成"想归档却跳去详情页"。
  守卫表达式必须含 `button` 与 `a[href]`（原为 `editing`，现为 `onControl`）。
  锁定于 `test_security_archive.py §D#7`。
- **补列不能依赖 schema_version**（2026-09-15）：用户库版本已等于 `TARGET_SCHEMA_VERSION`，
  `init_db` 会**整体跳过** `do_migration`，而 `executescript(SCHEMA)` 用的是
  `CREATE TABLE IF NOT EXISTS`、不补列 → 新增列必须在 `init_db` 里**无条件幂等**
  `ALTER TABLE ... ADD COLUMN`（`_ensure_security_columns`）。另：`_column_exists` 必须兼容
  未设 `row_factory` 的连接（`hasattr(r,'keys')`），否则"启动即失败"。
- **迁移重建路径的列一致性**（2026-09-15）：`securities__new` 的 DDL 列集合必须与
  `INSERT ... SELECT` 的复制列集合**完全一致** —— 漏一列会**静默清空**该列（不报错、只回
  DEFAULT）。锁定于 `test_security_archive.py §B#5d`。

## 验证约定

- 凡「一次性凭据 / token / append-only 写入」改动**必须跑并发探针**（技能内的
  `scripts/concurrency_probe.py`）；顺序路径全绿不能证明无缺陷。
- 并发数字要可复现：恒定写「严格 = 1」，波动写区间 + 不变式，**禁止写死某次观测到的数字**。
- 交付包自洽校验一条命令：`scripts/verify_pack.py <zip> --workspace . --rerun [--port-probe]`。
- 真实浏览器（真实服务 + 真实 Chromium）端到端见 `.tmp_v108x/verify/browser_e2e_archive.py`
  （38 断言，可在沙箱端口 8805 上重复跑）。**agent-browser 的硬约束（选择器不能带空格 /
  `click` 不滚动进视口 / 会话跑久了 `:hover` 失效 / `✓ Done` 不代表命中）先读
  `ENV-TRAPS.md`，别先怀疑产品** —— 2026-09-15 这几条各伪装过一次"功能坏掉了"。

## 待批准 / 开放项（不得自行推进）

- **R-026** preview cache 是进程内存态，服务重启后未用 token 全失效（预期行为）。
- **R-029** commit 被 `BaseException` 中断时 `in_flight` 不释放（低危，取舍"宁阻塞不重复"）。
- **R-024 / R-014 / R-015**：大批量导入单事务耗时；单一行情源（Tencent）；HKD 缺汇率手工录入。
- **R-030** 启动器候选链优先受管运行时目录，与"系统默认 Python"直觉可能不一致（低危）。
- `trades` 冲正机制（A/B/C 三方向待批）；`securities.research_pool` 字段废弃（SQLite 不支持
  DROP COLUMN）。
- 工作区临时目录（`archive/`、`audit_pack_src/`、`pack_v106_src/`、`.tmp_v108x/`、根目录旧版
  `PACK_MANIFEST.md`/`PACK_NOTES.md`）已被用户改判为「一并入库」，不再是清理项；
  但**删除或整理工作区文件仍需单独批准**。
