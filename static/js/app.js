/* World Cup 2026 Predictor — dashboard.
   The visual language is the imported Claude design; every number is computed
   client-side by the real Dixon-Coles model (model.js) from the shipped JSON
   artifacts. No backend, no mock data. */

const $ = (id) => document.getElementById(id);
const pctR = (x) => Math.round(x * 100);
const flag = (n) => window.WCFlags.flagOf(n) || "⚽";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtDate = (iso) => { const [y, m, d] = iso.split("-"); return `${MONTHS[+m - 1]} ${+d} ${y}`; };

const D = {};            // loaded data
const lab = { home: "France", away: "Brazil", neutral: true, open: null, q: { home: "", away: "" } };
let LAB_TEAMS = [];

async function boot() {
  try {
    const [dc, pre, elo, fixtures, metrics] = await Promise.all(
      ["dc_model", "dc_pretournament", "elo", "fixtures", "metrics"]
        .map((f) => fetch(`data/${f}.json`).then((r) => r.json())));
    Object.assign(D, { dc, pre, elo, fixtures, metrics });
    D.known = new Set(dc.teams);
    D.knownPre = new Set(pre.teams);
  } catch (e) {
    $("chips").innerHTML = `<div style="color:#9aa6be">Could not load model data.</div>`;
    return;
  }
  LAB_TEAMS = Object.entries(D.elo)
    .filter(([n]) => window.WCFlags.hasFlag(n))
    .sort((a, b) => b[1] - a[1])
    .map(([name, elo]) => ({ name, elo: Math.round(elo), flag: flag(name) }));

  renderHero();
  renderChips();
  renderFooter();
  renderFixtures();
  renderBracket();
  const acc = renderTrack();
  $("hero-acc").innerHTML = `${Math.floor(acc * 100)}<span style="font-size:0.46em; color:#7df0c9;">%</span>`;
  buildLab();
  setupTabs();
}

// ---------- hero / chips / footer ----------
function renderChips() {
  const m = D.metrics, p = m.backtest.pooled;
  const chips = [
    { big: `RPS ${p.rps_model}`, label: "Ranked probability score", sub: `BEATS ELO ${p.rps_elo} · NAIVE ${p.rps_naive}` },
    { big: `${m.fitted_teams}`, label: "International teams rated", sub: "GLOBAL ELO + POISSON FIT" },
    { big: m.data.matches.toLocaleString(), label: "Matches in training set", sub: `${m.data.window} · TIME-WEIGHTED` },
    { big: fmtDate(D.fixtures.as_of), label: "Data current through", sub: "REFIT NIGHTLY" },
  ];
  $("chips").innerHTML = chips.map((c) => `
    <div style="padding:16px 17px; border-radius:14px; background:linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)); border:1px solid rgba(255,255,255,0.08);">
      <div style="font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:21px; letter-spacing:-0.01em; color:#f3f6fc;">${c.big}</div>
      <div style="font-size:12.5px; color:#aeb8cf; margin-top:5px; font-weight:500;">${c.label}</div>
      <div style="font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:0.05em; color:#6e7892; margin-top:7px;">${c.sub}</div>
    </div>`).join("");
}
function renderHero() { /* hero number filled after track is computed */ }
function renderFooter() {
  const m = D.metrics;
  $("footer-stats").innerHTML =
    `<div>OUT-OF-SAMPLE · NOT TRAINING FIT</div>
     <div>${m.data.matches.toLocaleString()} MATCHES · ${m.fitted_teams} TEAMS</div>
     <div>DATA THROUGH ${fmtDate(D.fixtures.as_of).toUpperCase()}</div>`;
}

