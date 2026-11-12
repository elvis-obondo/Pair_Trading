// HL-VAULT1 Word report renderer. Reads ONLY research/model/logs/s1/s1_vault_docx_data.json (written by
// research/model/s1_vault_docx_data.py) and formats it into Word XML. This script holds NO result numbers and NO
// findings of its own: every figure, every sentence that states a result, every direction word comes from the JSON.
// What is typed here is structure (headings, column names, what a column means) and method descriptions without numbers.
//
//   cd research/model && node s1_vault_docx_render.js
//
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, HeadingLevel,
  ImageRun, PageBreak, PageOrientation,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const DATA_PATH = path.join(ROOT, "research/model/logs/s1/s1_vault_docx_data.json");
const OUT_PATH = process.env.VAULT_DOCX_OUT || path.join(process.env.HOME, "Downloads/HL-VAULT1_vault_report.docx");
const D = JSON.parse(fs.readFileSync(DATA_PATH, "utf8"));
const PC_PATH = path.join(ROOT, "research/model/logs/s1/s1_vault_docx_partc.json");
const PC_EARLY = fs.existsSync(PC_PATH) ? JSON.parse(fs.readFileSync(PC_PATH, "utf8")) : null;   // findings_extra sentences are written by the Part C script

const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 720;        // landscape: width/height swapped by docx-js
const TABLE_W = PAGE_H - 2 * MARGIN;

const isNil = (x) => x === null || x === undefined || Number.isNaN(x);
const pct = (x, d = 2) => (isNil(x) ? "n/a" : (x * 100).toFixed(d) + "%");
const num = (x, d = 2) => (isNil(x) ? "n/a" : Number(x).toFixed(d));
const money = (x, d = 2) => (isNil(x) ? "n/a" : (x < 0 ? "-$" : "$") + Math.abs(Number(x)).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const int = (x) => (isNil(x) ? "n/a" : Number(x).toLocaleString("en-US"));
const FM = { pct, num, money, int };
const STOPN = { "0p5": "0.5 sigma", "1p0": "1 sigma", "2p0": "2 sigma", none: "no stop" };
const stopLabel = (s) => STOPN[String(s)] || String(s);
// "q0.01_stop0p5_feemaker" -> "q 1% / 0.5 sigma stop / maker"
const keyLabel = (k) => {
  const m = /^q([0-9.]+)_stop(\w+)_fee(\w+)$/.exec(k);
  if (!m) return k;
  const st = m[2] === "none" ? "no stop" : `${stopLabel(m[2])} stop`;
  return `q ${parseFloat((parseFloat(m[1]) * 100).toPrecision(6))}% / ${st} / ${m[3]}`;
};

function h1(t) { return new Paragraph({ text: t, heading: HeadingLevel.HEADING_1 }); }
function h2(t) { return new Paragraph({ text: t, heading: HeadingLevel.HEADING_2 }); }
function h3(t) { return new Paragraph({ text: t, heading: HeadingLevel.HEADING_3 }); }
function p(t) { return new Paragraph({ children: [new TextRun({ text: t, font: "Arial", size: 20 })], spacing: { after: 100 } }); }
function bullets(items) { return items.map((t) => new Paragraph({ children: [new TextRun({ text: t, font: "Arial", size: 20 })], numbering: { reference: "bul", level: 0 }, spacing: { after: 60 } })); }
function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }

