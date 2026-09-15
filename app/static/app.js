'use strict';

/* ==================================================================
   A/H 投研交易工作台 · 前端  v1.0.10
   原则：系统只展示事实（价格区间关系、验证项状态），绝不生成买卖建议；
        一切"下一动作"均来自用户已录入的交易计划。

   安全说明（v1.0.2 修正）：
   - 动态用户内容（公司名/链接/备注等）经过 esc() 转义后用 textContent 或
     经过 esc 后的属性插入；这部分使用 innerHTML 是因为 esc 已经把
     `& < > " '` 替换为实体，不会执行任何用户脚本。
   - 可点击 URL 必须经过 sanitizeUrl() 过滤，禁止 javascript: / data: /
     vbscript: 等危险 scheme；其他 scheme 仅允许 http / https / mailto。
   - 不存在内嵌 iframe / eval / Function 构造器 / 动态 script src。

   v1.0.3 新增：动态执行层（execution layer）
   - 详情页新增"动态执行"面板（位于"交易计划"与"真实持仓"之间）
   - 首页卡片同时显示：静态价格位置（事实）+ 最新动态执行判断（人工录入）
   - 行情刷新不会修改 execution_view（永远由用户手动录入）
   - 无 execution record 时显式提示"尚未形成动态执行判断"，不自动生成

   v1.0.7 新增：导入与更新（import layer）
   - 新增路由 #/import（入口选择页）
   - 新增「导入研究结果」入口（format=ah-workbench-import）：
     粘贴 → 解析 → 预览差异 → 用户确认 → 写入完成
   - 新增「快速更新动态执行」入口（format=ah-workbench-execution）：
     只接受 identity + execution；不存在标的时拒绝，提示先完成研究导入
   - 严格两段式：先预览，不触库；用户点确认才走 commit_import_*

   v1.0.8 导入完整性封板（前端侧）：
   - token 由服务端生成并保存在服务端 cache；前端只原样回传，不解析不构造
   - 状态确认不再写入粘贴 JSON：勾选状态只存在前端内存
     （Import.confirmedStatus），commit 时单独提交 confirmed_status_changes
   - 预览页显式展示 name 不一致警告（不自动修改 name）
   - 移除"载入示例"按钮：不再一键载入真实候选标的的虚构研究/交易计划

   v1.0.9 最终并发与预览一致性修复（前端侧）：
   - 点击"确认并写入"后立即 disabled 并显示"正在写入…"，请求返回前不再发送
     第二次 commit；失败后按钮恢复。**仅为 UI 防误操作**，
     真正的防重由服务端 in_flight 原子 claim 保证。
   - 服务端返回 409（数据库写入冲突）时提示"稍后重试"，不前进到完成页。

   v1.0.10 启动脚本交付修复：
   - **前端零改动**。本版仅替换交付包内的 启动工作台.bat
     （旧版用 `where python` 判定解释器，在本机会命中 Microsoft Store 存根）。
   ================================================================== */

/* 工具：URL scheme 白名单 */
function sanitizeUrl(url) {
  if (url == null) return '';
  const s = String(url).trim();
  if (!s) return '';
  const m = s.toLowerCase().match(/^([a-z][a-z0-9+.\-]*):/);
  if (!m) {
    // 协议相对 / 纯路径 → 当作相对/绝对路径处理，前端不会跳协议
    return s;
  }
  const scheme = m[1];
  const allow = new Set(['http', 'https', 'mailto']);
  if (allow.has(scheme)) return s;
  return '';  // 拒绝 javascript: / data: / file: / vbscript: 等
}

/* ===== 全局状态 ===== */
const S = { secs: [], archived: [], settings: {}, quotes: {}, quoteTime: '', quoteError: '',
            lastSuccessAt: '', lastError: '', lastErrorAt: '' };
const STATUSES = ['可交易', '等价格', '等证据', '持仓中', '暂不参与'];
const STATUS_CLS = { '可交易': 'b-ready', '等价格': 'b-wait', '等证据': 'b-proof', '持仓中': 'b-hold', '暂不参与': 'b-pause' };
// v1.0.3 新增：动态执行层判断标准选项（白名单）。系统**不**根据价格自动切换 execution_view。
// v1.0.5：execution_view 改为自由文本输入；EXECUTION_VIEWS 仅作 datalist 建议项，
//         后端只校验非空，存储任意非空文本。
const EXECUTION_VIEWS = ['等待技术确认', '可以开始执行', '暂缓执行', '继续观察'];

/* ===== 工具 ===== */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const $ = sel => document.querySelector(sel);

function num(v, d) {
  if (d === undefined) d = 2;
  if (v === null || v === undefined || isNaN(v)) return '—';
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d });
}
const curSym = c => c === 'HKD' ? 'HK$' : '¥';
const decOf = c => c === 'HKD' ? 3 : 2;
const today = () => {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
};
// 归档是**可见性开关**（与交易状态 status 正交），不是只读开关 —— 后端没有任何
// mutation 端点校验 archived_at。故查找必须同时覆盖活跃与已归档：否则从 #/s/{id}
// （书签 / 浏览器后退 / 标的库的 A/H 关联链接）打开已归档标的时，详情抽屉上
// 「更新动态执行 / 录入交易 / 查看研究 / ··· 更多」会全部**点了毫无反应**（静默失效）。
const findSec = id => S.secs.find(s => s.id === Number(id))
  || (S.archived || []).find(s => s.id === Number(id));
const statusBadge = st => `<span class="badge ${STATUS_CLS[st] || 'b-pause'}">${esc(st)}</span>`;

async function api(path, opt) {
  opt = opt || {};
  const method = opt.method || 'GET';
  const res = await fetch(path, {
    method: method,
    headers: opt.body ? { 'Content-Type': 'application/json' } : {},
    body: opt.body ? JSON.stringify(opt.body) : undefined
  });
  let data = {};
  try { data = await res.json(); } catch (e) { /* ignore */ }
  if (!res.ok) {
    toast(data.error || ('请求失败：HTTP ' + res.status), true);
    throw new Error(data.error || String(res.status));
  }
  return data;
}

function toast(msg, bad) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = 'toast' + (bad ? ' bad' : '');
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 350); }, 2600);
}

/* ===== 行情 ===== */
function txSymbol(sec) {
  if (sec.exchange === 'HK') return 'hk' + String(sec.code).padStart(5, '0');
  return (sec.exchange === 'SH' ? 'sh' : 'sz') + sec.code;
}
const quoteOf = sec => S.quotes[txSymbol(sec)] || null;

/* 顶栏「数据更新」按钮。
   按钮位于 #app 之外的顶栏，render() 不会重绘它，所以忙碌态可原地安全切换。 */
const REFRESH_LABEL = '数据更新';

function setRefreshBusy(busy) {
  const btn = $('#btn-refresh');
  if (!btn) return;
  if (!btn.dataset.label) btn.dataset.label = btn.textContent.trim() || REFRESH_LABEL;
  btn.disabled = !!busy;
  btn.textContent = busy ? '更新中…' : btn.dataset.label;
}

async function refreshQuotes(manual, force) {
  if (!S.secs.length) {
    if (manual) toast('当前没有标的，无需更新行情', true);
    return;
  }
  // 手动「数据更新」必须真去联网拿最新数据，因此带 force=1 绕过后端 8 秒
  // 行情缓存；60 秒后台轮询不带 force，复用缓存，避免无谓请求。
  const showBusy = !!manual;
  if (showBusy) setRefreshBusy(true);
  const symbols = [...new Set(S.secs.map(txSymbol))].join(',');
  try {
    const url = '/api/quotes?symbols=' + encodeURIComponent(symbols) + (force ? '&force=1' : '');
    const data = await api(url);
    S.quotes = data.data || {};
    S.quoteTime = data.last_success_at || data.fetched_at || '';
    S.lastSuccessAt = data.last_success_at || '';
    S.lastError = data.last_error || '';
    S.lastErrorAt = data.last_error_at || '';
    S.quoteError = data.error || '';
  } catch (e) {
    S.quoteError = '行情获取失败';
    S.lastError = String(e.message || e);
    S.lastErrorAt = nowHHMMSS();
  } finally {
    if (showBusy) setRefreshBusy(false);
  }
  updateQuoteStatus();
  if (manual) {
    if (S.quoteError) toast('数据更新失败：' + String(S.quoteError).slice(0, 48), true);
    else toast('数据已更新 · ' + (S.lastSuccessAt || '—'));
  }
  render();
}
function nowHHMMSS() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0') + ' ' +
         String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0') + ':' + String(d.getSeconds()).padStart(2,'0');
}
function updateQuoteStatus() {
  const el = $('#quote-status');
  if (!el) return;
  if (S.quoteError && S.lastErrorAt && (!S.lastSuccessAt || S.lastErrorAt > S.lastSuccessAt)) {
    el.innerHTML = '<span style="color:var(--danger)">行情：获取失败，价格可能过期</span> · 最后成功 ' + esc(S.lastSuccessAt || '从未成功');
  } else if (S.lastSuccessAt) {
    el.textContent = '行情 最后成功 ' + S.lastSuccessAt + (S.lastError ? ' (有失败记录)' : '');
  } else {
    el.textContent = '行情：尚未获取';
  }
}
function quoteTimeHint(q) {
  if (!q) return '';
  if (q.market_time) return '行情时间 ' + q.market_time;
  return '行情时间未提供';
}

/* ===== 事实判断（只陈述事实，不出建议） ===== */
function inZone(p, lo, hi) {
  if (lo == null || hi == null || p == null) return false;
  return p >= Math.min(lo, hi) && p <= Math.max(lo, hi);
}
function zoneStr(lo, hi, d) {
  if (lo == null && hi == null) return '—';
  if (lo == null) return '≤ ' + num(hi, d);
  if (hi == null) return '≥ ' + num(lo, d);
  return num(lo, d) + ' – ' + num(hi, d);
}
function priceFacts(price, plan, cur, marketTime) {
  /* v1.0.2 修复：派生事实必须明确行情时间，不得伪装为今天的新事实。
     调用方应传入 q.market_time（来自 Tencent 接口的行情快照时间）。
     未传或无行情时不要伪造"今天"标记。 */
  const facts = [];
  if (price == null || !plan) return facts;
  const d = decOf(cur);
  const fl = plan.first_zone_low, fh = plan.first_zone_high;
  const al = plan.add_zone_low, ah = plan.add_zone_high;
  const ol = plan.odds_zone_low, oh = plan.odds_zone_high;
  const nc = plan.no_chase_price;
  if (inZone(price, ol, oh)) facts.push({ level: 'z3', text: marketTime ? `行情时间 ${marketTime}：价格进入强赔率区` : '当前价格已进入强赔率区' });
  if (inZone(price, al, ah)) facts.push({ level: 'z2', text: marketTime ? `行情时间 ${marketTime}：价格进入加仓区` : '当前价格已进入加仓区' });
  if (inZone(price, fl, fh)) facts.push({ level: 'z1', text: marketTime ? `行情时间 ${marketTime}：价格进入首仓区` : '当前价格已进入首仓区' });
  if (nc != null && price > nc) facts.push({ level: 'danger', text: marketTime ? `行情时间 ${marketTime}：价格已超过不追价（${num(nc, d)}）` : `当前价格已超过不追价（${num(nc, d)}）` });
  if (fl != null && fh != null && !inZone(price, fl, fh)) {
    if (price > fh) facts.push({ level: 'muted', text: '高于首仓区上限 ' + ((price / fh - 1) * 100).toFixed(1) + '%' });
    else if (price < fl && !inZone(price, al, ah) && !inZone(price, ol, oh))
      facts.push({ level: 'muted', text: '低于首仓区下限，距首仓区需上涨 ' + ((fl / price - 1) * 100).toFixed(1) + '%' });
  }
  return facts;
}
function wallTriggered(r) { return (r && r.wall_conditions || []).some(w => w.triggered); }
function wallSummary(r) {
  const ws = (r && r.wall_conditions) || [];
  if (!ws.length) return '—';
  const n = ws.filter(w => w.triggered).length;
  return n ? '触发 ' + n + ' 项' : '未触发';
}
function validationSummary(r) {
  const vs = (r && r.core_validations) || [];
  if (!vs.length) return '—';
  const worse = vs.filter(v => v.status === '已恶化').length;
  const proven = vs.filter(v => v.status === '已验证').length;
  if (worse) return '有 ' + worse + ' 项恶化';
  if (proven) return vs.length + ' 项跟踪中 · ' + proven + ' 项已验证';
  return '无变化（' + vs.length + ' 项跟踪中）';
}
function attention(sec) {
  const flags = [];
  const q = quoteOf(sec);
  const price = q ? q.current : null;
  const marketTime = q ? q.market_time : null;
  // v1.0.6 修复：stale 行情的派生事实（z1/z2/z3/danger）不得进入"需要处理"
  // 队列——它不是本次新变化，是历史缓存。但用户人工录入的事实
  // （status=可交易、危墙触发、核心验证项恶化）不依赖行情，必须保留。
  const isStale = q && q.is_stale === true;
  if (!isStale) {
    (priceFacts(price, sec.plan || {}, sec.currency, marketTime) || []).forEach(f => {
      if (f.level !== 'muted') flags.push(f.text);
    });
  }
  if (sec.status === '可交易') flags.push('状态已为可交易，等待执行下一动作');
  ((sec.research && sec.research.wall_conditions) || []).forEach(w => { if (w.triggered) flags.push('危墙触发：' + w.content); });
  ((sec.research && sec.research.core_validations) || []).forEach(v => { if (v.status === '已恶化') flags.push('验证项恶化：' + v.content); });
  return flags;
}
function realPosPct(sec, position) {
  // v1.0.1：直接使用后端算好的 position_pct（HKD 已含汇率换算）。
  // 缺汇率 / 缺账户规模时由后端返回 null，这里不二次计算。
  if (!position) return null;
  return position.position_pct;  // null / number，由后端决定
}

/* ===== 数据加载 ===== */
async function loadAll() {
  const [secs, archived, st] = await Promise.all([
    api('/api/securities'), api('/api/securities/archived'), api('/api/settings')]);
  S.secs = secs;
  S.archived = archived;
  S.settings = st;
}
async function afterMutation() {
  await loadAll();
  await refreshQuotes();
  await render();
}

/* ===== 路由 ===== */
function routeInfo() {
  const h = location.hash || '#/home';
  const m = h.match(/^#\/s\/(\d+)$/);
  if (m) return { page: 'detail', id: Number(m[1]) };
  if (h === '#/list') return { page: 'list' };
  if (h === '#/new') return { page: 'new' };
  if (h === '#/import' || h === '#/import/research' || h === '#/import/execution') {
    if (h === '#/import/research') return { page: 'import', mode: 'full' };
    if (h === '#/import/execution') return { page: 'import', mode: 'execution' };
    return { page: 'import', mode: 'landing' };
  }
  return { page: 'home' };
}
function setActiveNav(page) {
  document.querySelectorAll('.rail-nav a, .topbar nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.nav === page);
  });
}
async function render() {
  const r = routeInfo();
  setActiveNav(r.page === 'detail' ? 'list' : r.page);
  const el = $('#app');
  try {
    if (r.page === 'home') renderHome(el);
    else if (r.page === 'list') renderList(el);
    else if (r.page === 'new') renderNew(el);
    else if (r.page === 'import') renderImportPanel(el, r.mode);
    else await renderDetail(el, r.id);
  } catch (e) {
    el.innerHTML = '<div class="empty">页面加载失败：' + esc(e.message) + '</div>';
  }
}

