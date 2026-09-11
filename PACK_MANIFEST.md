# 个股工作台 v1.0.5 —— 发版包 SHA-256 清单

项目: A/H 投研交易工作台
版本: v1.0.5（封板准确性修复）
打包时间: 2026-09-10 19:06:01 (Asia/Shanghai)

## 文件数量（清晰表述）

- 清单列出的文件条目：**16 个**（`PACK_MANIFEST.md` 自身条目不在内）
- 加 `PACK_MANIFEST.md` 自身后，ZIP 内总文件数：**17 个**
- 送审文件累计字节数：392555

## 文件清单（按路径排序，不含 manifest 自身）

| # | 路径 | 大小 (bytes) | SHA-256 |
|---|------|-------------:|---------|
| 01 | `PACK_NOTES.md` | 4726 | `b5ed5cb81973c5abbe24baa06079f4f540740c06b4132d37099f5a456e92d076` |
| 02 | `app/server.py` | 77712 | `dabb23c98901639190d00f086122150f13e34d87112449ce39f514720bff21b0` |
| 03 | `app/static/app.js` | 52926 | `84e4ec3f12ed5a638b9cc63ccb9e64845ea66329b12324a1586cd9a8366e57a1` |
| 04 | `app/static/index.html` | 934 | `fb4c57198af812b4a317f40609a223ed47377598b034f30bb3bb32ac6f39aa8b` |
| 05 | `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| 06 | `data/workbench.db` | 81920 | `68d124c128baf1b6faddf0b76566eb079aa2af7b5f7ecdccff78d45dcc320f99` |
| 07 | `output/20260910-audit/build_docx_v105.py` | 24384 | `e93dd3c28499f2a7b0d703f86f56cfb21afd509312a603a287ce83254de4dda4` |
| 08 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.5.docx` | 45941 | `3db74c6e72256841317ab33a188e4494fcfe7473c11f8dd27bb8d4dfb483e699` |
| 09 | `tests/design_research_pool_history.md` | 4260 | `1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864` |
| 10 | `tests/design_reversal.md` | 1978 | `1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a` |
| 11 | `tests/fixtures/sample_seed.py` | 6900 | `57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde` |
| 12 | `tests/test_integration_quote.py` | 8190 | `0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6` |
| 13 | `tests/test_v102.py` | 23028 | `b2c5d07945c763f712c9e4e459f0c18f55d6c66e98a09eaab0a946ea5e389c8b` |
| 14 | `tests/test_v103.py` | 30434 | `877296d9896cb02d04908dc2b013aad31eaa9f585c44f75ac2ebcdefb9756eed` |
| 15 | `tests/test_v105.py` | 15193 | `eb4bdc8bd70337caa31af3c9ff6441e3682ba7e9d14806592d71c4a012cd076d` |
| 16 | `启动工作台.bat` | 445 | `8ae2a47b8da27c6ca3d43550fd372c4e6177fa3d0f13b44ab2af664ceada22c0` |

## 验证方法

接收方对每个送审文件执行 SHA-256 校验，
与上表【文件清单】节比对，差异一律视作篡改。

```bash
# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 <file>
# Linux/macOS
sha256sum <file>
```

## 关于本清单自身的完整性

为避免「清单包含自身 SHA → 内容变化 → SHA 又变化」的循环依赖，
本清单**不含**自身的 SHA 条目。
接收方如需独立验证清单文本未被在打包后修改，
直接对 `PACK_MANIFEST.md` 计算 SHA-256 即可。
