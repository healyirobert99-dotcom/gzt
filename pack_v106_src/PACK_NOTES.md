# v1.0.6 发版交付说明

## 版本
- **v1.0.6**（行情一致性修复）
- 基线：v1.0.5
- 打包时间：2026-09-10 19:51:48 (Asia/Shanghai)

## 本轮性质
用户明确批准的"v1.0.6 行情一致性修复"，共 9 条 spec：

1. get_quotes 区分本次成功与缺失的 symbol（symbol 粒度 partial_failure）
2. 成功证券正常更新 cache / 写 securities / 更新行情时间
3. 缺失证券保留旧 cache + 标记 is_stale=true + 旧 market_time
4. requested 非空且 fetched 为空 → 必须识别为本次行情失败（即使 fetch 未抛异常）
5. 部分成功返回明确"部分行情未更新"状态 + 列出缺失 symbol
6. 前端卡片对 stale 行情明确显示"上次成功行情 · 本次刷新未成功"
7. attention() 不得把 is_stale=true 缓存价格视作本次新变化（保留 status / wall / core_validation）
8. 新增 3 组回归测试（§A 部分成功 / §B 全部失败 / §C stale 不进 attention）
9. 保持 v1.0.5 已通过的 123 断言继续通过

## 边界（不允许越界）
- 不新增第二行情源
- 不增加技术指标（MA / EMA / MACD / RSI / KDJ / 布林带 / 自动支撑位等）
- 不修改交易规则 / 状态 / 自动判断
- 不新增字段 / 端点 / 缓存层
- 不得"顺带加入"未在 spec 中批准的内容

## 测试结果（153 断言全过）
- tests/test_v102.py：38/38 PASS
- tests/test_v103.py：60/60 PASS
- tests/test_v105.py：25/25 PASS
- tests/test_v106.py：30/30 PASS（§A 11 + §B 8 + §C 3 + §D 8）
- 生产 DB：schema_version=1.0.6, integrity_check=ok, FK 0 违规

## 验证方法（解压后请按此顺序检查）
1. 解压 ZIP 到任意目录
2. 打开 PACK_MANIFEST.md，对每个文件用 Get-FileHash / sha256sum 验证 SHA-256
3. 打开 docs 文件：A-H投研交易工作台交付审计文档-v1.0.6.docx
4. 启动应用：`启动工作台.bat`（或 `python app/server.py`）
5. 浏览器访问 http://localhost:8000

## 文件清单
共 17 个文件（清单 16 项 + PACK_MANIFEST.md 自身）：
- 源码：`app/server.py`、`app/static/{app.js,index.html,style.css}`
- 测试：`tests/test_v102.py`、`tests/test_v103.py`、`tests/test_v105.py`、`tests/test_v106.py`、`tests/test_integration_quote.py`
- 设计文档：`tests/design_reversal.md`、`tests/design_research_pool_history.md`
- Fixture：`tests/fixtures/sample_seed.py`
- 数据库：`data/workbench.db`（生产 DB，schema_version=1.0.6）
- 启动：`启动工作台.bat`
- 审计文档：`output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.6.docx`
- 生成器：`output/20260910-audit/build_docx_v106.py`
- 清单：`PACK_MANIFEST.md`（自身 SHA 由构建脚本生成时打印）

## 与 v1.0.5 的差异
- 后端 `server.py :: get_quotes()` 改造：每条返回 is_stale + 新增 partial_failure / missing_symbols / requested_count / fetched_count；requested 非空且 fetched 为空 → error 非空
- 前端 `app.js :: attention()` 新增 isStale 屏蔽（保留 status / wall / core_validation）
- 前端 `app.js :: cardHtml()` 新增 stale 横幅显示
- 全版本号统一 v1.0.6（DB TARGET / server_version / argparse / 启动打印 / 前端头 / docx）
- docx 彻底重写（不复用 v1.0.5 docx），新 docx SHA `d69bfd33...` ≠ v1.0.5 docx SHA