/* ===== 首页：今日工作台 ===== */
/* v1.0.4 修复：删除"通过证券名称或代码猜测 fixture"的逻辑。
   真实标的（恰好命中 fixture 名称/代码）不得被误判为示例数据。
   开发 fixture 如需提示，仅允许依据显式 fixture 标志（schema 字段或 settings 标志），
   当前未引入该字段，直接取消该提示机制。
   旧函数保留为空 stub 以保持潜在的外部引用不报错。 */
function isFixtureSeedPresent() { return false; }
function showSampleNoticeIfFixturePresent() { return ''; }
function dismissSample() { /* no-op for v1.0.4 */ }
function sampleBanner() { return ''; }

function cardHtml(s) {
  const q = quoteOf(s);
  const d = decOf(s.currency);
  const plan = s.plan || {};
  const facts = priceFacts(q ? q.current : null, plan, s.currency, q ? q.market_time : null);
  // v1.0.6：stale 行情下的派生事实不应作为"主事实"显示，避免误导
  const visibleFacts = (q && q.is_stale) ? [] : facts;
  const mainFact = visibleFacts.find(f => f.level !== 'muted') || visibleFacts[0];
  const flags = attention(s);
  // v1.0.3：同时展示"静态价格位置"+"最新动态执行判断"（互不混淆）
  const staticPos = staticPositionLabel(plan, q ? q.current : null, s.currency);
  const exec = execLatestLine(s);
  // v1.0.6：stale 行情明确标记"上次成功行情 + 本次刷新未成功"
  const staleBanner = (q && q.is_stale)
    ? `<div class="card-line" style="color:var(--warn);font-size:12px"><span>行情状态</span><b>上次成功行情 · 本次刷新未成功</b></div>`
    : '';
  return `<div class="card" onclick="location.hash='#/s/${s.id}'">
    <div class="card-top">
      <div><div class="card-name">${esc(s.name)}</div><div class="card-code">${esc(s.code)}.${esc(s.exchange)} · ${esc(s.sector || '')}</div></div>
      ${statusBadge(s.status)}
    </div>
    <div class="card-price">${q ? curSym(s.currency) + ' ' + num(q.current, d) : '暂无行情'}
      ${q ? `<span class="chg ${q.change_pct >= 0 ? 'up' : 'down'}">${q.change_pct >= 0 ? '+' : ''}${num(q.change_pct, 2)}%</span>` : ''}
    </div>
    <div class="card-quote-time muted">${q ? esc(quoteTimeHint(q)) : '尚未获取行情'}</div>
    ${staleBanner}
    <div class="card-fact">${mainFact ? esc(mainFact.text) : (q && q.is_stale ? '价格事实暂缓（行情未刷新）' : '暂无价格事实')}</div>
    <div class="card-line"><span>静态位置</span><b>${esc(staticPos)}</b></div>
    <div class="card-line"><span>动态执行</span><b>${exec.view}</b></div>
    ${exec.keyLevels ? `<div class="card-line"><span>当前关键位置</span><b style="white-space:normal">${exec.keyLevels}</b></div>` : ''}
    ${exec.condition ? `<div class="card-line"><span>等待条件</span><b style="white-space:normal">${exec.condition}</b></div>` : ''}
    ${exec.updated ? `<div class="muted" style="font-size:12px;margin-top:4px">${exec.updated}</div>` : ''}
    <div class="card-line"><span>首仓区</span><b>${zoneStr(plan.first_zone_low, plan.first_zone_high, d)}</b></div>
    <div class="card-line"><span>下一动作</span><b>${esc(plan.next_action || '—')}</b></div>
    <div class="card-line"><span>核心验证项</span><b>${esc(validationSummary(s.research))}</b></div>
    <div class="card-line"><span>危墙</span><b class="${wallTriggered(s.research) ? 'txt-danger' : ''}">${esc(wallSummary(s.research))}</b></div>
    ${flags.length ? `<div class="chips">${flags.map(f => `<span class="chip ${/危墙|恶化|不追价/.test(f) ? 'danger' : 'hot'}">${esc(f)}</span>`).join('')}</div>` : ''}
  </div>`;
}

function rowHtml(s) {
  const q = quoteOf(s);
  const d = decOf(s.currency);
  const plan = s.plan || {};
  return `<tr onclick="location.hash='#/s/${s.id}'">
    <td><span class="tname">${esc(s.name)}</span><span class="tcode">${esc(s.code)}.${esc(s.exchange)}</span></td>
    <td>${statusBadge(s.status)}</td>
    <td class="muted">${esc((s.research && s.research.research_pool) || '—')}</td>
    <td>${q ? curSym(s.currency) + ' ' + num(q.current, d) : '—'}</td>
    <td class="${q ? (q.change_pct >= 0 ? 'up' : 'down') : ''}">${q ? (q.change_pct >= 0 ? '+' : '') + num(q.change_pct, 2) + '%' : '—'}</td>
    <td style="white-space:normal;max-width:340px;overflow:hidden;text-overflow:ellipsis">${esc(plan.next_action || '—')}</td>
    <td>${wallTriggered(s.research) ? '<span class="txt-danger">危墙触发</span>' : attention(s).length ? '<span style="color:var(--warn)">有变化</span>' : '<span class="muted">—</span>'}</td>
  </tr>`;
}

/* ===== 静态位置事实（执行层辅助） =====
   返回卡片要展示的"静态位置"短句，从已录入的 trade_plans + 当前价派生。
   与 execution_view 严格分离：这是事实判断（价格与赔率区间的关系），
   不构成买卖建议。
*/
function staticPositionLabel(plan, price, cur) {
  const d = decOf(cur);
  const fl = plan.first_zone_low, fh = plan.first_zone_high;
  const al = plan.add_zone_low, ah = plan.add_zone_high;
  const ol = plan.odds_zone_low, oh = plan.odds_zone_high;
  const nc = plan.no_chase_price;
  if (price == null) return '暂无价格事实';
  if (inZone(price, ol, oh)) return '强赔率区';
  if (inZone(price, al, ah)) return '加仓区';
  if (inZone(price, fl, fh)) return '首仓区';
  if (nc != null && price > nc) return '已超过不追价';
  if (fl != null && fh != null) {
    if (price > fh) return '首仓区上方（高于上限）';
    return '首仓区下方（未进入）';
  }
  return '暂无价格事实';
}

/* ===== v1.0.3 动态执行层渲染（详情页 + 首页） ===== */
function execLatestLine(s) {
  // s.execution_latest = {execution_date, price_snapshot, support_zone, resistance_zone, technical_structure, execution_view, execution_condition, reason, created_at}
  const e = s.execution_latest;
  if (!e) {
    return {
        view: '尚未形成动态执行判断',
        viewSub: '',
        keyLevels: '',
        condition: '',
        updated: '',
        empty: true,
      };
  }
  const curSymLocal = curSym(s.currency);
  const priceLine = e.price_snapshot != null
    ? `${curSymLocal} ${num(e.price_snapshot, decOf(s.currency))}`
    : '—';
  const supLine = e.support_zone ? '当前支撑：' + esc(e.support_zone) : '';
  const resLine = e.resistance_zone ? '当前压力：' + esc(e.resistance_zone) : '';
  const keyLevels = [supLine, resLine].filter(Boolean).join(' · ');
  return {
    view: esc(e.execution_view || '—'),
    viewSub: e.execution_date ? '判断日期：' + esc(e.execution_date) + ' · 判断时价格：' + priceLine : '',
    keyLevels,
    condition: e.execution_condition ? '等待条件：' + esc(e.execution_condition) : '',
    structure: e.technical_structure ? '当前技术结构：' + esc(e.technical_structure) : '',
    reason: e.reason ? '本次依据：' + esc(e.reason) : '',
    updated: '执行判断更新于 ' + esc(e.created_at || ''),
    empty: false,
  };
}

function renderHome(el) {
  const attn = S.secs.filter(s => attention(s).length > 0);
  const rest = S.secs.filter(s => !attention(s).length);
  // v1.0.2：仅当存在 fixture 示例数据（美图/道通）时才显示提示，
  // 真实用户创建的第一只股票不再附带此提示。
  const banner = showSampleNoticeIfFixturePresent();
  el.innerHTML = `
    ${banner}
    <div class="section-title"><h2>需要处理</h2><span class="sub muted">${attn.length ? attn.length + ' 个标的存在值得处理的变化' : '当前没有需要处理的标的'}</span></div>
    ${attn.length ? `<div class="cards">${attn.map(cardHtml).join('')}</div>` : '<div class="empty">今天没有需要处理的变化。</div>'}
    <div class="section-title"><h2>继续跟踪</h2><span class="sub muted">${rest.length} 个标的，暂无需处理的变化</span></div>
    ${rest.length ? `<div class="cards">${rest.map(cardHtml).join('')}</div>` : ''}
  `;
}

function renderList(el) {
  el.innerHTML = `
    <div class="section-title"><h2>标的库</h2><span class="sub muted">共 ${S.secs.length} 个标的</span></div>
    ${S.secs.length ? `<div class="table-wrap"><table>
      <thead><tr><th>标的</th><th>交易状态</th><th>研究池</th><th>当前价</th><th>涨跌</th><th>下一动作</th><th>变化</th></tr></thead>
      <tbody>${S.secs.map(rowHtml).join('')}</tbody>
    </table></div>` : '<div class="empty">暂无标的，请前往「导入与更新」通过 JSON 导入。</div>'}
  `;
}

