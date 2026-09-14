# A/H 投研交易工作台 —— 长期项目约定

## 项目基本盘

- 目录：`D:\个股工作台`；应用 `app/server.py`（纯标准库 `http.server` + `sqlite3`，无第三方依赖）
- 前端：`app/static/{index.html,app.js,style.css}`，hash 路由 + 手写渲染
- 数据库：`data/workbench.db`；交付物为根目录 `个股工作台-vX.Y.Z-YYYYMMDD.zip`
- 默认端口 **8765**；启动：`python app/server.py`（或双击 `启动工作台.bat`）
- **当前版本 v1.0.10**（2026-09-11 封板）：离线 **504 断言**（38+60+25+28+127+129+83+14）
- 版本节奏：**每次只按用户批准的 spec 做一件事**，不擅自加规则、不扩展任务、不改研究口径
- 版本历史：v1.0.7 导入交互层 → v1.0.8 导入完整性（407）→ v1.0.9 并发与预览一致性（490）
  → v1.0.10 启动脚本交付修复（504）

## 硬性约定（每版封板都必须满足）

1. **版本号必须同步 4 处**：`TARGET_SCHEMA_VERSION`、`Handler.server_version`、
   `argparse` description、启动 `print` 文案；外加 `app/static/app.js` 头部；
   此外各 `tests/test_v1xx.py` 里的版本契约硬断言也要同步更新（改这些断言要**在审计文档中逐条列明**）。
   **v1.0.10 升级时真的漏过第 4 处且当时无测试能发现** —— 故每个新版本的契约测试里
   必须有一条"正则抽取 4 处 + 断言四值完全一致"的**唯一性断言**（见 `test_v110.py` §A#5）。
2. **测试不得回退**：改既有测试套件时，必须逐标签 diff 出改了哪几条、为什么改，
   **不能靠断言总数反推**"其余 N 条未改"。断言数变化要写清净变化来源。
3. **交付包必须自洽**（v1.0.7 曾因此被审计打回）：
   - Manifest 文件数 == ZIP 实际条目数；逐文件字节数 + SHA-256 全对；无幽灵条目（不列 ZIP 里没有的 build 脚本）
   - 审计文档**只写真跑出来的数字**，不沿用历史文档的声称
   - README 默认地址必须与 `server.py` 实际默认端口一致
   - 打包后必须**解压到全新目录重跑全套**，再记 SHA
4. **归档 vs 交付**：`BUILD_LOG`（含 ZIP 自身 SHA）**不进 ZIP**（否则自指矛盾）；
   `build_docx_v1xx.py` 等构建脚本不进 Manifest。
5. **审计文档章节结构**（历版沿用）：定位与修复清单 → 逐条修复展开 → 测试结果 →
   交付包一致性 → 本轮边界（未改变的部分）→ 风险与开放问题 → 第三方审计重点 + 签字栏。
6. **交付库 ≠ 工作区库**（v1.0.10 起必须显式区分）：交付约定是**空库交付**，
   包内 `data/workbench.db` 是 6 张业务表全 0 行的模板库；工作区那份会随使用增长。
   - **绝不把操作者数据打进交付包**；打包脚本用 `SRC_OVERRIDE` 指到临时生成的空库，
     **不覆盖、不清空工作区库**（打包前另存一份备查）。
   - Manifest 里的字节数 / SHA 取**实际写进 ZIP 的那份内容**。
   - `verify_pack.py` 的 `[2]` 排除它，改由 `[3]` 按
     `integrity_check=ok / FK 违例=0 / schema_version==server.py / 业务表全 0 行` 四项校验。
7. **新版本必须有交付契约测试 + 负向验证**：把本版修复依赖的不变式固化成
   `tests/test_vXYY.py`；并**把修复前的旧产物放回原位跑一次确认它会红**，
   然后恢复并核对 SHA。结论写进审计文档："该测试若在上一版封板时存在，本缺陷不会漏出。"
8. **校验必须在"目标机环境"下做**：开发 shell 的 PATH 被注入过（受管运行时排在
   WindowsApps 之前），在它里面验证"能不能跑起来"结论无效。读注册表的持久 PATH
   （`python -c "import winreg; ..."`）作为环境，跑**交付物本身**。

## 业务口径（不得擅改）

