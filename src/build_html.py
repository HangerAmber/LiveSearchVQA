# -*- coding: utf-8 -*-
"""Build a self-contained interactive HTML visualization of the benchmark.

Reads data/benchmark.json + data/stats.json, writes index.html at the
project root. Images are referenced relatively (data/images/*.jpg), so the
folder can be zipped and shared as-is.
"""
import os
import json
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")

QTYPE_LABEL = {
    "identification": "Identification",
    "factual_detail": "Factual detail",
    "numerical": "Numerical",
    "temporal": "Temporal",
    "causal": "Causal",
    "cross_modal": "Cross-modal",
}

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LiveSearchVQA — Daily Live VQA Benchmark for Web-Search Agents</title>
<style>
  :root {
    --bg: #0d1117; --panel: #161b22; --panel2: #1c2330;
    --border: #2d3644; --text: #e6edf3; --muted: #8b98a9;
    --accent: #4d9fff; --green: #3fb950; --red: #f85149; --amber: #d29922;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text);
         font: 15px/1.55 "Segoe UI", system-ui, -apple-system, sans-serif; }
  .wrap { max-width: 1280px; margin: 0 auto; padding: 28px 22px 80px; }

  header { padding: 26px 0 18px; border-bottom: 1px solid var(--border); }
  h1 { font-size: 26px; font-weight: 700; letter-spacing: .2px; }
  h1 .live { color: var(--red); }
  .sub { color: var(--muted); margin-top: 6px; font-size: 14px; }
  .sub b { color: var(--text); }

  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
           gap: 12px; margin: 20px 0; }
  .stat { background: var(--panel); border: 1px solid var(--border);
          border-radius: 10px; padding: 14px 16px; }
  .stat .v { font-size: 24px; font-weight: 700; color: var(--accent); }
  .stat .k { font-size: 12px; color: var(--muted); margin-top: 2px; }

  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
  @media (max-width: 860px) { .charts { grid-template-columns: 1fr; } }
  .chart { background: var(--panel); border: 1px solid var(--border);
           border-radius: 10px; padding: 14px 16px; }
  .chart h3 { font-size: 13px; color: var(--muted); font-weight: 600;
              text-transform: uppercase; letter-spacing: .6px; margin-bottom: 10px; }
  .bar-row { display: flex; align-items: center; gap: 8px; margin: 5px 0; font-size: 13px; }
  .bar-row .lbl { width: 120px; color: var(--muted); text-align: right;
                  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar-row .bar { flex: 1; background: var(--panel2); border-radius: 4px; height: 18px; overflow: hidden; }
  .bar-row .bar i { display: block; height: 100%; background: linear-gradient(90deg,#2f6feb,#4d9fff); border-radius: 4px; }
  .bar-row .n { width: 34px; font-variant-numeric: tabular-nums; color: var(--text); }

  .toolbar { display: flex; flex-wrap: wrap; gap: 10px; margin: 6px 0 20px; align-items: center; }
  select, input[type=search] {
    background: var(--panel); color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 12px; font-size: 14px; outline: none; }
  input[type=search] { flex: 1; min-width: 220px; }
  .toolbar button { background: var(--panel); color: var(--muted); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 14px; font-size: 13px; cursor: pointer; }
  .toolbar button.on { background: #1f3a5f; color: #fff; border-color: var(--accent); }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px,1fr)); gap: 16px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
          overflow: hidden; display: flex; flex-direction: column; }
  .card img { width: 100%; height: 210px; object-fit: cover; background: #000; cursor: zoom-in; }
  .card .body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 10px; flex: 1; }
  .badges { display: flex; flex-wrap: wrap; gap: 6px; }
  .badge { font-size: 11px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--border);
           color: var(--muted); background: var(--panel2); }
  .badge.qt { color: #9ecbff; border-color: #2f4a6f; }
  .q { font-weight: 600; font-size: 14.5px; }
  .opts { display: flex; flex-direction: column; gap: 6px; }
  .opt { border: 1px solid var(--border); border-radius: 8px; padding: 7px 11px;
         font-size: 13.5px; cursor: pointer; color: var(--text); background: var(--panel2);
         transition: border-color .15s; }
  .opt:hover { border-color: var(--accent); }
  .opt.correct { border-color: var(--green); background: rgba(63,185,80,.12); }
  .opt.wrong { border-color: var(--red); background: rgba(248,81,73,.12); }
  .opt b { margin-right: 6px; color: var(--muted); }
  .ev { display: none; font-size: 12.5px; color: var(--muted); border-left: 3px solid var(--amber);
        padding: 6px 10px; background: rgba(210,153,34,.06); border-radius: 0 6px 6px 0; }
  .card.revealed .ev { display: block; }
  .meta { margin-top: auto; font-size: 12px; color: var(--muted);
          display: flex; justify-content: space-between; gap: 8px; align-items: center; }
  .meta a { color: var(--accent); text-decoration: none; }
  .meta a:hover { text-decoration: underline; }
  .reveal { font-size: 12px; color: var(--muted); background: none; border: 1px solid var(--border);
            border-radius: 6px; padding: 3px 10px; cursor: pointer; }
  .reveal:hover { color: var(--text); }
  #lightbox { position: fixed; inset: 0; background: rgba(0,0,0,.85); display: none;
              align-items: center; justify-content: center; z-index: 50; cursor: zoom-out; }
  #lightbox img { max-width: 92vw; max-height: 92vh; border-radius: 8px; }
  .count-line { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
  footer { margin-top: 40px; color: var(--muted); font-size: 12.5px; border-top: 1px solid var(--border); padding-top: 14px; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>LiveSearchVQA <span class="live">●&nbsp;LIVE</span></h1>
  <div class="sub">A daily-refreshed VQA benchmark that measures whether vision-language
  agents can <b>search the web</b> to answer questions about events from the last 48 hours.
  Every question passed a <b>closed-book filter</b> (the VLM fails without search) and an
  <b>oracle filter</b> (the VLM succeeds with gold evidence). Build date: <b>__BUILD_DATE__</b></div>
</header>

<div class="stats" id="stats"></div>

<div class="charts">
  <div class="chart"><h3>Question type</h3><div id="chart-qtype"></div></div>
  <div class="chart"><h3>News source</h3><div id="chart-source"></div></div>
</div>

<div class="toolbar">
  <input type="search" id="search" placeholder="Search questions / titles...">
  <select id="f-source"><option value="">All sources</option></select>
  <select id="f-qtype"><option value="">All types</option></select>
  <button id="reveal-all">Reveal all answers</button>
</div>
<div class="count-line" id="count-line"></div>
<div class="grid" id="grid"></div>

<footer>
  LiveSearchVQA · fully automated pipeline: crawl fresh news (RSS, &lt;48 h) → VLM question
  generation → closed-book anti-memorization filter → oracle answerability filter.
  Each item ships with gold answer, verbatim evidence and source URL, enabling the
  closed-book / with-search / oracle three-way diagnostic evaluation.
</footer>
</div>

<div id="lightbox"><img id="lightbox-img" src="" alt=""></div>

<script>
const DATA = __DATA__;
const STATS = __STATS__;
const QTYPE_LABEL = __QTYPE_LABEL__;

const $ = s => document.querySelector(s);
let revealAll = false;

function counter(arr, key) {
  const m = {};
  arr.forEach(x => { const v = x[key]; m[v] = (m[v]||0)+1; });
  return Object.entries(m).sort((a,b)=>b[1]-a[1]);
}

function renderStats() {
  const gen = STATS.generated || 0;
  const kept = DATA.length;
  const cbDrop = STATS.drop_closed_book || 0;
  const nArticles = new Set(DATA.map(d=>d.article_id)).size;
  const cards = [
    [kept, "questions"],
    [nArticles, "news articles"],
    [new Set(DATA.map(d=>d.source)).size, "news sources"],
    [gen ? (100*cbDrop/gen).toFixed(0)+"%" : "-", "generated Qs dropped: closed-book solvable"],
    [gen ? (100*kept/gen).toFixed(0)+"%" : "-", "acceptance rate after all filters"],
  ];
  $("#stats").innerHTML = cards.map(([v,k]) =>
    `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");
}

function renderChart(el, entries, labelMap) {
  const max = Math.max(...entries.map(e=>e[1]));
  el.innerHTML = entries.map(([k,n]) => `
    <div class="bar-row">
      <div class="lbl" title="${k}">${(labelMap&&labelMap[k])||k}</div>
      <div class="bar"><i style="width:${(100*n/max).toFixed(1)}%"></i></div>
      <div class="n">${n}</div>
    </div>`).join("");
}

function fillSelect(sel, entries, labelMap) {
  entries.forEach(([k,n]) => {
    const o = document.createElement("option");
    o.value = k; o.textContent = `${(labelMap&&labelMap[k])||k} (${n})`;
    sel.appendChild(o);
  });
}

function cardHTML(d, i) {
  const letters = ["A","B","C","D"];
  const opts = d.options.map((o,j) => `
    <div class="opt" data-i="${i}" data-l="${letters[j]}"><b>${letters[j]}</b>${o}</div>`).join("");
  const pub = (d.pub_date||"").slice(0,16).replace("T"," ");
  return `<div class="card" data-i="${i}">
    <img src="data/${d.image}" loading="lazy" alt="">
    <div class="body">
      <div class="badges">
        <span class="badge qt">${QTYPE_LABEL[d.qtype]||d.qtype}</span>
        <span class="badge">${d.source}</span>
        <span class="badge">${d.category}</span>
        <span class="badge" title="closed-book prediction (filtered to be wrong)">closed-book: ${d.closed_book_pred||"?"} ✗</span>
      </div>
      <div class="q">${d.question}</div>
      <div class="opts">${opts}</div>
      <div class="ev">Evidence — ${d.evidence}</div>
      <div class="meta">
        <a href="${d.article_url}" target="_blank" rel="noopener" title="${d.article_title}">source ↗</a>
        <span>${pub}</span>
        <button class="reveal" data-i="${i}">answer</button>
      </div>
    </div>
  </div>`;
}

function currentFilter() {
  const q = $("#search").value.trim().toLowerCase();
  const src = $("#f-source").value, qt = $("#f-qtype").value;
  return DATA.map((d,i)=>({d,i})).filter(({d}) =>
    (!src || d.source===src) && (!qt || d.qtype===qt) &&
    (!q || d.question.toLowerCase().includes(q) ||
     (d.article_title||"").toLowerCase().includes(q)));
}

function reveal(card, d) {
  card.classList.add("revealed");
  card.querySelectorAll(".opt").forEach(el => {
    if (el.dataset.l === d.answer) el.classList.add("correct");
  });
}

function render() {
  const items = currentFilter();
  $("#count-line").textContent = `${items.length} / ${DATA.length} questions shown`;
  $("#grid").innerHTML = items.map(({d,i}) => cardHTML(d,i)).join("");
  document.querySelectorAll(".opt").forEach(el => el.addEventListener("click", () => {
    const d = DATA[+el.dataset.i];
    const card = el.closest(".card");
    if (el.dataset.l === d.answer) el.classList.add("correct");
    else { el.classList.add("wrong"); }
    reveal(card, d);
  }));
  document.querySelectorAll(".reveal").forEach(el => el.addEventListener("click", () => {
    reveal(el.closest(".card"), DATA[+el.dataset.i]);
  }));
  document.querySelectorAll(".card img").forEach(el => el.addEventListener("click", () => {
    $("#lightbox-img").src = el.src; $("#lightbox").style.display = "flex";
  }));
  if (revealAll) document.querySelectorAll(".card").forEach((c) => reveal(c, DATA[+c.dataset.i]));
}

renderStats();
renderChart($("#chart-qtype"), counter(DATA,"qtype"), QTYPE_LABEL);
renderChart($("#chart-source"), counter(DATA,"source"), null);
fillSelect($("#f-source"), counter(DATA,"source"), null);
fillSelect($("#f-qtype"), counter(DATA,"qtype"), QTYPE_LABEL);
["#search","#f-source","#f-qtype"].forEach(s => {
  $(s).addEventListener("input", render); $(s).addEventListener("change", render);
});
$("#reveal-all").addEventListener("click", () => {
  revealAll = !revealAll;
  $("#reveal-all").classList.toggle("on", revealAll);
  $("#reveal-all").textContent = revealAll ? "Hide answers" : "Reveal all answers";
  render();
});
$("#lightbox").addEventListener("click", () => $("#lightbox").style.display = "none");
render();
</script>
</body>
</html>
"""


def main():
    with open(os.path.join(DATA_DIR, "benchmark.json"), encoding="utf-8") as f:
        bench = json.load(f)
    stats_path = os.path.join(DATA_DIR, "stats.json")
    stats = {}
    if os.path.exists(stats_path):
        with open(stats_path, encoding="utf-8") as f:
            stats = json.load(f)

    html = (TEMPLATE
            .replace("__DATA__", json.dumps(bench, ensure_ascii=False))
            .replace("__STATS__", json.dumps(stats))
            .replace("__QTYPE_LABEL__", json.dumps(QTYPE_LABEL))
            .replace("__BUILD_DATE__", stats.get("build_date", "")))
    out = os.path.join(_ROOT, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    n = len(bench)
    print(f"wrote {out} with {n} questions "
          f"({Counter([b['qtype'] for b in bench])})")


if __name__ == "__main__":
    main()