/* ===== 详情页 ===== */
async function renderDetail(el, id) {
  const d = await api('/api/securities/' + id);
  const s = d.security, r = d.research, p = d.plan || {}, pos = d.position;
  const q = quoteOf(s);
  const cdec = decOf(s.currency);
  const price = q ? q.current : null;

  let ahHtml = '';
  if (s.ah_link_id) {
    // 关联标的可能已被归档（不在 S.secs 里）—— 两处都查，否则关联说明会凭空消失。
    const inActive = S.secs.find(x => x.id === s.ah_link_id);
    const o = inActive || (S.archived || []).find(x => x.id === s.ah_link_id);
    if (o) ahHtml = ` · A/H 关联：<a href="#/s/${o.id}">${esc(o.name)}（${esc(o.code)}.${esc(o.exchange)}）</a>${inActive ? '' : '（已归档）'}`;
  }

  /* 价格区间事实 */
  const factIn = (lo, hi) => inZone(price, lo, hi) ? '当前价在其中' : '';
  const factOver = (nc) => (nc != null && price != null && price > nc) ? '当前价已超过' : '';
  const zone = (label, lo, hi, cls, fact) => `
    <div class="zone ${cls || ''}">
      <span>${label}</span><b>${zoneStr(lo, hi, cdec)}</b><i>${esc(fact || '')}</i>
    </div>`;

  /* 持仓 */
  let posHtml;
  const realPct = realPosPct(s, pos);
  // v1.0.1+：market_value / market_value_currency 由后端 compute_position 计算
  // v1.0.2：HKD 盈亏标注 HKD，CNY 标注 CNY；折算后持仓市值统一标 CNY（带汇率标记）
  if (pos && pos.quantity > 0) {
    const q = quoteOf(s);
    const price = q ? q.current : null;
    const curSymLocal = curSym(s.currency);
    // v1.0.2：浮动盈亏按原币种展示，clear currency unit
    const upnl = price != null ? (price - pos.avg_cost) * pos.quantity : null;
    const upct = price != null && pos.avg_cost ? (price / pos.avg_cost - 1) * 100 : null;
    let mvDisplay;
    if (pos.market_value != null) {
      mvDisplay = `¥ ${num(pos.market_value, 0)}`;
    } else if (s.currency === 'HKD' && pos.fx_rate_missing) {
      mvDisplay = '无法计算 / 待汇率';
    } else if (!price) {
      mvDisplay = '—（无当前价）';
    } else {
      mvDisplay = '—';
    }
    let pctDisplay, pctHint;
    if (realPct != null) {
      pctDisplay = num(realPct, 1) + '%';
      pctHint = '目标 ' + num(p.target_position_pct, 1) + '%';
    } else if (!S.settings.account_size_cny) {
      pctDisplay = '—';
      pctHint = '未设置账户规模（设置入口在右上）';
    } else if (s.currency === 'HKD' && pos.fx_rate_missing) {
      pctDisplay = '无法计算';
      pctHint = '请在设置中填 HKD→CNY 汇率';
    } else {
      pctDisplay = '—';
      pctHint = '缺少必要输入';
    }
    posHtml = `
      <div class="pos-grid">
        <div class="zone"><span>持仓数量</span><b>${num(pos.quantity, 0)} 股</b><i></i></div>
        <div class="zone"><span>摊薄成本（原币）</span><b>${curSymLocal} ${num(pos.avg_cost, cdec)}</b><i>${esc(s.currency)}</i></div>
        <div class="zone"><span>持仓市值${pos.market_value_currency ? '（已折算）' : ''}</span><b>${mvDisplay}</b><i>${pos.market_value_currency ? esc(pos.market_value_currency) : (s.currency === 'HKD' ? '原币 HK$ ' + num(price ? price * pos.quantity : 0, 0) : '原币 ¥ ' + num(price ? price * pos.quantity : 0, 0))}</i></div>
        <div class="zone"><span>浮动盈亏（原币 · ${esc(s.currency)}）</span><b class="${upnl != null ? (upnl >= 0 ? 'up' : 'down') : ''}">${upnl != null ? (upnl >= 0 ? '+' : '') + num(upnl, 0) + (upct != null ? '（' + (upct >= 0 ? '+' : '') + num(upct, 2) + '%）' : '') : '—'}</b><i>${esc(s.currency)}</i></div>
        <div class="zone"><span>已实现盈亏（原币 · ${esc(s.currency)}）</span><b class="${pos.realized_pnl >= 0 ? 'up' : 'down'}">${pos.realized_pnl >= 0 ? '+' : ''}${num(pos.realized_pnl, 0)}</b><i>${esc(s.currency)}</i></div>
        <div class="zone"><span>真实仓位（折算为 CNY）</span><b>${pctDisplay}</b><i>${pctHint}</i></div>
      </div>`;
  } else {
    posHtml = `<div class="empty">当前无真实持仓（计划目标仓位 ${num(p.target_position_pct, 1)}%）。交易计划与真实持仓分开管理。</div>`;
  }

  // 持仓/状态一致性提示（不自动改状态）
  const pc = d.position_consistency;
  let pcBanner = '';
  if (pc && pc.issues && pc.issues.length) {
    pcBanner = pc.issues.map(it => `
      <div class="banner warn">
        <span class="banner-tag">${esc(it.level === 'danger' ? '严重' : '提示')}</span>
        <span>${esc(it.message)}</span>
        <span class="muted">本系统不自动调整 status，请人工复核。</span>
      </div>`).join('');
  }

  const valList = (r && r.core_validations) || [];
  const wallList = (r && r.wall_conditions) || [];
  const vTag = v => v.status === '已恶化' ? '<span class="tag worse">已恶化</span>' : v.status === '已验证' ? '<span class="tag proven">已验证</span>' : '<span class="tag track">跟踪中</span>';
  const wTag = w => w.triggered ? '<span class="tag fired">已触发</span>' : '<span class="tag safe">未触发</span>';

  const tl = (d.ledger || []).map(e => `
    <div class="tl-item">
      <div class="tl-date">${esc(e.event_date)}</div>
      <div class="tl-body">
        <div class="tl-sum"><span class="tl-type ${esc(e.event_type)}">${esc(e.event_type)}</span>${esc(e.summary)}</div>
        ${e.reason ? `<div class="tl-reason">原因：${esc(e.reason)}</div>` : ''}
        <div class="tl-meta">记录于 ${esc(e.created_at)}</div>
      </div>
    </div>`).join('');

  const hist = (list, title, fmt) => list.length <= 1 ? '' : `
    <details class="hist"><summary>${title}（共 ${list.length} 个版本）</summary>
      <div class="hist-body">${list.slice(1).map(fmt).join('')}</div>
    </details>`;
  const rh = hist(d.research_history || [], '研究结论历史', v => `
    <div class="kv"><span class="w">v${v.version} · ${esc(v.created_at || '')}</span></div>
    <div class="kv"><span class="w">研究池</span>${esc(v.research_pool || '—')}</div>
    <div class="kv"><span class="w">一句话逻辑</span>${esc(v.one_liner || '—')}</div>
    ${v.change_note ? `<div class="kv"><span class="w">修改说明</span>${esc(v.change_note)}</div>` : ''}<hr>`);
  const ph = hist(d.plan_history || [], '交易计划历史', v => `
    <div class="kv"><span class="w">v${v.version} · ${esc(v.created_at || '')}</span></div>
    <div class="kv"><span class="w">价格区间</span>首仓 ${zoneStr(v.first_zone_low, v.first_zone_high, cdec)} · 加仓 ${zoneStr(v.add_zone_low, v.add_zone_high, cdec)} · 强赔率 ${zoneStr(v.odds_zone_low, v.odds_zone_high, cdec)} · 不追价 ${v.no_chase_price != null ? num(v.no_chase_price, cdec) : '—'}</div>
    <div class="kv"><span class="w">目标 / 动作</span>${num(v.target_position_pct, 1)}% · ${esc(v.next_action || '—')}</div>
    ${v.change_note ? `<div class="kv"><span class="w">修改说明</span>${esc(v.change_note)}</div>` : ''}<hr>`);

  const trades = (d.trades || []).map(t => `
    <tr><td>${esc(t.trade_date)}</td><td class="${t.side === '买入' ? 'up' : 'down'}">${esc(t.side)}</td>
    <td>${num(t.price, cdec)}</td><td>${num(t.quantity, 0)}</td><td>${num(t.fee, 2)}</td>
    <td style="white-space:normal">${esc(t.note || '')}</td></tr>`).join('');

  el.innerHTML = `
    <a class="back" href="#/list">← 标的库</a>
    ${pcBanner || ''}
    <div class="dhead">
      <div>
        <div class="dname">${esc(s.name)} ${statusBadge(s.status)}</div>
        <div class="dsub">${esc(s.code)}.${esc(s.exchange)} · ${esc(s.market)} · 结算货币 ${esc(s.currency)} · ${esc(s.sector || '未分类')}${ahHtml}</div>
        <div class="dsub muted" style="margin-top:8px">
          研究池：${esc((r && r.research_pool) || '—')} ｜ 最近研究：${esc((r && r.research_date) || '—')}
        </div>
        <div class="dsub muted" style="margin-top:6px">
          ${q ? esc(quoteTimeHint(q)) + (S.lastErrorAt && (!S.lastSuccessAt || S.lastErrorAt > S.lastSuccessAt) ? ' · <span style="color:var(--danger)">行情获取失败，价格可能过期</span>' : '') : '尚未获取行情'}
        </div>
      </div>
      <div class="dhead-right">
        <div class="dprice">${q ? curSym(s.currency) + ' ' + num(q.current, cdec) : '暂无行情'}
          ${q ? `<span class="chg ${q.change_pct >= 0 ? 'up' : 'down'}">${q.change >= 0 ? '+' : ''}${num(q.change, cdec)}（${q.change_pct >= 0 ? '+' : ''}${num(q.change_pct, 2)}%）</span>` : ''}
        </div>
        <div class="dbtns">
          <button class="btn sm" onclick="openStatusModal(${s.id})">变更状态</button>
          <button class="btn sm ghost" onclick="openBasicModal(${s.id})">编辑信息</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h3>一句话逻辑</h3><button class="btn sm ghost" onclick="openResearchModal(${s.id})">更新研究结论</button></div>
      <div class="oneliner">${esc((r && r.one_liner) || '尚未录入研究结论。')}</div>
      ${(r && r.positive_changes) ? `<div class="kv"><span class="w">正向变化</span>${esc(r.positive_changes)}</div>` : ''}
      ${(r && r.report_link) ? `<div class="kv"><span class="w">研究报告</span><a href="${esc(sanitizeUrl(r.report_link))}" target="_blank" rel="noopener noreferrer">${esc(r.report_link)}</a></div>` : ''}
    </div>

    <div class="panel">
      <div class="panel-head"><h3>交易计划${p.version ? '（v' + p.version + '）' : ''}</h3><button class="btn sm ghost" onclick="openPlanModal(${s.id})">修改计划</button></div>
      <div class="kv"><span class="w">下一动作</span><b>${esc(p.next_action || '—')}</b></div>
      <div class="zones">
        ${zone('首仓区', p.first_zone_low, p.first_zone_high, inZone(price, p.first_zone_low, p.first_zone_high) ? 'hit' : '', factIn(p.first_zone_low, p.first_zone_high))}
        ${zone('加仓区', p.add_zone_low, p.add_zone_high, inZone(price, p.add_zone_low, p.add_zone_high) ? 'hit' : '', factIn(p.add_zone_low, p.add_zone_high))}
        ${zone('强赔率区', p.odds_zone_low, p.odds_zone_high, inZone(price, p.odds_zone_low, p.odds_zone_high) ? 'hit' : '', factIn(p.odds_zone_low, p.odds_zone_high))}
        ${zone('不追价', p.no_chase_price, null, factOver(p.no_chase_price) ? 'danger' : '', factOver(p.no_chase_price) || '当前价未超过')}
        ${zone('目标仓位', null, null, '', p.target_position_pct != null ? num(p.target_position_pct, 1) + '%' : '')}
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h3>动态执行</h3><button class="btn sm ghost" onclick="openExecutionModal(${s.id})">更新动态执行判断</button></div>
      ${(() => {
        const e = d.execution_latest;
        if (!e) {
          return `<div class="empty">尚未形成动态执行判断。行情变化、技术面变化以及动态执行判断，<b>不会自动修改</b>上方交易计划；下方按钮用于人工录入本次执行判断。</div>`;
        }
        const curSymLocal = curSym(s.currency);
        const priceLine = e.price_snapshot != null ? curSymLocal + ' ' + num(e.price_snapshot, cdec) : '—';
        const histList = (d.execution_history || []).slice(1);
        const histHtml = histList.length ? `
          <details class="hist"><summary>历史执行判断（共 ${d.execution_history.length} 条）</summary>
            <div class="hist-body">${histList.map(h => `
              <div class="kv"><span class="w">${esc(h.execution_date)} · ${esc(h.execution_view)}${h.price_snapshot != null ? ' · ' + curSymLocal + ' ' + num(h.price_snapshot, cdec) : ''}</span></div>
              ${h.support_zone ? `<div class="kv"><span class="w">支撑</span>${esc(h.support_zone)}</div>` : ''}
              ${h.resistance_zone ? `<div class="kv"><span class="w">压力</span>${esc(h.resistance_zone)}</div>` : ''}
              ${h.technical_structure ? `<div class="kv"><span class="w">技术结构</span>${esc(h.technical_structure)}</div>` : ''}
              ${h.execution_condition ? `<div class="kv"><span class="w">等待条件</span>${esc(h.execution_condition)}</div>` : ''}
              ${h.reason ? `<div class="kv"><span class="w">依据</span>${esc(h.reason)}</div>` : ''}
              <div class="kv"><span class="w">记录于</span>${esc(h.created_at || '')}</div>
              <hr>`).join('')}
          </div></details>` : '';
        return `
          <div class="kv"><span class="w">判断日期</span>${esc(e.execution_date)}</div>
          <div class="kv"><span class="w">判断时价格</span>${priceLine}</div>
          ${e.support_zone ? `<div class="kv"><span class="w">当前支撑</span>${esc(e.support_zone)}</div>` : ''}
          ${e.resistance_zone ? `<div class="kv"><span class="w">当前压力</span>${esc(e.resistance_zone)}</div>` : ''}
          ${e.technical_structure ? `<div class="kv"><span class="w">当前技术结构</span><span style="white-space:normal">${esc(e.technical_structure)}</span></div>` : ''}
          <div class="kv"><span class="w">当前执行判断</span><b>${esc(e.execution_view)}</b></div>
          ${e.execution_condition ? `<div class="kv"><span class="w">等待条件</span><span style="white-space:normal">${esc(e.execution_condition)}</span></div>` : ''}
          ${e.reason ? `<div class="kv"><span class="w">本次依据</span><span style="white-space:normal">${esc(e.reason)}</span></div>` : ''}
          <div class="kv muted"><span class="w">执行判断更新于</span>${esc(e.created_at || '')}</div>
          ${histHtml}`;
      })()}
    </div>

    <div class="panel">
      <h3>投资逻辑 · 核心验证项</h3>
      ${valList.length ? `<ul class="vlist">${valList.map(v => `<li>${vTag(v)}<span>${esc(v.content)}</span></li>`).join('')}</ul>` : '<div class="empty" style="margin-top:10px">尚未录入核心验证项。</div>'}
      <h3 style="margin-top:16px">危墙条件</h3>
      ${wallList.length ? `<ul class="vlist">${wallList.map(w => `<li>${wTag(w)}<span class="${w.triggered ? 'txt-danger' : ''}">${esc(w.content)}</span></li>`).join('')}</ul>` : '<div class="empty" style="margin-top:10px">尚未录入危墙条件。</div>'}
    </div>

    <div class="panel">
      <div class="panel-head"><h3>真实持仓（由流水推导）</h3><button class="btn sm primary" onclick="openTradeModal(${s.id})">录入交易流水</button></div>
      ${posHtml}
      ${(d.trades || []).length ? `<div class="table-wrap" style="margin-top:14px"><table>
        <thead><tr><th>日期</th><th>方向</th><th>价格</th><th>数量</th><th>费用</th><th>备注</th></tr></thead>
        <tbody>${trades}</tbody></table></div>` : ''}
    </div>

    <div class="panel">
      <div class="panel-head"><h3>决策台账（append-only，保留当时的判断）</h3><button class="btn sm ghost" onclick="openNoteModal(${s.id})">添加记录</button></div>
      ${tl ? `<div class="timeline">${tl}</div>` : '<div class="empty">暂无记录。</div>'}
      ${rh}${ph}
    </div>
    ${s.notes ? `<div class="panel"><h3>备注</h3><div class="muted" style="font-size:13px">${esc(s.notes)}</div></div>` : ''}
  `;
  window.scrollTo(0, 0);
}

/* ===== 新建标的 ===== */
const fld = (label, inner, req) => `<label class="f"><span>${label}${req ? ' *' : ''}</span>${inner}</label>`;

function rowsEditorHtml(items, mode) {
  items = items || [];
  const rows = (items.length ? items : [{}]).map(it => rowHtml2(it, mode)).join('');
  return `<div class="ledit" id="ledit-${mode}">${rows}</div>
    <button type="button" class="btn sm ghost" onclick="addRow('${mode}')">＋ 添加一行</button>`;
}
function rowHtml2(it, mode) {
  if (mode === 'val') {
    const st = it.status || '跟踪中';
    return `<div class="lrow">
      <input class="lrow-c" placeholder="例如：订阅收入同比增速维持在 20% 以上" value="${esc(it.content || '')}">
      <select class="lrow-s">${['跟踪中', '已验证', '已恶化'].map(x => `<option${x === st ? ' selected' : ''}>${x}</option>`).join('')}</select>
      <button type="button" class="btn sm danger" onclick="this.parentNode.remove()">✕</button></div>`;
  }
  return `<div class="lrow">
    <input class="lrow-c" placeholder="例如：订阅增速连续两个季度明显下滑" value="${esc(it.content || '')}">
    <label class="lrow-t"><input type="checkbox" class="lrow-s"${it.triggered ? ' checked' : ''}>已触发</label>
    <button type="button" class="btn sm danger" onclick="this.parentNode.remove()">✕</button></div>`;
}
function addRow(mode) {
  const el = document.getElementById('ledit-' + mode);
  if (el) el.insertAdjacentHTML('beforeend', rowHtml2({}, mode));
}
function collectRows(mode) {
  const root = document.getElementById('ledit-' + mode);
  if (!root) return [];
  const out = [];
  root.querySelectorAll('.lrow').forEach(r => {
    const c = r.querySelector('.lrow-c').value.trim();
    if (!c) return;
    if (mode === 'val') out.push({ content: c, status: r.querySelector('select.lrow-s').value });
    else out.push({ content: c, triggered: r.querySelector('input.lrow-s').checked });
  });
  return out;
}

function zoneFields(p) {
  p = p || {};
  const z = (name, label) => fld(label, `<input name="${name}" type="number" step="any" value="${p[name] != null ? p[name] : ''}">`);
  return `
    <div class="grid3">
      ${z('first_zone_low', '首仓区 · 下限')}${z('first_zone_high', '首仓区 · 上限')}${z('no_chase_price', '不追价')}
    </div>
    <div class="grid3">
      ${z('add_zone_low', '加仓区 · 下限')}${z('add_zone_high', '加仓区 · 上限')}${z('target_position_pct', '目标仓位（%）')}
    </div>
    <div class="grid3">
      ${z('odds_zone_low', '强赔率区 · 下限')}${z('odds_zone_high', '强赔率区 · 上限')}${fld('下一动作', `<input name="next_action" value="${esc(p.next_action || '')}">`)}
    </div>`;
}
function collectPlan(fd) {
  const out = {};
  ['first_zone_low', 'first_zone_high', 'add_zone_low', 'add_zone_high',
   'odds_zone_low', 'odds_zone_high', 'no_chase_price', 'target_position_pct'].forEach(k => {
    const v = fd.get(k);
    if (v === '' || v == null) { out[k] = null; return; }
    const f = parseFloat(v);
    if (isNaN(f)) throw new Error('「' + k + '」不是有效数字');
    out[k] = f;
  });
  out.next_action = (fd.get('next_action') || '').trim();
  out.change_note = (fd.get('change_note') || '').trim();
  return out;
}
function researchFieldsHtml(r) {
  r = r || {};
  return `
    ${fld('研究池', `<input name="research_pool" value="${esc(r.research_pool || '')}" placeholder="例如：核心优质错配池">`)}
    ${fld('一句话逻辑', `<textarea name="one_liner" required>${esc(r.one_liner || '')}</textarea>`)}
    ${fld('正向价值变化', `<textarea name="positive_changes">${esc(r.positive_changes || '')}</textarea>`)}
    <div class="f"><span>核心验证项（投资逻辑成立需要持续确认的事实）</span>${rowsEditorHtml(r.core_validations, 'val')}</div>
    <div class="f"><span>危墙条件（触发即需重新深穿复核）</span>${rowsEditorHtml(r.wall_conditions, 'wall')}</div>
    <div class="grid2">
      ${fld('研究报告链接', `<input name="report_link" value="${esc(r.report_link || '')}">`)}
      ${fld('最近研究日期', `<input name="research_date" type="date" value="${esc(r.research_date || today())}">`)}
    </div>`;
}
function collectResearch(fd) {
  return {
    research_pool: (fd.get('research_pool') || '').trim(),
    one_liner: (fd.get('one_liner') || '').trim(),
    positive_changes: (fd.get('positive_changes') || '').trim(),
    core_validations: collectRows('val'),
    wall_conditions: collectRows('wall'),
    report_link: (fd.get('report_link') || '').trim(),
    research_date: (fd.get('research_date') || '').trim(),
    change_note: (fd.get('change_note') || '').trim()
  };
}

