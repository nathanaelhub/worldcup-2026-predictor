const $ = (id) => document.getElementById(id);
const pct = (x) => `${Math.round(x * 100)}%`;
const get = (u) => fetch(u).then((r) => r.json());

// ---- tabs ----
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $(t.dataset.tab).classList.add("active");
  });
});

const probBar = (d) => `
  <div class="bar">
    <i class="h" style="width:${d.p_home * 100}%">${Math.round(d.p_home * 100)}</i>
    <i class="d" style="width:${d.p_draw * 100}%">${Math.round(d.p_draw * 100)}</i>
    <i class="a" style="width:${d.p_away * 100}%">${Math.round(d.p_away * 100)}</i>
  </div>`;

// ---- model card ----
async function loadCard() {
  const m = await get("/api/metrics");
  if (!m.ready) {
    $("modelcard").innerHTML = `<span class="muted">Run <code>python scripts/train.py</code> to build the model.</span>`;
    return;
  }
  const p = m.backtest.pooled || {};
  $("modelcard").innerHTML = `
    <div class="stat"><span class="v good">${pct(p.outcome_accuracy || 0)}</span><span class="k">Backtest accuracy</span></div>
    <div class="stat"><span class="v">${p.rps_model ?? "–"}</span><span class="k">RPS (vs ${p.rps_elo} Elo)</span></div>
    <div class="stat"><span class="v">${m.fitted_teams}</span><span class="k">Teams rated</span></div>
    <div class="stat"><span class="v">${(m.data.matches / 1000).toFixed(0)}k</span><span class="k">Matches ${m.data.window}</span></div>
    <div class="stat"><span class="v">${m.as_of}</span><span class="k">Data through</span></div>`;
}

// ---- upcoming fixtures ----
async function loadUpcoming() {
  const r = await get("/api/upcoming");
  if (!r.ready) return;
  $("upcoming-grid").innerHTML = r.fixtures
    .map(
      (d) => `
    <div class="fx">
      <div class="grp">Group ${d.group}</div>
      <div class="teams"><b>${d.home}</b> <span class="score">${d.most_likely_score}</span> <b>${d.away}</b></div>
      ${probBar(d)}
      <div class="legend"><span>${d.home} ${pct(d.p_home)}</span><span>Draw ${pct(d.p_draw)}</span><span>${d.away} ${pct(d.p_away)}</span></div>
    </div>`
    )
    .join("");
}

// ---- track record ----
async function loadTrack() {
  const r = await get("/api/recent");
  if (!r.ready) return;
  $("acc-pct").textContent = pct(r.accuracy);
  $("track-body").innerHTML = r.results
    .map(
      (x) => `
    <tr>
      <td class="muted">${x.date.slice(5)}</td>
      <td>${x.group}</td>
      <td>${x.home} <span class="muted">v</span> ${x.away}</td>
      <td>${x.pred}</td>
      <td><b>${x.score}</b></td>
      <td>${x.correct ? '<span class="tick">✓</span>' : '<span class="cross">✗</span>'}</td>
    </tr>`
    )
    .join("");
}

// ---- match lab ----
async function loadTeams() {
  const r = await get("/api/teams");
  if (!r.ready) return;
  const opts = r.teams.map((t) => `<option value="${t.team}">${t.team} (${t.elo})</option>`).join("");
  $("home").innerHTML = opts;
  $("away").innerHTML = opts;
  if (r.teams[1]) $("away").value = r.teams[1].team;
}

async function predict() {
  const d = await fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ home: $("home").value, away: $("away").value, neutral: $("neutral").checked }),
  }).then((r) => r.json());
  if (d.error) return alert(d.error);
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
$("go").addEventListener("click", predict);

loadCard();
loadUpcoming();
loadTrack();
loadTeams();
