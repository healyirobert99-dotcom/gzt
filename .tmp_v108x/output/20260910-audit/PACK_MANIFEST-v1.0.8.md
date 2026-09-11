# 个股工作台 v1.0.8 —— PACK_MANIFEST（交付物清单）

生成日期: 2026-09-11
版本号: Workbench v1.0.8

---

## 文件清单

| # | 相对路径 | 字节数 | SHA-256 |
|---|---|---:|---|
| 01 | `README.txt` | 1008 | `2e0fbe49032ce46e852d99e0d09fce55fe1287c4ac48089b72a332a97014f55a` |
| 02 | `app/server.py` | 137033 | `143d1d57125548bc83032d7dd933042c524382a23bcfa1e56392439ec549c8ac` |
| 03 | `app/static/app.js` | 82486 | `8748054b22308248ea1dbb7b2e1f5c46f9203a7ef74cf172efa6e98061aa93db` |
| 04 | `app/static/index.html` | 995 | `0d376a2ea40b78512de91e625262c5b01b43384f813c73236adca989a3ce634a` |
| 05 | `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| 06 | `启动工作台.bat` | 388 | `caf74fb14c04cbef56ebbda0a70700594fd0e55136ad01cedd372843e18244c4` |
| 07 | `data/workbench.db` | 81920 | `db6ca3daf965f7298d807e50d8d5e55d2a3257ef945237c64ab0f8a955cf126e` |
| 08 | `tests/test_v102.py` | 23101 | `255fd894822d6ad1d72efdcc4282b4065a40430534e39ed2c73e432296bd1103` |
| 09 | `tests/test_v103.py` | 30434 | `877296d9896cb02d04908dc2b013aad31eaa9f585c44f75ac2ebcdefb9756eed` |
| 10 | `tests/test_v105.py` | 15193 | `eb4bdc8bd70337caa31af3c9ff6441e3682ba7e9d14806592d71c4a012cd076d` |
| 11 | `tests/test_v106.py` | 12693 | `f4ccc2990d877f92cd7935d7d00c2879f32229e613e0e9a293237ceacdaa47b4` |
| 12 | `tests/test_v107.py` | 46141 | `092c7f31dacc3b0da5c2da9af72783060a24b5a282f13f2f83810eec870fc6dc` |
| 13 | `tests/test_v108.py` | 44352 | `d46a7163ce10add1499d0bdaeba84f04a61d082d6b96db4710fe3e8e414f1aa9` |
| 14 | `tests/test_integration_quote.py` | 8190 | `0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6` |
| 15 | `tests/fixtures/sample_seed.py` | 6900 | `57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde` |
| 16 | `tests/design_reversal.md` | 1978 | `1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a` |
| 17 | `tests/design_research_pool_history.md` | 4260 | `1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864` |
| 18 | `samples/json/example-full-import.json` | 3108 | `a40e4b0469335ac6309d977e6bfbf42124e3c424f66fa89d535b806117374172` |
| 19 | `samples/json/example-execution-update.json` | 746 | `4ca5b03c327bff518ae92f89af704fc68ebd17c19454a6eba64267d87a0fb873` |
| 20 | `output/20260910-audit/PACK_NOTES-v1.0.8.md` | 8154 | `c63dd53bf49dd59e50ccc3eee31a44122b26370e2647c93b60d13d536fcf8ca8` |
| 21 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.8.docx` | 44156 | `64747e5dd0e7c75de55b76e1a8d66d2f58d9abe8e13f27e8eb1bb26fa4755b0e` |
| 22 | `output/20260910-audit/smoke_v108_http.py` | 7908 | `71826c8eed949d535fb80d34026e8e9d465f1fda59c9ea9b6228f1a6a7479a1f` |
| 23 | `output/20260910-audit/PACK_MANIFEST-v1.0.8.md` | —（随本清单生成） | `—（本清单自身，不含 SHA）` |

---

## 总计

- **ZIP 内文件总数: 23 个**（含本 Manifest 自身）
- 交付内容总字节数（不含本 Manifest）: 574728 B

> 本清单列出的每一条路径都真实存在于 ZIP 中；
> 不列出任何 ZIP 中不存在的构建脚本。文件数量由打包脚本统计，非人工填写。

---

## 自洽验证

```bash
# 1) 启动（默认端口 8765）
python app/server.py
# A/H 投研交易工作台 v1.0.8 已启动: http://127.0.0.1:8765

# 2) 离线测试套件（407 断言）
python tests/test_v102.py    # 38 PASS
python tests/test_v103.py    # 60 PASS
python tests/test_v105.py    # 25 PASS
python tests/test_v106.py    # 28 PASS
python tests/test_v107.py    # 127 PASS
python tests/test_v108.py    # 129 PASS

# 3) HTTP 端到端冒烟（14 PASS）
python output/20260910-audit/smoke_v108_http.py
```