function renderNew(el) {
  el.innerHTML = `
    <a class="back" href="#/list">← 标的库</a>
    <div class="panel form-panel">
      <h2 style="margin:0 0 6px">新建标的</h2>
      <div class="form-hint">承接深穿结论：先录入研究结论与交易计划，之后工作台持续跟踪。所有字段之后都可以修改（旧版本会保留）。</div>
      <form id="newform">
        <h3>一、基本信息</h3>
        <div class="grid3">
          ${fld('公司名称', `<input name="name" required placeholder="例如：美图公司">`, true)}
          ${fld('证券代码', `<input name="code" required placeholder="A股 6 位 / 港股 5 位数字">`, true)}
          ${fld('交易所', `<select name="exchange"><option value="SH">SH · 上交所</option><option value="SZ">SZ · 深交所</option><option value="HK">HK · 港交所</option></select>`)}
        </div>
        <div class="grid2">
          ${fld('行业 / 主题', `<input name="sector" placeholder="例如：消费 / AI 应用">`)}
          ${fld('初始交易状态', `<select name="status">${STATUSES.map(s => `<option${s === '等价格' ? ' selected' : ''}>${s}</option>`).join('')}</select>`)}
        </div>

        <h3>二、研究结论</h3>
        ${researchFieldsHtml({})}

        <h3>三、交易计划</h3>
        ${zoneFields({})}
        ${fld('计划修改说明（记入台账）', `<input name="change_note" value="初始计划">`)}

        <div class="mfoot">
          <a class="btn ghost" href="#/list">取消</a>
          <button class="btn primary" type="submit">创建标的</button>
        </div>
      </form>
    </div>`;

  $('#newform').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const body = {
        name: (fd.get('name') || '').trim(),
        code: (fd.get('code') || '').trim(),
        exchange: fd.get('exchange'),
        sector: (fd.get('sector') || '').trim(),
        status: fd.get('status'),
        research: collectResearch(fd),
        plan: collectPlan(fd)
      };
      const res = await api('/api/securities', { method: 'POST', body: body });
      toast('标的已创建');
      await afterMutation();
      location.hash = '#/s/' + res.id;
    } catch (err) { /* toast 已提示 */ }
  });
}

/* ===== 弹窗 ===== */
function openModal(title, bodyHTML, onSubmit, submitLabel) {
  const root = $('#modal-root');
  root.innerHTML = `<div class="mask" onclick="if(event.target===this)closeModal()">
    <div class="modal"><h3>${esc(title)}</h3>
      <form id="mform">
        ${bodyHTML}
        <div class="mfoot">
          <button type="button" class="btn ghost" onclick="closeModal()">取消</button>
          <button class="btn primary" type="submit">${esc(submitLabel || '保存')}</button>
        </div>
      </form>
    </div></div>`;
  $('#mform').addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await onSubmit(new FormData(e.target), e.target);
      closeModal();
    } catch (err) { /* toast 已提示，弹窗保留 */ }
  });
  const first = root.querySelector('input,select,textarea');
  if (first) setTimeout(() => first.focus(), 50);
}
function closeModal() { $('#modal-root').innerHTML = ''; }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

function openStatusModal(id) {
  const s = findSec(id); if (!s) return;
  openModal('变更交易状态 · ' + s.name, `
    <div class="grid2">
      ${fld('新状态', `<select name="status">${STATUSES.map(x => `<option value="${esc(x)}"${x === s.status ? ' selected' : ''}>${esc(x)}</option>`).join('')}</select>`)}
      ${fld('生效日期', `<input name="event_date" type="date" value="${today()}">`)}
    </div>
    ${fld('变更原因（必填，永久记入决策台账）', `<textarea name="reason" required placeholder="例如：进入既定首仓区，核心验证项没有恶化"></textarea>`, true)}
  `, async fd => {
    await api(`/api/securities/${id}/status`, {
      method: 'POST',
      body: { status: fd.get('status'), reason: fd.get('reason'), event_date: fd.get('event_date') }
    });
    toast('状态已变更，并记入决策台账');
    await afterMutation();
  });
}

function openBasicModal(id) {
  const s = findSec(id); if (!s) return;
  const others = S.secs.filter(x => x.id !== s.id);
  // 已归档的关联标的必须仍作为候选项保留：它不在 S.secs 里，若只照 S.secs 生成下拉，
  // 浏览器会回落到首项「— 无 —」，用户只是改个行业/备注再保存，就会把 A/H 关联
  // **静默清空**（归档功能引入的回归，实测见 .tmp_v108x/verify/check_ah_link_archive.py）。
  const ahOptions = others.map(o => `<option value="${o.id}"${s.ah_link_id === o.id ? ' selected' : ''}>${esc(o.name)}（${esc(o.code)}.${esc(o.exchange)}）</option>`);
  const linkedArchived = (s.ah_link_id && !others.some(o => o.id === s.ah_link_id))
    ? (S.archived || []).find(x => x.id === s.ah_link_id) : null;
  if (linkedArchived) ahOptions.push(`<option value="${linkedArchived.id}" selected>${esc(linkedArchived.name)}（${esc(linkedArchived.code)}.${esc(linkedArchived.exchange)}）· 已归档</option>`);
  openModal('编辑基本信息 · ' + s.name, `
    ${fld('公司名称', `<input name="name" required value="${esc(s.name)}">`, true)}
    ${fld('行业 / 主题', `<input name="sector" value="${esc(s.sector || '')}">`)}
    ${fld('A/H 两地上市关联', `<select name="ah_link_id"><option value="">— 无 —</option>${ahOptions.join('')}</select>`)}
    ${fld('备注', `<textarea name="notes">${esc(s.notes || '')}</textarea>`)}
  `, async fd => {
    await api(`/api/securities/${id}`, {
      method: 'PUT',
      body: { name: fd.get('name'), sector: fd.get('sector'), notes: fd.get('notes'), ah_link_id: fd.get('ah_link_id') }
    });
    toast('基本信息已更新');
    await afterMutation();
  });
}

function openResearchModal(id) {
  const s = findSec(id); if (!s) return;
  const r = s.research || {};
  openModal('更新研究结论 · ' + s.name + '（生成新版本，旧版保留）', `
    ${researchFieldsHtml(r)}
    ${fld('修改说明（记入台账）', `<input name="change_note" placeholder="例如：中报后更新订阅收入验证项">`)}
  `, async fd => {
    await api(`/api/securities/${id}/research`, { method: 'PUT', body: collectResearch(fd) });
    toast('研究结论已更新至新版本');
    await afterMutation();
  }, '保存为新版本');
}

function openPlanModal(id) {
  const s = findSec(id); if (!s) return;
  openModal('修改交易计划 · ' + s.name + '（生成新版本，旧版保留）', `
    ${zoneFields(s.plan || {})}
    ${fld('修改说明（记入台账）', `<input name="change_note" placeholder="例如：中报后估值中枢变化，上调首仓区">`)}
  `, async fd => {
    await api(`/api/securities/${id}/plan`, { method: 'PUT', body: collectPlan(fd) });
    toast('交易计划已更新至新版本');
    await afterMutation();
  }, '保存为新版本');
}

function openTradeModal(id) {
  const s = findSec(id); if (!s) return;
  const pos = s.position || {};
  openModal('录入交易流水 · ' + s.name, `
    <div class="grid3">
      ${fld('日期', `<input name="trade_date" type="date" value="${today()}">`)}
      ${fld('方向', `<select name="side"><option>买入</option><option>卖出</option></select>`)}
      ${fld('价格（' + esc(s.currency) + '）', `<input name="price" type="number" step="any" required>`, true)}
    </div>
    <div class="grid3">
      ${fld('数量（股）', `<input name="quantity" type="number" step="any" required>`, true)}
      ${fld('费用', `<input name="fee" type="number" step="any" value="0">`)}
      ${fld('备注', `<input name="note">`)}
    </div>
    <div class="form-hint">当前持仓：${pos.quantity ? num(pos.quantity, 0) + ' 股，摊薄成本 ' + num(pos.avg_cost, decOf(s.currency)) : '无'}。持仓完全由流水推导，流水录入后不可修改（append-only）。</div>
  `, async fd => {
    await api(`/api/securities/${id}/trades`, {
      method: 'POST',
      body: {
        trade_date: fd.get('trade_date'), side: fd.get('side'),
        price: fd.get('price'), quantity: fd.get('quantity'),
        fee: fd.get('fee'), note: fd.get('note')
      }
    });
    toast('交易流水已录入');
    await afterMutation();
  });
}

function openNoteModal(id) {
  const s = findSec(id); if (!s) return;
  openModal('添加决策记录 · ' + s.name, `
    ${fld('日期', `<input name="event_date" type="date" value="${today()}">`)}
    ${fld('记录内容（必填）', `<textarea name="summary" required placeholder="例如：今日进入首仓区但选择继续等待，原因是……"></textarea>`, true)}
    ${fld('补充说明', `<textarea name="reason"></textarea>`)}
  `, async fd => {
    await api(`/api/securities/${id}/ledger`, {
      method: 'POST',
      body: { event_date: fd.get('event_date'), summary: fd.get('summary'), reason: fd.get('reason') }
    });
    toast('记录已写入决策台账');
    await afterMutation();
  });
}

async function openExecutionModal(id) {
  const s = findSec(id); if (!s) return;
  // v1.0.4 修复：走真实详情接口，避免依赖首页 S.secs 中可能缺失/陈旧的 execution_latest
  // （list_securities() 链路此时已包含 execution_latest，但以详情接口为权威口径）
  const detail = await api(`/api/securities/${id}`);
  const prev = (detail && detail.execution_latest) || {};
  // v1.0.5：execution_date 默认 = today()。新判断记录当前时点的判断，
  // 与上一条历史判断的日期无关——上一条仍可在历史列表中按其原日期查阅。
  // 6 项内容（execution_view / support_zone / resistance_zone / technical_structure /
  // execution_condition / reason）继续从 prev 继承，方便"在上一判断基础上微调"。
  const todayVal = today();
  // 预填判断时价格 = 当前行情（如有）。只预填，不持久化到 execution_view。
  let prePrice = '';
  const q = quoteOf(s);
  if (q && q.current != null) prePrice = q.current;
  // 上一次执行判断的视图文本原样预填（任意非空文本，包括白名单外自定义文本）。
  const prevViewRaw = prev.execution_view || '';
  openModal('更新动态执行判断 · ' + s.name, `
    <div class="form-hint" style="margin-bottom:10px">
      静态交易计划决定"什么价格值得交易"；动态执行层记录<b>当前是否适合执行</b>的人工判断。<br>
      行情刷新<b>不会自动</b>改写此处的判断；每次提交将作为一条新记录永久保留（append-only）。<br>
      判断日期默认为今天（不继承上一条日期）；6 项内容继承上一条便于微调。
    </div>
    ${fld('判断日期', `<input name="execution_date" type="date" value="${esc(todayVal)}" required>`, true)}
    <div class="grid2">
      ${fld('判断时价格（' + esc(s.currency) + '）', `<input name="price_snapshot" type="number" step="any" value="${prePrice}">`)}
      ${fld('当前执行判断（自由文本）',
        `<input name="execution_view" list="execution-view-suggest" value="${esc(prevViewRaw)}" required placeholder="可以是任意文本，常用：等待技术确认 / 可以开始执行 / 暂缓执行 / 继续观察">
         <datalist id="execution-view-suggest">${EXECUTION_VIEWS.map(v => `<option value="${esc(v)}">`).join('')}</datalist>`,
        true)}
    </div>
    <div class="grid2">
      ${fld('当前支撑区（自由文本）', `<input name="support_zone" value="${esc(prev.support_zone || '')}" placeholder="例如：4.18–4.22 / 前低附近">`)}
      ${fld('当前压力区（自由文本）', `<input name="resistance_zone" value="${esc(prev.resistance_zone || '')}" placeholder="例如：4.30–4.35 / 4.43–4.50">`)}
    </div>
    ${fld('当前技术结构', `<textarea name="technical_structure" placeholder="例如：连续下跌，已到前期支撑区，但尚未确认止跌">${esc(prev.technical_structure || '')}</textarea>`)}
    ${fld('等待条件（接下来等待什么）', `<textarea name="execution_condition" placeholder="例如：观察4.20附近承接以及能否重新收回4.30–4.35">${esc(prev.execution_condition || '')}</textarea>`)}
    ${fld('本次判断依据', `<textarea name="reason" placeholder="例如：已进入静态首仓赔率区，但短线仍处于下跌结构">${esc(prev.reason || '')}</textarea>`)}
  `, async fd => {
    const body = {
      execution_date: fd.get('execution_date'),
      price_snapshot: fd.get('price_snapshot'),
      support_zone: fd.get('support_zone'),
      resistance_zone: fd.get('resistance_zone'),
      technical_structure: fd.get('technical_structure'),
      execution_condition: fd.get('execution_condition'),
      execution_view: fd.get('execution_view'),
      reason: fd.get('reason'),
    };
    await api(`/api/securities/${id}/execution`, { method: 'POST', body });
    toast('动态执行判断已新增一条');
    await afterMutation();
  }, '新增判断（保留旧记录）');
}

function openSettingsModal() {
  openModal('设置', `
    ${fld('账户总规模（元，CNY，用于计算真实仓位占比）', `<input name="account_size_cny" type="number" step="any" value="${esc(S.settings.account_size_cny || '')}" placeholder="例如：1000000">`)}
    ${fld('港元兑人民币汇率（HKD→CNY）', `<input name="hkd_cny_rate" type="number" step="any" value="${esc(S.settings.hkd_cny_rate || '')}" placeholder="例如：0.92">`)}
    <div class="form-hint">真实仓位 = 持仓市值（港股按上述汇率折算）÷ 账户总规模。该数字仅用于展示事实，不影响任何判断。<br>
    v1.0.2 起不再提供任何默认值；未填时港股持仓市值与真实仓位显示"无法计算"。</div>
  `, async fd => {
    S.settings = await api('/api/settings', {
      method: 'PUT',
      body: { account_size_cny: fd.get('account_size_cny'), hkd_cny_rate: fd.get('hkd_cny_rate') }
    });
    toast('设置已保存');
    render();
  });
}

