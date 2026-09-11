# 个股工作台 v1.0.5 —— 最终发版交付包

## 项目

- 名称：A/H 投研交易工作台
- 版本：v1.0.5（封板准确性修复）
- 打包时间：2026-09-10 19:06:01（Asia/Shanghai）
- 项目根：`.workbuddy/` 之外的工作目录本体

## v1.0.5 关键修复（vs v1.0.4）

| # | 修复项 | 严重度 |
|---|--------|--------|
| 1 | `add_trade_tx()` 历史补录交易校验：candidate 携带 `trade_date` + `(date ASC, id ASC)` 排序，与 `compute_position()` 完全一致口径 | P0 |
| 2 | `execution_view` 前端改为自由文本 `<input>` + `<datalist>`，4 项仅作常用建议 | FAIL |
| 3 | `execution_date` 默认 = `today()`，不再继承 `prev.execution_date` | FAIL |
| 4 | 新增 test_v105 §E/§F/§G/§H 前端契约静态扫描测试 | - |
| 5 | 全部内部版本号统一 v1.0.5（TARGET_SCHEMA / server_version / argparse / 启动打印 / 前端头 / docx） | P2 |
| 6 | 彻底重写审计 DOCX 生成器（`build_docx_v105.py`），不再复用 v1.0.4 docx 字节 | FAIL |
| 7 | 修正 `PACK_NOTES` / `PACK_MANIFEST` 文件数量措辞 | - |
| 8 | 新增 `tests/test_v105.py`（25 断言：账本零污染 + 前端契约） | - |

## 数据库状态（已就绪）

- `data/workbench.db` schema_version=`1.0.5`
- integrity_check=ok
- FK 检查 0 违规
- 当前为正式空库，可直接录入第一只研究标的

## 测试覆盖

- `tests/test_v102.py` 38/38 PASS
- `tests/test_v103.py` 60/60 PASS（§A-§K）
- `tests/test_v105.py` 25/25 PASS（§A-§H，本轮新增）
- `tests/test_integration_quote.py` 联网集成（运行时可独立执行）
- **总计 123 断言全通过**

## 启动方式

```bash
# Windows 工作台启动
启动工作台.bat

# 命令行
cd app && python server.py
```

## 验收清单（接收方）

1. 解压 ZIP
2. 检查 `PACK_MANIFEST.md` 列出的 SHA-256，逐文件比对
3. 打开 `data/workbench.db`（用任意 SQLite 工具）确认 `schema_version=1.0.5`
4. 跑 `python tests/test_v102.py` + `python tests/test_v103.py` + `python tests/test_v105.py` 确认全过
5. 双击 `启动工作台.bat`，访问首页确认无「示例数据」提示
6. 录入第一笔交易后尝试「补录更早日期的卖出」，确认会被拒绝且 trades 表无残留数据

## 包含 / 排除说明

### ✅ 已包含（送审 / 发版范围）

- `app/server.py`、`app/static/*`：当前 v1.0.5 应用源码（`__pycache__/` 已剔除）
- `tests/test_v102.py`、`tests/test_v103.py`、`tests/test_v105.py`、`tests/test_integration_quote.py`：测试套件
- `tests/design_reversal.md`、`tests/design_research_pool_history.md`：设计文档
- `tests/fixtures/sample_seed.py`：测试 fixture
- `data/workbench.db`：当前生产数据库（v1.0.5 schema）
- `启动工作台.bat`：启动脚本
- `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.5.docx`：审计文档
- `output/20260910-audit/build_docx_v105.py`：审计 docx 生成器（v1.0.5 全新）
- `PACK_NOTES.md`：本说明
- `PACK_MANIFEST.md`：SHA-256 校验清单

### ❌ 已排除（不送审 / 不发版范围）

- `archive/v101/`、`v102/`、`v103/`：历史版本完整归档
- `data/backup/`：迁移前快照（pre-v103 系列）
- `audit_pack_src/`：上一轮审计专用临时源（仅审计方需要）
- `app/__pycache__/`、`tests/__pycache__/`：Python 编译缓存
- `.workbuddy/`：用户助手记忆 + 工具脚本（私有）
- `logs/`：空目录
- `output/20260910-audit/stage1/`、`stage2/`、`trace/`、`working/`：审计过程产物
- 旧版 docx (`v1.0.1`、`v1.0.2`、`v1.0.3`、`v1.0.4`) 及对应生成器 (`build_docx_v101.py`、`v102.py`、`v103.py`、`v104.py`)
- 旧版全量 ZIP (`个股工作台-v1.0.4-20260910.zip`) 和审计交付包 ZIP

## 验证方法

```bash
# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 <file>

# Linux/macOS
sha256sum <file>
```

## 已知保留约束（v1.0.5 继续生效）

- `execution_reviews` append-only，无 UPDATE / DELETE 业务接口
- `execution_reviews` + `decision_ledger` 同 SQLite 事务写入
- 行情刷新（`/api/quote/refresh`）不得修改 `execution_reviews`
- 动态执行层不得反向修改 `trade_plan`
- 动态执行层不得生成真实 `trades`
- 无 execution record 时显示「尚未形成动态执行判断」
- `add_trade_tx` 写入前必须按 `(trade_date ASC, id ASC)` 排序验证累计持仓，负持仓立即拒绝（v1.0.5 新增）
- `execution_date` 只校验 ISO 格式与日期真实性，不再限制未来日期
- `execution_view` 后端仅校验非空，前端用 `<datalist>` 提供 4 个常用建议项
