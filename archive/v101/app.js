'use strict';

/* ==================================================================
   A/H 投研交易工作台 · 前端
   原则：系统只展示事实（价格区间关系、验证项状态），绝不生成买卖建议；
        一切"下一动作"均来自用户已录入的交易计划。
   ================================================================== */

/* ===== 全局状态 ===== */
const S = { secs: [], settings: {}, quotes: {}, quoteTime: '', quoteError: '',
            lastSuccessAt: '', lastError: '', lastErrorAt: '' };
const STATUSES = ['可交易', '等价格', '等证据', '持仓中', '暂不参与'];
const STATUS_CLS = { '可交易': 'b-ready', '等价格': 'b-wait', '等证据': 'b-proof', '持仓中': 'b-hold', '暂不参与': 'b-pause' };

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
function priceFacts(price, plan, cur) {
  const facts = [];
  if (price == null || !plan) return facts;
  const d = decOf(cur);
  const fl = plan.first_zone_low, fh = plan.first_zone_high;
  const al = plan.add_zone_low, ah = plan.add_zone_high;
  const ol = plan.odds_zone_low, oh = plan.odds_zone_high;
  const nc = plan.no_chase_price;
  if (inZone(price, ol, oh)) facts.push({ level: 'z3', text: '当前价格已进入强赔率区' });
  if (inZone(price, al, ah)) facts.push({ level: 'z2', text: '当前价格已进入加仓区' });
  if (inZone(price, fl, fh)) facts.push({ level: 'z1', text: '当前价格已进入首仓区' });
  if (nc != null && price > nc) facts.push({ level: 'danger', text: '当前价格已超过不追价（' + num(nc, d) + '）' });
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
  (priceFacts(price, sec.plan || {}, sec.currency) || []).forEach(f => {
    if (f.level !== 'muted') flags.push(f.text);
  });
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
function sampleBanner() {
  return `<div class="notice">
    <span>当前展示的是<b>示例数据</b>（美图公司、道通科技）。请在标的详情页将研究结论与交易计划编辑为实际内容，数据结构即为正式用法。</span>
    <button class="btn sm ghost" onclick="dismissSample()">知道了</button>
  </div>`;
}
function dismissSample() { localStorage.setItem('wb_sample_ok', '1'); render(); }

function cardHtml(s) {
  const q = quoteOf(s);
  const d = decOf(s.currency);
  const plan = s.plan || {};
  const facts = priceFacts(q ? q.current : null, plan, s.currency);
  const mainFact = facts.find(f => f.level !== 'muted') || facts[0];
  const flags = attention(s);
  return `<div class="card" onclick="location.hash='#/s/${s.id}'">
    <div class="card-top">
      <div><div class="card-name">${esc(s.name)}</div><div class="card-code">${esc(s.code)}.${esc(s.exchange)} · ${esc(s.sector || '')}</div></div>
      ${statusBadge(s.status)}
    </div>
    <div class="card-price">${q ? curSym(s.currency) + ' ' + num(q.current, d) : '暂无行情'}
      ${q ? `<span class="chg ${q.change_pct >= 0 ? 'up' : 'down'}">${q.change_pct >= 0 ? '+' : ''}${num(q.change_pct, 2)}%</span>` : ''}
    </div>
    <div class="card-quote-time muted">${q ? esc(quoteTimeHint(q)) : '尚未获取行情'}</div>
    <div class="card-fact">${mainFact ? esc(mainFact.text) : '暂无价格事实'}</div>
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

function renderHome(el) {
  const attn = S.secs.filter(s => attention(s).length > 0);
  const rest = S.secs.filter(s => !attention(s).length);
  const banner = (!localStorage.getItem('wb_sample_ok') && S.secs.length) ? sampleBanner() : '';
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
  // v1.0.1：market_value / market_value_currency 由后端 compute_position 计算
  // HKD 缺汇率时 market_value=None，position_pct=None
  if (pos && pos.quantity > 0) {
    const q = quoteOf(s);
    const price = q ? q.current : null;
    const upnl = price != null ? (price - pos.avg_cost) * pos.quantity : null;
    const upct = price != null && pos.avg_cost ? (price / pos.avg_cost - 1) * 100 : null;
    let mvDisplay;
    if (pos.market_value != null) {
      mvDisplay = `¥ ${num(pos.market_value, 0)}`;
    } else if (s.currency === 'HKD' && pos.fx_rate_missing) {
      // 港股 HKD→CNY 汇率未配置，明确提示
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
        <div class="zone"><span>摊薄成本</span><b>${curSym(s.currency)} ${num(pos.avg_cost, cdec)}</b><i></i></div>
        <div class="zone"><span>持仓市值${pos.market_value_currency ? '（已折算）' : ''}</span><b>${mvDisplay}</b><i>${pos.market_value_currency ? '¥ (' + esc(pos.market_value_currency) + ')' : s.currency === 'HKD' ? '原币: HK$ ' + num(price ? price * pos.quantity : 0, 0) : '原币: ¥ ' + num(price ? price * pos.quantity : 0, 0)}</i></div>
        <div class="zone"><span>浮动盈亏</span><b class="${upnl != null ? (upnl >= 0 ? 'up' : 'down') : ''}">${upnl != null ? (upnl >= 0 ? '+' : '') + num(upnl, 0) + (upct != null ? '（' + (upct >= 0 ? '+' : '') + num(upct, 2) + '%）' : '') : '—'}</b><i></i></div>
        <div class="zone"><span>已实现盈亏</span><b class="${pos.realized_pnl >= 0 ? 'up' : 'down'}">${pos.realized_pnl >= 0 ? '+' : ''}${num(pos.realized_pnl, 0)}</b><i></i></div>
        <div class="zone"><span>真实仓位</span><b>${pctDisplay}</b><i>${pctHint}</i></div>
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
      ${(r && r.report_link) ? `<div class="kv"><span class="w">研究报告</span><a href="${esc(r.report_link)}" target="_blank" rel="noopener">${esc(r.report_link)}</a></div>` : ''}
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
      ${fld('新状态', `<select name="status">${STATUSES.map(x => `<option${x === s.status ? '' : ''}>${x}</option>`).join('')}</select>`)}
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

function openSettingsModal() {
  openModal('设置', `
    ${fld('账户总规模（元，CNY，用于计算真实仓位占比）', `<input name="account_size_cny" type="number" step="any" value="${esc(S.settings.account_size_cny || '')}" placeholder="例如：1000000">`)}
    ${fld('港元兑人民币汇率（HKD→CNY）', `<input name="hkd_cny_rate" type="number" step="any" value="${esc(S.settings.hkd_cny_rate || '0.92')}">`)}
    <div class="form-hint">真实仓位 = 持仓市值（港股按上述汇率折算）÷ 账户总规模。该数字仅用于展示事实，不影响任何判断。</div>
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