/* ===== 导入与更新（v1.0.7 新增，v1.0.8 强化） ===== */
const Import = {
  mode: null,       // 'landing' / 'full' / 'execution'
  step: 'paste',    // 'paste' / 'preview' / 'done'
  pasteText: '',
  preview: null,    // preview_import_* 返回值
  commit: null,     // commit_import_* 返回值
  parseError: '',
  // v1.0.8：状态确认只存在于前端内存，绝不写回粘贴 JSON。
  // 数组元素是 securities[] 的下标；commit 时作为 confirmed_status_changes 单独提交。
  confirmedStatus: [],
  // v1.0.9：commit 请求进行中标记。点击"确认并写入"后置 True，
  // 按钮立即 disabled 并显示"正在写入…"，请求返回前不再发送第二次请求；
  // 失败/成功后复位。仅为 UI 防误操作，服务端另有 in_flight 原子 claim。
  committing: false,
};
function setImportState(patch) {
  Object.assign(Import, patch);
  render();
}
function resetImport() {
  Import.mode = null;
  Import.step = 'paste';
  Import.pasteText = '';
  Import.preview = null;
  Import.commit = null;
  Import.parseError = '';
  Import.confirmedStatus = [];
}

function renderImportPanel(el, mode) {
  if (!Import.mode && location.hash === '#/import') {
    Import.mode = 'landing';
  } else if (Import.mode && mode !== 'landing' && Import.mode !== mode) {
    // hash 切回 /resetImport 行为：保持当前 mode
  }
  // 切到 /import 入口选择页
  if (location.hash === '#/import' || mode === 'landing') {
    Import.mode = 'landing';
    return renderImportLanding(el);
  }
  if (mode === 'full') {
    return Import.step === 'preview' ? renderImportFullPreview(el)
         : Import.step === 'done'   ? renderImportFullDone(el)
         : renderImportFullPaste(el);
  }
  if (mode === 'execution') {
    return Import.step === 'preview' ? renderImportExecPreview(el)
         : Import.step === 'done'   ? renderImportExecDone(el)
         : renderImportExecPaste(el);
  }
  renderImportLanding(el);
}

function importGo(mode) {
  resetImport();
  Import.mode = mode;
  location.hash = mode === 'full' ? '#/import/research'
                 : mode === 'execution' ? '#/import/execution'
                 : '#/import';
}

/* ---- 入口选择 ---- */
function renderImportLanding(el) {
  el.innerHTML = `
    <div class="section-title"><h2>导入与更新</h2><span class="sub muted">通过复制 ChatGPT 生成的稳定 JSON 块，把深穿研究、静态交易计划与动态执行判断写入工作台。系统不做 AI 自由文本解析，只接受固定 JSON。</span></div>
    <div class="cards">
      <div class="card" style="cursor:default">
        <div class="card-top"><div class="card-name">① 导入研究结果</div></div>
        <div class="muted" style="font-size:13px;margin:8px 0">
          用于一次导入一只或多只标的的
          <b>identity + 可选 status + research + trade_plan + 可选 execution</b>。
          支持批量。流程：粘贴 → 预览 → 确认。
        </div>
        <div style="margin-top:10px"><button class="btn primary" onclick="importGo('full')">打开 · 导入研究结果</button></div>
      </div>
      <div class="card" style="cursor:default">
        <div class="card-top"><div class="card-name">② 快速更新动态执行</div></div>
        <div class="muted" style="font-size:13px;margin:8px 0">
          只针对<b>已存在</b>的标的，一次追加一条动态执行判断（append-only）。
          不会触碰研究 / 静态计划 / 持仓 / 状态。找不到标的时拒绝，提示先走研究导入。
        </div>
        <div style="margin-top:10px"><button class="btn primary" onclick="importGo('execution')">打开 · 快速更新动态执行</button></div>
      </div>
    </div>
    <div class="panel">
      <h3>导入规则</h3>
      <ul style="line-height:1.85">
        <li>稳定 JSON 两种格式：<code>ah-workbench-import</code>（完整 / 多只 / 可批量）/ <code>ah-workbench-execution</code>（仅 execution / 单只）</li>
        <li>证券唯一身份 = <b>exchange + code</b>。禁止用公司名猜测；名称不一致会在预览中显式提示</li>
        <li>preview 阶段只解析 + 对比，不触库；用户点确认才走 commit</li>
        <li>preview 有效期为 <b>5 分钟</b>且只能提交一次；提交前工作台数据若变化，需重新解析预览</li>
        <li>已有标的的研究 / 计划：内容相同不生成新版本；内容变化新增版本（<b>旧版本永久保留</b>）</li>
        <li>已有标的的 execution：永远 append-only</li>
        <li>状态字段变化：必须在预览页勾选确认，否则 commit 整批拒绝（粘贴 JSON 无法自行声明已确认）</li>
        <li>同一批 <code>securities[]</code> 内 <code>(exchange, code)</code> 必须唯一，重复则整体拒绝</li>
        <li>整批原子化：任何一项失败 → 整体 ROLLBACK，不留半完成状态</li>
        <li>导入模块<b>不会</b>修改 trade_plans 真实流水（trades 由"录入交易流水"入口独立管理）</li>
        <li>导入模块<b>不会</b>自动修改 securities.name/sector/notes 等身份信息（请用"编辑基本信息"）</li>
      </ul>
    </div>
  `;
}

/* ---- 完整导入：粘贴页 ---- */
/* v1.0.8：移除内置"载入示例"（原示例内置了某个真实候选标的的虚构研究/交易计划，
   存在被误写入正式库的风险）。现在只提供格式骨架提示，不提供任何可直接提交的示例数据。 */
const FULL_PLACEHOLDER = '{\n  "format": "ah-workbench-import",\n  "format_version": "1.0",\n  "generated_at": "YYYY-MM-DD",\n  "securities": [ { "identity": {...}, "research": {...}, "trade_plan": {...} } ]\n}';

function renderImportFullPaste(el) {
  el.innerHTML = `
    <a class="back" href="#/import">← 返回导入与更新</a>
    <div class="panel">
      <h2 style="margin:0 0 6px">① 导入研究结果 · 第 1 步：粘贴 JSON</h2>
      <div class="form-hint">支持一次导入一只或多只标的。预览阶段<b>不写库</b>，用户确认后才正式写入。</div>
      <form id="imp1">
        ${fld('在下方粘贴 ChatGPT 生成的 <code>ah-workbench-import</code> JSON 块',
          `<textarea name="json" rows="22" style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px" placeholder='${esc(FULL_PLACEHOLDER)}'>${esc(Import.pasteText)}</textarea>`)}
        ${Import.parseError ? `<div class="banner warn"><span class="banner-tag">解析失败</span><span>${esc(Import.parseError)}</span></div>` : ''}
        <div class="mfoot">
          <button class="btn primary" type="submit">解析并预览</button>
        </div>
      </form>
    </div>
    <div class="panel">
      <h3>导入格式要点</h3>
      <ul style="line-height:1.8">
        <li>顶层 <code>format="ah-workbench-import"</code>、<code>format_version="1.0"</code> 必填</li>
        <li><code>securities[]</code> 每只标的需要：<code>identity</code> 必填（exchange / code / name）、<code>research.one_liner</code> 必填</li>
        <li>可选：<code>status</code>、<code>trade_plan</code>、<code>execution</code>（首次导入建议都给齐）</li>
        <li>已有证券：缺省 status 表示不修改状态；缺省 research/plan 表示不修改</li>
        <li><code>core_validations[]</code> 每项必须是 <code>{"content": 非空文本, "status": 跟踪中|已验证|已恶化}</code></li>
        <li><code>wall_conditions[]</code> 每项必须是 <code>{"content": 非空文本, "triggered": true|false}</code></li>
        <li>同一批 <code>securities[]</code> 内 <code>(exchange, code)</code> 必须唯一</li>
      </ul>
      <div class="form-hint">preview 有效期为 5 分钟；提交前工作台数据若发生变化，需重新解析预览。</div>
    </div>
  `;
  $('#imp1').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (fd.get('json') || '').trim();
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      Import.pasteText = text;
      Import.parseError = '不是合法 JSON：' + (err.message || err);
      render();
      return;
    }
    try {
      const prev = await api('/api/import/preview', { method: 'POST', body: parsed });
      Import.pasteText = text;
      Import.preview = prev;
      Import.parseError = '';
      Import.step = 'preview';
      // v1.0.8：每次 preview 都是新的确认上下文 —— 勾选状态归零，
      // 用户必须针对这一份 preview 重新勾选。
      Import.confirmedStatus = [];
      // v1.0.9：新一轮 preview 必然带着新 token，commit 进行中标记一并复位
      Import.committing = false;
      render();
    } catch (err) {
      Import.pasteText = text;
      Import.parseError = err.message || String(err);
      render();
    }
  });
}

/* ---- 完整导入：预览 ---- */
function renderImportFullPreview(el) {
  const p = Import.preview;
  if (!p) return renderImportFullPaste(el);
  // v1.0.8：勾选状态来自前端内存（Import.confirmedStatus），不来自 preview 返回。
  const isConfirmed = (i) => Import.confirmedStatus.includes(i);
  const statusConfirmRequired = p.securities.some((s, i) =>
    s.status_change && s.status_change.requires_confirm && !isConfirmed(i)
  );
  const nameMismatches = p.securities.filter(s => s.name_mismatch);
  const secHtml = p.securities.map((s, i) => {
    const idLine = `<span class="muted">#${esc(s.exchange)} · ${esc(s.code)} · ${esc(s.name)}</span>`;
    const existsTag = s.exists
      ? '<span class="tag safe" style="margin-left:6px">已存在</span>'
      : '<span class="tag proven" style="margin-left:6px">新建</span>';
    let statusHtml = '';
    if (s.status_change) {
      if (s.status_change.changed && !s.status_change.is_new) {
        const checked = isConfirmed(i);
        statusHtml = `<div class="kv warn"><span class="w">状态变化</span>
          当前状态：<b>${esc(s.status_change.current)}</b> → 导入状态：<b style="color:var(--warn)">${esc(s.status_change.imported)}</b>
          <span style="color:var(--danger);margin-left:8px">${checked ? '已勾选' : '未勾选'}</span>
          <label style="margin-left:10px"><input type="checkbox" ${checked ? 'checked' : ''} onchange="toggleStatusConfirm(${i})"> 确认状态变化</label>
        </div>`;
      } else {
        statusHtml = `<div class="kv"><span class="w">状态</span>新建标的初始状态：<b>${esc(s.status_change.imported)}</b></div>`;
      }
    } else {
      statusHtml = `<div class="kv"><span class="w">状态</span>${s.exists ? '保持当前 status 不变（未在 JSON 中给出）' : '新建标的'}</div>`;
    }

    // v1.0.8：名称不一致显式提示（身份只认 exchange+code；本轮不自动改 name）
    const nameWarnHtml = s.name_mismatch
      ? `<div class="banner warn" style="margin:6px 0"><span class="banner-tag">名称不一致</span>
           <span>工作台：<b>${esc(s.security && s.security.name_current)}</b><br>
           导入块：<b>${esc(s.name)}</b><br>
           证券仍按 exchange+code 识别，请人工核对。本轮<b>不会</b>自动修改工作台中的名称
           （如需改名请用「编辑基本信息」）。</span></div>`
      : '';

    let researchHtml = '';
    if (s.research) {
      if (s.research.has_current && s.research.unchanged) {
        researchHtml = `<div class="kv"><span class="w">研究结论</span><span style="color:var(--muted)">研究无变化（不生成新版本）</span></div>`;
      } else {
        const ver = s.research.has_current ? `当前 v${s.research.current_version} → 将新增 v${s.research.next_version}` : '新增 v1';
        const changed = s.research.fields_changed.length ? s.research.fields_changed.join('、') : '（新增）';
        const diffs = s.research.diff_summary.map(d => `
          <div class="kv"><span class="w">${esc(d.field)}</span><span style="white-space:normal"><span class="muted">${esc(d.before || '（空）')}</span> → <b>${esc((d.after || '').slice(0, 200))}</b></span></div>
        `).join('');
        researchHtml = `<div class="kv"><span class="w">研究结论</span><span>${esc(ver)}；变化字段：<b>${esc(changed)}</b></span></div>${diffs}`;
      }
    } else {
      researchHtml = `<div class="kv"><span class="w">研究结论</span>${s.exists ? '保持现有研究不变' : '<span style="color:var(--danger)">新建标的必须包含 research 块</span>'}</div>`;
    }

    let planHtml = '';
    if (s.trade_plan) {
      if (s.trade_plan.has_current && s.trade_plan.unchanged) {
        planHtml = `<div class="kv"><span class="w">静态交易计划</span><span style="color:var(--muted)">静态交易计划无变化（不生成新版本）</span></div>`;
      } else {
        const ver = s.trade_plan.has_current ? `当前 v${s.trade_plan.current_version} → 将新增 v${s.trade_plan.next_version}` : '新增 v1';
        const changed = s.trade_plan.fields_changed.length ? s.trade_plan.fields_changed.join('、') : '（新增）';
        planHtml = `<div class="kv"><span class="w">静态交易计划</span><span>${esc(ver)}；变化字段：<b>${esc(changed)}</b></span></div>`;
      }
    } else {
      planHtml = `<div class="kv"><span class="w">静态交易计划</span>${s.exists ? '保持现有计划不变' : '<span class="muted">本次未提供 trade_plan；新建标的默认空记录</span>'}</div>`;
    }

    let execHtml = '';
    if (s.execution) {
      const e = s.execution.to_add;
      execHtml = `<div class="kv"><span class="w">动态执行</span><span>将<b>新增 1 条</b>append-only execution</span></div>
        <div class="kv"><span class="w">判断日期</span>${esc(e.execution_date)}</div>
        ${e.price_snapshot != null ? `<div class="kv"><span class="w">判断时价格</span>${esc(e.price_snapshot)}</span>` : ''}
        <div class="kv"><span class="w">当前执行判断</span><b>${esc(e.execution_view)}</b></div>
        ${e.support_zone ? `<div class="kv"><span class="w">支撑</span>${esc(e.support_zone)}</div>` : ''}
        ${e.resistance_zone ? `<div class="kv"><span class="w">压力</span>${esc(e.resistance_zone)}</div>` : ''}
        ${e.execution_condition ? `<div class="kv"><span class="w">等待条件</span><span style="white-space:normal">${esc(e.execution_condition)}</span></div>` : ''}
        ${e.reason ? `<div class="kv"><span class="w">依据</span><span style="white-space:normal">${esc(e.reason)}</span></div>` : ''}
        ${s.execution.previous_latest_date ? `<div class="kv muted"><span class="w">上一条</span>${esc(s.execution.previous_latest_date)} · ${esc(s.execution.previous_latest_view)}</div>` : ''}
      `;
    } else {
      execHtml = `<div class="kv"><span class="w">动态执行</span>${s.exists ? '本次不追加 execution' : '<span class="muted">本次未提供 execution</span>'}</div>`;
    }

    return `<div class="panel">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-size:18px;font-weight:600">${esc(s.name)}</span>${existsTag}
      </div>
      <div class="kv"><span class="w">exchange · code</span>${esc(s.exchange)} · ${esc(s.code)}${s.security_id ? ` (id=${s.security_id})` : ''}</div>
      ${nameWarnHtml}${statusHtml}${researchHtml}${planHtml}${execHtml}
    </div>`;
  }).join('');

  el.innerHTML = `
    <a class="back" href="#/import">← 返回导入与更新</a>
    <div class="section-title"><h2>① 导入研究结果 · 第 2 步：预览差异</h2><span class="sub muted">确认后才会真正写入。库对比按 exchange+code 唯一识别。</span></div>
    ${nameMismatches.length ? `<div class="banner warn"><span class="banner-tag">需人工核对</span><span>本批有 ${nameMismatches.length} 只标的的名称与工作台记录不一致（详见各卡片）。证券仍按 exchange+code 识别，名称不会被自动修改。</span></div>` : ''}
    ${secHtml}
    ${statusConfirmRequired ? `<div class="banner warn"><span class="banner-tag">必须确认</span><span>有状态变化未在预览中勾选"确认状态变化"，无法提交导入。请回到上方勾选。</span></div>` : ''}
    <div class="mfoot">
      <button type="button" class="btn ghost" onclick="goBackToPaste('full')" ${Import.committing ? 'disabled' : ''}>返回修改</button>
      <button class="btn primary" type="button" data-commit-btn onclick="commitFull()" ${(statusConfirmRequired || Import.committing) ? 'disabled' : ''}>${Import.committing ? '正在写入…' : '确认并写入'}</button>
    </div>
  `;
}