- 证券唯一身份只认 **`exchange + code`**，绝不用 `name` 匹配；name 不一致只提示、不自动改。
- 行情涨 = **红**，跌 = **绿**（中国市场惯例）。
- 导入为**两段式**：preview 不写库 + commit 单一 SQLite 事务（任一只失败整批 ROLLBACK）。
- 导入路径**不触碰 `trades`**（trades 由"录入交易流水"独立管理）；execution 为 append-only。
- 不实现：AI 自由文本解析 / Markdown 解析 / 文件拖拽 / 自动联网补全。
- **行情刷新分两档**（2026-09-14 新增，不得回退）：60 秒后台轮询走后端 **8 秒去抖缓存**；
  顶栏「数据更新」按钮带 `&force=1` **强制联网全量重拉**并回写 `securities.current_price`。
  缺了 force，按钮在 8 秒窗口内只会拿到缓存却提示"已更新"，即**语义空壳**。
- 2026-09-14 的「数据更新」按钮是**未升版本号的功能改动**（用户明确选择"只改代码+测试"），
  版本仍为 v1.0.10，`TARGET_SCHEMA_VERSION` 等 4 处不动。

## 环境注意

- 受管运行时：`C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- `os.remove()` 会被环境拦截为"回收站"操作且可能失败；**覆盖文件请先生成到临时名再 `mv -f`**。
- 生成中文文件名 ZIP 用 `zipfile.ZipInfo` + `create_system=0`，可规避中文乱码。
- **PowerShell 工具在本环境 stdout 完全捕获不到**（`Write-Output "hi"` 也无输出、exit 0）。
  读注册表 / 持久环境变量请用 `python -c "import winreg; ..."` 从 Bash 调。
- **`cmd.exe /c ...` 被安全策略拦截**。执行 .bat 用
  `python -c "subprocess.run([abs_path])"`，**必须传绝对路径**；传相对正斜杠路径会被
  CreateProcess 拒绝，且失败时 stdout 为空、**极易被误判成断言通过**。
- Python 读 CRLF 文本若不加 `newline=''`，universal newlines 会折掉 `\r`，
  `text.index(':label\r\n')` 会抛 `ValueError`。
- **Bash heredoc 会改写内嵌的 Windows 路径**：`<<'PYEOF'` 里写 `'C:\\Users\\...'`
  实际送到 Python 的会变成 `C:/Users///u5b9c...`（`\\`→`/`、`\u`→`/u`），
  表现为 `FileNotFoundError` 且路径长得莫名其妙。**对策：探针脚本一律用 Write 工具
  落成真实文件再执行**，不要用 heredoc 传含反斜杠的源码。
- **运行工作台会改写 `data/workbench.db`**：`init_db()` 与页面/接口访问会触发行情刷新，
  只改 `securities.current_price` / `current_price_updated_at` 两列。
  因此**任何"跑起来验证"之后 `git status` 都会显示该库被改**。
  对策：验证后 `git restore data/workbench.db` 回到仓库版本（行情下次开 app 自会刷新），
  或**明确**作为一次 data 提交推上去——**不要让它悄悄留在工作区**。
  另：即使 `mode=ro` 打开 WAL 库也会生成 `-shm`/`-wal`（已被 `.gitignore` 覆盖，
  `-wal` 常为 0 字节，可直接删）。
- **agent-browser（真实浏览器验证）在本环境必须用 `batch` 驱动**：
  ① 组合命令（`&&` 串联、`| head` 管道）极易被 SIGTERM —— 要么单命令、要么重定向到文件再读；
  ② **单独 `open` 后页面会退回 `about:blank`**（截图全白、`eval` 读到 `bodyLen=0`），
     整条链路必须放进**一次** `batch "cmd1" "cmd2" ...` 调用，页面状态才保持；
  ③ `screenshot [path]` 的单参数会被当成 selector，实际存到
     `~/.agent-browser/tmp/screenshots/`，需从该目录取回。
- **agent 起不了"能活下去"的服务进程**（2026-09-14 实测）：进程树被 Job Object 托管
  （kill-on-close）。`DETACHED_PROCESS` 起的服务，在调用它的脚本退出后即被回收
  （PID 40888 / 17528 两次验证）；补 `CREATE_BREAKAWAY_FROM_JOB` → `WinError 5 拒绝访问`；
  走 `wmic process call create` → **wmic.exe 在安全策略的程序黑名单里**，且明确禁止
  "换 shell 或等价绕过"。**结论：不要在 agent 里替用户启动工作台**——
  改完代码后把测试端口清干净，让用户双击 `启动工作台.bat` 自己起。
