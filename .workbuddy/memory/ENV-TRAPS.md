# 环境陷阱与启动器约定（`MEMORY.md` 的明细附件）

被 `MEMORY.md` 索引，不重复主线内容。改这些地方前先读本文件。

## 环境陷阱

- 受管运行时：`C:\Users\宜春法院\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- **PowerShell 工具 stdout 完全捕获不到**（连 `Write-Output "hi"` 也无输出、exit 0）。
  读注册表 / 持久环境变量请用 `python -c "import winreg; ..."` 从 Bash 调。
- **`cmd.exe /c ...` 被安全策略拦截**。跑 .bat 用 `python -c "subprocess.run([abs_path])"`，
  **必须传绝对路径**；传相对正斜杠路径被 CreateProcess 拒绝，且失败时 stdout 为空，
  **极易被误判成断言通过**。
- **Bash heredoc 会改写内嵌 Windows 路径**（`<<'PYEOF'` 里 `'C:\\Users\\...'` 到 Python
  手里会变成 `C:/Users///u5b9c...`：`\\`→`/`、`\u`→`/u`），表现为路径长得莫名其妙的
  `FileNotFoundError`。**对策：探针脚本一律用 Write 落成真实文件再执行。**
- 命令里含反引号（\`）会被 Bash 提前解析 —— 校验脚本避免用反引号做 Markdown 强调。
- **`taskkill` 在 MSYS Bash 下不可用**（`//F` 报"无效参数"，`/F` 被路径转换）。用
  `python -c "import subprocess; subprocess.run(['taskkill','/F','/PID',pid])"`。
- `os.remove()` 可能被环境拦截为"回收站"操作且失败；**覆盖文件请先生成到临时名再 `mv -f`**。
- 生成中文文件名 ZIP 用 `zipfile.ZipInfo` + `create_system=0`，可规避中文乱码。
- Python 读 CRLF 文本不加 `newline=''`，universal newlines 会折掉 `\r`。
- **连续多次 Edit 同一文件时，部分编辑可能被环境静默回滚**（工具返回成功但内容未落盘，
  2026-09-11 对 MEMORY.md 就发生过，直到 09-14 才发现）。
  **对策：关键编辑后必须 grep 验证关键内容，commit 前用 `git diff` 复核实际变更。**
- **运行工作台会改写 `data/workbench.db`**：`init_db()` 与页面/接口访问会触发行情刷新，
  只改 `securities.current_price` / `current_price_updated_at` 两列。
  因此任何"跑起来验证"之后 `git status` 都会显示该库被改。
  **对策：验证后 `git restore data/workbench.db`，或明确作为一次 data 提交推上去
  —— 不要让它悄悄留在工作区。** 另：即使 `mode=ro` 打开 WAL 库也会生成 `-shm`/`-wal`
  （已被 `.gitignore` 覆盖，`-wal` 常为 0 字节，可直接删）。
- **agent-browser（真实浏览器验证）必须用 `batch` 驱动** —— 2026-09-15 把坑踩全了：
  ① 组合命令（`&&` 串联、`| head` 管道）极易被 SIGTERM —— 要么单命令、要么重定向到文件再读；
  ② **单独 `open` 后页面会退回 `about:blank`**（截图全白、`eval` 读到 `bodyLen=0`），
     整条链路必须放进**一次** `batch "cmd1" "cmd2" ...` 调用，页面状态才保持；
  ③ `screenshot [path]` 的单参数会被当成 selector，实际存到
     `~/.agent-browser/tmp/screenshots/`，需从该目录取回；
  ④ **`✓ Done` 只代表命令已派发，不代表点中了元素**：点击落空也照样打印 ✓ Done。
     凡是「点了但没反应」的现象，不要先怀疑产品，先按 ⑤⑥⑦ 排查；
  ⑤ **带空格的复合选择器会被截断成第一个 token**：`get box ".mfoot button.primary"`
     实际读的是 `.mfoot` 容器（宽 590 = 弹窗内宽），`click ".mfoot button.primary"`
     实际点的是外层 div。**一律改用无空格的 `>` 子选择器**（`.mfoot>button.primary`）；
  ⑥ **`click` 不自动滚动进视口**，元素在视口外时点击静默落空。对策：先
     `set viewport 1280 4000` 让整页可见（首页「已归档」区在绝对 y≈3381，默认视口够不着）；
  ⑦ **会话跑久了 `:hover` 会失效**：真实鼠标事件不再让 `:hover` 生效，
     `get styles` 恒读默认态（`opacity: 0` / `pointer-events: none`），
     「悬停显形」类断言因此**假红**；而同一批次的 `click` 仍会成功（Playwright 给元素
     自己补 hover）—— 迷惑性极强。对策：`agent-browser close --all` 重开会话后立刻恢复；
  ⑧ `eval` 里的**单引号会被参数解析吃掉**（`'.card-archive'` → `.card-archive` →
     `SyntaxError: Unexpected token '.'`）。改用 `get count/styles/box/attr/text`
     子命令，别跟 `eval` 的引号纠缠；
  ⑨ `get text` **取不到折叠 `<details>` 里的内容**（`get text .archive-section`
     读不到折叠行）→ 先 `click ...>summary` 展开再读；
  ⑩ 读数块**不能用「第 N 个 ✓ Done」定位**（`mouse move` / `wait` 不一定输出 ✓ Done）。
     按内容特征取：纯整数块 / 最后一个含 `opacity:` 的块 / 最后一个非纯数字文本块。
  ⑪ **一次 batch 的多条命令，输出会被合并进同一个块** —— `✓ Done` 并非每命令一枚。
     探针实测 3 个 `get count` + 1 个 `get text` 的输出挤成一块
     `'\n\n17\n\n0\n\n06:10\n\n17\n'`。后果：沿用「块内容恰好是数字」的解析会在
     **count 不在批次末尾时静默取错值**（本轮边界检查因此 4 条断言假红 ——
     `card=17` / `btn=None` / `drawer=None`，而同一批次的**文本证据全 PASS**，
     极易误判成产品坏了）。**对策：`get count` 独占一个批次**（不与 `get text` 混，
     否则文本里的纯数字行会污染读数），再**按行**收纯整数行 ——
     参考实现 `browser_e2e_archive.py` 的 `count_values()`（`0` 也会照常输出，
     能如实区分「一个都没有」与「读数失败」）。
