# v1.0.8 ZIP 构建日志

> 本文件是**工作区侧**构建记录，**刻意不打包进 ZIP**。
> 原因：它记录 ZIP 自身的 SHA-256，若放入 ZIP 会改变 ZIP 指纹，形成自指矛盾。
> 验收方收到 ZIP 后，用下方 `ZIP_SHA256` 核对完整性，再用 ZIP 内
> `output/20260910-audit/PACK_MANIFEST-v1.0.8.md` 核对逐文件 SHA-256。

## 交付包指纹

- ZIP_PATH: `D:\个股工作台\个股工作台-v1.0.8-20260911.zip`
- ZIP_BYTES: 180933
- ZIP_SHA256: `c852eb3b900df1d346a06480c3c863b40a8bba8e5590698abfff6412e2d0b06d`
- ENTRIES: 23（含 `PACK_MANIFEST-v1.0.8.md` 自身）
- UNCOMPRESSED_TOTAL: 583157 B
- 交付内容总字节数（不含 Manifest）: 579449 B

### 版本谱系（同一工作日内 3 次作废 + 1 次有效）

初版封板后，交付前验证又发现两处问题，均**未改动任何代码**（`app/` 下四个文件的
SHA-256 自始至终一致），只重建文档与打包：

| 序 | ZIP_SHA256 | 字节 | docx_SHA256 | 发现的问题 | 处置 |
|---|---|---:|---|---|---|
| 1 | `6f37fe1248f4…` | 177966 | `64747e5d…` | 审计文档 §8.2 称"test_v107.py 原有 **127** 断言…其余 **124** 条业务语义断言未做任何修改"，与事实不符 | 作废 |
| 2 | `afe93129…` | 178621 | `9ab1681c…` | §8.2 已修正为"v1.0.7 为 **126** 断言…5 条被改写…**121 条**逐字未动"；但此时尚未发现并登记 R-027 / R-028 | 作废 |
| 3 | `553e23f22112…` | 180448 | `27ab29e0…` | 已补 R-027 / R-028，但复现次数**写死**为"3 次返回 200 / 追加 3 条 / 4~5 次返回 500"—— 与本机实测区间（成功 **2~3** 次）不符，仍属"数字不可复现" | 作废 |
| 4 | **`c852eb3b900d…`** | **180933** | **`e51a829e…`** | **当前有效**：次数改为区间（2~3 次 / 1~2 条 / 2~5 次）并给出**不变式**（成功次数恒 > 1、append-only 表恒被多写、5xx 恒 > 0），符合"只写真实可复现结果" | **交付** |

第 1、3 版留档（不随交付）：
- `.tmp_v108x/verify/superseded-r1-docx-claim-false.zip`
- `.tmp_v108x/verify/superseded-r2-fixed-counts.zip`

第 2 版未单独留档（已被第 3 版覆盖）。
对抗性验证与探针：`.tmp_v108x/verify/probe_race.py`；
可复用并发探针：`skills/ah-workbench-release-verify/scripts/concurrency_probe.py`（3/3 稳定复现）。

> 教训（第 3 → 第 4 版）：**并发缺陷的"成功次数"随线程调度波动，
> 写死具体次数同样属于不可复现的声称。应给不变式，并说明波动区间。**

## 关键产物指纹

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.8.docx` | 45764 | `e51a829e91447087e06e0f2ffb7e466dfc9ff78590f9fb65390036e7d04fa285` |
| `output/20260910-audit/PACK_NOTES-v1.0.8.md` | 11267 | `726c93eef11b7335f64a4f0cafdd160cf79eea04139599aa55b322a8dacf373b` |
| `output/20260910-audit/PACK_MANIFEST-v1.0.8.md` | 3708 | `752b45e3a80e5c54c8bb159469c28f68baa9be1e060267090a800154b913bf9a` |
| `app/server.py` | 137033 | `143d1d57125548bc83032d7dd933042c524382a23bcfa1e56392439ec549c8ac` |
| `app/static/app.js` | 82486 | `8748054b22308248ea1dbb7b2e1f5c46f9203a7ef74cf172efa6e98061aa93db` |
| `data/workbench.db` | 81920 | `db6ca3daf965f7298d807e50d8d5e55d2a3257ef945237c64ab0f8a955cf126e` |

## 本轮实跑结果（可复现）

在**解压后的交付 ZIP** 内直接执行，结果如下：

| 套件 | 断言数 | 结果 | 依赖外网 |
|---|---:|---|---|
| `tests/test_v102.py` | 38 | PASS | 否 |
| `tests/test_v103.py` | 60 | PASS | 否 |
| `tests/test_v105.py` | 25 | PASS | 否 |
| `tests/test_v106.py` | 28 | PASS | 否 |
| `tests/test_v107.py` | 127 | PASS | 否 |
| `tests/test_v108.py` | 129 | PASS | 否 |
| **离线套件小计** | **407** | **PASS / FAIL 0** | — |
| `tests/test_integration_quote.py` | 14 | PASS | 是（腾讯行情接口） |
| `output/20260910-audit/smoke_v108_http.py` | 14 | PASS | 否（本机临时端口） |

## 一致性自检（本轮实际执行）

| 检查项 | 结果 |
|---|---|
| Manifest 逐文件 SHA-256 / 字节数 vs ZIP 实际内容 | 22/22 全部一致 |
| Manifest 条数 vs ZIP 实际文件数 | 23 vs 23 一致 |
| Manifest 是否存在 ZIP 中不存在的条目 | 无幽灵条目 |
| ZIP 内文件 vs 工作区源码 SHA-256 | 除 `README.txt`（打包时生成）外全部一致 |
| ZIP 内是否含 `tests/test_integration_quote.py` | 含 |
| `README.txt` 默认地址 | `http://127.0.0.1:8765`（与 `server.py` 默认端口一致） |
| 生产库 `schema_version` | `1.0.8` |

## 与 v1.0.7 的差异

- v1.0.7 BUILD_LOG 记录 ZIP_SHA256 `b794ebbd194acc684e2e9858858649ecb1f4168592644e77844211d0923ed001`，
  但该 ZIP **不含** `tests/test_integration_quote.py`，解压后 `tests/test_v102.py` 必然失败 ——
  这正是本轮要修复的"交付包无法复现文档宣称结果"问题。
- v1.0.8 已把该文件纳入 ZIP，并在**解压后的包内**重新跑完全部套件，上表数字全部来自实跑。
