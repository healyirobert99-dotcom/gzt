# 个股工作台 v1.0.8 —— 交付说明（导入完整性封板修复）

## 项目

- 名称：A/H 投研交易工作台
- 版本：v1.0.8（导入完整性封板修复）
- 基线：v1.0.7 → v1.0.8
- 性质：**仅修复** v1.0.7 独立代码审计发现的导入完整性与交付一致性问题
- 边界：不新增业务模块、不新增数据库表 / 列、不改动写入函数 SQL、不改变研究口径

## 一、本轮修复清单（对应审计 9 条）

| # | 审计发现 | v1.0.8 处理 | 严重度 |
|---|---|---|---|
| 1 | base64(JSON) token 不能证明 preview 实际发生过 | 改为服务端 `secrets.token_urlsafe(32)` 随机 token + 服务端 preview cache + 5 分钟 TTL + 一次性失效；代码与文档不再称 base64(JSON) 为"预览 token" | P0 |
| 2 | 状态确认来自导入 JSON | `status_change_confirmed` 一律忽略；preview 初次 `change_confirmed` 恒为 `false`；确认只来自 commit 请求的 `confirmed_status_changes` | P0 |
| 3 | commit 前未校验 preview snapshot | commit 前重读数据库逐项对照 snapshot；status / research version / trade_plan version 变化或原不存在证券已出现 → 拒绝并提示"工作台数据自预览后已发生变化，请重新解析预览。" | P0 |
| 4 | 同一批可重复出现同一证券 | `_parse_import_full()` 在 preview 前检查 `securities[]` 内 (exchange, code) 唯一，重复整体拒绝 | P0 |
| 5 | 研究数组结构未严格校验 | `core_validations` / `wall_conditions` 按 ah-workbench-import v1.0 **固定 Schema** 严格校验，不猜测、不自动转换 | P0 |
| 6 | 名称不一致仅在返回 JSON 中暗藏 | preview 返回 `name_mismatch` + `name_mismatch_notice`，前端页面明显展示；本轮不自动改 name | FAIL |
| 7 | 「载入示例」可一键载入真实标的的虚构数据 | 删除「载入示例」按钮；样例 JSON 仅保留明显虚构标的并标注"请勿写入正式库" | FAIL |
| 8 | 缺少导入完整性回归测试 | 新增 `tests/test_v108.py`（129 断言）+ HTTP 端到端冒烟脚本，覆盖审计要求的 14 类场景 | - |
| 9 | 交付包无法复现声称的数字、Manifest 与 ZIP 不一致 | 重新实跑全套测试、重建 ZIP 与 Manifest、重算 SHA-256、README 修正默认地址 | P0 |

## 二、两段式导入的真实机制

```
POST /api/import/preview
  → 解析 + 对比生成 diff（不写库）
  → 生成随机 token，服务端保存 token → {validated, snapshot, expires_at}
  → 返回 {token, token_ttl_seconds: 300, securities: [...], warnings: [...]}

POST /api/import/commit
  ← {token, confirmed_status_changes: [...]}
  → token 必须命中服务端 cache（未预览 / 已过期 / 已使用 → 400）
  → 漂移检测：重读数据库对照 snapshot（漂移 → 400，要求重新预览）
  → 单一 SQLite 事务写入
  → 成功后 token 立即失效（一次性）
```

snapshot 记录涉及证券的：`security_id`、当前 `status`、`research` 当前 `version`、
`trade_plan` 当前 `version`、`execution_latest.id`。

## 三、研究数组固定 Schema（v1.0.8 起为 ah-workbench-import v1.0 正式定义）

```jsonc
"core_validations": [
  { "content": "非空文本", "status": "跟踪中 | 已验证 | 已恶化" }
],
"wall_conditions": [
  { "content": "非空文本", "triggered": true }
]
```

明确拒绝：字符串 / 数字 / null / 缺 content 的对象、非法 `status`、非严格布尔的 `triggered`
（`"false"` 字符串与 `0/1` 数字均拒绝）。

## 四、测试结果（本轮实际运行，可复现）

| 套件 | 断言数 | 结果 | 依赖外网 |
|---|---:|---|---|
| `tests/test_v102.py` | 38 | PASS | 否 |
| `tests/test_v103.py` | 60 | PASS | 否 |
| `tests/test_v105.py` | 25 | PASS | 否 |
| `tests/test_v106.py` | 28 | PASS | 否 |
| `tests/test_v107.py` | 127 | PASS | 否 |
| `tests/test_v108.py` | 129 | PASS | 否 |
| **离线套件小计** | **407** | **PASS** | — |
| `tests/test_integration_quote.py` | 14 | PASS | 是（真实行情接口） |
| `output/20260910-audit/smoke_v108_http.py` | 14 | PASS | 否（本机临时端口） |