// ---------- fixtures ----------
function fixtureCard(d) {
  const ml = d.most_likely_score.replace("-", " – ");
  return `
  <div style="position:relative; padding:18px 18px 16px; border-radius:16px; background:linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.012)); border:1px solid rgba(255,255,255,0.08);">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
      <span style="font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:0.1em; color:#9aa6be; padding:3px 8px; border:1px solid rgba(255,255,255,0.1); border-radius:6px;">${d.groupLabel}</span>
      <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:0.08em; color:#5f6b85;">${d.stageLabel}</span>
    </div>
    <div style="display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:8px; margin-bottom:16px;">
      <div style="min-width:0;">
        <div style="font-size:25px; line-height:1;">${flag(d.home)}</div>
        <div style="font-size:13.5px; font-weight:600; color:#e9eef8; margin-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${d.home}</div>
      </div>
      <div style="text-align:center; padding:0 4px;">
        <div style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:30px; letter-spacing:-0.02em; color:#f3f6fc;">${ml}</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:9px; letter-spacing:0.1em; color:#5f6b85; margin-top:2px;">EXP. SCORE</div>
      </div>
      <div style="min-width:0; text-align:right;">
        <div style="font-size:25px; line-height:1;">${flag(d.away)}</div>
        <div style="font-size:13.5px; font-weight:600; color:#e9eef8; margin-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${d.away}</div>
      </div>
    </div>
    <div style="display:flex; height:8px; border-radius:5px; overflow:hidden; background:rgba(255,255,255,0.06);">
      <div style="flex:0 0 ${d.p_home * 100}%; background:#2ee6a6;"></div>
      <div style="flex:0 0 ${d.p_draw * 100}%; background:#56617c;"></div>
      <div style="flex:0 0 ${d.p_away * 100}%; background:#f0b948;"></div>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:9px; font-family:'IBM Plex Mono',monospace; font-size:11.5px;">
      <span style="color:#2ee6a6; font-weight:600;">${pctR(d.p_home)}%<span style="color:#3c6f5e; font-size:9px; margin-left:3px;">WIN</span></span>
      <span style="color:#8893ac; font-weight:600;">${pctR(d.p_draw)}%<span style="color:#525c74; font-size:9px; margin-left:3px;">DRAW</span></span>
      <span style="color:#f0b948; font-weight:600;">${pctR(d.p_away)}%<span style="color:#7a6334; font-size:9px; margin-left:3px;">WIN</span></span>
    </div>
  </div>`;
}
function renderFixtures() {
  const up = D.fixtures.upcoming || [];
  let rows, heading, sub;
  if (up.length) {
    rows = up
      .map((fx) => ({ ...window.WCModel.predict(D.dc, D.known, D.elo, fx.home, fx.away, true),
                      groupLabel: `GROUP ${fx.group}`, stageLabel: "MATCHDAY 3", _k: fx.group }))
      .sort((a, b) => a._k.localeCompare(b._k));
    heading = "Remaining group-stage fixtures";
    sub = `${rows.length} matches · most-likely scoreline & outcome odds`;
  } else {
    // group stage finished → the next real matches are the Round of 32
    const seeds = (D.fixtures.bracket && D.fixtures.bracket.seeds) || [];
    rows = [];
    for (let i = 0; i < seeds.length; i += 2) {
      rows.push({ ...window.WCModel.predict(D.dc, D.known, D.elo, seeds[i], seeds[i + 1], true),
                  groupLabel: "ROUND OF 32", stageLabel: "KNOCKOUT" });
    }
    heading = "Round of 32 — next up";
    sub = `${rows.length} ties · 90-minute outcome odds · see the full path in Bracket`;
  }
  $("panel-fixtures").innerHTML = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:18px;">
      <h2 style="margin:0; font-size:19px; font-weight:700; letter-spacing:-0.01em; color:#f3f6fc;">${heading}</h2>
      <span style="font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:#6e7892;">${sub}</span>
    </div>
    <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(326px,1fr)); gap:14px;">
      ${rows.map(fixtureCard).join("")}
    </div>`;
}

// ---------- track record ----------
function renderTrack() {
  const cols = "62px 50px 1fr 132px 64px 42px";
  let correct = 0;
  const rows = D.fixtures.recent.map((r) => {
    const p = window.WCModel.predict(D.pre, D.knownPre, D.elo, r.home, r.away, r.neutral);
    const o = window.WCModel.predOutcome(p);
    const actual = r.home_score > r.away_score ? "H" : r.home_score === r.away_score ? "D" : "A";
    const hit = o === actual;
    if (hit) correct++;
    const pick = o === "H" ? r.home : o === "A" ? r.away : "Draw";
    return { ...r, pick, pickFlag: o === "D" ? "" : flag(pick), hit };
  });
  const total = rows.length;
  const acc = total ? correct / total : 0;
  const accPct = (Math.round(acc * 1000) / 10).toFixed(1);

  $("panel-record").innerHTML = `
    <div style="display:flex; flex-wrap:wrap; align-items:center; gap:clamp(18px,4vw,40px); padding:22px 24px; border-radius:18px; background:linear-gradient(110deg, rgba(46,230,166,0.10), rgba(46,230,166,0.02)); border:1px solid rgba(46,230,166,0.22); margin-bottom:22px;">
      <div>
        <div style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:clamp(46px,8vw,62px); line-height:0.9; letter-spacing:-0.03em; color:#2ee6a6;">${accPct}<span style="font-size:0.42em;">%</span></div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:0.1em; color:#7df0c9; margin-top:8px;">CALLED CORRECTLY · OUT-OF-SAMPLE</div>
      </div>
      <div style="flex:1 1 220px; min-width:200px;">
        <div style="font-size:14px; line-height:1.6; color:#cdd6e8;">${correct} of ${total} settled group games called by the pre-tournament model. Each pick was locked <span style="color:#fff; font-weight:600;">before kickoff</span> — no hindsight, no retraining.</div>
        <div style="display:flex; height:7px; border-radius:5px; overflow:hidden; background:rgba(255,255,255,0.08); margin-top:14px; max-width:360px;">
          <div style="flex:0 0 ${acc * 100}%; background:linear-gradient(90deg,#2ee6a6,#1b9c87);"></div>
        </div>
      </div>
    </div>
    <div style="border-radius:16px; overflow:hidden; border:1px solid rgba(255,255,255,0.08);">
      <div style="display:grid; grid-template-columns:${cols}; gap:10px; padding:11px 16px; background:rgba(255,255,255,0.035); font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:0.1em; color:#6e7892;">
        <span>DATE</span><span>GRP</span><span>MATCH</span><span>MODEL PICK</span><span>SCORE</span><span style="text-align:right;">CALL</span>
      </div>
      ${rows.map((r) => `
        <div style="display:grid; grid-template-columns:${cols}; gap:10px; align-items:center; padding:13px 16px; border-top:1px solid rgba(255,255,255,0.055); background:${r.hit ? "rgba(46,230,166,0.04)" : "rgba(240,100,139,0.045)"};">
          <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; color:#8893ac;">${r.date.slice(5)}</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#9aa6be;">${r.group}</span>
          <span style="font-size:13.5px; color:#e9eef8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${flag(r.home)} ${r.home} <span style="color:#5f6b85;">v</span> ${r.away} ${flag(r.away)}</span>
          <span style="font-size:13px; color:#cdd6e8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${r.pickFlag} ${r.pick}</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; color:#e9eef8;">${r.home_score}-${r.away_score}</span>
          <span style="text-align:right; font-size:15px; font-weight:700; color:${r.hit ? "#2ee6a6" : "#f0648b"};">${r.hit ? "✓" : "✗"}</span>
        </div>`).join("")}
    </div>`;
  return acc;
}

// ---------- match lab ----------
function buildLab() {
  $("panel-lab").innerHTML = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:16px;">
      <h2 style="margin:0; font-size:19px; font-weight:700; letter-spacing:-0.01em; color:#f3f6fc;">Match lab</h2>
      <span style="font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:#6e7892;">${LAB_TEAMS.length} rated nations · live model</span>
    </div>
    <div id="lab-backdrop" style="position:fixed; inset:0; z-index:15; display:none;"></div>
    <div style="position:relative; z-index:16; display:grid; grid-template-columns:1fr auto 1fr; gap:12px; align-items:end; margin-bottom:18px;">
      ${picker("home", "HOME / TEAM A", "#2ee6a6")}
      <button type="button" id="neutral-btn" style="display:flex; flex-direction:column; align-items:center; gap:5px; padding:9px 13px; border-radius:12px; cursor:pointer; min-width:84px;"></button>
      ${picker("away", "AWAY / TEAM B", "#f0b948")}
    </div>
    <div id="lab-results"></div>`;

  $("neutral-btn").addEventListener("click", () => { lab.neutral = !lab.neutral; updateResults(); });
  $("lab-backdrop").addEventListener("click", closeDrops);
  ["home", "away"].forEach((side) => {
    $(`${side}-btn`).addEventListener("click", (e) => { e.stopPropagation(); toggleDrop(side); });
    $(`${side}-search`).addEventListener("input", (e) => { lab.q[side] = e.target.value; fillOptions(side); });
    fillOptions(side);
  });
  updateResults();
}

