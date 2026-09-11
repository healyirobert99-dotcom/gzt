# 个股工作台 v1.0.9 —— PACK_MANIFEST（交付物清单）

生成日期: 2026-09-11
版本号: Workbench v1.0.9

---

## 文件清单

| # | 相对路径 | 字节数 | SHA-256 |
|---|---|---:|---|
| 01 | `README.txt` | 1560 | `010283af64a47f00c0ce4398a26582bed430c4b9e78e9546b4b5c7fea8f42070` |
| 02 | `app/server.py` | 148060 | `be8dd23fbaf5fe7de84af2b00e962f57d56db419bf5393aaec9fb73bc044ece2` |
| 03 | `app/static/app.js` | 84469 | `9855a8893e440d8ba0b2badeff31a440681d6bba83462855bc8e42bd18afc459` |
| 04 | `app/static/index.html` | 995 | `0d376a2ea40b78512de91e625262c5b01b43384f813c73236adca989a3ce634a` |
| 05 | `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| 06 | `启动工作台.bat` | 388 | `caf74fb14c04cbef56ebbda0a70700594fd0e55136ad01cedd372843e18244c4` |
| 07 | `data/workbench.db` | 81920 | `e16a18202e069748f650c95ae6708219d872fcd18fa07ced74473cbdc625642a` |
| 08 | `tests/test_v102.py` | 23101 | `255fd894822d6ad1d72efdcc4282b4065a40430534e39ed2c73e432296bd1103` |
| 09 | `tests/test_v103.py` | 30434 | `877296d9896cb02d04908dc2b013aad31eaa9f585c44f75ac2ebcdefb9756eed` |
| 10 | `tests/test_v105.py` | 15193 | `eb4bdc8bd70337caa31af3c9ff6441e3682ba7e9d14806592d71c4a012cd076d` |
| 11 | `tests/test_v106.py` | 12693 | `f4ccc2990d877f92cd7935d7d00c2879f32229e613e0e9a293237ceacdaa47b4` |
| 12 | `tests/test_v107.py` | 46141 | `a90f1cb283f3e1e327e49f841a10d6d679fe7c3ccf65857305ae27ea7b51dc76` |
| 13 | `tests/test_v108.py` | 44459 | `4a48b3919191af55235ee3fbf23d38d1691e4f73527973200dd0a7310047c54d` |
| 14 | `tests/test_v109.py` | 31557 | `bd9a25a1a9ec170235d7ba840d775ae1408a833c4d0f104c09142f14c04c5ba6` |
| 15 | `tests/test_integration_quote.py` | 8190 | `0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6` |
| 16 | `tests/fixtures/sample_seed.py` | 6900 | `57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde` |
| 17 | `tests/design_reversal.md` | 1978 | `1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a` |
| 18 | `tests/design_research_pool_history.md` | 4260 | `1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864` |
| 19 | `samples/json/example-full-import.json` | 3108 | `a40e4b0469335ac6309d977e6bfbf42124e3c424f66fa89d535b806117374172` |
| 20 | `samples/json/example-execution-update.json` | 746 | `4ca5b03c327bff518ae92f89af704fc68ebd17c19454a6eba64267d87a0fb873` |
| 21 | `output/20260910-audit/PACK_NOTES-v1.0.9.md` | 11248 | `1aa650c5bc1b934de7d33604b412c288da81cacdd272687505c8d9e640d9fadf` |
| 22 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.9.docx` | 47227 | `7f26486eda0478c6dcf692e49e092d65b54f76fb5f0bb2682b738022089a6389` |
| 23 | `output/20260910-audit/smoke_v108_http.py` | 7908 | `71826c8eed949d535fb80d34026e8e9d465f1fda59c9ea9b6228f1a6a7479a1f` |
| 24 | `output/20260910-audit/smoke_v109_http.py` | 17684 | `ada790c5d7d1a96b2539539a525a9af0779d220d26191c2975190e8f30ff5956` |
| 25 | `output/20260910-audit/PACK_MANIFEST-v1.0.9.md` | —（随本清单生成） | `—（本清单自身，不含 SHA）` |

---

## 总计

- **ZIP 内文件总数: 25 个**（含本 Manifest 自身）
- 交付内容总字节数（不含本 Manifest）: 643803 B

> 本清单列出的每一条路径都真实存在于 ZIP 中；
> 不列出任何 ZIP 中不存在的构建脚本（文档生成脚本一律不进交付包）。
> 文件数量由打包脚本统计，非人工填写；打包后立即回读 ZIP 逐条校验字节数与 SHA-256。

---

## 自洽验证

```bash
# 1) 启动（默认端口 8765，与 README.txt 一致）
python app/server.py
# A/H 投研交易工作台 v1.0.9 已启动: http://127.0.0.1:8765

# 2) 离线测试套件（合计 490 断言）
python tests/test_v102.py    # 38 PASS
python tests/test_v103.py    # 60 PASS
python tests/test_v105.py    # 25 PASS
python tests/test_v106.py    # 28 PASS
python tests/test_v107.py    # 127 PASS
python tests/test_v108.py    # 129 PASS
python tests/test_v109.py    # 83 PASS

# 3) HTTP 端到端冒烟
python output/20260910-audit/smoke_v109_http.py   # 38 PASS
python output/20260910-audit/smoke_v108_http.py   # 14 PASS（回归）

# 4) 联网集成（需外网）
python tests/test_integration_quote.py            # 14 PASS
```
