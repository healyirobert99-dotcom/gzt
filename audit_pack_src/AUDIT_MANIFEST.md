# 审计交付包文件清单  Manifest

项目: A/H 投研交易工作台 (Individual Stock Workbench)
版本: v1.0.3
打包时间: 2026-09-10 17:40 (Asia/Shanghai)
送审文件数: 15 （仅含送审源码与文档；本清单与构建日志的 SHA 在构建脚本输出与 build_log.txt 中查证）
送审文件总大小: 378839 bytes (370.0 KB)

## 送审文件清单（按路径排序）

| # | 路径 | 大小 (bytes) | SHA-256 |
|---|------|-------------:|---------|
| 01 | `app/server.py` | 76892 | `214ce0c599efcc431b48db28d6fee64c83beb9ffc3dbf3cf2cc91469c250ed54` |
| 02 | `app/static/app.js` | 51924 | `7d3712e59ba35b86715e9f76815be92ddfebcdf193593f0100104c6539745eb5` |
| 03 | `app/static/index.html` | 934 | `fb4c57198af812b4a317f40609a223ed47377598b034f30bb3bb32ac6f39aa8b` |
| 04 | `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| 05 | `data/workbench.db` | 81920 | `cd059157d5c884332adef2cb19ba96682823a2d1bffb041fccd024194039ec9f` |
| 06 | `output/20260910-audit/build_docx_v104.py` | 28322 | `c68b44f76fba4bd5ba1dcee3b518531ed3f435fe6aff08373a6b7f4021fcafa2` |
| 07 | `output/20260910-audit/pipeline-state.yaml` | 2089 | `1c46c4619f843789f49e6014c62e0540d28d1cc17aa4503fe4bb34bcaa7806cb` |
| 08 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.4.docx` | 47939 | `0ae20afe1949ffd800ff965fb1c3a1201d45ddaf713de277ac9bb857f3877838` |
| 09 | `tests/design_research_pool_history.md` | 4260 | `1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864` |
| 10 | `tests/design_reversal.md` | 1978 | `1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a` |
| 11 | `tests/fixtures/sample_seed.py` | 6900 | `57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde` |
| 12 | `tests/test_integration_quote.py` | 8190 | `0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6` |
| 13 | `tests/test_v102.py` | 23028 | `a784e2ed63e3e9a029954db65c76095264ebd99cdc5e4ff9e5401ffddfc54b7a` |
| 14 | `tests/test_v103.py` | 30434 | `877296d9896cb02d04908dc2b013aad31eaa9f585c44f75ac2ebcdefb9756eed` |
| 15 | `启动工作台.bat` | 445 | `8ae2a47b8da27c6ca3d43550fd372c4e6177fa3d0f13b44ab2af664ceada22c0` |

## 范围说明（Inclusion / Exclusion）

### 已包含（送审计范围）

- `app/server.py`、`app/static/*` —— 当前 v1.0.3 应用源码（`__pycache__/` 已剔除）
- `tests/test_v102.py`、`tests/test_v103.py`、`tests/test_integration_quote.py` —— 测试套件
- `tests/design_reversal.md`、`tests/design_research_pool_history.md` —— 设计文档
- `tests/fixtures/sample_seed.py` —— 测试 fixture
- `data/workbench.db` —— 当前生产数据库（v1.0.3 schema）
- `启动工作台.bat` —— 启动脚本
- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.3.docx` —— 当前版本审计文档
- `output/20260910-audit/build_docx_v103.py` —— 审计文档生成器
- `output/20260910-audit/pipeline-state.yaml` —— 审计流水线状态
- `AUDIT_MANIFEST.md` —— 本清单（自身 SHA 在 `build_log.txt` 中查证）
- `build_log.txt` —— 构建日志（ZIP 整体 SHA + 15 个送审文件 SHA + 本清单 SHA）

### 已排除（不送审计范围）

- `app/__pycache__/` —— Python 编译缓存
- `data/backup/workbench-pre-v101-*`、`pre-v102-*`、`pre-v103-*` —— 5 个历史快照
- `archive/v101/`、`archive/v102/` —— 历史版本完整归档（含已废弃 server.py / app.js / test_v101.py 等）
- `output/20260910-audit/stage1/`、`stage2/intermediate/`、`trace/`、`working/` —— 审计过程产物 / 空目录
- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档.docx` —— 原始版（已被 v1.0.3 取代）
- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.1.docx`、`v1.0.2.docx` —— 已 superseded
- `output/20260910-audit/build_docx_v101.py`、`build_docx_v102.py` —— 已 superseded 生成器
- `logs/` —— 空目录
- `.workbuddy/` —— 个人助手记忆，不属于审计范围
- `audit_pack_src/` —— 打包临时目录（打包后保留以便复核，审计方无需关注）
- `个股工作台-v1.0.3-20260910.zip` —— 已存在的旧包（不含审计筛选）

## 审计要点（提请审计方关注）

1. **v1.0.3 新增「动态执行层」**：append-only `execution_reviews` 表 + 4 视图白名单 + 行情刷新不触 execution_view
2. **事务原子性**：`execution_reviews` 与 `decision_ledger` 同一 SQLite 事务，含 `_LEDGER_FAIL_INJECT` 回滚测试
3. **回归测试**：test_v102.py 38 断言 + test_v103.py 35 断言，全部通过
4. **设计文档**：详见 `tests/design_reversal.md` 与 `tests/design_research_pool_history.md`
5. **完整审计文档**：详见内含 `A-H投研交易工作台交付审计文档-v1.0.3.docx`

## 验证方法

审计方可按本清单逐文件比对 SHA-256 哈希值，确认无篡改。

```bash
# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 <file>
# Linux/macOS
sha256sum <file>
```

## 关于本清单自身的完整性

本清单只列 15 个送审文件的 SHA-256，**不含**自身与 `build_log.txt` 的条目，
以避免「清单记录自身 SHA → 内容变化 → SHA 又变化」的循环依赖。

**审计方验证步骤**：
1. 解压 ZIP
2. 对照本清单的 15 项 SHA，比对 ZIP 内对应文件的实际 SHA-256
3. 打开 `build_log.txt` 比对其【1】节 ZIP 整体 SHA 与本 ZIP 的 SHA
4. 打开 `build_log.txt` 比对其【2】节中 15 个文件的 SHA-256
5. 需要校验本清单 / 构建日志自身时，对它们直接计算 SHA-256