function picker(side, label, color) {
  const align = side === "away" ? "text-align:right;" : "";
  return `
  <div style="position:relative;">
    <label style="display:block; font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:0.12em; color:${color}; margin-bottom:8px; ${align}">${label}</label>
    <button type="button" id="${side}-btn" style="width:100%; display:flex; align-items:center; gap:9px; padding:13px 14px; border-radius:12px; background:rgba(255,255,255,0.045); border:1px solid rgba(255,255,255,0.1); color:#e9eef8; font-size:15px; font-weight:600; font-family:'Inter',sans-serif; cursor:pointer; text-align:left;">
      <span id="${side}-flag" style="font-size:20px;"></span>
      <span id="${side}-name" style="flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"></span>
      <span style="color:#5f6b85; font-size:11px;">▾</span>
    </button>
    <div id="${side}-drop" style="display:none; position:absolute; z-index:20; top:100%; left:0; right:0; margin-top:6px; background:#0d1424; border:1px solid rgba(255,255,255,0.12); border-radius:12px; box-shadow:0 24px 50px rgba(0,0,0,0.55); overflow:hidden;">
      <input type="text" id="${side}-search" placeholder="Search ${LAB_TEAMS.length} nations…" style="width:100%; padding:12px 14px; background:rgba(255,255,255,0.04); border:none; border-bottom:1px solid rgba(255,255,255,0.08); color:#e9eef8; font-size:14px; font-family:'Inter',sans-serif; outline:none;">
      <div id="${side}-opts" style="max-height:264px; overflow-y:auto;"></div>
    </div>
  </div>`;
}

