# v1.0.6 发版交付包文件清单  Manifest

项目：A/H 投研交易工作台 (Individual Stock Workbench)
版本：v1.0.6（行情一致性修复）
打包时间：2026-09-10 19:51:49 (Asia/Shanghai)
清单中文件数：17 + 清单自身 1 = 总 18 个

## 文件清单（按路径排序，不含清单自身以避免循环依赖）

| # | 路径 | 大小 (bytes) | SHA-256 |
|---|------|-------------:|---------|
| 01 | `app/server.py` | 80222 | `2cdf5f8c5a308fdf237c69b216d51b512c62042b60953b78e36559dfe9003dd8` |
| 02 | `app/static/app.js` | 53815 | `cda6910811784406cf9a224c123bbc49f3d36b6d700fe9f795e4f7ed33083784` |
| 03 | `app/static/index.html` | 934 | `fb4c57198af812b4a317f40609a223ed47377598b034f30bb3bb32ac6f39aa8b` |
| 04 | `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| 05 | `tests/test_v102.py` | 23028 | `055f5b4b3717f642f5ed9ca08a51d40a471ff10c5aa5a563787bd6db0329fb3b` |
| 06 | `tests/test_v103.py` | 30434 | `877296d9896cb02d04908dc2b013aad31eaa9f585c44f75ac2ebcdefb9756eed` |
| 07 | `tests/test_v105.py` | 15193 | `eb4bdc8bd70337caa31af3c9ff6441e3682ba7e9d14806592d71c4a012cd076d` |
| 08 | `tests/test_v106.py` | 12693 | `f4ccc2990d877f92cd7935d7d00c2879f32229e613e0e9a293237ceacdaa47b4` |
| 09 | `tests/test_integration_quote.py` | 8190 | `0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6` |
| 10 | `tests/design_reversal.md` | 1978 | `1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a` |
| 11 | `tests/design_research_pool_history.md` | 4260 | `1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864` |
| 12 | `tests/fixtures/sample_seed.py` | 6900 | `57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde` |
| 13 | `data/workbench.db` | 81920 | `f74f35c88fc8579cb2335ad6a24c085e11d8f2199c9ad1a99080e6782f02a75c` |
| 14 | `启动工作台.bat` | 445 | `8ae2a47b8da27c6ca3d43550fd372c4e6177fa3d0f13b44ab2af664ceada22c0` |
| 15 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.6.docx` | 44489 | `d69bfd33a540a861f145d7c3180c19a2752ff7eb4bc9fa36c48cbeef4fa8ecbe` |
| 16 | `output/20260910-audit/build_docx_v106.py` | 20940 | `ad27b259220ecc10f822827307a58cf6559f5d38fa037ee01ee373a92bb6cdad` |
| 17 | `PACK_NOTES.md` | 3347 | `3bcfc876e46c88dde8334e80b0732539aac0ac4aab9c0a82e067ca9c7abe904f` |

## 范围说明

### ✅ 已包含（送审范围）

- 当前 v1.0.6 应用源码（`app/server.py` + `app/static/*`）
- 完整测试套件（v1.0.2 + v1.0.3 + v1.0.5 + v1.0.6）
- 设计文档（reversal / research_pool_history）
- 测试 fixture（sample_seed.py）
- 当前生产数据库（`data/workbench.db`，schema_version=1.0.6）
- 启动脚本（`启动工作台.bat`）
- 当前版本审计文档（v1.0.6 docx，与 v1.0.5 docx SHA 不同）
- 审计 docx 生成器（`build_docx_v106.py`）
- 本清单（`PACK_MANIFEST.md`）
- 交付说明（`PACK_NOTES.md`）

### ❌ 已排除

- `audit_pack_src/` —— 上一轮 v1.0.5 审计专用临时源
- `data/backup/` —— 迁移历史快照（按用户要求清理即可）
- `__pycache__/` —— Python 编译缓存
- `.workbuddy/` —— 个人助手记忆与工具
- 旧版 docx（v1.0.3 / v1.0.4 / v1.0.5）—— 已 superseded
- 旧版生成器（build_docx_v103 / v104 / v105）
- 旧版 ZIP（v1.0.3 / v1.0.4 / v1.0.5）

## 关于本清单自身的完整性

为避免「清单包含自身 SHA → 内容变化 → SHA 又变化」的循环依赖，
本清单**不含**自身的 SHA 条目；其真实 SHA 由构建脚本
`build_v106_final.py` 在打包时计算并打印在 stdout 中。审计方若需校验
清单文本未在打包后被修改，可直接对 `PACK_MANIFEST.md` 计算 SHA-256 并
与构建脚本的 stdout 输出比对。

## 验证方法

```bash
# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 <file>
# Linux/macOS
sha256sum <file>
# ZIP 整体
certutil -hashfile 个股工作台-v1.0.6-20260910.zip SHA256
```