# 个股工作台 v1.0.10 —— PACK_MANIFEST（交付物清单）

生成日期: 2026-09-11
版本号: Workbench v1.0.10

---

## 文件清单

| # | 相对路径 | 字节数 | SHA-256 |
|---|---|---:|---|
| 01 | `README.txt` | 4961 | `60d3092bf70884cb2cdd18d331a0d8096aeb241f563312bd14c59708f3a8b4d4` |
| 02 | `app/server.py` | 149287 | `6d29e63f177afa3b965f5929bb498970f8235185901afd2884b759e38b97d322` |
| 03 | `app/static/app.js` | 84687 | `e5e62b8e186c2f29b46cece98f6323927afd31ee1d58ca4aed06b451595e7bf6` |
| 04 | `app/static/index.html` | 995 | `0d376a2ea40b78512de91e625262c5b01b43384f813c73236adca989a3ce634a` |
| 05 | `app/static/style.css` | 13584 | `185092e89a103195126e7945d16f9641057d3355a5408cdd9f75814288a5a635` |
| 06 | `启动工作台.bat` | 3970 | `65414590d0804b255830ce6b489e384db7501659ccb50b9ebf8c0dc64f70fb93` |
| 07 | `data/workbench.db` | 73728 | `cce3b15e10e4fb08183f7f640c82255085a46ca570039e61391e5a0781421ec4` |
| 08 | `tests/test_v102.py` | 23101 | `255fd894822d6ad1d72efdcc4282b4065a40430534e39ed2c73e432296bd1103` |
| 09 | `tests/test_v103.py` | 30434 | `877296d9896cb02d04908dc2b013aad31eaa9f585c44f75ac2ebcdefb9756eed` |
| 10 | `tests/test_v105.py` | 15193 | `eb4bdc8bd70337caa31af3c9ff6441e3682ba7e9d14806592d71c4a012cd076d` |
| 11 | `tests/test_v106.py` | 12693 | `f4ccc2990d877f92cd7935d7d00c2879f32229e613e0e9a293237ceacdaa47b4` |
| 12 | `tests/test_v107.py` | 46147 | `ec87013675b077057554b64267d79360828914eb10e3f0fb3b77073a534252af` |
| 13 | `tests/test_v108.py` | 44466 | `e6ede997c0ddcddc0b47406f41f5a174d5bc2141e8297062c436b2f824a5e960` |
| 14 | `tests/test_v109.py` | 31676 | `d63d4692ebee355256c8402483648dc875789c2a128ab0de1deeeddd7c0dab85` |
| 15 | `tests/test_v110.py` | 7430 | `14aea424b2eb7c25232854f8a50bea4fb80f9cf75b5b7f86e378a32aba7f3406` |
| 16 | `tests/test_integration_quote.py` | 8190 | `0140d7b7100cb3c8ca7b1e4b5183f9be92676d8292d998fc67c713d7b0fb21f6` |
| 17 | `tests/fixtures/sample_seed.py` | 6900 | `57ed8bec48cd584bfef4af3b711191f2bfcd1f946a5bdc6a55aae7f2b3ee4bde` |
| 18 | `tests/design_reversal.md` | 1978 | `1f650f362250923ddb5d13917b860b1cefee7119e935f228436ca1b7aa07283a` |
| 19 | `tests/design_research_pool_history.md` | 4260 | `1dbc359ca22ad71c73c5bb3cc5d0f69f09a794e8b59433d972164faa67f05864` |
| 20 | `samples/json/example-full-import.json` | 3108 | `a40e4b0469335ac6309d977e6bfbf42124e3c424f66fa89d535b806117374172` |
| 21 | `samples/json/example-execution-update.json` | 746 | `4ca5b03c327bff518ae92f89af704fc68ebd17c19454a6eba64267d87a0fb873` |
| 22 | `output/20260910-audit/PACK_NOTES-v1.0.10.md` | 14444 | `5a5255c86475fc74002e08040cdd24963078c5bfcb932f623811af116d6b5319` |
| 23 | `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.10.docx` | 47806 | `5952d1ca3ca17d1525c8c393555d3b73f91163cc48a098fb7ec62da1e8c2e45a` |
| 24 | `output/20260910-audit/smoke_v108_http.py` | 7908 | `71826c8eed949d535fb80d34026e8e9d465f1fda59c9ea9b6228f1a6a7479a1f` |
| 25 | `output/20260910-audit/smoke_v109_http.py` | 17684 | `ada790c5d7d1a96b2539539a525a9af0779d220d26191c2975190e8f30ff5956` |
| 26 | `output/20260910-audit/PACK_MANIFEST-v1.0.10.md` | —（随本清单生成） | `—（本清单自身，不含 SHA）` |

---

## 总计

- **ZIP 内文件总数: 26 个**（含本 Manifest 自身）
- 交付内容总字节数（不含本 Manifest）: 655376 B

> 本清单列出的每一条路径都真实存在于 ZIP 中；
> 不列出任何 ZIP 中不存在的构建脚本（文档生成脚本一律不进交付包）。
> 文件数量由打包脚本统计，非人工填写；打包后立即回读 ZIP 逐条校验字节数与 SHA-256。

### 关于 `data/workbench.db`

交付的是**空库模板**（6 张业务表行数均为 0，`schema_version = 1.0.10`，
`integrity_check = ok`，`PRAGMA foreign_key_check` 违例 0）。
它与本机工作区的 `data/workbench.db` **不是同一份文件**：
工作区那份含操作者的实际标的与研究数据，按交付约定不夹带进交付包。

---

## 自洽验证

```bash
# 1) 启动（默认端口 8765，与 README.txt 一致）
python app/server.py
# A/H 投研交易工作台 v1.0.10 已启动: http://127.0.0.1:8765

# 2) 离线测试套件（合计 504 断言）
python tests/test_v102.py    # 38 PASS
python tests/test_v103.py    # 60 PASS
python tests/test_v105.py    # 25 PASS
python tests/test_v106.py    # 28 PASS
python tests/test_v107.py    # 127 PASS
python tests/test_v108.py    # 129 PASS
python tests/test_v109.py    # 83 PASS
python tests/test_v110.py    # 14 PASS

# 3) HTTP 端到端冒烟
python output/20260910-audit/smoke_v109_http.py   # 38 PASS
python output/20260910-audit/smoke_v108_http.py   # 14 PASS（回归）

# 4) 联网集成（需外网）
python tests/test_integration_quote.py            # 14 PASS
```