function fillOptions(side) {
  const q = lab.q[side].trim().toLowerCase();
  const cur = lab[side];
  const accent = side === "home" ? "rgba(46,230,166,0.1)" : "rgba(240,185,72,0.1)";
  const opts = LAB_TEAMS.filter((t) => !q || t.name.toLowerCase().includes(q)).slice(0, 60);
  $(`${side}-opts`).innerHTML = opts.map((t) => `
    <button type="button" class="wc-opt" data-side="${side}" data-name="${t.name}"
      style="width:100%; display:flex; align-items:center; gap:10px; padding:10px 14px; background:${t.name === cur ? accent : "transparent"}; border:none; color:#dbe2f0; font-size:14px; font-family:'Inter',sans-serif; cursor:pointer; text-align:left;">
      <span style="font-size:18px;">${t.flag}</span>
      <span style="flex:1;">${t.name}</span>
      <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#5f6b85;">${t.elo}</span>
    </button>`).join("");
  $(`${side}-opts`).querySelectorAll(".wc-opt").forEach((b) =>
    b.addEventListener("click", () => { lab[b.dataset.side] = b.dataset.name; closeDrops(); updateResults(); }));
}

function toggleDrop(side) {
  const open = lab.open === side ? null : side;
  lab.open = open;
  ["home", "away"].forEach((s) => {
    $(`${s}-drop`).style.display = s === open ? "block" : "none";
    $(`${s}-btn`).style.borderColor = s === open
      ? (s === "home" ? "rgba(46,230,166,0.5)" : "rgba(240,185,72,0.5)") : "rgba(255,255,255,0.1)";
  });
  $("lab-backdrop").style.display = open ? "block" : "none";
  if (open) { lab.q[open] = ""; $(`${open}-search`).value = ""; fillOptions(open); $(`${open}-search`).focus(); }
}
function closeDrops() {
  lab.open = null;
  ["home", "away"].forEach((s) => { $(`${s}-drop`).style.display = "none"; $(`${s}-btn`).style.borderColor = "rgba(255,255,255,0.1)"; });
  $("lab-backdrop").style.display = "none";
}

