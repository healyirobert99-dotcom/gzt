# research_pool 字段现状与问题报告（v1.0.2 事实一致版）

> **状态：** 事实一致的问题报告。**本版本未自作主张改造数据结构**。
>
> v1.0.1 时期的初版 design 报告存在事实错误：实际 `research` 表已经包含
> `research_pool` 列（v1.0.1 SCHEMA 第 76 行可见），并非"v1.0.1 schema
> 中没有该列"。本报告以代码现实为准重新梳理，不再执行 v1.0.1 时期
> 的"在 research 表加列 + 回填"伪迁移（那一段在 v1.0.2 中没有意义，
> 会被自动跳过）。

## 1. 现状（v1.0.2 实际代码）

### 1.1 `securities` 表

- 仍保留 `research_pool TEXT DEFAULT ''`（**只读向后兼容字段**）
- 未 DROP COLUMN（SQLite 不支持 DROP COLUMN，且本轮严守"不擅自删字段"边界）
- 写入路径：`create_security` 时从 form `research.research_pool` 同步
  写入此列；`update_security` **不**改它（避免静默覆盖）

### 1.2 `research` 表

- 已经包含 `research_pool TEXT DEFAULT ''`（SCHEMA 显式定义，详见
  server.py 的 `SCHEMA` 字符串）。
- `update_research` 写入新版本时把 form 中 `research_pool` 同步到新
  版本行；旧版本行原样保留 → 实现"研究池随版本变化"。
- 默认 `change_note` 在历史版本可为空字符串（并不要求强制）。

### 1.3 实际行为（不再有 v1.0.1 错误描述的"覆盖"问题）

- 当前研究的 `research_pool` 由 `research` 表最新版 `version DESC` 取到
  （通过 `current_row(conn, 'research', sid)`，server.py 的 `enrich`）。
- `securities.research_pool` 仅在创建时初始化一次，**后续不修改**，
  因此不再发生"修改 research_pool 会覆盖历史分类"。
- 复盘"美图当时属于哪个研究池"时可以查询 `research_history` 数组中
  任意时间点的 `research_pool` 字段。

## 2. 与 v1.0.1 设计稿的差异说明

| 项 | v1.0.1 design 描述 | 实际代码（v1.0.2） |
|---|---|---|
| `research` 表是否已有 research_pool | "未加列，需要脚本加"（错误） | **已存在**（SCHEMA 直接定义） |
| `securities.research_pool` 是否可改 | "可 UPDATE" | **首次创建写入后不再改**（`update_security` 不动它） |
| 是否需要回填 | "回填最新版本" | **不需要**（结构本身已具备版本化） |
| 是否需要 UI 强制填 | "强制" | **不强制**（写入空字符串合法） |

## 3. 仍存在的实际限制（不是 bug，但需用户知晓）

1. **历史分类的语义边界**：迁移前（v1.0.1 之前）修改过 `securities.research_pool`
   的用户：当时确实发生过"覆盖"。本轮只在 `securities` 字段层面做"只读"
   处理，并未回填已经覆盖的历史。已被覆盖的旧值无法追溯——这是数据结构
   升级的已知代价。
2. **写入规则不对称**：
   - 标的创建时，`securities.research_pool` 和 `research.research_pool`
     会被同步写入 → 两处一致；
   - 研究更新（`update_research`）时，`research.research_pool` 走新版本，
     `securities.research_pool` 不变 → 两处分歧；
   这意味着 `securities.research_pool` 在用户多次更新研究后**滞后**于
   `research.research_pool`。前端首页 / 列表 / 详情页应统一读
   `sec.research.research_pool` 而非 `sec.research_pool`。
3. **代码层面的小统一**：`rowHtml` / `cardHtml` 中读 `(s.research && s.research.research_pool)`
   已是正确路径。

## 4. 风险登记（已迁移到审计文档）

| 风险 | 状态 | 缓解 |
|---|---|---|
| 用户在 UI 看不到 `securities.research_pool` 字段编辑入口 | **已知设计** | 这是有意为之；UI 不暴露即不会误改 |
| 数据迁移前覆盖历史 | **不可追溯** | 由用户自行评估是否需要手动重录 |
| 旧 audit 文档说"无 research_pool 列" | **本文档已纠正** | 旧文档需要以新版覆盖 |

## 5. 后续路径（不在本轮范围）

- 若用户日后希望"securities.research_pool 字段彻底废弃"：需要在
  SQLite ≥ 3.35（支持 DROP COLUMN）下明确单独立项，本轮不擅自 DROP。
- 若希望"研究更新时强制要求 research_pool 非空"：这是 UI 字段强化
  需求，需用户单独批准。