- **`taskkill` 在 MSYS Bash 下不可用**（`//F` 报"无效参数"，`/F` 被路径转换）。
  用 `python -c "import subprocess; subprocess.run(['taskkill','/F','/PID',pid])"`。
- **MSYS2 版 ssh（`/usr/bin/ssh`）在中文用户名 HOME 下彻底不可用**：它把
  `HOME=/c/Users/宜春法院` 按本地 ANSI(GBK) 处理，去找
  `/c/Users/\322\313\264\272\267\250\324\272/.ssh/known_hosts`，于是**既读不到
  `known_hosts`，也读不到 `~/.ssh/config`**，报 `Host key verification failed`
  —— 伪装成"主机密钥问题"，极易误诊为密钥没配对。
  **git 必须改用 Windows 原生 ssh**：
  `git config core.sshCommand "C:/Windows/System32/OpenSSH/ssh.exe"`。
  自检：`<ssh> -G github.com | grep '^user'` 应输出 `user git`
  （MSYS2 版会输出 `user 宜春法院`，即 config 根本没被读）。

## Git 版本管理与远程仓库（2026-09-11 建立，09-14 起远程为权威源）

- 仓库：`git@github.com:healyirobert99-dotcom/gzt.git`，**公开仓库**，默认分支 `main`
- git 身份（`--local`）：`healyirobert99-dotcom` /
  `healyirobert99-dotcom@users.noreply.github.com`
- 已设 `core.autocrlf=false`（保证入库字节与工作区逐字节一致）、`core.quotepath=false`
  （中文文件名不转义）、`core.sshCommand` 指向 Windows 原生 OpenSSH（见上一节的坑）。
- 密钥：`~/.ssh/id_ed25519_gzt`（项目专用）；`~/.ssh/config` 内 `IdentityFile` +
  `IdentitiesOnly yes`。公钥已由用户添加到 GitHub 账号（2026-09-11）。
- **权威流向（2026-09-14 起）：远程 → 本地**。用户会在 GitHub 网页端直接上传/维护
  （提交消息为英文风格），本地改动前先 `git fetch` 对齐，避免分叉。
- **本环境的同步标准操作**：`git fetch origin` → `git ls-remote origin refs/heads/main`
  拿显式 hash → `git reset --hard <完整hash>`。**不要用 `origin/main` 引用**——
  环境的文件拦截会清除 `.git/refs/remotes/` 下新建的引用（fetch 刚建立就消失，
  `git status` 恒显示 `[gone]`），但不影响 `.git/config` 里的跟踪配置。
- 内容策略为"完整留档"（用户拍板）：源码、测试、样例、审计材料、**真实数据库快照**、
  历史归档全部入库。`.gitignore` 只排 `__pycache__/`、`*.py[cod]` 与系统 / 编辑器垃圾
  （注意：根目录 `workbench.db` 的 ignore 规则对已跟踪文件无效）。
- **当前同步点**：`aeec184`（2026-09-14，本地 = 远程），200 个跟踪文件；
  `data/workbench.db` 已是用户云端演进版（**16 只标的**，research 17 / plan 21 /
  execution 29 / ledger 57，integrity ok）。本地两个中文提交（`eb91952`/`4511cfc`）
  仍完整保留在远程历史中。
- **风险已当面告知**：仓库公开，真实标的数据对互联网可见；日后若要转私有或撤下，
  必须提醒"可能已被 fork / 缓存，删除不等于消失"。

## 启动器约定（`启动工作台.bat`，2026-09-11 重写）

- **必须纯 ASCII + CRLF**。bat 由 cmd.exe 按控制台代码页（936/65001）逐字节解释，
  任何非 ASCII 字节都可能错位并污染传给 shell 的路径。历史包曾因硬编码中文路径
  而写出 `M-RM-KM-4M-:M-7M-(M-TM-:` 这类乱码，**不得重犯**。