function updateResults() {
  $("home-flag").textContent = flag(lab.home);
  $("home-name").textContent = lab.home;
  $("away-flag").textContent = flag(lab.away);
  $("away-name").textContent = lab.away;
  const nb = $("neutral-btn");
  nb.style.background = lab.neutral ? "rgba(255,255,255,0.04)" : "rgba(46,230,166,0.12)";
  nb.style.border = `1px solid ${lab.neutral ? "rgba(255,255,255,0.1)" : "rgba(46,230,166,0.4)"}`;
  nb.innerHTML = `<span style="font-size:17px;">${lab.neutral ? "🏟️" : "🏠"}</span>
    <span style="font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:0.06em; color:${lab.neutral ? "#9aa6be" : "#2ee6a6"};">${lab.neutral ? "NEUTRAL" : "HOME ADV"}</span>`;

  const d = window.WCModel.predict(D.dc, D.known, D.elo, lab.home, lab.away, lab.neutral);
  const maxTop = d.top_scores[0][1] || 1;
  $("lab-results").innerHTML = `
    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:14px;">
      ${probCard(flag(lab.home), pctR(d.p_home), `${lab.home} WIN`, "#2ee6a6", "rgba(46,230,166,0.14)", "rgba(46,230,166,0.3)", "#7df0c9")}
      ${probCard("✕", pctR(d.p_draw), "DRAW", "#cdd6e8", "rgba(255,255,255,0.04)", "rgba(255,255,255,0.1)", "#8893ac", true)}
      ${probCard(flag(lab.away), pctR(d.p_away), `${lab.away} WIN`, "#f0b948", "rgba(240,185,72,0.14)", "rgba(240,185,72,0.3)", "#f0b948")}
    </div>
    <div style="display:flex; height:9px; border-radius:6px; overflow:hidden; background:rgba(255,255,255,0.06); margin-bottom:18px;">
      <div style="flex:0 0 ${d.p_home * 100}%; background:#2ee6a6;"></div>
      <div style="flex:0 0 ${d.p_draw * 100}%; background:#56617c;"></div>
      <div style="flex:0 0 ${d.p_away * 100}%; background:#f0b948;"></div>
    </div>
    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:14px;">
      <div style="padding:20px; border-radius:16px; background:rgba(255,255,255,0.028); border:1px solid rgba(255,255,255,0.08);">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:0.12em; color:#6e7892; margin-bottom:16px;">TOP 5 MOST-LIKELY SCORELINES</div>
        ${d.top_scores.map(([label, p]) => `
          <div style="display:grid; grid-template-columns:54px 1fr 48px; gap:12px; align-items:center; margin-bottom:13px;">
            <span style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:17px; color:#e9eef8;">${label}</span>
            <div style="height:7px; border-radius:4px; background:rgba(255,255,255,0.06); overflow:hidden;">
              <div style="height:100%; width:${(p / maxTop) * 100}%; background:linear-gradient(90deg,#2ee6a6,#1b9c87); border-radius:4px;"></div>
            </div>
            <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; color:#aeb8cf; text-align:right;">${pctR(p)}%</span>
          </div>`).join("")}
      </div>
      <div style="padding:20px; border-radius:16px; background:rgba(255,255,255,0.028); border:1px solid rgba(255,255,255,0.08);">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:0.12em; color:#6e7892; margin-bottom:16px;">MATCH METRICS</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
          ${metric(d.exp_goals[0], `${lab.home} xG`, "#2ee6a6", "rgba(46,230,166,0.07)", "rgba(46,230,166,0.16)")}
          ${metric(d.exp_goals[1], `${lab.away} xG`, "#f0b948", "rgba(240,185,72,0.07)", "rgba(240,185,72,0.16)")}
          ${metric(pctR(d.p_over_2_5) + "<span style='font-size:0.55em; color:#6e7892;'>%</span>", "Over 2.5 goals", "#e9eef8", "rgba(255,255,255,0.035)", "rgba(255,255,255,0.08)")}
          ${metric(pctR(d.p_btts) + "<span style='font-size:0.55em; color:#6e7892;'>%</span>", "Both teams score", "#e9eef8", "rgba(255,255,255,0.035)", "rgba(255,255,255,0.08)")}
        </div>
        <div style="margin-top:15px; padding-top:14px; border-top:1px solid rgba(255,255,255,0.07); display:flex; align-items:center; justify-content:space-between;">
          <span style="font-size:12.5px; color:#9aa6be;">Most-likely scoreline</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:18px; color:#f3f6fc;">${d.most_likely_score.replace("-", " – ")}</span>
        </div>
      </div>
    </div>`;
}