> 复现命令：
> ```bash
> python tests/test_v102.py && python tests/test_v103.py && python tests/test_v105.py \
>   && python tests/test_v106.py && python tests/test_v107.py && python tests/test_v108.py
> python tests/test_integration_quote.py        # 需联网
> python output/20260910-audit/smoke_v108_http.py
> ```

### 与 v1.0.7 文档声称的差异（必须说明）

v1.0.7 的 PACK_NOTES 声称"合计 279 断言全通过"，该数字**无法复现**：
交付 ZIP 内缺少 `tests/test_integration_quote.py`，导致 `test_v102.py` 中的
"集成测试文件存在"断言在解压后必然失败；且当时尚无 v1.0.8 套件。
本版不再沿用任何未经实跑的数字。

### 既有测试未回退

`test_v107.py` 原有 127 断言全部保留并通过。其中 3 条是"当前版本契约"硬断言，
随本轮合法升级同步更新，其余 124 条业务语义断言未做任何修改：

| 断言 | v1.0.7 期望 | v1.0.8 期望 |
|---|---|---|
| §P#1 | `TARGET_SCHEMA_VERSION = '1.0.7'` | `TARGET_SCHEMA_VERSION = '1.0.8'` |
| §P#2 | `server_version = 'Workbench/1.0.7'` | `server_version = 'Workbench/1.0.8'` |
| §P#6 | `def commit_import_full(token):` | `def commit_import_full(token, confirmed_status_changes=None):` |

## 五、交付包一致性修复

| 项 | v1.0.7 问题 | v1.0.8 处理 |
|---|---|---|
| 集成测试文件 | ZIP 缺 `test_integration_quote.py`，`test_v102.py` 解压后失败 | 已纳入 ZIP |
| 测试数字 | 声称 279，不可复现 | 写入实跑真实数字 |
| Manifest 数量 | 列 14 项，ZIP 实际 17 项 | 逐项与 ZIP 实际内容一一对应 |
| Manifest 幽灵条目 | 列出 ZIP 中不存在的 build 脚本 | 不再列出任何 ZIP 中不存在的脚本 |
| README 地址 | 写 `http://127.0.0.1:8000`，与默认端口不符 | 改为 `http://127.0.0.1:8765` |
| SHA-256 | 基于不一致的文件集计算 | 对 ZIP 内全部文件重新计算 |
| 启动脚本 | 硬编码本机绝对路径且中文用户名乱码 | 改为 PATH 查找 `python`，去除非可移植路径 |
| 生产数据库 | `schema_version` 仍为 `1.0.7` | 已迁移至 `1.0.8` |

## 六、数据库状态（已就绪）

- `data/workbench.db`：`schema_version = '1.0.8'`
- `PRAGMA integrity_check` = ok
- `PRAGMA foreign_key_check` = 0 违规
- `securities` 行数 = 0（正式空库，可直接录入第一只研究标的）
- 本轮**未新增表 / 列**

## 七、启动方式

```bash
# Windows
启动工作台.bat

# 命令行
python app/server.py
# 默认地址 http://127.0.0.1:8765
```

## 八、验收清单（接收方）

1. 解压 ZIP（**含 `tests/test_integration_quote.py`**）
2. 按 `PACK_MANIFEST-v1.0.8.md` 逐文件比对 SHA-256
3. 运行 §四 的复现命令，确认离线套件 407 断言全过
4. 检查 `data/workbench.db` 的 `schema_version = '1.0.8'`
5. 启动工作台，进入「导入与更新」：
   - 确认页面**没有**「载入示例」按钮
   - 粘贴 JSON 直接点提交 → 应被拒绝（未预览）
   - 预览后不勾选状态变化直接提交 → 应被拒绝
   - 预览后手工改动库内 status 再提交 → 应提示"请重新解析预览"
6. 确认 `README.txt` 默认地址为 `http://127.0.0.1:8765`

## 九、继续生效的既有约束

- `execution_reviews` append-only，无 UPDATE / DELETE 业务接口
- `execution_reviews` + `decision_ledger` 同 SQLite 事务写入
- 行情刷新（`/api/quote/refresh`）不得修改 `execution_reviews`
- 动态执行层不得反向修改 `trade_plan`
- 动态执行层不得生成真实 `trades`
- 导入层不得触碰 `trades`；导入失败整批 ROLLBACK
- `add_trade_tx` 写入前按 `(trade_date ASC, id ASC)` 排序验证累计持仓
- 证券唯一身份只认 `exchange + code`，不用 name 匹配

## 十、本轮新增风险

- **R-026**：preview cache 为进程内存态，服务重启后未使用的 token 全部失效，
  用户需重新执行「解析并预览」。这是"服务端持有预览状态"的必然代价，属预期行为。
