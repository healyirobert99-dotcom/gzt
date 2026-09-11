# trades 冲正（reversal）问题报告与设计方向（v1.0.2）

> **状态：** 问题报告 + 已有方案被否。本轮 **不实施** 任何冲正机制。

## 1. v1.0.2 当前结论

- **不实施任何冲正**：v1.0.1 时期的 design_reversal.md 提出"反向真实 trade"方案。
- **否决理由**：原方案会污染 `realized_pnl`（卖出方向的 realized_pnl 计算依赖
  `cost = 原 avg_cost`；如果原 trade 错录会导致 avg_cost 计算有误，再做"反向
  trade"会按错的 avg_cost 派生出错误的 realized_pnl，使审计无法分辨错误来自
  原 trade 错录还是冲正 trade 本身）。
- **当前 `trades` 表保持严格 append-only**。

## 2. 需求仍存在

人工误录（输错价格 / 数量 / 日期）依旧是合理场景，需要可修正。
但实现必须 **不污染 realized_pnl**，且必须保留"当时的判断"原则。

## 3. 待用户批准后才能重新设计（v1.0.2+ 后续任务）

可能的改进方向（**不承诺，仍待评估**）：

- 方案 A：新增一列 `is_reversal_of INTEGER REFERENCES trades(id)`，在
  `compute_position` 里识别并按冲正语义计算，让 avg_cost 与 realized_pnl
  都回到"如果没有错录"的真实值。这要求 `compute_position` 显式处理回
  溯依赖，复杂度增加。
- 方案 B：增加独立 `trade_corrections` 表（append-only）；原 `trades` 行
  仍 append-only；`compute_position` 读 two-table-view 合并；UI 明示
  "X 号 trade 被 Y 号 correction 修正"。
- 方案 C：保留人工通过 `add_note` 写台账 + 在台账里手动"调平"；不引入
  自动化机制。

## 4. 边界

- 不擅自引入新表 / 新列 / 新约束
- 不修改 `compute_position` 既有口径
- 不修改既有 trades 的 append-only 性质
- 不引入新审批流

任何方向（A / B / C），均需用户先明确批准。本轮收尾关闭 O-001，并按用户
口径（"未实施"）保留为本设计稿的"未决项"。