function probCard(icon, pct, label, color, bg, border, labelColor, plain) {
  return `<div style="padding:18px 16px; border-radius:16px; background:${plain ? bg : `linear-gradient(180deg, ${bg}, rgba(255,255,255,0.02))`}; border:1px solid ${border}; text-align:center;">
    <div style="font-size:22px; ${icon === "✕" ? "color:#8893ac;" : ""}">${icon}</div>
    <div style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:clamp(30px,6vw,44px); letter-spacing:-0.03em; color:${color}; margin-top:4px;">${pct}<span style="font-size:0.42em;">%</span></div>
    <div style="font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:0.1em; color:${labelColor}; margin-top:2px;">${label}</div>
  </div>`;
}
function metric(val, label, color, bg, border) {
  return `<div style="padding:14px; border-radius:12px; background:${bg}; border:1px solid ${border};">
    <div style="font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:26px; color:${color};">${val}</div>
    <div style="font-size:11.5px; color:#9aa6be; margin-top:3px;">${label}</div>
  </div>`;
}

// ---------- bracket ----------
function playMatch(home, away) {
  const p = window.WCModel.predict(D.dc, D.known, D.elo, home, away, true);
  const aAdv = p.p_home + p.p_draw / 2, bAdv = p.p_away + p.p_draw / 2;
  const aWin = aAdv >= bAdv;
  const ae = D.elo[home] || 1500, be = D.elo[away] || 1500;
  return {
    a: { name: home, adv: aAdv, win: aWin },
    b: { name: away, adv: bAdv, win: !aWin },
    winner: aWin ? home : away,
    winAdv: aWin ? aAdv : bAdv,
    upset: aWin ? ae < be : be < ae,
  };
}

function teamRow(c, top) {
  return `<div style="display:flex; align-items:center; gap:7px; padding:7px 9px; ${top ? "border-bottom:1px solid rgba(255,255,255,0.06);" : ""} background:${c.win ? "rgba(46,230,166,0.10)" : "transparent"};">
    <span style="font-size:14px;">${flag(c.name)}</span>
    <span style="flex:1; font-size:12px; font-weight:${c.win ? 600 : 500}; color:${c.win ? "#e9eef8" : "#7e89a3"}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${c.name}</span>
    <span style="font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:${c.win ? "#2ee6a6" : "#5f6b85"};">${Math.round(c.adv * 100)}</span>
  </div>`;
}
const tieCell = (m) => `<div style="position:relative; width:100%; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.09); border-radius:9px; overflow:hidden;">
    ${m.upset ? `<span style="position:absolute; top:5px; right:6px; z-index:2; font-family:'IBM Plex Mono',monospace; font-size:7px; letter-spacing:0.05em; color:#0a0f1a; background:#f0b948; padding:1px 4px; border-radius:3px; font-weight:700;">UPSET</span>` : ""}
    ${teamRow(m.a, true)}${teamRow(m.b, false)}
  </div>`;
const bracketCol = (ties) => `<div style="flex:0 0 158px; display:flex; flex-direction:column;">${ties
    .map((m) => `<div style="flex:1; display:flex; align-items:center;">${tieCell(m)}</div>`).join("")}</div>`;
const SPACER = `<div style="flex:0 0 28px;"></div>`;
const colLabel = (t) => `<div style="flex:0 0 158px;">${t}</div>`;