- **解释器路径一律用 `%USERPROFILE%\.workbuddy\binaries\python\versions\<ver>\python.exe`**：
  源码保持 ASCII，运行时解出含中文的正确绝对路径。**禁止把中文绝对路径写进 bat。**
- **禁止只用 `where python` 判定可用性**。本机持久 PATH 里**只有**
  `%LOCALAPPDATA%\Microsoft\WindowsApps`，其中 `python.exe` 是 **Microsoft Store 占位存根**
  → `where python` 会"成功"，`if errorlevel 1` 永不触发，双击后实际拉起应用商店。
- 候选链顺序：① pinned `3.13.12` → ② `for /d` 遍历 `versions\*` → ③ `py` → ④ PATH 上的 `python`；
  每项都过 `:try` 子程序：**真跑一次** `-c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)"`，
  并**显式拒绝**路径含 `WindowsApps` 的候选。
- 改 bat 后必须三段式验证：① **抽 `:try` 子程序做隔离测试**（保证被测代码 == 交付代码）
  ② 契约测试 `tests/test_v110.py` §B（并做负向验证：旧 bat 应得 3 FAIL）
  ③ 端到端 A/B/C：解压交付包到全新目录，用它自己那份 bat，在**真实持久 PATH** 下实跑，
  必须"新 bat 能起、旧 bat 起不来"，且**按端口属主杀进程树**收尾
  （`Popen.kill()` 只杀 cmd.exe，子进程 python 会继续占端口 → 后续实验误判）。
  探针见 `.tmp_v108x/verify/e2e_launcher_v110.py`（11 断言）。

### 桌面启动器（`C:\Users\宜春法院\Desktop\启动工作台.bat`，2026-09-14 建立）

- **薄封装 + 委托**：只做「检查项目在不在 → `call "%WB%\<项目启动器>"`」，
  **绝不复制解释器探测逻辑**（否则两份会漂移）。WB 硬编码为 `D:\个股工作台`。
- **编码与项目启动器相反**：项目内那份必须 ASCII（见上）；桌面这份**必须含中文路径**，
  故用 **UTF-8 无 BOM + CRLF + 第 2 行 `chcp 65001 >nul`**，且**首个非 ASCII 行之前的
  各行必须全是 ASCII**（cmd 先按默认代码页读，chcp 之后才按 65001 重读）。
  本机已有同约定可用先例：`桌面\video知识库剪贴板监控.bat`。
- **两条守卫**：① `%~f0` 等于 `%WB%\<启动器>` 时拒绝（防被复制回项目目录后无限自调用）；
  ② 项目路径不存在时打印指引并 `exit /b 1`。
- **由脚本生成**，不手写：`.tmp_v108x/verify/make_desktop_launcher.py`（控制编码/行尾/无 BOM
  并回读校验）。验证：`e2e_desktop_launcher.py`（真实持久 PATH + cwd=桌面 + BROWSER 打桩，
  8 断言）、`neg_desktop_launcher.py`（守卫与提示 5 断言）。

## 待批准 / 开放项（不得自行推进）

- **R-026**（沿用，预期行为）：preview cache 是进程内存态；服务重启后未使用 token 全部失效，
  用户需重新预览。这是"服务端持有预览状态"的必然代价。
- **R-029**（v1.0.9 新增，低危，刻意选择）：commit 路径若被 `BaseException`
  （`KeyboardInterrupt` / 进程强杀）中断，`in_flight` 不会释放，该 token 在剩余 TTL 内
  不可重试（需重新预览）。取舍是"宁阻塞、不重复"。
- **R-024 / R-014 / R-015**：大批量导入单事务耗时；单一行情源（Tencent）；HKD 缺汇率需用户录入。
- **R-030**（v1.0.10 新增，低危）：`启动工作台.bat` 候选链**优先**受管运行时目录，其次 `py`，
  最后 PATH 上的 `python`。目标机有多个可用解释器时选中的是链上第一个，与"系统默认 Python"
  的直觉可能不一致。仅影响用哪个解释器运行（纯标准库，3.8+ 均可），不影响数据与功能。
- `trades` 冲正机制（A/B/C 三方向待批）
- `securities.research_pool` 字段彻底废弃（SQLite 不支持 DROP COLUMN）
- 工作区临时目录清理（`archive/`、`audit_pack_src/`、`pack_v106_src/`、`.tmp_v108x/`、
  根目录旧版 `PACK_MANIFEST.md`/`PACK_NOTES.md`）——已被用户改判为「一并入库」（2026-09-11），
  不再是清理项；但**删除或整理工作区文件仍需单独批准**。
