'use strict';

/* ==================================================================
   A/H 投研交易工作台 · 前端  v1.0.6
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
const S = { secs: [], settings: {}, quotes: {}, quoteTime: '', quoteError: '',
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
const findSec = id => S.secs.find(s => s.id === Number(id));
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

async function refreshQuotes(manual) {
  if (!S.secs.length) return;
  const symbols = [...new Set(S.secs.map(txSymbol))].join(',');
  try {
    const data = await api('/api/quotes?symbols=' + encodeURIComponent(symbols));
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
  }
  updateQuoteStatus();
  if (manual) toast(S.quoteError ? '行情已刷新，但接口出现错误' : '行情已刷新');
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
  const [secs, st] = await Promise.all([api('/api/securities'), api('/api/settings')]);
  S.secs = secs;
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
  return { page: 'home' };
}
function setActiveNav(page) {
  document.querySelectorAll('.topbar nav a').forEach(a => {
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
    </table></div>` : '<div class="empty">暂无标的，点击右上角「新建标的」开始。</div>'}
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
    const o = S.secs.find(x => x.id === s.ah_link_id);
    if (o) ahHtml = ` · A/H 关联：<a href="#/s/${o.id}">${esc(o.name)}（${esc(o.code)}.${esc(o.exchange)}）</a>`;
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
  openModal('编辑基本信息 · ' + s.name, `
    ${fld('公司名称', `<input name="name" required value="${esc(s.name)}">`, true)}
    ${fld('行业 / 主题', `<input name="sector" value="${esc(s.sector || '')}">`)}
    ${fld('A/H 两地上市关联', `<select name="ah_link_id"><option value="">— 无 —</option>${others.map(o => `<option value="${o.id}"${s.ah_link_id === o.id ? ' selected' : ''}>${esc(o.name)}（${esc(o.code)}.${esc(o.exchange)}）</option>`).join('')}</select>`)}
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

/* ===== 启动 ===== */
(async function init() {
  window.addEventListener('hashchange', render);
  $('#btn-refresh').addEventListener('click', () => refreshQuotes(true));
  $('#btn-settings').addEventListener('click', openSettingsModal);
  try { await loadAll(); } catch (e) { /* 首页会显示错误 */ }
  await render();
  refreshQuotes();
  setInterval(() => refreshQuotes(), 60000);
})();