function renderBracket() {
  const b = D.fixtures.bracket;
  if (!b || !b.seeds) { $("panel-bracket").innerHTML = `<p class="muted">Bracket unavailable.</p>`; return; }
  const seeds = b.seeds;
  const r32 = [];
  for (let i = 0; i < 32; i += 2) r32.push(playMatch(seeds[i], seeds[i + 1]));
  const next = (prev) => { const o = []; for (let i = 0; i < prev.length; i += 2) o.push(playMatch(prev[i].winner, prev[i + 1].winner)); return o; };
  const r16 = next(r32), qf = next(r16), sf = next(qf), fin = next(sf);
  const champ = fin[0].winner, champAdv = fin[0].winAdv;

  const note = b.projected
    ? `<div style="padding:11px 14px; border-radius:10px; background:rgba(240,185,72,0.08); border:1px solid rgba(240,185,72,0.22); color:#d9c08a; font-size:12.5px; line-height:1.5; margin-bottom:16px;">
         Group stage in progress (${b.groups_complete}/12 groups final) — the 32-team field is <b>projected</b> from current standings plus the model's predicted remaining group games, power-seeded by rating. It firms up daily as groups finish.
       </div>` : "";

  $("panel-bracket").innerHTML = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:6px;">
      <h2 style="margin:0; font-size:19px; font-weight:700; letter-spacing:-0.01em; color:#f3f6fc;">Predicted path to the final</h2>
      <span style="font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:#6e7892;">model favourite advances each tie · neutral venue</span>
    </div>
    <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:16px; font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:#6e7892;">
      <span style="display:inline-flex; align-items:center; gap:6px;"><span style="width:10px; height:10px; border-radius:3px; background:rgba(46,230,166,0.6);"></span>ADVANCES (WIN + ½ DRAW)</span>
      <span style="display:inline-flex; align-items:center; gap:6px;"><span style="font-size:8px; color:#0a0f1a; background:#f0b948; padding:1px 4px; border-radius:3px; font-weight:700;">UPSET</span>LOWER-RATED SIDE WINS</span>
    </div>
    ${note}
    <div style="overflow-x:auto; padding-bottom:10px;">
      <div style="min-width:1090px;">
        <div style="display:flex; margin-bottom:12px; font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:0.12em; color:#5f6b85; text-align:center;">
          ${colLabel("ROUND OF 32")}${SPACER}${colLabel("ROUND OF 16")}${SPACER}${colLabel("QUARTER-FINALS")}${SPACER}${colLabel("SEMI-FINALS")}${SPACER}${colLabel("FINAL")}<div style="flex:0 0 30px;"></div><div style="flex:0 0 150px; color:#f0b948;">CHAMPION</div>
        </div>
        <div style="display:flex; height:clamp(820px,116vh,1000px);">
          ${bracketCol(r32)}${SPACER}${bracketCol(r16)}${SPACER}${bracketCol(qf)}${SPACER}${bracketCol(sf)}${SPACER}${bracketCol(fin)}<div style="flex:0 0 30px;"></div>
          <div style="flex:0 0 150px; display:flex; align-items:center;">
            <div style="width:100%; padding:16px 12px; text-align:center; border-radius:12px; background:linear-gradient(180deg, rgba(240,185,72,0.16), rgba(240,185,72,0.03)); border:1px solid rgba(240,185,72,0.35);">
              <div style="font-size:30px;">${flag(champ)}</div>
              <div style="font-size:14px; font-weight:700; color:#f3f6fc; margin-top:6px;">${champ}</div>
              <div style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:#f0b948; margin-top:4px;">${Math.round(champAdv * 100)}% TO WIN THE FINAL</div>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

// ---------- tabs ----------
function setupTabs() {
  const tabs = ["fixtures", "bracket", "record", "lab"];
  const btns = document.querySelectorAll(".wc-tab");
  const activate = (t) => {
    const idx = tabs.indexOf(t);
    if (idx < 0) return;
    btns.forEach((x) => x.classList.toggle("active", x.dataset.tab === t));
    tabs.forEach((name) => { $(`panel-${name}`).hidden = name !== t; });
    $("tab-ind").style.transform = `translateX(${idx * 100}%)`;
    const panel = $(`panel-${t}`);
    panel.style.animation = "none"; void panel.offsetWidth; panel.style.animation = "";
    if (t === "lab") closeDrops();
  };
  btns.forEach((b) => b.addEventListener("click", () => {
    activate(b.dataset.tab);
    history.replaceState(null, "", `#${b.dataset.tab}`);
  }));
  // deep-link: open the tab named in the URL hash (e.g. #bracket), else the first
  activate(tabs.includes(location.hash.slice(1)) ? location.hash.slice(1) : "fixtures");
}

boot();