function cell(text, width, header, fs) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: "D9D9D9", color: "auto" } : undefined,
    margins: { top: 30, bottom: 30, left: 60, right: 60 },
    children: [new Paragraph({ children: [new TextRun({ text: String(text), bold: !!header, font: "Arial", size: fs })] })],
  });
}
function autoWidths(headers, rows) {
  const wt = headers.map((h, i) => Math.min(38, Math.max(5, Math.min(String(h).length, 16), ...rows.map((r) => String(r[i]).length))));
  const sum = wt.reduce((a, b) => a + b, 0);
  const w = wt.map((x) => Math.floor((x / sum) * TABLE_W));
  w[0] += TABLE_W - w.reduce((a, b) => a + b, 0);
  return w;
}
function table(headers, rows, widths, fs = 16) {
  const w = widths || headers.map((_, i) => Math.floor(TABLE_W / headers.length));
  const total = w.reduce((a, b) => a + b, 0);
  const hr = new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, w[i], true, fs)) });
  const br = rows.map((r) => new TableRow({ children: r.map((v, i) => cell(v, w[i], false, fs)) }));
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: w, rows: [hr, ...br] });
}
function flat(obj, prefix = "") {
  const rows = [];
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}: ${k}` : k;
    if (Array.isArray(v)) rows.push([key, v.map((x) => (STOPN[String(x)] !== undefined ? STOPN[String(x)] : String(x))).join(", ")]);
    else if (v !== null && typeof v === "object") rows.push(...flat(v, key));
    else rows.push([key, String(v)]);
  }
  return rows;
}
function kv(obj, keyW = 4200) {
  const rows = flat(obj);
  return table(["field", "value"], rows, [keyW, TABLE_W - keyW], 18);
}
function img(file, w, h) {
  return new Paragraph({ children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: w, height: h } })] });
}
function firstW(n, first, rest) { return [first, ...Array(n - 1).fill(rest)]; }

const body = [];
const run = (k) => k; // run keys are printed as stored

// ---------------------------------------------------------------------------
body.push(new Paragraph({ text: "HL-VAULT1: the vault, opened once", heading: HeadingLevel.TITLE }));
body.push(h1("1. Summary"));
body.push(...bullets(D.summary));
body.push(h3("Runs ending above the $1,000 start (of 24)"));
body.push(table(["test open10", "test open20", "vault open10", "vault open20"],
  [[D.runs_above_start.test_open10, D.runs_above_start.test_open20, D.runs_above_start.vault_open10, D.runs_above_start.vault_open20].map(String)]));
body.push(p("Reported, not judged: the vault has no pass/fail rule. Nothing in this report recommends a change to the plan."));
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("2. Setup"));
body.push(h2("Data and window"));
body.push(kv({ "vault window start": D.setup.window_start, "last vault event": D.setup.last_event, "events": int(D.setup.n_events),
  "calendar days with events (vault)": D.setup.n_days,
  "engine annualisation window, days (vault / test months)": `${D.setup.engine_window_days} / ${D.setup.test_engine_window_days}`, "coins": D.setup.n_coins, "test window (for comparison)": D.setup.test_window.join(" to ") }));
body.push(h2("Model (one pre-vault refit on every search event before the vault)"));
body.push(kv(D.setup.model_settings));
body.push(kv(D.setup.model_fit));
body.push(h2("Picks (Rule A, fixed before the vault was read)"));
body.push(table(["q", "cut-off on raw p_10h (from fold 7's test predictions)", "picks"],
  Object.keys(D.setup.picks).map((q) => [q, num(D.setup.cutoffs[q], 10), int(D.setup.picks[q])])));
body.push(h2("Probability calibration (isotonic)"));
body.push(kv(D.setup.pcal));
body.push(p("2 h and 5 h maps (fitted on the same pooled test-fold predictions, S1-H's guard at the horizon's own length):"));
body.push(kv(Object.fromEntries(["2", "5"].map((h) => [`${h} h map`, { n_fit: D.setup.iso_settings[h].n_fit, n_dropped: D.setup.iso_settings[h].n_dropped, distinct_levels: D.setup.iso_settings[h].distinct_levels }]))));
body.push(h2("Trading and cost assumptions (engine configuration of the vault runs)"));
body.push(kv(D.setup.engine_config));
body.push(h2("Known gaps"));
body.push(...bullets([
  "Slippage is set to zero (see slippage_spread_share above): costs are a lower bound and the results an upper bound.",
  "Maker fills are assumed to fill; in practice they may not.",
  "Maximum leverage per coin is today's snapshot, not the limits that applied in the past.",
  "Liquidation is checked on 1-minute closes; a move inside a minute can liquidate earlier.",
  "The test side of every comparison is the per-fold out-of-fold predictions; the vault is scored by one pre-vault refit with one calibration map. They are different fits.",
  "The vault window is shorter than the test period, so equity, return and CAGR are not per-month comparable.",
  ...D.setup.model_known_gaps,
]));
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("3. Ranking quality"));
body.push(p("Lift = (mean reach within 10 h minus mean chance of the picked set) minus the same gap over all events of the same group. A positive lift means the picked events revert more often, net of what chance alone would give."));
body.push(h2("3.1 Lift by set size, with intervals"));
body.push(p(`Intervals: day-block bootstrap, ${int(D.meta.n_resamples)} resamples, level ${D.meta.level}, random seed ${D.meta.seed}. Test-side Rule A sets are the pooled test months (folds 1-7); the S1-D rows cover folds 0-7 (see the note under the table).`));
const liftRows = (arr, f17) => arr.map((r) => [r.label, isNil(r.n) ? "n/a" : int(r.n), isNil(r.share) ? "n/a" : pct(r.share, 4), isNil(r.reach) ? "n/a" : num(r.reach, 4), isNil(r.chance) ? "n/a" : num(r.chance, 4), num(r.lift, 4), num(r.lo, 4), num(r.hi, 4)]
  .concat(f17 ? [isNil(r.lift_folds_1_7) ? "(row is folds 1-7)" : num(r.lift_folds_1_7, 4)] : []));
body.push(h3("Vault"));
body.push(table(["set", "n", "share of events", "actual reach 10 h", "chance 10 h", "lift", "interval low", "interval high"], liftRows(D.rank.lift_sets.vault)));
body.push(h3("Test months"));
body.push(table(["set", "n", "share of events", "actual reach 10 h", "chance 10 h", "lift", "interval low", "interval high", "lift over folds 1-7 only (n-weighted, no interval)"], liftRows(D.rank.lift_sets.test, true)));
body.push(p("Rule A rows are computed on the pooled test months (folds 1-7). S1-D rows come from s1d_report.json and cover folds 0-7; the last column gives the folds 1-7 value from the same file, weighted by picks per fold."));
body.push(h2("3.2 Lift by month"));
const grpRows = (arr) => arr.map((r) => [r.group + (r.start ? ` (${r.start})` : ""), int(r.n_all), int(r.n_picks), num(r.reach_all, 4), isNil(r.reach_picks) ? "n/a" : num(r.reach_picks, 4), isNil(r.chance_picks) ? "n/a" : num(r.chance_picks, 4), isNil(r.gap_all) ? "n/a" : num(r.gap_all, 4), isNil(r.gap_picks) ? "n/a" : num(r.gap_picks, 4), isNil(r.lift) ? "n/a" : num(r.lift, 4)]);
const grpHead = (g) => [g, "events", "q=1% picks", "reach (all)", "reach (picks)", "chance (picks)", "gap (all)", "gap (picks)", "lift"];
body.push(h3("Vault, by UTC month"));
body.push(table(grpHead("month"), grpRows(D.rank.by_month.vault)));
body.push(h3("Test months, by fold"));
body.push(table(grpHead("fold (start)"), grpRows(D.rank.by_month.test)));
body.push(img(D.charts.lift_month, 600, 285));
body.push(h2("3.3 Lift by week (vault)"));
body.push(table(grpHead("week starting (Monday)"), grpRows(D.rank.by_week.vault)));
body.push(h2("3.4 Long versus short spread"));
body.push(p("Short the spread when z > 0, long when z < 0. Share of q=1% picks that short the spread is in the findings."));
body.push(h3("Vault"));
body.push(table(grpHead("direction"), grpRows(D.rank.by_dir.vault)));
body.push(h3("Test months"));
body.push(table(grpHead("direction"), grpRows(D.rank.by_dir.test)));
body.push(h2("3.5 By |z| bucket"));
body.push(h3("Vault"));
body.push(table(grpHead("|z|"), grpRows(D.rank.by_z.vault)));
body.push(h3("Test months"));
body.push(table(grpHead("|z|"), grpRows(D.rank.by_z.test)));
body.push(h2("3.6 By coin (an event counts for both of its legs)"));
const coinRows = (arr) => arr.map((r) => [r.coin, int(r.n_pick_legs), int(r.n_all_legs), num(r.reach_picks, 4), num(r.gap_picks, 4), num(r.gap_all, 4), num(r.lift, 4)]);
const coinHead = ["coin", "pick legs", "all legs", "reach (picks)", "gap (picks)", "gap (all)", "lift"];
body.push(h3("Vault: the 15 coins with the most q=1% pick legs"));
body.push(table(coinHead, coinRows(D.rank.by_coin.vault)));
body.push(kv(D.rank.coin_summary.vault));
body.push(h3("Test months: the 15 coins with the most q=1% pick legs"));
body.push(table(coinHead, coinRows(D.rank.by_coin.test)));
body.push(kv(D.rank.coin_summary.test));
body.push(h3("Coins the model never saw in training (vault)"));
body.push(kv(D.rank.unseen_coin_picks));
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("4. Calibration at 2 h, 5 h and 10 h"));
body.push(p("Predicted versus actual reach rate. 'Calibrated' is the isotonic map: for 2 h and 5 h the new vault maps, for 10 h the existing p_cal. Test-month columns are S1-H's per-fold out-of-fold numbers (isotonic fitted per fold on earlier folds). The vault side is the single pre-vault refit with one map fitted on folds 0-7: a different fit. Deciles are each side's own."));
body.push(img(D.charts.calibration, 900, 285));
const fv = (x) => (isNil(x) ? "n/a" : num(x, 4));
for (const h of ["2", "5", "10"]) {
  const c = D.calib[h];
  body.push(h2(`${h} h`));
  body.push(p(`All vault events: log loss raw ${num(c.logloss_raw, 4)}, calibrated ${num(c.logloss_cal, 4)}; Brier raw ${num(c.brier_raw, 4)}, calibrated ${num(c.brier_cal, 4)}. Calibrated values at exactly 0 or 1: ${int(c.n_sat)}, contradicted by the label: ${int(c.n_contradicted)}.`));
  body.push(table(["bucket", "n", "mean raw p", "mean calibrated p", "actual reach", "actual - calibrated", "test mean raw", "test mean calibrated", "test actual"],
    c.rows.map((r) => [r.bucket, int(r.n), fv(r.raw), fv(r.cal), fv(r.actual), (r.actual - r.cal >= 0 ? "+" : "") + num(r.actual - r.cal, 4), fv(r.t_raw), fv(r.t_cal), fv(r.t_actual)]),
    [2600, 1300, 1300, 1500, 1300, 1700, 1500, 1700, 1500]));
}
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("5. Horizons: which picks revert fast?"));
body.push(p("Picks of each q are split into quintiles of the calibrated p_2h (and, separately, p_5h); quintile 1 is the lowest. Ties share a bin, so bins can be unequal; n is printed. 'Reach within h' is the reversion rate inside the horizon. Trades: no stop, max_open 10, per fee mode; only picks that were actually traded. 'Win' is an exit at the mean; 'profitable' is net above zero. 'Open at 2 h / 5 h' is the share of traded picks held longer than 120 / 300 minutes. The test months are shown beside the vault, computed by the same function."));
const speedHead = ["quintile", "n picks", "mean calibrated p", "reach within h", "reach within 10 h", "median minutes to mean (reachers)"];
const tradeHead = (fee) => [`${fee}: n traded`, "win", "profitable", "mean net $", "mean net/notional", "mean hold min", "open at 2 h", "open at 5 h"];
function horizonBlocks(side, label) {
  for (const q of Object.keys(D.horizons[side])) {
    const H = D.horizons[side][q];
    for (const h of ["2", "5"]) {
      const rows = H[`by_p${h}h`];
      body.push(h3(`${label}: q=${q}, quintiles of calibrated p_${h}h (${int(H.n_picks)} picks)`));
      body.push(table(speedHead, rows.map((r) => [r.quintile, int(r.n), num(r.mean_cal_p, 4), num(r.reach_h, 4), num(r.reach_10h, 4), isNil(r.mtm_median) ? "n/a" : num(r.mtm_median, 0)])));
      const tr = [];
      for (const r of rows) {
        const row = [r.quintile];
        for (const fee of ["maker", "taker"]) {
          row.push(int(r[`${fee}_n_traded`]), pct(r[`${fee}_win_mu`], 1), pct(r[`${fee}_share_profitable`], 1), num(r[`${fee}_mean_net_usd`], 3), num(r[`${fee}_mean_net_over_notional`], 5), num(r[`${fee}_mean_hold_min`], 0), pct(r[`${fee}_open_at_2h`], 1), pct(r[`${fee}_open_at_5h`], 1));
        }
        tr.push(row);
      }
      body.push(table(["quintile", ...tradeHead("maker"), ...tradeHead("taker")], tr, [700, ...Array(16).fill(Math.floor((TABLE_W - 700) / 16))], 14));
    }
    for (const fee of ["maker", "taker"]) {
      const a = H[`all_traded_${fee}`];
      body.push(p(`${label}, q=${q}, ${fee}, all traded picks: n ${int(a.n)}, win ${pct(a.win_mu, 1)}, profitable ${pct(a.share_profitable, 1)}, mean net $ ${num(a.mean_net_usd, 3)}, open at 2 h ${pct(a.open_at_2h, 1)}, open at 5 h ${pct(a.open_at_5h, 1)}.`));
    }
  }
}
body.push(h2("5.1 Vault"));
horizonBlocks("vault", "Vault");
body.push(h2("5.2 Test months (for comparison)"));
horizonBlocks("test", "Test months");
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("6. Trading: all 48 vault runs"));
body.push(p("Start $1,000, margin 5% of equity per position, leverage the lower of 10 and both coins' maximum, cross margin, fees 0.045% taker / 0.015% maker per fill, funding on, $10 minimum order. Win rate is the share of trades exiting at the mean. Long/short columns count trades by the sign of z at entry (short the spread when z > 0)."));
function tradingTables(tag, title) {
  const runs = Object.values(D.trading[tag]);
  body.push(h2(title));
  body.push(table(["q", "stop", "fee", "final equity", "net PnL", "return", "trades", "win rate", "mean win $", "mean loss $", "profit factor", "max drawdown", "Sharpe"],
    runs.map((r) => [r.q, stopLabel(r.stop), r.fee, money(r.final_equity), money(r.net_pnl), pct(r.total_return), int(r.n_trades), pct(r.win_rate), money(r.mean_win), money(r.mean_loss), num(r.profit_factor, 3), pct(r.max_dd_pct), num(r.sharpe, 2)])));
  body.push(table(["q", "stop", "fee", "gross $", "fees $", "fee share of gross", "funding paid $", "funding received $", "best day $", "worst day $", "mean hold min", "stop share", "timeout share", "liquidations"],
    runs.map((r) => [r.q, stopLabel(r.stop), r.fee, money(r.gross), money(r.fees), pct(r.fee_share), money(r.funding_paid), money(r.funding_received), money(r.best_day), money(r.worst_day), num(r.mean_hold_min, 0), pct(r.stop_share), pct(r.timeout_share), int(r.n_liquidations)]), undefined, 15));
  body.push(table(["q", "stop", "fee", "skipped: book full", "skipped: margin", "skipped: min order", "peak margin $", "mean open", "min distance to liquidation", "mean leverage", "long trades", "short trades", "long win", "short win", "long net $", "short net $"],
    runs.map((r) => [r.q, stopLabel(r.stop), r.fee, int(r.skip_book_full), int(r.skip_margin), int(r.skip_min_order), money(r.peak_margin), num(r.mean_open, 2), num(r.min_dist_liq, 3), num(r.mean_leverage, 2), int(r.n_long), int(r.n_short), pct(r.win_long, 1), pct(r.win_short, 1), money(r.net_long), money(r.net_short)]), undefined, 14));
}
tradingTables("vault_open10", "6.1 Vault, max_open 10");
tradingTables("vault_open20", "6.2 Vault, max_open 20");
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("7. Detail for the best configurations"));
body.push(p("Best configuration = the run with the highest final equity within each vault tag, plus the standing reference run (q 1%, no stop, maker fees). The same configuration in the test months is shown beside it."));
for (const tag of Object.keys(D.best)) {
  body.push(h2(`7. ${tag}`));
  body.push(img(D.charts[`equity_${tag}`], 600, 285));
  for (const [key, det] of Object.entries(D.best[tag])) {
    const v = D.trading[tag][key], t = det.test_counterpart;
    body.push(h3(`${keyLabel(key)} (${det.role})`));
    const metrics = [["final equity", money, "final_equity"], ["net PnL", money, "net_pnl"], ["return", pct, "total_return"], ["trades", int, "n_trades"], ["win rate", pct, "win_rate"], ["profit factor", (x) => num(x, 3), "profit_factor"], ["Sharpe", (x) => num(x, 2), "sharpe"], ["max drawdown", pct, "max_dd_pct"], ["fees", money, "fees"], ["fee share of gross", pct, "fee_share"], ["min distance to liquidation", (x) => num(x, 3), "min_dist_liq"]];
    body.push(table(["metric", "vault", "test months (same config)"], metrics.map(([n, f, k]) => [n, f(v[k]), f(t[k])]), [4000, 3000, 3000], 18));
    body.push(p("Calendar-month PnL (daily changes summed)."));
    body.push(table(["month", "PnL $", "days"], det.monthly.map((m) => [m.month, money(m.pnl), int(m.days)]), [2500, 2500, 2000], 18));
    body.push(p("Deepest drawdown episodes (peak day, bottom day, recovery day):"));
    body.push(table(["side", "peak day", "bottom day", "recovery day", "depth", "days underwater"],
      [...det.drawdowns.map((d) => ["vault", d.peak_day, d.bottom_day, d.recovery_day, pct(d.depth), int(d.days_underwater)]),
       ...det.test_drawdowns.map((d) => ["test months", d.peak_day, d.bottom_day, d.recovery_day, pct(d.depth), int(d.days_underwater)])]));
    body.push(p(`Exit reasons: ${Object.entries(det.exit_reasons).map(([k, v]) => `${k} ${int(v)}`).join("; ")}`));
    const mapRows = (o) => Object.entries(o).map(([k, x]) => [k, money(x)]);
    body.push(table(["top 10 coins (net $)", "", "bottom 10 coins (net $)", ""],
      Array.from({ length: Math.max(Object.keys(det.top_coins).length, Object.keys(det.bottom_coins).length) }, (_, i) => {
        const a = mapRows(det.top_coins)[i] || ["", ""], b = mapRows(det.bottom_coins)[i] || ["", ""];
        return [a[0], a[1], b[0], b[1]];
      }), [3500, 3500, 3500, 3500], 16));
    body.push(table(["top 10 pairs (net $)", "", "bottom 10 pairs (net $)", ""],
      Array.from({ length: Math.max(Object.keys(det.top_pairs).length, Object.keys(det.bottom_pairs).length) }, (_, i) => {
        const a = mapRows(det.top_pairs)[i] || ["", ""], b = mapRows(det.bottom_pairs)[i] || ["", ""];
        return [a[0], a[1], b[0], b[1]];
      }), [3500, 3500, 3500, 3500], 16));
    body.push(p("PnL by |z| bucket and by direction (trades of this run):"));
    body.push(table(["group", "trades", "net $", "mean net $", "win rate"], [...det.by_z, ...det.by_dir].map((g) => [g.group, int(g.n), money(g.net), money(g.mean_net, 3), pct(g.win_mu, 1)]), [4000, 2000, 2400, 2400, 2000], 18));
  }
}
body.push(pageBreak());

// ---------------------------------------------------------------------------
body.push(h1("8. Side by side: test months versus vault, every metric"));
body.push(p("Every metric of section 6, for each of the 24 runs, in four columns: test months at max_open 10 and 20, vault at max_open 10 and 20. Window lengths differ (the vault is shorter), so equity, return, PnL and trade counts are not per-month comparable; ratios and rates are the fairer comparison."));
const METRIC_FMT = { final_equity: "money", net_pnl: "money", total_return: "pct", cagr: "pct", n_trades: "int", gross: "money", fees: "money", fee_share: "pct", funding_paid: "money", funding_received: "money", win_rate: "pct", mean_win: "money", mean_loss: "money", profit_factor: "num", max_dd_pct: "pct", max_dd_usd: "money", sharpe: "num", sortino: "num", best_day: "money", worst_day: "money", share_positive_days: "pct", mean_hold_min: "num", stop_share: "pct", timeout_share: "pct", liquidation_share: "pct", n_liquidations: "int", skip_book_full: "int", skip_margin: "int", skip_min_order: "int", peak_margin: "money", mean_open: "num", min_dist_liq: "num", mean_net: "money", mean_leverage: "num", mean_notional: "money", n_short: "int", win_short: "pct", net_short: "money", n_long: "int", win_long: "pct", net_long: "money" };
const colNames = D.side_by_side_cols.map((c) => c.replace("_", " "));
for (const [metric, byRun] of Object.entries(D.side_by_side)) {
  const f = FM[METRIC_FMT[metric] || "num"];
  body.push(h3(metric));
  body.push(table(["run", ...colNames], Object.entries(byRun).map(([k, vals]) => [keyLabel(k), ...vals.map((x) => f(x))]), [4400, 2500, 2500, 2500, 2500], 15));
}
body.push(pageBreak());

// ---------------------------------------------------------------------------

body.push(h1("9. Findings and caveats"));
body.push(p("Stated plainly. These are observations from the tables above; none of them is a recommendation."));
body.push(...bullets([...D.findings, ...(PC_EARLY ? PC_EARLY.findings_extra : [])]));
body.push(h2("Caveats"));
body.push(...bullets([
  "The model, the pick rule, the 10 h probability calibration and the backtest settings were fixed before any vault label or outcome was read and were not changed afterwards. The 2 h and 5 h calibration maps and this report were added afterwards at the user's request; the maps are fitted on search-period data only (summary, first point).",
  "The calibration comparison sets two different fits side by side (per-fold out-of-fold on the test months; one pre-vault refit on the vault).",
  "Slippage is zero and maker fills are assumed, so the trading results are an upper bound. The last finding above (capacity) states how large the traded legs are against the traded notional of the same coins in the entry minute; Part C-6 gives the arithmetic effect of extra slippage.",
  "Group tables (by week, coin, |z|) give point values without intervals; small groups are noisy, and every table prints its n.",
  "|z| bucket edges were fixed before any bucket result was read.",
]));
// ---------------------------------------------------------------------------
// Parts B and C: pre-formatted sections written by s1_vault_docx_partb.py / s1_vault_docx_partc.py
function wideTable(t) {
  const rows = t.rows;
  const fs = t.columns.length > 14 ? 12 : t.columns.length > 10 ? 14 : 16;
  return table(t.columns, rows, autoWidths(t.columns, rows), fs);
}
function renderParts(file, partTitle, partIntro) {
  const fp = path.join(ROOT, "research/model/logs/s1", file);
  if (!fs.existsSync(fp) && process.env.VAULT_ALLOW_MISSING === "1") { console.log(`[DOCX] WARNING: ${file} missing, part skipped (test run only)`); return null; }
  const P = JSON.parse(fs.readFileSync(fp, "utf8"));
  body.push(pageBreak());
  body.push(h1(partTitle));
  body.push(p(partIntro));
  for (const sec of P.sections) {
    body.push(h2(sec.heading));
    if (sec.intro) body.push(p(sec.intro));
    for (const im of sec.images || []) body.push(img(im, 640, 210));
    for (const t of sec.tables) {
      body.push(h3(t.title));
      body.push(wideTable(t));
      if (t.note) body.push(p(t.note));
    }
    if (sec.flags && sec.flags.length) body.push(...bullets(sec.flags));
  }
  return P;
}
const PB_JSON = renderParts("s1_vault_docx_partb.json", "Part B. Distance from mu, winners and losers, timing, paths, costs",
  "Distance from mu is |z| in sigma units. Vault and test months side by side. Descriptive only: no filter or rule is chosen, and the vault is open, so any |z| or probability cut-off read off these tables is a hypothesis for later, not a result.");
const PC_JSON = renderParts("s1_vault_docx_partc.json", "Part C. Ranking, risk, exposure, capacity and cost sensitivity",
  "Analysis of saved outputs only: no engine run, no baselines, no filter chosen. Vault and test months side by side. Entry-delay sensitivity is not included: the saved 1-minute prices would give only the gross price effect of a shifted entry, while exits, stops, fees, funding and the position book need the engine, so it cannot be done without an engine change.");

body.push(h1("Appendix: where every number comes from"));
body.push(...bullets([
  "Data file: research/model/logs/s1/s1_vault_docx_data.json, written by research/model/s1_vault_docx_data.py (log: research/model/logs/s1/s1_vault_docx_data.log). Renderer: research/model/s1_vault_docx_render.js.",
  "Trading numbers: research/model/logs/s1/s1_profit1_numbers_report_vault_open10.json and ..._vault_open20.json (script s1_profit1_numbers_gen.py with PROFIT1_VAULT=1) and the trade files under research/model/logs/profit1/; test months: s1_profit1_numbers_report.json and ..._open20.json.",
  "Picks and cut-offs: research/model/logs/s1/s1_vault_picks.parquet and s1_vault_picks_settings.json (script s1_vault_picks.py).",
  "Calibration: research/model/logs/s1/s1_vault_iso_2h5h.json (script s1_vault_iso_2h5h.py); test-month columns: s1h_report.json. Lift references: s1d_report.json.",
  "Parts B and C: research/model/s1_vault_docx_partb.py and s1_vault_docx_partc.py, writing logs/s1/s1_vault_docx_partb.json and ..._partc.json (logs next to them).",
  "Horizons test side: research/model/s1_profit1_horizons.py frame and base trade logs. NUMBERS.md sections: [HL-VAULT1], [HL-VAULT1 vault_open10], [HL-VAULT1 vault_open20], [HL-VAULT1 iso25].",
]));

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: "bullet", text: "•", alignment: "left", style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 20 } },
      heading1: { run: { font: "Arial", size: 32, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true } },
      heading2: { run: { font: "Arial", size: 26, bold: true }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true } },
      heading3: { run: { font: "Arial", size: 22, bold: true }, paragraph: { spacing: { before: 160, after: 80 }, keepNext: true } },
      title: { run: { font: "Arial", size: 40, bold: true }, paragraph: { spacing: { before: 0, after: 200 }, keepNext: true } },
    },
  },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.LANDSCAPE }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    children: body,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT_PATH, buf);
  console.log(`[DOCX] wrote ${OUT_PATH} (${buf.length} bytes)`);
});