function toggleStatusConfirm(idx) {
  // v1.0.8：勾选只改前端内存；绝不写回粘贴 JSON，也不再重发 preview。
  // commit 时由 commitFull() 作为 confirmed_status_changes 单独提交。
  const arr = Import.confirmedStatus;
  const k = arr.indexOf(idx);
  if (k >= 0) arr.splice(k, 1);
  else arr.push(idx);
  render();
}

function goBackToPaste(mode) {
  Import.step = 'paste';
  if (mode === 'full') {
    location.hash = '#/import/research';
  }
  render();
}

async function commitFull() {
  if (!Import.preview) return;
  // v1.0.9：前端最小防重 —— 请求返回前不再发出第二次 commit。
  if (Import.committing) { toast('正在写入，请稍候…', true); return; }
  const p = Import.preview;
  // v1.0.8：状态变化必须由用户在前端勾选（Import.confirmedStatus）。
  // 该勾选不进粘贴 JSON，只在 commit 请求体里单独作为 confirmed_status_changes 提交。
  for (let i = 0; i < p.securities.length; i++) {
    const s = p.securities[i];
    if (s.status_change && s.status_change.requires_confirm
        && !Import.confirmedStatus.includes(i)) {
      toast('存在未确认的状态变化，请勾选后再提交', true);
      return;
    }
  }
  // v1.0.9：先置位并重绘 —— 按钮立即 disabled 且文案变为"正在写入…"
  Import.committing = true;
  render();
  try {
    const result = await api('/api/import/commit', {
      method: 'POST',
      body: {
        token: p.token,
        // 只提交本次 preview 上下文里用户真正勾选的条目
        confirmed_status_changes: Import.confirmedStatus.slice(),
      },
    });
    Import.committing = false;
    Import.commit = result;
    Import.step = 'done';
    render();
    // 异步刷新首页数据
    try { await afterMutation(); } catch (e) {}
  } catch (err) {
    // v1.0.9：失败即恢复按钮（服务端 in_flight 也已释放，可修正后重试）
    Import.committing = false;
    // 服务器已将整批回滚；展示错误并不前进
    const msg = err.message || String(err);
    if (msg.indexOf('自预览后已发生变化') >= 0) {
      // v1.0.8：数据漂移 —— 明确引导用户重新解析预览
      toast('数据已变化，请重新解析预览', true);
      Import.parseError = msg;
      Import.step = 'paste';
      Import.confirmedStatus = [];
      render();
      return;
    }
    toast('导入失败：' + msg, true);
    render();
  }
}

/* ---- 完整导入：完成 ---- */
function renderImportFullDone(el) {
  const r = Import.commit;
  if (!r) return renderImportFullPaste(el);
  const rowsHtml = (r.securities || []).map(s => `
    <tr>
      <td>${esc(s.name)}</td>
      <td>${esc(s.exchange)} · ${esc(s.code)}</td>
      <td>${s.is_new ? '<span class="tag proven">新建</span>' : '<span class="tag safe">已存在</span>'}</td>
      <td>${s.actions.status_changed ? '<b style="color:var(--warn)">是</b>' : '—'}</td>
      <td>${s.actions.new_research_version ? 'v' + s.actions.new_research_version : (s.actions.unchanged_research ? '无变化' : '—')}</td>
      <td>${s.actions.new_plan_version ? 'v' + s.actions.new_plan_version : (s.actions.unchanged_plan ? '无变化' : '—')}</td>
      <td>${s.actions.new_execution_id ? '新增 #' + s.actions.new_execution_id : '—'}</td>
    </tr>`).join('');
  el.innerHTML = `
    <div class="section-title"><h2>① 导入研究结果 · 第 3 步：导入完成</h2></div>
    <div class="panel">
      <div class="kv"><span class="w">导入完成</span><b style="color:var(--accent)">成功处理 ${r.total} 只</b></div>
      <div class="kv"><span class="w">新建标的</span><b>${r.created_count}</b></div>
      <div class="kv"><span class="w">状态变更</span><b>${r.status_changed_count || 0}</b></div>
      <div class="kv"><span class="w">新增研究版本</span><b>${r.new_research_versions || 0}</b></div>
      <div class="kv"><span class="w">新增静态计划版本</span><b>${r.new_plan_versions || 0}</b></div>
      <div class="kv"><span class="w">新增动态执行判断</span><b>${r.new_executions || 0}</b></div>
      <div class="kv"><span class="w">内容无变化跳过</span><b>${r.unchanged_skipped || 0}</b></div>
    </div>
    <div class="panel">
      <h3>明细</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>标的</th><th>exchange · code</th><th>类型</th><th>状态变化</th><th>研究</th><th>计划</th><th>执行</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table></div>
      <div class="muted" style="margin-top:10px;font-size:12px">所有写入均同步写入 decision_ledger（append-only）。研究/计划/状态等历史版本永久保留。</div>
    </div>
    <div class="mfoot">
      <button class="btn ghost" onclick="backToImport()">返回导入与更新</button>
      <button class="btn primary" onclick="goHome()">返回工作台</button>
    </div>
  `;
}

function backToImport() { resetImport(); location.hash = '#/import'; }
function goHome() { resetImport(); location.hash = '#/home'; }

/* ==================================================================
   UI/UX refresh · 深色金融终端
   仅重排现有数据与既有动作；不新增接口、字段、指标或交易规则。
   ================================================================== */
function uiMiniChart(q, cls) {
  if (!q || q.current == null) return '<span class="mini-chart-empty">—</span>';
  const change = Number(q.change_pct || 0);
  const start = change >= 0 ? 28 : 10;
  const end = change >= 0 ? 9 : 27;
  const mid = change >= 0 ? 17 : 18;
  const points = `0,${start} 12,${start - (start - mid) * .25} 24,${mid + 3} 36,${mid - 3} 48,${mid + 2} 60,${mid - 5} 72,${mid + 1} 86,${end}`;
  return `<svg class="mini-chart ${cls || ''}" viewBox="0 0 90 36" aria-hidden="true"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><polyline points="${points} 90,36 0,36" fill="currentColor" opacity=".08" stroke="none"/></svg>`;
}

function uiRiskCount() {
  return S.secs.filter(s => wallTriggered(s.research) ||
    ((s.research && s.research.core_validations) || []).some(v => v.status === '已恶化')).length;
}

function uiLifecyclePrice(s) {
  const q = quoteOf(s);
  return q && !q.is_stale && q.current != null ? Number(q.current) : null;
}

function uiHasPosition(s) {
  const qty = s.position && s.position.quantity;
  if (qty != null && Number(qty) > 0) return true;
  // 当前系统部分标的还没有正式流水，沿用现有 status 作为临时持仓 fallback。
  return s.status === '持仓中';
}

function uiZoneRange(plan, key, currency) {
  const low = plan[key + '_low'], high = plan[key + '_high'];
  return low != null && high != null ? zoneStr(low, high, decOf(currency)) : '';
}

function uiLifecycle(s) {
  const p = s.plan || {};
  const price = uiLifecyclePrice(s);
  const d = decOf(s.currency);
  const hasPosition = uiHasPosition(s);
  const wall = wallTriggered(s.research);
  const zone = (key) => price != null && inZone(price, p[key + '_low'], p[key + '_high']);
  const firstComplete = p.first_zone_low != null && p.first_zone_high != null;
  const addComplete = p.add_zone_low != null && p.add_zone_high != null;
  const firstRange = uiZoneRange(p, 'first_zone', s.currency);
  const addRange = uiZoneRange(p, 'add_zone', s.currency);
  const oddsRange = uiZoneRange(p, 'odds_zone', s.currency);
  const corePool = String((s.research && s.research.research_pool) || s.research_pool || '');
  const isCore = /核心/.test(corePool);
  const otherAttention = attention(s).filter(text => !/价格进入|超过不追价|高于首仓区|低于首仓区/.test(text));
  const base = { hasPosition, price, nextRange: '', distance: null, reason: '', primary: '', nextLabel: '', bucket: 'candidate', risk: wall };

  if (wall) {
    return { ...base, bucket: 'today', sortRank: 0, reason: '危墙条件已触发', primary: '风险优先重新判断', nextLabel: '查看危墙与动态执行' };
  }

  if (hasPosition) {
    if (zone('odds_zone')) return { ...base, bucket: 'today', sortRank: 1, reason: `已进入强赔率区 ${oddsRange}`, primary: '当前已进入强赔率区', nextLabel: '重新检查基本面和动态执行判断' };
    if (zone('add_zone')) return { ...base, bucket: 'today', sortRank: 2, reason: `已进入加仓区 ${addRange}`, primary: '当前已进入加仓区', nextLabel: '是否加仓需结合最新动态执行判断' };
    if (otherAttention.length) return { ...base, bucket: 'today', sortRank: 4, reason: otherAttention[0], primary: '需要重新打开判断', nextLabel: '查看动态执行与研究事实' };
    if (addComplete) {
      const distance = price != null && price > p.add_zone_high ? price - p.add_zone_high : null;
      return { ...base, bucket: 'holding', sortRank: 0, nextRange: addRange, distance, primary: '首仓已完成', nextLabel: '下一价格观察：加仓区 ' + addRange, reason: distance != null ? `距加仓区上沿 ${num(distance, d)}` : '等待进入加仓区' };
    }
    return { ...base, bucket: 'holding', sortRank: 1, primary: '当前持仓', nextLabel: '下一观察：等待动态执行 / 研究证据', reason: '暂无完整加仓价格带' };
  }

  if (zone('odds_zone') || zone('add_zone') || (firstComplete && price != null && price < p.first_zone_low)) {
    const reason = price != null && firstComplete && price < p.first_zone_low
      ? `价格已低于原首仓区 ${firstRange}，当前无仓位`
      : `当前无仓位，价格已进入原${zone('add_zone') ? '加仓区' : '强赔率区'} ${zone('add_zone') ? addRange : oddsRange}`;
    return { ...base, bucket: 'today', sortRank: 3, reason, primary: '当前无仓位，需重新判断首仓方案', nextLabel: '形成/更新动态执行判断' };
  }
  if (zone('first_zone')) return { ...base, bucket: 'today', sortRank: 3, reason: `已进入首仓区 ${firstRange}`, primary: '已进入首仓区', nextLabel: '形成/更新动态执行判断' };
  if (otherAttention.length) return { ...base, bucket: 'today', sortRank: 4, reason: otherAttention[0], primary: '需要重新打开判断', nextLabel: '查看动态执行与研究事实' };
  if (firstComplete) {
    const distance = price != null && price > p.first_zone_high ? price - p.first_zone_high : null;
    return { ...base, bucket: 'first', sortRank: 0, nextRange: firstRange, distance, primary: '当前未持仓', nextLabel: '下一价格观察：首仓区 ' + firstRange, reason: distance != null ? `距首仓区上沿 ${num(distance, d)}` : '等待进入首仓区' };
  }

  if (isCore) return { ...base, bucket: 'core', sortRank: 0, primary: '等待价格 / 证据', nextLabel: '核心验证：' + ((s.research && s.research.core_validations || [])[0]?.content || '等待研究证据'), reason: '核心候选，当前主要等待研究证据' };
  return { ...base, bucket: 'candidate', sortRank: 0, primary: '候补研究', nextLabel: '等待人工确认优先级', reason: '当前不属于核心交易候选' };
}

function uiLifecycleSort(a, b) {
  const la = uiLifecycle(a), lb = uiLifecycle(b);
  if (la.sortRank !== lb.sortRank) return la.sortRank - lb.sortRank;
  if (la.distance != null && lb.distance != null) return la.distance - lb.distance;
  return S.secs.indexOf(a) - S.secs.indexOf(b);
}

function uiPositionBand(s, life = uiLifecycle(s)) {
  const p = s.plan || {};
  const q = quoteOf(s);
  const price = q && !q.is_stale ? q.current : null;
  const d = decOf(s.currency);
  const ranges = [p.odds_zone_low, p.odds_zone_high, p.add_zone_low, p.add_zone_high, p.first_zone_low, p.first_zone_high, p.no_chase_price].filter(v => v != null).map(Number);
  const min = ranges.length ? Math.min(...ranges) : 0;
  const max = ranges.length ? Math.max(...ranges) : 1;
  const span = Math.max(max - min, 1);
  const zones = [
    ['强赔率区', p.odds_zone_low, p.odds_zone_high, 'odds'],
    ['加仓区', p.add_zone_low, p.add_zone_high, 'add'],
    ['首仓区', p.first_zone_low, p.first_zone_high, 'first'],
  ];
  const active = zones.find(z => inZone(price, z[1], z[2]));
  const activeLabel = active ? active[0] : (price != null && p.no_chase_price != null && price > p.no_chase_price ? '不追价' : '区间外');
  const marker = price == null ? null : Math.max(1, Math.min(99, ((price - min) / span) * 100));
  const track = `<div class="price-track"><span class="track-line"></span>${zones.map(z => `<span class="track-zone ${z[3]}" style="left:${Math.max(0, Math.min(100, (((z[1] || min) - min) / span) * 100))}%;width:${Math.max(5, (((z[2] || z[1] || min) - (z[1] || min)) / span) * 100)}%"></span>`).join('')}${p.no_chase_price != null ? `<span class="track-no-chase" style="left:${Math.max(0, Math.min(100, ((p.no_chase_price - min) / span) * 100))}%"></span>` : ''}${marker != null ? `<span class="track-marker" style="left:${marker}%"><i>${num(price, d)}</i></span>` : ''}</div>`;
  return `<div class="price-rail lifecycle-rail ${life.hasPosition ? 'holding-rail' : ''} ${life.bucket === 'today' ? 'attention-rail' : ''}" aria-label="静态价格位置"><div class="price-band-title">价格区间</div><div class="rail-legend">${zones.map(z => { const zr = zoneStr(z[1], z[2], d); const compactZr = zr.replace(/\s*[–-]\s*/g, '–'); const activeClass = active && active[3] === z[3] ? 'active-zone' : ''; const nextClass = life.nextRange && zr === life.nextRange ? 'next-zone' : ''; return `<span class="rail-zone-${z[3]} ${activeClass} ${nextClass}"><i class="legend-dot ${z[3]}"></i><b>${z[0]}</b><em>${compactZr || '未设置'}</em></span>`; }).join('')}<span class="rail-zone-no-chase"><i class="legend-dot no-chase"></i><b>不追价</b><em>&gt;${p.no_chase_price != null ? num(p.no_chase_price, d) : '未设置'}</em></span></div>${track}<div class="rail-labels"><span>${num(min, d)}</span><span>${p.first_zone_low != null ? num(p.first_zone_low, d) : '—'}</span><span>${p.no_chase_price != null ? '&gt; ' + num(p.no_chase_price, d) : '—'}</span></div><div class="band-caption"><span>${life.hasPosition && life.nextRange ? '下一关注' : '当前所在'}</span><b>${esc(life.nextRange || activeLabel)}</b></div></div>`;
}

