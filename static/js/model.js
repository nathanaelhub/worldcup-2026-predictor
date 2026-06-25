/* Client-side Dixon-Coles inference — a faithful port of wc2026/dixon_coles.py.
   The model is just coefficients (attack/defense per team + intercept, home
   advantage, rho), so the whole prediction runs in the browser. */

const MAX_GOALS = 10;
const BASE_TOTAL_GOALS = 2.6;
const SUPREMACY_PER_100 = 0.35;

function poissonPmf(k, lam) {
  let fact = 1;
  for (let i = 2; i <= k; i++) fact *= i;
  return (Math.exp(-lam) * Math.pow(lam, k)) / fact;
}

function dcTau(i, j, lh, la, rho) {
  if (i === 0 && j === 0) return 1 - lh * la * rho;
  if (i === 0 && j === 1) return 1 + lh * rho;
  if (i === 1 && j === 0) return 1 + la * rho;
  if (i === 1 && j === 1) return 1 - rho;
  return 1;
}

function scoreMatrix(lh, la, rho) {
  const h = [], a = [];
  for (let k = 0; k <= MAX_GOALS; k++) { h.push(poissonPmf(k, lh)); a.push(poissonPmf(k, la)); }
  const m = [];
  let total = 0;
  for (let i = 0; i <= MAX_GOALS; i++) {
    m[i] = [];
    for (let j = 0; j <= MAX_GOALS; j++) {
      let v = h[i] * a[j];
      if (i <= 1 && j <= 1) v *= dcTau(i, j, lh, la, rho);
      m[i][j] = v;
      total += v;
    }
  }
  for (let i = 0; i <= MAX_GOALS; i++)
    for (let j = 0; j <= MAX_GOALS; j++) m[i][j] /= total;
  return m;
}

function forecastFromLambdas(lh, la, rho) {
  const m = scoreMatrix(lh, la, rho);
  let pH = 0, pD = 0, pA = 0, over = 0, btts = 0, exH = 0, exA = 0;
  const cells = [];
  for (let i = 0; i <= MAX_GOALS; i++) {
    for (let j = 0; j <= MAX_GOALS; j++) {
      const p = m[i][j];
      if (i > j) pH += p; else if (i === j) pD += p; else pA += p;
      if (i + j > 2) over += p;
      if (i > 0 && j > 0) btts += p;
      exH += p * i; exA += p * j;
      cells.push([`${i}-${j}`, p]);
    }
  }
  cells.sort((x, y) => y[1] - x[1]);
  const r4 = (x) => Math.round(x * 1e4) / 1e4;
  return {
    p_home: r4(pH), p_draw: r4(pD), p_away: r4(pA),
    top_scores: cells.slice(0, 5).map(([s, p]) => [s, r4(p)]),
    exp_goals: [Math.round(exH * 100) / 100, Math.round(exA * 100) / 100],
    p_over_2_5: r4(over), p_btts: r4(btts),
  };
}

function expectedGoals(model, home, away, neutral) {
  const adv = neutral ? 0 : model.home_adv;
  const lh = Math.exp(model.intercept + (model.attack[home] || 0) - (model.defense[away] || 0) + adv);
  const la = Math.exp(model.intercept + (model.attack[away] || 0) - (model.defense[home] || 0));
  return [lh, la];
}

function eloForecast(elo, home, away, neutral) {
  const adv = neutral ? 0 : 100;
  const sup = (((elo[home] || 1500) + adv - (elo[away] || 1500)) / 100) * SUPREMACY_PER_100;
  return forecastFromLambdas(
    Math.max(0.2, BASE_TOTAL_GOALS / 2 + sup / 2),
    Math.max(0.2, BASE_TOTAL_GOALS / 2 - sup / 2), -0.05);
}

/* Unified prediction: Dixon-Coles when both teams are rated, else Elo fallback. */
function predict(model, knownSet, elo, home, away, neutral) {
  let fc, source;
  if (knownSet.has(home) && knownSet.has(away)) {
    const [lh, la] = expectedGoals(model, home, away, neutral);
    fc = forecastFromLambdas(lh, la, model.rho);
    source = "dixon-coles";
  } else {
    fc = eloForecast(elo, home, away, neutral);
    source = "elo-fallback";
  }
  const favorite = fc.p_home >= fc.p_away ? home : away;
  return { home, away, ...fc, favorite, source };
}

function predOutcome(p) {
  if (p.p_home >= p.p_draw && p.p_home >= p.p_away) return "H";
  if (p.p_away >= p.p_draw && p.p_away >= p.p_home) return "A";
  return "D";
}

window.WCModel = { predict, predOutcome };
