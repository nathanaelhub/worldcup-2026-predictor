/* Fully client-side dashboard — loads the model coefficients + fixtures as static
   JSON and computes every prediction in the browser via model.js. No backend. */

const $ = (id) => document.getElementById(id);
const pct = (x) => `${Math.round(x * 100)}%`;
const outcomeOf = (hs, as_) => (hs > as_ ? "H" : hs === as_ ? "D" : "A");

const probBar = (d) => `
  <div class="bar">
    <i class="h" style="width:${d.p_home * 100}%">${Math.round(d.p_home * 100)}</i>
    <i class="d" style="width:${d.p_draw * 100}%">${Math.round(d.p_draw * 100)}</i>
    <i class="a" style="width:${d.p_away * 100}%">${Math.round(d.p_away * 100)}</i>
  </div>`;

// tab switching
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $(t.dataset.tab).classList.add("active");
  });
});

const DATA = {};

async function boot() {
  try {
    const [dc, pre, elo, fixtures, metrics] = await Promise.all([
      "dc_model", "dc_pretournament", "elo", "fixtures", "metrics",
    ].map((f) => fetch(`data/${f}.json`).then((r) => r.json())));
    Object.assign(DATA, { dc, pre, elo, fixtures, metrics });
    DATA.known = new Set(dc.teams);
    DATA.knownPre = new Set(pre.teams);
  } catch (e) {
    $("modelcard").innerHTML = `<span class="muted">Could not load model data.</span>`;
    return;
  }
  renderCard();
  renderUpcoming();
  renderTrack();
  renderTeams();
}

function renderCard() {
  const m = DATA.metrics;
  const p = (m.backtest && m.backtest.pooled) || {};
  $("modelcard").innerHTML = `
    <div class="stat"><span class="v good">${pct(p.outcome_accuracy || 0)}</span><span class="k">Backtest accuracy</span></div>
    <div class="stat"><span class="v">${p.rps_model ?? "–"}</span><span class="k">RPS (vs ${p.rps_elo} Elo)</span></div>
    <div class="stat"><span class="v">${m.fitted_teams}</span><span class="k">Teams rated</span></div>
    <div class="stat"><span class="v">${(m.data.matches / 1000).toFixed(0)}k</span><span class="k">Matches ${m.data.window}</span></div>
    <div class="stat"><span class="v">${DATA.fixtures.as_of}</span><span class="k">Data through</span></div>`;
}

function renderUpcoming() {
  const rows = DATA.fixtures.upcoming
    .map((fx) => ({ ...WCModel.predict(DATA.dc, DATA.known, DATA.elo, fx.home, fx.away, true), group: fx.group }))
    .sort((a, b) => a.group.localeCompare(b.group));
  $("upcoming-grid").innerHTML = rows
    .map((d) => `
      <div class="fx">
        <div class="grp">Group ${d.group}</div>
        <div class="teams"><b>${d.home}</b> <span class="score">${d.top_scores[0][0]}</span> <b>${d.away}</b></div>
        ${probBar(d)}
        <div class="legend"><span>${d.home} ${pct(d.p_home)}</span><span>Draw ${pct(d.p_draw)}</span><span>${d.away} ${pct(d.p_away)}</span></div>
      </div>`)
    .join("");
}

function renderTrack() {
  let correct = 0;
  const rows = DATA.fixtures.recent.map((r) => {
    const p = WCModel.predict(DATA.pre, DATA.knownPre, DATA.elo, r.home, r.away, r.neutral);
    const actual = outcomeOf(r.home_score, r.away_score);
    const hit = WCModel.predOutcome(p) === actual;
    if (hit) correct++;
    const pick = WCModel.predOutcome(p) === "D" ? "Draw" : p.favorite;
    return { ...r, pick, hit };
  });
  $("acc-pct").textContent = pct(rows.length ? correct / rows.length : 0);
  $("track-body").innerHTML = rows
    .map((x) => `
      <tr>
        <td class="muted">${x.date.slice(5)}</td>
        <td>${x.group}</td>
        <td>${x.home} <span class="muted">v</span> ${x.away}</td>
        <td>${x.pick}</td>
        <td><b>${x.home_score}-${x.away_score}</b></td>
        <td>${x.hit ? '<span class="tick">✓</span>' : '<span class="cross">✗</span>'}</td>
      </tr>`)
    .join("");
}

function renderTeams() {
  const ranked = Object.entries(DATA.elo).sort((a, b) => b[1] - a[1]);
  const opts = ranked.map(([t, r]) => `<option value="${t}">${t} (${Math.round(r)})</option>`).join("");
  $("home").innerHTML = opts;
  $("away").innerHTML = opts;
  if (ranked[1]) $("away").value = ranked[1][0];
}

function runLab() {
  const d = WCModel.predict(DATA.dc, DATA.known, DATA.elo, $("home").value, $("away").value, $("neutral").checked);
  $("lab-result").classList.remove("hidden");
  $("lbl-home").textContent = d.home;
  $("lbl-away").textContent = d.away;
  $("p-home").textContent = pct(d.p_home);
  $("p-draw").textContent = pct(d.p_draw);
  $("p-away").textContent = pct(d.p_away);
  $("top-scores").innerHTML = d.top_scores.map(([s, p]) => `<li><b>${s}</b> · ${pct(p)}</li>`).join("");
  $("lab-meta").textContent =
    `xG ${d.exp_goals[0]}–${d.exp_goals[1]} · Over 2.5: ${pct(d.p_over_2_5)} · BTTS: ${pct(d.p_btts)} · model: ${d.source}`;
}
$("go").addEventListener("click", runLab);

boot();