function uiQuickActions(s) {
  return `<div class="quick-actions" onclick="event.stopPropagation()">
    <button type="button" class="quick-action" onclick="openExecutionModal(${s.id})"><span>↗</span>执行</button>
    <button type="button" class="quick-action" onclick="openTradeModal(${s.id})"><span>⇄</span>交易</button>
    <button type="button" class="quick-action" onclick="openResearchModal(${s.id})"><span>⌁</span>研究</button>
    <button type="button" class="quick-action" onclick="openMoreActions(${s.id})"><span>···</span>更多</button>
  </div>`;
}

function openMoreActions(id) {
  openModal('更多操作', `<div class="more-actions">
    <button class="btn" type="button" onclick="closeModal();openStatusModal(${id})">变更状态</button>
    <button class="btn" type="button" onclick="closeModal();openPlanModal(${id})">修改交易计划</button>
    <button class="btn" type="button" onclick="closeModal();openBasicModal(${id})">编辑基本信息</button>
    <button class="btn" type="button" onclick="closeModal();openNoteModal(${id})">添加决策记录</button>
  </div>`, null, '关闭');
}

/* ===== 标的归档 / 恢复（软删除，不升版本号） =====
   卡片右上角的「×」触发归档。归档不是删除：后端只给 securities.archived_at 打时间戳，
   research / trade_plans / execution_reviews / decision_ledger / trades 一行都不动。
   故确认弹窗必须先把「保留多少历史」摆给用户看，再让用户确认。
   —— 前端不做二次判断：is_archived 以后端 /archive-impact 的返回为准。 */

const ARCHIVE_IMPACT_FIELDS = [
  ['研究版本', 'research'], ['交易计划', 'plans'], ['动态执行', 'executions'],
  ['决策台账', 'ledger'], ['交易流水', 'trades']
];

function archiveImpactGrid(im) {
  return `<div class="archive-impact">${ARCHIVE_IMPACT_FIELDS
    .map(([label, key]) => `<div><span>${label}</span><b>${Number(im[key] || 0)}</b></div>`)
    .join('')}</div>`;
}

function archiveTargetHtml(im) {
  return `<div class="archive-target"><b>${esc(im.name)}</b>
    <span>${esc(im.code)} · ${esc(im.exchange)}</span>${statusBadge(im.status)}</div>`;
}

async function openArchiveModal(id) {
  let im;
  try { im = await api('/api/securities/' + id + '/archive-impact'); } catch (e) { return; }
  if (im.is_archived) return openRestoreModal(id);
  const warn = im.status === '持仓中'
    ? '<p class="archive-warn">该标的当前状态为「持仓中」—— 归档只是从工作台隐藏，'
      + '<b>不会改变状态，也不会删除任何持仓或交易记录</b>。</p>'
    : '';
  openModal('归档标的', `
    ${archiveTargetHtml(im)}
    <p class="archive-lead">归档后该标的从工作台隐藏，下列历史<b>全部原样保留</b>，随时可以恢复：</p>
    ${archiveImpactGrid(im)}
    <p class="archive-note">共 <b>${Number(im.total || 0)}</b> 条记录<b>不会被删除</b>；
      本次归档会在决策台账追加 1 条「标的归档」记录。</p>
    ${warn}
    <label class="archive-reason"><span>归档原因（可选，写入决策台账）</span>
      <input name="reason" maxlength="200" placeholder="例如：研究逻辑已被推翻 / 误录入"></label>
  `, async fd => {
    const res = await api('/api/securities/' + id + '/archive',
      { method: 'POST', body: { reason: String(fd.get('reason') || '') } });
    closeDrawer();
    await loadAll();
    await render();
    toast(res.changed ? ('已归档 · ' + res.name) : (res.name + ' 本就处于归档状态'));
  }, '确认归档');
}

async function openRestoreModal(id) {
  let im;
  try { im = await api('/api/securities/' + id + '/archive-impact'); } catch (e) { return; }
  if (!im.is_archived) { toast('该标的当前未归档'); return; }
  openModal('恢复标的', `
    ${archiveTargetHtml(im)}
    <p class="archive-lead">恢复后该标的重新出现在工作台，
      研究 / 计划 / 执行 / 台账<b>没有任何改动</b>。</p>
    ${archiveImpactGrid(im)}
    <p class="archive-note">归档于 ${esc(String(im.archived_at || '').slice(0, 19))}；
      本次恢复会在决策台账追加 1 条「标的恢复」记录。</p>
  `, async () => {
    const res = await api('/api/securities/' + id + '/unarchive', { method: 'POST', body: {} });
    await loadAll();
    await render();
    toast('已恢复 · ' + res.name);
  }, '确认恢复');
}

function uiArchivedRow(s) {
  const bits = [];
  if (s.research) bits.push('研究 v' + s.research.version);
  if (s.plan) bits.push('计划 v' + s.plan.version);
  if (s.execution_latest) bits.push('执行 ' + (s.execution_latest.execution_date || ''));
  bits.push('归档于 ' + String(s.archived_at || '').slice(0, 16));
  return `<div class="archive-row" data-archived-id="${s.id}">
    <div class="archive-row-main"><b>${esc(s.name)}</b>
      <span>${esc(s.code)} · ${esc(s.exchange)} · ${esc(s.market || '')}</span></div>
    <div class="archive-row-meta">${statusBadge(s.status)}<span>${esc(bits.join(' · '))}</span></div>
    <button type="button" class="btn sm ghost" onclick="openRestoreModal(${s.id})">恢复</button>
  </div>`;
}

function uiArchivedSection() {
  const list = S.archived || [];
  if (!list.length) return '';
  return `<section class="work-section archive-section">
    <div class="section-heading"><div><div class="section-kicker">ARCHIVED / RESTORE</div>
      <h2>已归档</h2></div><span>${list.length} 个标的</span></div>
    <details class="candidate-disclosure"><summary>默认折叠 · ${list.length} 个标的
      （历史完整保留，可恢复）</summary>
      <div class="archive-list">${list.map(uiArchivedRow).join('')}</div></details></section>`;
}

function uiCardHtml(s, compact) {
  const q = quoteOf(s), d = decOf(s.currency), plan = s.plan || {};
  const exec = s.execution_latest;
  const life = uiLifecycle(s);
  const risk = life.risk || ((s.research && s.research.core_validations) || []).some(v => v.status === '已恶化');
  const bucketClass = 'lifecycle-' + life.bucket;
  return `<article class="terminal-card lifecycle-card ${compact ? 'compact-card' : ''} ${bucketClass} ${risk ? 'has-risk' : ''}" tabindex="0" data-sec-id="${s.id}" onclick="location.hash='#/s/${s.id}'">
    <button type="button" class="card-archive" data-archive-id="${s.id}"
      title="归档该标的：从工作台隐藏，研究/计划/执行/台账全部保留，可随时恢复"
      aria-label="归档 ${esc(s.name)}"
      onclick="event.stopPropagation();event.preventDefault();openArchiveModal(${s.id})">×</button>
    <div class="terminal-card-head">
      <div class="identity"><div class="identity-name">${esc(s.name)}</div><div class="identity-code">${esc(s.code)} · ${esc(s.exchange)} · ${esc(s.market || '')}</div></div>
      ${statusBadge(s.status)}
    </div>
    <div class="quote-row">
      <div><div class="quote-price">${q ? curSym(s.currency) + ' ' + num(q.current, d) : '暂无行情'}</div><div class="quote-change ${q ? (q.change_pct >= 0 ? 'up' : 'down') : ''}">${q ? (q.change_pct >= 0 ? '+' : '') + num(q.change_pct, 2) + '%' : '等待行情'}</div></div>
      ${uiMiniChart(q, q && q.change_pct >= 0 ? 'trend-up' : 'trend-down')}
    </div>
    <div class="lifecycle-focus"><strong>${esc(life.primary)}</strong><span>${esc(life.reason)}</span></div>
    <div class="lifecycle-next"><span>${esc(life.nextLabel || '下一观察')}</span>${life.distance != null ? `<b>距目标 ${num(life.distance, d)}</b>` : ''}</div>
    ${uiPositionBand(s, life)}
    <div class="exec-focus exec-neutral ${exec ? '' : 'is-empty'}">
      <div class="eyebrow">动态执行判断</div>
      <div class="exec-view">${esc(exec ? (exec.execution_view || '—') : '尚未形成动态执行判断')}</div>
      ${exec && exec.execution_condition ? `<div class="exec-sub">${esc(exec.execution_condition)}</div>` : ''}
    </div>
    <div class="next-action"><span>下一动作</span><b>${esc(plan.next_action || life.nextLabel || '—')}</b></div>
    ${compact ? '' : uiQuickActions(s)}
  </article>`;
}

function renderTerminalHome(el) {
  const groups = { today: [], holding: [], first: [], core: [], candidate: [] };
  S.secs.forEach(s => groups[uiLifecycle(s).bucket].push(s));
  Object.values(groups).forEach(list => list.sort(uiLifecycleSort));
  const section = (key, title, kicker, list, compact) => `<section class="work-section lifecycle-section lifecycle-${key}-section"><div class="section-heading"><div><div class="section-kicker">${kicker}</div><h2>${title}</h2></div><span>${list.length} 个标的</span></div>${list.length ? `<div class="terminal-grid">${list.map(s => uiCardHtml(s, compact)).join('')}</div>` : '<div class="empty-state"><div><b>暂无标的</b></div></div>'}</section>`;
  el.innerHTML = `<div class="workspace-shell">
    ${section('today', '进入首仓区', 'TODAY / DECISION', groups.today, false)}
    ${section('holding', '伺机加仓', 'HOLDING / NEXT TARGET', groups.holding, false)}
    ${section('first', '价格观察', 'WAITING / FIRST ENTRY', groups.first, false)}
    ${section('core', '核心观察', 'CORE / EVIDENCE', groups.core, true)}
    <section class="work-section lifecycle-candidate-section"><div class="section-heading"><div><div class="section-kicker">RESEARCH / CANDIDATES</div><h2>候补研究</h2></div><span>${groups.candidate.length} 个标的</span></div><details class="candidate-disclosure" ${groups.candidate.length ? '' : 'open'}><summary>默认折叠 · ${groups.candidate.length} 个标的</summary>${groups.candidate.length ? `<div class="terminal-grid">${groups.candidate.map(s => uiCardHtml(s, true)).join('')}</div>` : '<div class="empty-state"><div><b>暂无候补标的</b></div></div>'}</details></section>
    ${uiArchivedSection()}
  </div>`;
}

function uiDrawerDetail(d) {
  const s = d.security, r = d.research || {}, p = d.plan || {}, q = quoteOf(s), dec = decOf(s.currency);
  const e = d.execution_latest;
  const vals = r.core_validations || [], walls = r.wall_conditions || [];
  const wallCount = walls.filter(w => w.triggered).length;
  const support = e && e.support_zone ? e.support_zone : '—';
  return `<div class="drawer-mask" onclick="if(event.target===this)closeDrawer()"><aside class="detail-drawer" role="dialog" aria-label="标的详情">
    <button class="drawer-close" type="button" onclick="closeDrawer()" aria-label="关闭">×</button>
    <div class="drawer-scroll">
      <div class="drawer-header"><div class="eyebrow">${esc(s.market || s.exchange)} · ${esc(s.currency)}</div><h2>${esc(s.name)}</h2><div class="drawer-code">${esc(s.code)} · ${esc(s.exchange)} ${statusBadge(s.status)}</div>
        <div class="drawer-quote"><div><b>${q ? curSym(s.currency) + ' ' + num(q.current, dec) : '暂无行情'}</b><span class="${q && q.change_pct >= 0 ? 'up' : 'down'}">${q ? (q.change_pct >= 0 ? '+' : '') + num(q.change_pct, 2) + '%' : '—'}</span></div>${uiMiniChart(q, q && q.change_pct >= 0 ? 'trend-up' : 'trend-down')}</div>
      </div>
      <section class="drawer-section execution-panel"><div class="drawer-section-title"><span class="section-kicker">01 · PRIORITY</span><button class="btn sm ghost" onclick="openExecutionModal(${s.id})">更新</button></div><h3>动态执行判断</h3>
        ${e ? `<div class="execution-hero"><div class="eyebrow">当前判断</div><strong>${esc(e.execution_view || '—')}</strong><span>${esc(e.execution_date || '')}</span></div><div class="detail-kv"><span>支撑 / 压力</span><b>${esc(support)} / ${esc(e.resistance_zone || '—')}</b></div><div class="detail-kv"><span>技术结构</span><b>${esc(e.technical_structure || '—')}</b></div><div class="detail-kv"><span>等待条件</span><b>${esc(e.execution_condition || '—')}</b></div><div class="detail-kv"><span>本次依据</span><b>${esc(e.reason || '—')}</b></div>` : '<div class="drawer-empty">尚未形成动态执行判断</div>'}
      </section>
      <section class="drawer-section"><div class="drawer-section-title"><span class="section-kicker">02 · PLAN</span><button class="btn sm ghost" onclick="openPlanModal(${s.id})">修改</button></div><h3>静态交易计划</h3>${uiPositionBand(s)}<div class="detail-kv"><span>目标仓位</span><b>${p.target_position_pct != null ? num(p.target_position_pct, 1) + '%' : '—'}</b></div><div class="detail-kv"><span>下一动作</span><b>${esc(p.next_action || '—')}</b></div></section>
      <section class="drawer-section"><div class="drawer-section-title"><span class="section-kicker">03 · RESEARCH FACTS</span><button class="btn sm ghost" onclick="openResearchModal(${s.id})">查看 / 更新</button></div><h3>核心验证项 <small>${vals.length} 项 · ${validationSummary(r)}</small></h3>${vals.length ? `<details class="drawer-disclosure"><summary>${vals.length} 项跟踪中　展开</summary><ul class="vlist">${vals.map(v => `<li><span class="tag ${v.status === '已恶化' ? 'worse' : v.status === '已验证' ? 'proven' : 'track'}">${esc(v.status)}</span><span>${esc(v.content)}</span></li>`).join('')}</ul></details>` : '<div class="drawer-empty">尚未录入核心验证项</div>'}</section>
      <section class="drawer-section ${wallCount ? 'wall-section-fired' : ''}"><div class="drawer-section-title"><span class="section-kicker">04 · WALLS</span>${wallCount ? '<span class="risk-pill">已触发 ' + wallCount + ' 项</span>' : '<span class="safe-pill">未触发</span>'}</div><h3>危墙条件 <small>（${walls.length}）</small></h3>${walls.length ? `<details class="drawer-disclosure" ${wallCount ? 'open' : ''}><summary>${wallCount ? '发现已触发项　展开' : '未触发　展开'}</summary><ul class="vlist wall-list">${walls.map(w => `<li class="${w.triggered ? 'wall-fired' : ''}"><span class="tag ${w.triggered ? 'fired' : 'safe'}">${w.triggered ? '已触发' : '未触发'}</span><span>${esc(w.content)}</span></li>`).join('')}</ul></details>` : '<div class="drawer-empty">尚未录入危墙条件</div>'}</section>
      <section class="drawer-section research-summary"><h3>研究摘要</h3><p>${esc(r.one_liner || '尚未录入研究结论。')}</p></section>
    </div>
    <div class="drawer-actions"><button class="btn primary" onclick="openExecutionModal(${s.id})">↗ 更新动态执行</button><button class="btn" onclick="openTradeModal(${s.id})">⇄ 录入交易</button><button class="btn ghost" onclick="openResearchModal(${s.id})">⌁ 查看研究</button><button class="btn ghost" onclick="openMoreActions(${s.id})">··· 更多</button></div>
  </aside></div>`;
}

