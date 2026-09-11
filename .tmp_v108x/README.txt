个股工作台 v1.0.8 封板交付包

项目: A/H 投研交易工作台
版本: v1.0.8（导入完整性封板修复）

使用步骤:
  1. 解压本 ZIP 到任意目录
  2. cd <解压目录>
  3. python app/server.py
  4. 浏览器自动打开 http://127.0.0.1:8765

注意: 默认端口为 8765（用 --port 可指定其它端口）。

文档:
  - output/20260910-audit/PACK_NOTES-v1.0.8.md
  - output/20260910-audit/PACK_MANIFEST-v1.0.8.md
  - output/20260910-audit/stage3/A-H投研交易工作台交付审计文档-v1.0.8.docx

测试（离线套件，共 407 断言）:
  python tests/test_v102.py    # 38
  python tests/test_v103.py    # 60
  python tests/test_v105.py    # 25
  python tests/test_v106.py    # 28
  python tests/test_v107.py    # 127
  python tests/test_v108.py    # 129

联网测试（需外网，单独执行）:
  python tests/test_integration_quote.py        # 14

端到端冒烟（真实 HTTP，本机临时端口）:
  python output/20260910-audit/smoke_v108_http.py   # 14
