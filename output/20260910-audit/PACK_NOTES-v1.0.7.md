# 个股工作台 v1.0.7 — PACK_NOTES（导入与更新封板版）

版本号:Workbench **v1.0.7**
封板日期:2026-09-11
封板范围:新增「导入与更新」模块（不改变数据库结构、不改变投资口径）

---

## 1. 本次封板内容（与 v1.0.6 对比）

v1.0.7 在 **v1.0.6 全部功能冻结** 的基础上,新增 **导入与更新模块**:

| 模块 | v1.0.6 | v1.0.7 |
|---|---|---|
| 标的库 / 研究(版本化) / 静态计划(版本化) | ✅ | ✅ 不变 |
| 动态执行层（execution_reviews append-only）| ✅ | ✅ 不变 |
| 多标的行情刷新一致性（per-symbol `is_stale`）| ✅ | ✅ 不变 |
| 数据库迁移与数据保护 | ✅ | ✅ 不变 |
| **导入与更新（粘贴 → 预览 → 确认 → 写入）**| ❌ | ✅ 新增 |

---

## 2. 新增导入与更新模块的功能边界

### 2.1 只新增交互层,不动数据结构

| 项目 | 状态 |
|---|---|
| 新增表 / 新增字段 / 新增索引 | **无** |
| 复用现有 `create_security_tx` | ✅ |
| 复用现有 `update_research_tx` | ✅ |
| 复用现有 `update_plan_tx` | ✅ |
| 复用现有 `add_execution_tx` | ✅ |
| 复用现有 `ledger_add` | ✅ |
| 复用现有 decision_ledger 事件类型 | ✅ |

### 2.2 严格两段式

- **第一步:粘贴 + 预览(不触库)**
  用户粘贴 → POST `/api/import/preview` → 返回 `token` + 差异报告
- **第二步:确认 + 提交(走事务)**
  用户点击"确认导入" → POST `/api/import/commit` 携带 `token` → 一次性事务化写入

**禁止"粘贴后直接写库"** —— 已在 server.py 中通过 `IMPORT_PREVIEW_CACHE` 强制 token 必须先经过 preview。

### 2.3 证券识别规则

- **唯一身份只使用 exchange + code**,禁止依靠公司名称判断。
- 已存在:`create_security_tx` 拒绝创建;走差异更新。
- 不存在:按 `create_security_tx` 一致方式新建,且 **不覆盖任何已有数据**。

### 2.4 版本控制规则(append-only)

| 类型 | 重复内容 | 有变化 |
|---|---|---|
| research | 显示"研究无变化",**不生成版本** | 显示具体变化字段,确认后新增版本;旧版本永久保留 |
| trade_plan | 显示"静态交易计划无变化",**不生成版本** | 预览差异,确认后新增版本;禁止因动态执行而新建 plan 版本 |
| execution | 每次均 append-only,同事务写入 ledger | 永远 append-only,不修改上一条 |
| status | 当前值与导入值相同 → 不动作 | **必须在预览中单独确认**;确认后写 ledger |
| trades | 导入过程中**不得产生任何 trades 行** | 严格隔离:导入路径不调用 `add_trade_tx` |

### 2.5 状态变化确认

导入数据若包含 status 且与当前不同:
- 不得自动改变;
- 预览中必须显示"当前状态 → 导入状态";
- 前端要求用户**显式勾选**"我已知晓状态变化";
- 没有勾选时,提交阶段被拒绝(`status_change_confirmed=false`);
- 状态变化同事务写入 ledger。

### 2.6 事务原子化

整批导入统辖在 **一个 SQLite 事务** 中:
- 任一只标的失败 → 整批 ROLLBACK;
- 已用 `_LEDGER_FAIL_INJECT` 测试钩子验证(§K);
- 任何不完整状态都会导致整个 DB 状态保持原样。

### 2.7 快速更新动态执行入口的硬边界

- 只接受 format = `ah-workbench-execution`;
- 不修改 research、trade_plan、securities 任何字段;
- 找不到证券时 **明确拒绝** 并提示"标的尚未进入工作台,请先使用导入研究结果";
- 写入后同事务追加 1 条 ledger 事件;
- 多次调用 → 多次 append,执行历史完整可追溯。

---

