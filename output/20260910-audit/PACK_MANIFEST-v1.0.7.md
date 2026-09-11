# 个股工作台 v1.0.7 — PACK_MANIFEST（封板交付物清单）

生成日期:2026-09-11
版本号:Workbench v1.0.7

---

## A. 核心源码

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 1 | `app/server.py` | 120067 | `99ce0abf0c4d` | v1.0.7;含 IMPORT_FORMAT_*、preview_import_*/commit_import_*、4 个新 API |
| 2 | `app/static/app.js` | 81480 | `7a5984d22031` | v1.0.7;新增 #/import 等 3 路由、renderImport* 函数 |
| 3 | `app/static/index.html` | 995 | `0d376a2ea40b` | v1.0.7;左侧导航新增「导入与更新」入口 |
| 4 | `app/static/style.css` | 13584 | `185092e89a10` | v1.0.7;沿用 v1.0.6 样式,未变动 |

## B. 测试

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 5 | `tests/test_v107.py` | 45144 | `a38b3520cc27` | 新增导入测试(15 节 / 126 断言) |
| 6 | `tests/test_v102.py` | 23101 | `255fd894822d` | v1.0.7 适配;schema_version 期望值改为动态读取 |

历史测试 `tests/test_v103.py` / `tests/test_v105.py` / `tests/test_v106.py` 字节级未变。

## C. 示例 JSON(samples/json/)

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 7 | `samples/json/example-full-import.json` | 2274 | `ff2a54e3b9df` | format=ah-workbench-import;2 只证券完整导入 |
| 8 | `samples/json/example-execution-update.json` | 504 | `141a09cb2ca9` | format=ah-workbench-execution;快速执行 |

## D. 操作截图(output/20260910-audit/screenshots/)

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 9 | `output/20260910-audit/screenshots/screenshot-1-full-import-done.svg` | 7229 | `a38a14a965db` | 「导入研究结果」完成页视觉示意 |
| 10 | `output/20260910-audit/screenshots/screenshot-2-execution-update-preview.svg` | 5956 | `2af9ccc2e5b1` | 「快速更新动态执行」预览页视觉示意 |

## E. 交付审计文档(output/20260910-audit/stage3/)

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 11 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.7.docx` | 49403 | `631906a2c50d` | v1.0.7 完整封板审计文档 |

## F. 交付备注

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 12 | `output/20260910-audit/PACK_NOTES-v1.0.7.md` | 9713 | `b1a793169a20` | 本次封板说明(本轮变更、测试结果、原则) |

## G. 生成脚本(非交付物,仅备追溯)

| # | 相对路径 | 字节数 | SHA-256 (12) | 说明 |
|---|---|---:|---|---|
| 13 | `output/20260910-audit/build_docx_v107.py` | 35092 | `e46c629c3848` | v1.0.7 docx 生成脚本 |
| 14 | `.workbuddy/tools/build_v107_screenshots.py` | 12093 | `2b8c4afb6724` | SVG 截图生成脚本 |

---

## 总计

- **文件数:14(交付项 12 + 生成脚本 2)**
- **总字节数:406,635 B(交付项 ≈ 359,450 B)**

---

## 自洽验证

```bash
# 1. 工作台启动到 v1.0.7
$ python app/server.py --port 8765 --no-browser
A/H 投研交易工作台 v1.0.7 已启动: http://127.0.0.1:8765

# 2. 全部测试套件 PASS
$ python tests/test_v102.py    # 38 PASS
$ python tests/test_v103.py    # 60 PASS
$ python tests/test_v105.py    # 25 PASS
$ python tests/test_v106.py    # 30 PASS
$ python tests/test_v107.py    # 126 PASS

# 3. 完整流程端到端冒烟
$ python -c "import sys; sys.path.insert(0,'app'); import server; \
             server.init_db(seed=False); print('init_db OK')"
init_db OK
```

数据库 `schema_version = '1.0.7'`,PRAGMA foreign_key_check = 0 violations,integrity_check = ok。