# A/H 投研交易工作台 · UI/UX 重构前端送审包

送审日期：2026-09-11

本包仅包含本轮 UI/UX 重构涉及的前端页面文件，不包含后端、数据库、测试数据或运行时临时文件。

## 本轮范围

- 深色金融终端视觉系统
- 今日工作台首页与股票卡片
- 右侧详情抽屉
- Quick Actions 与命令框
- 导入与更新三步流程视觉包装
- 价格区域具体区间展示
- 移除分时图与“新建标的”入口；新增标的统一通过 JSON 导入

## 业务边界

本轮未修改数据库结构、后端 API、研究口径、交易规则、行情源或业务判断逻辑。

## 文件

- `frontend/app/static/index.html`
- `frontend/app/static/app.js`
- `frontend/app/static/style.css`

## 验收

- 浏览器验收：1440px / 1920px 首页、卡片 hover、详情抽屉、导入页
- 快捷键验收：Ctrl/Cmd+K、J/K、Enter、Esc、详情内 E/T/R
- 现有业务回归测试全部通过