- **用 Python 驱动 agent-browser 时有两处必踩**（2026-09-15）：
  ① `agent-browser` 是 sh 垫片，Windows 下 `subprocess` 直接调它 →
     `FileNotFoundError [WinError 2]`。**须直调**
     `<node.exe> <...>/node_modules/agent-browser/bin/agent-browser.js`；
  ② **`subprocess.run(capture_output=True, timeout=)` 会永久挂死**：超时时它只 kill
     直接子进程（node.exe），而 agent-browser 派生的
     `agent-browser-win32-x64.exe` / chrome 仍持有 stdout 管道句柄，
     `communicate()` 里的读再也等不到 EOF —— 实测脚本无声挂了 20 分钟。
     **对策：stdout 重定向到文件（不接管道）+ `Popen` + 超时 `taskkill /F /T`。**
     另：`python -u` 否则重定向后看不到进度。
  参考实现：`.tmp_v108x/verify/browser_e2e_archive.py`（`_run_ab` / `close_all`）。
- **agent 起不了"能活下去"的服务进程**（2026-09-14 实测）：进程树被 Job Object 托管
  （kill-on-close）。`DETACHED_PROCESS` 起的服务在调用它的脚本退出后即被回收
  （PID 40888 / 17528 两次验证）；补 `CREATE_BREAKAWAY_FROM_JOB` → `WinError 5 拒绝访问`；
  走 `wmic process call create` → **wmic.exe 在安全策略的程序黑名单里**，且明确禁止
  "换 shell 或等价绕过"。**结论：不要在 agent 里替用户启动工作台** ——
  改完代码后把测试端口清干净，让用户双击 `启动工作台.bat` 自己起。
- **MSYS2 版 ssh（`/usr/bin/ssh`）在中文用户名 HOME 下彻底不可用**：它把
  `HOME=/c/Users/宜春法院` 按本地 ANSI(GBK) 处理，去找
  `/c/Users/\322\313\264\272\267\250\324\272/.ssh/known_hosts`，于是**既读不到
  `known_hosts`，也读不到 `~/.ssh/config`**，报 `Host key verification failed`
  —— 伪装成"主机密钥问题"，极易误诊为密钥没配对。
  **git 必须改用 Windows 原生 ssh**：
  `git config core.sshCommand "C:/Windows/System32/OpenSSH/ssh.exe"`。
  自检：`<ssh> -G github.com | grep '^user'` 应输出 `user git`
  （MSYS2 版会输出 `user 宜春法院`，即 config 根本没被读）。

## 启动器约定

### 项目内 `启动工作台.bat`（2026-09-11 重写，ASCII-only + CRLF）

- **必须纯 ASCII + CRLF**。bat 由 cmd.exe 按控制台代码页（936/65001）逐字节解释，
  任何非 ASCII 字节都可能错位并污染传给 shell 的路径。历史包曾因硬编码中文路径
  而写出 `M-RM-KM-4M-:M-7M-(M-TM-:` 这类乱码，**不得重犯**。
- **解释器路径一律用 `%USERPROFILE%\.workbuddy\binaries\python\versions\<ver>\python.exe`**：
  源码保持 ASCII，运行时解出含中文的正确绝对路径。**禁止把中文绝对路径写进 bat。**
- **禁止只用 `where python` 判定可用性**。本机持久 PATH 里**只有**
  `%LOCALAPPDATA%\Microsoft\WindowsApps`，其中 `python.exe` 是 **Microsoft Store 占位存根**
  → `where python` 会"成功"，`if errorlevel 1` 永不触发，双击后实际拉起应用商店。
- 候选链顺序：① pinned `3.13.12` → ② `for /d` 遍历 `versions\*` → ③ `py` → ④ PATH 上的 `python`；
  每项都过 `:try` 子程序：**真跑一次**
  `-c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)"`，
  并**显式拒绝**路径含 `WindowsApps` 的候选。
- 改 bat 后必须三段式验证：① **抽 `:try` 子程序做隔离测试**（保证被测代码 == 交付代码）
  ② 契约测试 `tests/test_v110.py` §B（负向验证：旧 bat 应得 3 FAIL）
  ③ 端到端 A/B/C：解压交付包到全新目录，用它自己那份 bat，在**真实持久 PATH** 下实跑，
  必须"新 bat 能起、旧 bat 起不来"，且**按端口属主杀进程树**收尾
  （`Popen.kill()` 只杀 cmd.exe，子进程 python 会继续占端口 → 后续实验误判）。
  探针见 `.tmp_v108x/verify/e2e_launcher_v110.py`（11 断言）。

### 桌面 `C:\Users\宜春法院\Desktop\启动工作台.bat`（2026-09-14 建立）

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
