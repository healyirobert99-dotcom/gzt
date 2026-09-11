# -*- coding: utf-8 -*-
"""独立 fixture：示例数据种子。

**不在 v1.0.1 生产数据库中预置**（v1.0.0 → v1.0.1 变更：正式生产数据库不得预置美图、道通等测试证券）。
本文件保留示例 fixture 供以下场景使用：
  - 测试套件（tests/test_v101.py）
  - 开发者本地演示（显式 python server.py --seed 或单独调用 seed_sample 函数）

使用示例：
    import sys
    sys.path.insert(0, '<workbench>/tests/fixtures')
    from sample_seed import seed_sample
    conn = sqlite3.connect('<workbench>/data/workbench.db')
    conn.row_factory = sqlite3.Row
    seed_sample(conn)
    conn.commit()
    conn.close()
"""
import json
import os
import sys

# 添加 server.py 路径以复用 now_str()
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import server  # noqa: E402


def seed_sample(conn):
    """示例数据写入（fixture）：美图公司（01357.HK）+ 道通科技（688208.SH）。

    仅在调用方主动传入 conn 后写；调用方负责事务提交。
    """
    cur = conn.execute(
        'INSERT INTO securities (code, exchange, name, currency, market, sector, notes, status, created_at, updated_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?)',
        ('01357', 'HK', '美图公司', 'HKD', '港股', '消费 / AI 应用',
         '示例数据：fixture 内置，仅用于开发演示或测试，正式生产不预置。', '等价格',
         server.now_str(), server.now_str()))
    sid = cur.lastrowid
    conn.execute(
        'INSERT INTO research (security_id, version, research_pool, one_liner, positive_changes, '
        'core_validations, wall_conditions, report_link, research_date, change_note, created_at) '
        'VALUES (?,1,?,?,?,?,?,?,?,?,?)',
        (sid, '核心优质错配池',
         'AI 影像工具订阅化打开第二增长曲线，市场仍按工具型公司定价。',
         'AI 会员订阅收入高速增长；产品矩阵 MAU 回升；付费渗透率持续提升。',
         json.dumps([
             {'content': '订阅收入同比增速维持在 20% 以上', 'status': '跟踪中'},
             {'content': 'AI 付费渗透率持续提升', 'status': '跟踪中'},
             {'content': 'MAU 不出现连续两个季度下滑', 'status': '跟踪中'}], ensure_ascii=False),
         json.dumps([
             {'content': '订阅增速连续两个季度明显下滑', 'triggered': False},
             {'content': '主要股东大幅减持', 'triggered': False},
             {'content': '商誉或投资资产出现减值迹象', 'triggered': False}], ensure_ascii=False),
         '', '2026-08-15', '初始研究结论（示例数据）', server.now_str()))
    conn.execute(
        'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, add_zone_low, '
        'add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, target_position_pct, '
        'next_action, change_note, created_at) VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?)',
        (sid, 4.20, 4.80, 3.60, 4.20, 3.00, 3.60, 5.50, 8,
         '继续等待价格进入首仓区，期间跟踪订阅数据。', '初始交易计划（示例数据）', server.now_str()))
    server.ledger_add(conn, sid, '2026-08-15', '标的创建',
                      '新建标的 美图公司（01357.HK），初始交易状态：等价格')

    cur = conn.execute(
        'INSERT INTO securities (code, exchange, name, currency, market, sector, notes, status, created_at, updated_at) '
        'VALUES (?,?,?,?,?,?,?,?,?,?)',
        ('688208', 'SH', '道通科技', 'CNY', 'A股', '汽车 / 新能源检测',
         '示例数据：fixture 内置，仅用于开发演示或测试，正式生产不预置。', '持仓中',
         server.now_str(), server.now_str()))
    sid2 = cur.lastrowid
    conn.execute(
        'INSERT INTO research (security_id, version, research_pool, one_liner, positive_changes, '
        'core_validations, wall_conditions, report_link, research_date, change_note, created_at) '
        'VALUES (?,1,?,?,?,?,?,?,?,?,?)',
        (sid2, '核心优质错配池',
         '汽车智能诊断出海龙头，新能源检测第二曲线放量，估值低于海外可比公司。',
         '海外营收占比与增速保持稳定；新能源检测业务收入持续放量；毛利率维持高位。',
         json.dumps([
             {'content': '海外营收占比与增速保持稳定', 'status': '跟踪中'},
             {'content': '新能源检测业务收入持续放量', 'status': '跟踪中'},
             {'content': '毛利率维持在 55% 以上', 'status': '跟踪中'}], ensure_ascii=False),
         json.dumps([
             {'content': '欧美关税或贸易政策显著恶化', 'triggered': False},
             {'content': '大客户集中度风险暴露', 'triggered': False},
             {'content': '汇率大幅波动侵蚀利润', 'triggered': False}], ensure_ascii=False),
         '', '2026-07-20', '初始研究结论（示例数据）', server.now_str()))
    conn.execute(
        'INSERT INTO trade_plans (security_id, version, first_zone_low, first_zone_high, add_zone_low, '
        'add_zone_high, odds_zone_low, odds_zone_high, no_chase_price, target_position_pct, '
        'next_action, change_note, created_at) VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?)',
        (sid2, 24.00, 26.00, 22.00, 24.00, 19.00, 22.0, 29.0, 10,
         '持有；价格进入加仓区则按计划加仓，触发危墙条件则回到深穿复核。', '初始交易计划（示例数据）', server.now_str()))
    server.ledger_add(conn, sid2, '2026-07-20', '标的创建',
                      '新建标的 道通科技（688208.SH），初始交易状态：等价格')
    conn.execute(
        'INSERT INTO trades (security_id, trade_date, side, price, quantity, fee, note, created_at) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (sid2, '2026-08-20', '买入', 25.80, 300, 5, '首仓建仓（示例）', server.now_str()))
    server.ledger_add(conn, sid2, '2026-08-20', '买入',
                      '买入 300 股 @ 25.8，首仓建仓（示例）')
    conn.execute(
        'INSERT INTO trades (security_id, trade_date, side, price, quantity, fee, note, created_at) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (sid2, '2026-09-02', '买入', 25.20, 200, 5, '加仓（示例）', server.now_str()))
    server.ledger_add(conn, sid2, '2026-09-02', '买入',
                      '买入 200 股 @ 25.2，加仓（示例）')
    conn.execute("UPDATE securities SET status='持仓中', updated_at=? WHERE id=?",
                 (server.now_str(), sid2))
    server.ledger_add(conn, sid2, '2026-08-20', '状态变更', '状态变更：等价格 → 持仓中',
                      '已按计划完成首仓建仓，核心验证项无恶化。')