async function openDetailDrawer(id) {
  const root = document.getElementById('drawer-root') || (() => { const x = document.createElement('div'); x.id = 'drawer-root'; document.body.appendChild(x); return x; })();
  root.innerHTML = '<div class="drawer-mask"><aside class="detail-drawer"><div class="drawer-loading">加载标的详情…</div></aside></div>';
  try { root.innerHTML = uiDrawerDetail(await api('/api/securities/' + id)); S.drawerId = Number(id); document.body.classList.add('drawer-open'); document.querySelectorAll('.terminal-card').forEach(card => card.classList.toggle('selected-card', Number(card.dataset.secId) === S.drawerId)); } catch (e) { root.innerHTML = ''; }
}
function closeDrawer() { const root = document.getElementById('drawer-root'); if (root) root.innerHTML = ''; document.body.classList.remove('drawer-open'); document.querySelectorAll('.selected-card').forEach(card => card.classList.remove('selected-card')); S.drawerId = null; if (routeInfo().page === 'detail') history.pushState({}, '', '#/home'); }

function renderTerminal(el) {
  const r = routeInfo();
  if (r.page !== 'detail' && S.drawerId) {
    const drawerRoot = document.getElementById('drawer-root');
    if (drawerRoot) drawerRoot.innerHTML = '';
    document.body.classList.remove('drawer-open');
    S.drawerId = null;
  }
  setActiveNav(r.page === 'detail' ? 'home' : r.page);
  if (r.page === 'home') return renderTerminalHome(el);
  if (r.page === 'detail') { renderTerminalHome(el); return openDetailDrawer(r.id); }
  if (r.page === 'list') return renderList(el);
  if (r.page === 'new') { location.hash = '#/import'; return; }
  if (r.page === 'import') return renderImportPanel(el, r.mode);
}

/* 覆盖渲染入口，保留所有原有业务函数与页面路由。 */
render = async function() {
  const el = $('#app');
  try { await renderTerminal(el); } catch (e) { el.innerHTML = '<div class="empty">页面加载失败：' + esc(e.message) + '</div>'; }
};

const uiOriginalRenderImportPanel = renderImportPanel;
renderImportPanel = function(el, mode) {
  uiOriginalRenderImportPanel(el, mode);
  const active = mode === 'landing' ? 0 : (Import.step === 'preview' ? 1 : Import.step === 'done' ? 2 : 0);
  const steps = ['① 粘贴', '② 差异预览', '③ 完成'];
  el.insertAdjacentHTML('afterbegin', `<div class="import-steps">${steps.map((x, i) => `<div class="import-step ${i === active ? 'active' : ''}">${x}</div>`).join('')}</div>`);
};

function setupTerminalInteractions() {
  const input = $('#command-input');
  if (!input) return;
  const results = $('#command-results');
  const clock = $('#top-clock');
  const updateClock = () => { if (clock) clock.textContent = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }); };
  updateClock();
  setInterval(updateClock, 30000);
  const drawCommands = (query) => {
    const q = String(query || '').trim().toLowerCase();
    const commands = [
      { label: '打开今日工作台', hint: '导航', run: () => { location.hash = '#/home'; } },
      { label: '导入与更新', hint: '导航', run: () => { location.hash = '#/import'; } },
      { label: '标的库', hint: '导航', run: () => { location.hash = '#/list'; } },
      ...S.secs.filter(s => !q || (s.name + s.code + s.exchange).toLowerCase().includes(q)).slice(0, 6).map(s => ({ label: '打开 ' + s.name, hint: s.code + ' · ' + s.exchange, run: () => { location.hash = '#/s/' + s.id; } }))
    ].filter(c => !q || c.label.toLowerCase().includes(q) || c.hint.toLowerCase().includes(q));
    results.innerHTML = commands.slice(0, 7).map((c, i) => `<button type="button" class="command-item" data-command-index="${i}"><span>${esc(c.label)}</span><small>${esc(c.hint)}</small></button>`).join('');
    results.hidden = !commands.length;
    results.querySelectorAll('.command-item').forEach((b, i) => b.addEventListener('click', () => { commands[i].run(); input.value = ''; results.hidden = true; }));
  };
  input.addEventListener('focus', () => drawCommands(input.value));
  input.addEventListener('input', () => drawCommands(input.value));
  input.addEventListener('keydown', e => { if (e.key === 'Enter') { const first = results.querySelector('.command-item'); if (first) first.click(); } if (e.key === 'Escape') { results.hidden = true; input.blur(); } });
  document.addEventListener('click', e => { if (!e.target.closest('.command-box')) results.hidden = true; });
}

document.addEventListener('keydown', e => {
  const active = document.activeElement;
  // 焦点落在**任何**可交互控件时，页面级快捷键一律让路。
  // 必须含 button / a[href]：否则 Tab 聚焦到卡片右上角的「×」后按 Enter，
  // 会被下面 `e.key === 'Enter'` 分支先 preventDefault（按钮的默认点击被吞），
  // 结果是"想归档却跳去了详情页"——键盘用户完全无法归档。
  const onControl = active && (active.matches('a[href], button, input, textarea, select, [contenteditable="true"]') || active.isContentEditable);
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); $('#command-input')?.focus(); return; }
  if (onControl) return;
  if (e.key === 'Escape' && S.drawerId) { e.preventDefault(); closeDrawer(); return; }
  if (S.drawerId && e.key.toLowerCase() === 'e') { e.preventDefault(); openExecutionModal(S.drawerId); return; }
  if (S.drawerId && e.key.toLowerCase() === 't') { e.preventDefault(); openTradeModal(S.drawerId); return; }
  if (S.drawerId && e.key.toLowerCase() === 'r') { e.preventDefault(); openResearchModal(S.drawerId); return; }
  if (routeInfo().page !== 'home') return;
  const cards = [...document.querySelectorAll('.terminal-card')];
  if (!cards.length) return;
  S.focusIndex = S.focusIndex == null ? 0 : S.focusIndex;
  if (e.key.toLowerCase() === 'j' || e.key.toLowerCase() === 'k') { e.preventDefault(); S.focusIndex = (S.focusIndex + (e.key.toLowerCase() === 'j' ? 1 : -1) + cards.length) % cards.length; cards.forEach((c, i) => c.classList.toggle('keyboard-focus', i === S.focusIndex)); cards[S.focusIndex].scrollIntoView({ block: 'nearest' }); }
  if (e.key === 'Enter') { e.preventDefault(); const id = cards[S.focusIndex].dataset.secId; location.hash = '#/s/' + id; }
});

setupTerminalInteractions();

/* ---- execution-only 粘贴页 ---- */
/* v1.0.8：移除内置示例（原示例绑定某个真实候选标的）。
   只保留格式骨架提示，不提供可直接提交的示例数据。 */
const EXEC_ONLY_PLACEHOLDER = '{\n  "format": "ah-workbench-execution",\n  "format_version": "1.0",\n  "identity": {"exchange": "HK", "code": "XXXXX"},\n  "execution": { "execution_date": "YYYY-MM-DD", "execution_view": "..." }\n}';

function renderImportExecPaste(el) {
  el.innerHTML = `
    <a class="back" href="#/import">← 返回导入与更新</a>
    <div class="panel">
      <h2 style="margin:0 0 6px">② 快速更新动态执行 · 第 1 步：粘贴 JSON</h2>
      <div class="form-hint">只更新<b>已存在</b>标的的一条 execution review。<br>
      不会修改研究 / 静态计划 / 持仓 / 状态。<br>
      找不到标的时拒绝导入，提示先使用「导入研究结果」。</div>
      <form id="imp2">
        ${fld('在下方粘贴 <code>ah-workbench-execution</code> JSON 块',
          `<textarea name="json" rows="14" style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px" placeholder='${esc(EXEC_ONLY_PLACEHOLDER)}'>${esc(Import.pasteText)}</textarea>`)}
        ${Import.parseError ? `<div class="banner warn"><span class="banner-tag">解析失败</span><span>${esc(Import.parseError)}</span></div>` : ''}
        <div class="mfoot">
          <button class="btn primary" type="submit">解析并预览</button>
        </div>
      </form>
    </div>
  `;
  $('#imp2').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (fd.get('json') || '').trim();
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      Import.pasteText = text;
      Import.parseError = '不是合法 JSON：' + (err.message || err);
      render();
      return;
    }
    try {
      const prev = await api('/api/import/execution/preview', { method: 'POST', body: parsed });
      Import.pasteText = text;
      Import.preview = prev;
      Import.parseError = '';
      Import.step = 'preview';
      Import.confirmedStatus = [];
      // v1.0.9：新一轮 preview 带着新 token，commit 进行中标记复位
      Import.committing = false;
      render();
    } catch (err) {
      Import.pasteText = text;
      Import.parseError = err.message || String(err);
      render();
    }
  });
}

function renderImportExecPreview(el) {
  const p = Import.preview;
  if (!p) return renderImportExecPaste(el);
  const sec = p.security;
  const e = p.execution_to_add;
  el.innerHTML = `
    <a class="back" href="#/import">← 返回导入与更新</a>
    <div class="section-title"><h2>② 快速更新动态执行 · 第 2 步：预览</h2></div>
    <div class="panel">
      <h3 style="margin-top:0">即将新增 execution</h3>
      <div class="kv"><span class="w">标的</span><b>${esc(sec.name)}（${esc(sec.exchange)} · ${esc(sec.code)} · id=${esc(sec.id)}）</b></div>
      <div class="kv"><span class="w">当前状态</span>${esc(sec.status)}（不会被本次导入修改）</div>
      ${sec.current_latest_execution
        ? `<div class="kv"><span class="w">上一条 execution</span>${esc(sec.current_latest_execution.date)} · ${esc(sec.current_latest_execution.view)}</div>`
        : `<div class="kv muted"><span class="w">上一条 execution</span>暂无</div>`}
      <hr/>
      <div class="kv"><span class="w">判断日期</span><b>${esc(e.execution_date)}</b></div>
      <div class="kv"><span class="w">判断时价格</span>${e.price_snapshot != null ? esc(e.price_snapshot) : '—'}</div>
      <div class="kv"><span class="w">当前执行判断</span><b>${esc(e.execution_view)}</b></div>
      ${e.support_zone ? `<div class="kv"><span class="w">支撑</span>${esc(e.support_zone)}</div>` : ''}
      ${e.resistance_zone ? `<div class="kv"><span class="w">压力</span>${esc(e.resistance_zone)}</div>` : ''}
      ${e.technical_structure ? `<div class="kv"><span class="w">技术结构</span><span style="white-space:normal">${esc(e.technical_structure)}</span></div>` : ''}
      ${e.execution_condition ? `<div class="kv"><span class="w">等待条件</span><span style="white-space:normal">${esc(e.execution_condition)}</span></div>` : ''}
      ${e.reason ? `<div class="kv"><span class="w">依据</span><span style="white-space:normal">${esc(e.reason)}</span></div>` : ''}
    </div>
    <div class="banner warn"><span class="banner-tag">仅追加</span><span>本次确认将<b>追加一条</b>execution（append-only），同步写入 decision_ledger。<br>研究 / 静态计划 / 持仓 / 状态不会被修改。</span></div>
    <div class="mfoot">
      <button type="button" class="btn ghost" onclick="Import.step='paste';render();" ${Import.committing ? 'disabled' : ''}>返回修改</button>
      <button class="btn primary" type="button" data-commit-btn onclick="commitExec()" ${Import.committing ? 'disabled' : ''}>${Import.committing ? '正在写入…' : '确认并写入'}</button>
    </div>
  `;
}

async function commitExec() {
  if (!Import.preview) return;
  // v1.0.9：前端最小防重（真正的防重由服务端原子 claim 保证）
  if (Import.committing) { toast('正在写入，请稍候…', true); return; }
  Import.committing = true;
  render();
  try {
    const result = await api('/api/import/execution/commit', {
      method: 'POST', body: { token: Import.preview.token },
    });
    Import.committing = false;
    Import.commit = result;
    Import.step = 'done';
    render();
    try { await afterMutation(); } catch (e) {}
  } catch (err) {
    Import.committing = false;
    const msg = err.message || String(err);
    if (msg.indexOf('自预览后已发生变化') >= 0) {
      toast('数据已变化，请重新解析预览', true);
      Import.parseError = msg;
      Import.step = 'paste';
      render();
      return;
    }
    toast('快速更新失败：' + msg, true);
    render();
  }
}

function renderImportExecDone(el) {
  const r = Import.commit;
  if (!r) return renderImportExecPaste(el);
  el.innerHTML = `
    <div class="section-title"><h2>② 快速更新动态执行 · 第 3 步：完成</h2></div>
    <div class="panel">
      <div class="kv"><span class="w">导入完成</span><b style="color:var(--accent)">execution 已追加 1 条</b></div>
      <div class="kv"><span class="w">标的</span><b>${esc(r.security_name)}（${esc(r.security_exchange)} · ${esc(r.security_code)} · id=${esc(r.security_id)}）</b></div>
      <div class="kv"><span class="w">新增 execution id</span><b>#${esc(r.new_execution_id)}</b></div>
      <div class="kv muted"><span class="w">已写入决策台账</span>append-only ledger（event_type=动态执行判断更新）</div>
    </div>
    <div class="mfoot">
      <button class="btn ghost" onclick="backToImport()">返回导入与更新</button>
      <button class="btn primary" onclick="goHome()">返回工作台</button>
    </div>
  `;
}

/* ===== 启动 ===== */
(async function init() {
  window.addEventListener('hashchange', render);
  $('#btn-refresh').addEventListener('click', () => refreshQuotes(true, true));
  $('#btn-settings').addEventListener('click', openSettingsModal);
  try { await loadAll(); } catch (e) { /* 首页会显示错误 */ }
  await render();
  refreshQuotes();
  setInterval(() => refreshQuotes(), 60000);
})();