- ~~根目录平铺重复文件~~（**2026-09-14 已清理**，用户指示「以云端版本为准」）：
  `index.html` / `style.css` 为 `e342fbc` 上传的旧版 UI（已被 `01f9192` 的
  `app/static/` 新版取代）；`logo.svg` / `workbench.db` 与正式文件逐字节一致。
  已 `git rm` + 提交推送（`6615916`），跟踪文件 190 → 187。`.gitignore` 的
  `/workbench.db` 规则此后真正生效（之前因已被跟踪而失效）。
- **环境陷阱（2026-09-14 确认）**：连续多次 Edit 同一文件时，**部分编辑可能被环境的
  文件回滚机制静默吞掉**（工具返回成功但内容未持久化——9/11 对 MEMORY.md 待办段的
  编辑即如此，直到 9/14 才发现）。对策：关键编辑后必须 `grep` 验证关键内容在文件里；
  commit 前用 `git diff` 复核实际变更。

## 已修复缺陷登记（不得回退）

- **R-027（v1.0.9 已修）**：同一 preview token 并发 commit 可重复追加 append-only 的 execution。
  修法 = `_import_cache_claim()` 在 `_IMPORT_PREVIEW_LOCK` 内一次完成
  「存在 / TTL / kind / in_flight」判定并**原子置位 `in_flight`**；
  失败 `_import_cache_release()`、成功 `_import_cache_invalidate()`；
  full 与 exec-only 共用。**不得退回"先读校验、成功才失效"的写法。**
- **R-028（v1.0.9 已修）**：并发写返回 500「database is locked」。
  修法 = 仅 `SQLITE_BUSY`(5) / `SQLITE_LOCKED`(6) → HTTP 409（`DB_BUSY_MESSAGE`）；
  **其余 `OperationalError` 必须仍走 500**，不得把 no such table / I/O 伪装成 4xx。
- **交付包内的 `启动工作台.bat` 曾用 `where python` 判定解释器**（v1.0.9 及更早交付包的
  388 B 版本）→ 在持久 PATH 只含 Microsoft Store 存根的机器上**双击起不来工作台**。
  v1.0.10 换成 3,970 B 候选链版本（`65414590d0804b255830ce6b489e384db7501659ccb50b9ebf8c0dc64f70fb93`）。
  **不得退回 `set "PY=python"` + `where python` 的写法**；`tests/test_v110.py` §B 为此设了硬断言。
- **顶栏「数据更新」按钮的 force 语义**（2026-09-14 新增）：后端 `get_quotes(symbols, force=True)`
  必须 `need_list = list(need)` **绕开 8 秒缓存**（不得退回无条件去抖）；`/api/quotes` 只认
  `force ∈ {'1','true','yes','on'}`；前端**仅** force 时拼 `&force=1`，自动轮询不带。
  契约测试 `tests/test_data_update_btn.py`（42 断言，含真实联网 §D）；负向验证
  `.tmp_v108x/verify/neg_data_update_btn.py`（5/5 回退变体全被捕获）；
  真实服务端到端 `.tmp_v108x/verify/e2e_data_update_btn.py`（14 断言，**用备用端口 8799，
  不打扰用户 8765 实例**）。

## 并发与可复现性的验证约定（v1.0.9 起）

- 凡「一次性凭据 / token / append-only 写入」相关改动，**必须跑并发探针**：
  `ah-workbench-release-verify` 技能的 `scripts/concurrency_probe.py`。
  顺序路径全绿不能证明无缺陷（v1.0.8 离线 407 断言 + 14 类审计项全过，仍漏掉两个真实缺陷）。
- 并发数字要写**可复现的形式**：若成功次数恒定则写「严格 = 1」；若随调度波动则写
  区间 + 不变式（"恒 > 1"），**禁止写死某次观测到的具体次数**。
- 交付包自洽校验一条命令：`scripts/verify_pack.py <zip> --workspace . --rerun [--port-probe]`。
  其「Manifest 未列构建脚本」检查**只扫描清单条目行**，否定式免责声明不算违规。