## 3. 新增 API

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/import/preview` | 解析导入 JSON,返回差异预览 + token(**不触库**) |
| POST | `/api/import/commit` | 携带 token,事务化正式写入 |
| POST | `/api/import/execution/preview` | 解析 execution-only JSON,返回预览 + token |
| POST | `/api/import/execution/commit` | 携带 token,事务化新增 1 条 execution review |

所有 4 个端点共用同一份 `IMPORT_PREVIEW_CACHE`(内存中,token 5 分钟有效)。

---

## 4. 数据结构是否发生变化?

**没有**。本轮严格遵守 spec 第一段:不为了导入功能重新设计数据库或投资规则。

唯一发生的 DB 写入是 `schema_version: '1.0.6' → '1.0.7'` 这一条 settings 行的值变更。

---

## 5. 测试结果

| 测试套件 | 断言数 | 结果 |
|---|---|---|
| tests/test_v102.py | 38 | ✅ PASS |
| tests/test_v103.py | 60 | ✅ PASS |
| tests/test_v105.py | 25 | ✅ PASS |
| tests/test_v106.py | 30 | ✅ PASS |
| tests/test_v107.py | **126** | ✅ PASS(15 节全覆盖,见下表) |
| **合计** | **279** | ✅ **PASS** |

### tests/test_v107.py 的 15 节用例

| 节 | 测试项 | spec 序号 |
|---|---|---|
| §A | 单只新证券完整导入 | 1 |
| §B | 多只批量导入 | 2 |
| §C | 已有证券正确识别 | 3 |
| §D | research 完全相同时不生成重复版本 | 4 |
| §E | research 变化时生成新版本,旧版本保留 | 5 |
| §F | trade_plan 无变化不生成版本 | 6 |
| §G | trade_plan 有变化生成新版本 | 7 |
| §H | execution 每次均 append-only | 8 |
| §I | 快速 execution 不修改 research / trade_plan | 9 |
| §J | 快速 execution 找不到证券时拒绝 | 10 |
| §K | 状态变化必须进入预览,不得自动覆盖 | 11 |
| §L | 非法 JSON 不写库 | 12 |
| §M | 导入失败不得污染既有数据 | 13 |
| §N | execution + ledger 原子性保持 | 14 |
| §O | 导入过程中真实 trades 不得发生任何变化 | 15 |

---

## 6. 操作截图(基于实际工作台 HTML / JS 渲染的视觉示意)

agent-browser 在本环境受网络限制无法启动 Chromium 截图;已使用 SVG 绘制两张视觉示意,内容来源于 `app/static/index.html` 与 `app/static/app.js` 的真实样式和文案:

| 截图 | 文件 | 描述 |
|---|---|---|
| screenshot-1-full-import-done.svg | `output/20260910-audit/screenshots/` | 「导入研究结果」完整流程的"完成页":成功处理 2 只、新建 2 只、新增研究版本 2、新增静态计划版本 2、新增动态执行判断 1、无变化跳过 0 |
| screenshot-2-execution-update-preview.svg | `output/20260910-audit/screenshots/` | 「快速更新动态执行」流程的"预览页":仅输入 identity + execution,预览新增 1 条 execution review |

---

## 7. 示例 JSON

| 文件 | 用途 |
|---|---|
| samples/json/example-full-import.json | format=ah-workbench-import;2 只证券完整导入 |
| samples/json/example-execution-update.json | format=ah-workbench-execution;仅快速更新动态执行 |

两份示例均已通过 `preview_import_full` / `commit_import_full` / `preview_import_execution` / `commit_import_execution` 端到端验证。

---

## 8. 数据库状态(封板后)

| 表 | 行数 | 说明 |
|---|---|---|
| securities | 既有数据 | 未被 import 模块改动 |
| research | 既有数据 + 测试新增 | 全部为版本化追加 |
| trade_plans | 既有数据 + 测试新增 | 全部为版本化追加 |
| execution_reviews | 既有数据 + 测试新增 | append-only |
| decision_ledger | 既有数据 + import 触发的事件 | 全部新增事件均为 import 模块追加 |
| trades | **0 新增** | import 路径严格禁止生成 trades |
| settings.schema_version | '1.0.7' | init_db 自动升级 |

PRAGMA foreign_key_check = 0 violations;PRAGMA integrity_check = ok。

---

## 9. 封板原则(不变)

> **未经用户明确批准,不得新增规则、扩展任务或改变研究口径。**

本次 v1.0.7 严格按 spec 实施:
- 没有新增任何模块(只新增导入交互层)
- 没有修改既有数据库结构
- 没有修改既有业务函数(create_security_tx / update_research_tx / update_plan_tx / add_execution_tx / ledger_add 全部 0 行改动)
- 没有自动联网、自动 LLM 解析、自动补全投资数据

---

## 10. 文件清单(本次新增/修改)

```
新增:
  tests/test_v107.py                                        新增导入测试(15 节 / 126 断言)
  samples/json/example-full-import.json                     完整导入示例 JSON
  samples/json/example-execution-update.json                快速执行示例 JSON
  output/20260910-audit/screenshots/screenshot-1-full-import-done.svg
  output/20260910-audit/screenshots/screenshot-2-execution-update-preview.svg
  output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.7.docx
  output/20260910-audit/build_docx_v107.py                  docx 生成脚本
  .workbuddy/tools/build_v107_screenshots.py                SVG 截图生成脚本

修改:
  app/server.py                                             升级 TARGET_SCHEMA_VERSION=1.0.7;新增 IMPORT_FORMAT_* 常量、_import_*_payload、
                                                              preview_import_full/commit_import_full/preview_import_execution/commit_import_execution、
                                                              4 个新 API 路由、_run_in_transaction 加 functools.wraps
  app/static/index.html                                     左侧导航新增「导入与更新」入口
  app/static/app.js                                         升级头注释到 v1.0.7;新增 #/import、#/import/research、#/import/execution 路由;
                                                              新增 renderImportLanding / renderImportResearch / renderImportExecution 等函数
  tests/test_v102.py                                        schema_version 断言改为动态读取 TARGET_SCHEMA_VERSION
```

业务函数(create_security_tx / update_research_tx / update_plan_tx / add_execution_tx / ledger_add / get_detail 等)**0 行改动**。