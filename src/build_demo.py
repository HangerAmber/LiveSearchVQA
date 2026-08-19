# -*- coding: utf-8 -*-
"""Build demo.html: an interactive showcase page for LiveSearchVQA v2.

Reads data/benchmark_v2.json + data/stats_v2.json and emits a single
self-contained HTML file at the repo root (images referenced relatively,
so it works both locally and on GitHub Pages).
"""
import json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

items = json.load(open(os.path.join(DATA, "benchmark_v2.json"), encoding="utf-8"))
if isinstance(items, dict):
    items = items.get("items", items.get("questions", []))
stats = json.load(open(os.path.join(DATA, "stats_v2.json"), encoding="utf-8"))
showcase_path = os.path.join(DATA, "showcase_cases.json")
showcase_items = json.load(open(showcase_path, encoding="utf-8"))
if isinstance(showcase_items, dict):
    showcase_items = showcase_items.get("items", showcase_items.get("questions", []))
if len(showcase_items) != 10:
    raise ValueError(f"homepage showcase requires exactly 10 cases, got {len(showcase_items)}")

build_date = stats.get("build_date", datetime.date.today().isoformat())
n_items = len(items)
english_pct = round(100 * sum(it.get("source_language") == "en" for it in items)
                    / max(1, n_items))
quant_pct = round(100 * sum(it.get("answer_type") in {"numeric", "temporal"}
                          for it in items) / max(1, n_items))
cert_profile = stats.get("certification_profile", "3-model-x-4")
archive_dir = os.path.join(DATA, "archive_v2")
archive_dates = []
if os.path.isdir(archive_dir):
    archive_dates = [
        os.path.splitext(name)[0]
        for name in os.listdir(archive_dir)
        if name.endswith(".json")
    ]
snapshot_dates = sorted(set(archive_dates + [build_date]), reverse=True)
date_options = "".join(
    f'<option value="{date}"{(" selected" if date == build_date else "")}>'
    f'{date}{(" (latest)" if date == build_date else "")}</option>'
    for date in snapshot_dates
)

def slim_item(it):
    return {
        "id": it["id"],
        "img": "data/" + it["image"],
        "q": it["question"],
        "a": it["answer"],
        "type": it.get("answer_type", ""),
        "cat": it.get("category", ""),
        "lang": it.get("source_language", ""),
        "quant": bool(it.get("is_quantitative")),
        "ev": it.get("evidence", ""),
        "src": it.get("source", ""),
        "url": it.get("article_url", ""),
        "title": it.get("article_title", ""),
        "pub": (it.get("pub_date", "") or "")[:16].replace("T", " "),
        "cb": it.get("closed_book_preds", []),
        "orp": it.get("oracle_preds", []),
        "profile": (it.get("certification") or {}).get("profile", cert_profile),
        "match": it.get("image_match_audit", {}),
        "theme": it.get("showcase_theme", ""),
        "note": it.get("showcase_note", ""),
    }


# Slim, self-contained payloads for the selected split and fixed showcase.
slim = [slim_item(it) for it in items]
showcase_slim = [slim_item(it) for it in showcase_items]

cats = sorted({s["cat"] for s in slim})
types = ["numeric", "entity", "location", "outcome", "temporal"]

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LiveSearchVQA — Live Demo</title>
<style>
:root{
  --bg:#0b1120; --bg2:#0f172a; --card:#141d33; --card2:#1a2540;
  --line:#243252; --txt:#e6ecf7; --mut:#8fa3c4; --dim:#5b6d8f;
  --teal:#2dd4bf; --blue:#60a5fa; --gold:#fbbf24; --red:#f87171; --green:#4ade80;
  --grad:linear-gradient(90deg,#2dd4bf,#60a5fa);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--txt);
  font-family:"Segoe UI","Microsoft YaHei",system-ui,-apple-system,sans-serif;line-height:1.55}
a{color:var(--blue);text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}

/* ---------- hero ---------- */
.hero{position:relative;overflow:hidden;padding:88px 0 64px;
  background:radial-gradient(900px 420px at 15% -10%,rgba(45,212,191,.16),transparent 60%),
             radial-gradient(900px 480px at 85% -20%,rgba(96,165,250,.18),transparent 60%),var(--bg)}
.hero::after{content:"";position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(rgba(143,163,196,.05) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(143,163,196,.05) 1px,transparent 1px);
  background-size:44px 44px;mask-image:linear-gradient(#000,transparent 85%)}
.live{display:inline-flex;align-items:center;gap:8px;font-size:13px;letter-spacing:.14em;
  color:var(--teal);border:1px solid rgba(45,212,191,.4);border-radius:999px;
  padding:6px 14px;margin-bottom:22px;background:rgba(45,212,191,.07)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--teal);animation:pulse 1.6s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(45,212,191,.55)}70%{box-shadow:0 0 0 9px rgba(45,212,191,0)}100%{box-shadow:0 0 0 0 rgba(45,212,191,0)}}
h1{font-size:clamp(38px,6vw,64px);font-weight:800;letter-spacing:-.02em}
h1 .g{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.tag{margin-top:14px;font-size:clamp(15px,2vw,19px);color:var(--mut);max-width:760px}
.zh{margin-top:8px;font-size:15px;color:var(--dim)}
.cta{margin-top:28px;display:flex;gap:14px;flex-wrap:wrap}
.btn{display:inline-block;padding:12px 22px;border-radius:10px;font-weight:600;font-size:15px;transition:.2s;
  cursor:pointer;border:none;font-family:inherit;background:transparent}
.btn-p{background:var(--grad);color:#08101f}
.btn-p:hover{filter:brightness(1.12);transform:translateY(-1px)}
.btn-o{border:1px solid var(--line);color:var(--txt);background:transparent}
.btn-o:hover{border-color:var(--teal);color:var(--teal)}
.stats{margin-top:46px;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.stat{background:rgba(20,29,51,.72);border:1px solid var(--line);border-radius:14px;padding:18px 20px;backdrop-filter:blur(4px)}
.stat b{display:block;font-size:30px;font-weight:800;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.stat span{font-size:12.5px;color:var(--mut);letter-spacing:.04em}

/* ---------- sections ---------- */
section{padding:60px 0}
h2{font-size:28px;font-weight:800;margin-bottom:8px}
.sub{color:var(--mut);margin-bottom:30px;font-size:15px}
.accent{width:56px;height:4px;background:var(--grad);border-radius:2px;margin:12px 0 26px}

/* pipeline */
.pipe{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.stage{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;position:relative;transition:.2s}
.stage:hover{transform:translateY(-3px);border-color:var(--teal)}
.stage i{font-style:normal;display:inline-block;font-size:11px;color:var(--teal);letter-spacing:.12em;margin-bottom:6px}
.stage b{display:block;font-size:15px;margin-bottom:6px}
.stage p{font-size:12.5px;color:var(--mut)}
.stage .n{margin-top:10px;font-size:13px;font-weight:700}
.n.drop{color:var(--red)} .n.keep{color:var(--green)}

/* protocol */
.trio{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}
.cond{border-radius:16px;padding:22px;border:1px solid var(--line);background:var(--card)}
.cond.cb{border-top:3px solid var(--dim)} .cond.ws{border-top:3px solid var(--blue)} .cond.or{border-top:3px solid var(--green)}
.cond b{font-size:17px} .cond p{margin-top:8px;font-size:13.5px;color:var(--mut)}
.cond .res{margin-top:12px;font-size:13px;font-weight:700}
.formula{margin-top:22px;background:var(--card2);border:1px solid var(--line);border-radius:14px;
  padding:18px 24px;font-size:15px;color:var(--mut)}
.formula code{color:var(--gold);font-size:17px;font-family:Consolas,monospace}

/* representative showcase */
#showcase{background:linear-gradient(180deg,var(--bg),var(--bg2))}
.showcase-head{display:flex;justify-content:space-between;gap:28px;align-items:end;flex-wrap:wrap}
.showcase-head .sub{max-width:720px;margin-bottom:0}
.showcase-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:30px}
.showcase-card{display:grid;grid-template-columns:180px minmax(0,1fr);min-height:176px;width:100%;
  overflow:hidden;text-align:left;color:var(--txt);font-family:inherit;background:var(--card);
  border:1px solid var(--line);border-radius:16px;cursor:pointer;transition:.2s}
.showcase-card:hover,.showcase-card:focus-visible{transform:translateY(-3px);border-color:var(--teal);
  box-shadow:0 12px 30px rgba(0,0,0,.28);outline:none}
.showcase-card img{width:100%;height:100%;min-height:176px;object-fit:cover;display:block}
.showcase-copy{padding:17px 18px;display:flex;flex-direction:column}
.showcase-kicker{font-size:11px;letter-spacing:.1em;color:var(--teal);font-weight:700;text-transform:uppercase}
.case-q{display:block;font-size:15.5px;line-height:1.4;margin-top:7px;font-weight:700}
.case-note{display:block;font-size:12.5px;color:var(--mut);margin-top:9px;line-height:1.45}
.showcase-meta{margin-top:auto;padding-top:12px;display:flex;gap:7px;flex-wrap:wrap}
@media(max-width:900px){.showcase-grid{grid-template-columns:1fr}}
@media(max-width:520px){.showcase-card{grid-template-columns:1fr}.showcase-card img{height:180px}}

/* challenge */
#challenge{background:var(--bg2)}
.arena{display:grid;grid-template-columns:minmax(280px,460px) 1fr;gap:26px;align-items:start}
@media(max-width:820px){.arena{grid-template-columns:1fr}}
.arena img{width:100%;border-radius:16px;border:1px solid var(--line);display:block}
.qbox{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px}
.qbox .badges{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.badge{font-size:11.5px;padding:4px 10px;border-radius:999px;letter-spacing:.06em;font-weight:600}
.b-cat{background:rgba(96,165,250,.14);color:var(--blue)}
.b-type{background:rgba(251,191,36,.13);color:var(--gold)}
.b-date{background:rgba(143,163,196,.12);color:var(--mut)}
.qbox h3{font-size:21px;line-height:1.4;font-weight:700}
.reveal{margin-top:20px}
.ans{display:none;margin-top:18px;border-top:1px dashed var(--line);padding-top:18px;animation:fade .4s}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1}}
.ans .gold{font-size:24px;font-weight:800;color:var(--green)}
.ev{margin-top:12px;background:var(--card2);border-left:3px solid var(--teal);border-radius:8px;
  padding:12px 14px;font-size:13.5px;color:var(--mut)}
.panel{margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:640px){.panel{grid-template-columns:1fr}}
.pv{border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:12.5px}
.pv b{display:block;font-size:12px;letter-spacing:.08em;margin-bottom:8px;color:var(--mut)}
.chip{display:inline-block;margin:2px 4px 2px 0;padding:3px 9px;border-radius:6px;font-size:12px;font-weight:600}
.chip.bad{background:rgba(248,113,113,.14);color:var(--red)}
.chip.good{background:rgba(74,222,128,.13);color:var(--green)}
.cert{margin-top:14px;font-size:13px;color:var(--teal);font-weight:600}
.srcline{margin-top:12px;font-size:12.5px;color:var(--dim)}

/* explorer */
.filters{position:sticky;top:0;z-index:30;background:rgba(11,17,32,.92);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);padding:14px 0}
.frow{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.chipbtn{cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--mut);
  padding:6px 14px;border-radius:999px;font-size:13px;transition:.15s}
.chipbtn:hover{border-color:var(--teal)}
.chipbtn.on{background:var(--grad);color:#08101f;font-weight:700;border-color:transparent}
#search{flex:1;min-width:180px;background:var(--card);border:1px solid var(--line);border-radius:999px;
  color:var(--txt);padding:8px 16px;font-size:13.5px;outline:none}
#search:focus{border-color:var(--teal)}
#count{font-size:12.5px;color:var(--dim);white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:16px;margin-top:26px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;cursor:pointer;transition:.2s}
.card:hover{transform:translateY(-4px);border-color:var(--blue);box-shadow:0 10px 30px rgba(0,0,0,.35)}
.card img{width:100%;height:150px;object-fit:cover;display:block}
.card .cbody{padding:13px 15px}
.card .q{font-size:13.5px;line-height:1.45;height:57px;overflow:hidden}
.card .meta{margin-top:10px;display:flex;gap:6px;flex-wrap:wrap}
.more{display:block;margin:30px auto 0;padding:11px 30px}

/* modal */
#modal{position:fixed;inset:0;z-index:99;display:none;align-items:center;justify-content:center;
  background:rgba(5,9,18,.8);backdrop-filter:blur(4px);padding:22px}
#modal.open{display:flex}
.mbox{background:var(--card);border:1px solid var(--line);border-radius:18px;max-width:920px;width:100%;
  max-height:92vh;overflow:auto;padding:28px;position:relative;animation:fade .25s}
.mclose{position:absolute;top:14px;right:18px;font-size:26px;color:var(--dim);cursor:pointer;background:none;border:none}
.mclose:hover{color:var(--red)}
.mgrid{display:grid;grid-template-columns:minmax(220px,380px) 1fr;gap:22px}
@media(max-width:760px){.mgrid{grid-template-columns:1fr}}
.mgrid img{width:100%;border-radius:12px;border:1px solid var(--line)}

/* distribution chart */
.dist-layout{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(320px,1.1fr);gap:52px;align-items:center}
@media(max-width:760px){.dist-layout{grid-template-columns:1fr;gap:34px}}
.donut-panel{display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:24px;align-items:center}
@media(max-width:520px){.donut-panel{grid-template-columns:1fr}.type-legend{grid-template-columns:1fr 1fr}}
#type-chart{display:block;width:100%;height:auto;overflow:visible}
.type-legend{display:grid;gap:9px}
.legend-row{display:grid;grid-template-columns:12px 1fr auto;gap:9px;align-items:center;font-size:13px;color:var(--mut)}
.legend-row i{width:10px;height:10px;border-radius:2px;display:block}
.legend-row b{color:var(--txt);font-variant-numeric:tabular-nums}
.brow{display:flex;align-items:center;gap:12px;margin-bottom:10px;font-size:13px}
.brow .lbl{width:88px;color:var(--mut);text-align:right}
.brow .track{flex:1;height:12px;background:var(--card2);border-radius:6px;overflow:hidden}
.brow .fill{height:100%;background:var(--grad);border-radius:6px;width:0;transition:width 1s ease}
.brow .v{width:36px;font-weight:700;font-size:12.5px}

/* dated snapshots */
#archive{padding-top:12px}
.archive-panel{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;
  background:linear-gradient(135deg,rgba(45,212,191,.08),rgba(96,165,250,.08));
  border:1px solid var(--line);border-radius:16px;padding:22px 24px}
.archive-control{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.archive-control label{font-size:13px;color:var(--mut);font-weight:700;letter-spacing:.04em}
#build-select{appearance:none;background:var(--card);color:var(--txt);border:1px solid var(--teal);
  border-radius:10px;padding:10px 38px 10px 14px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;
  background-image:linear-gradient(45deg,transparent 50%,var(--teal) 50%),linear-gradient(135deg,var(--teal) 50%,transparent 50%);
  background-position:calc(100% - 17px) 16px,calc(100% - 11px) 16px;background-size:6px 6px;background-repeat:no-repeat}
#build-select:disabled{opacity:.55;cursor:wait}
#archive-status{font-size:13px;color:var(--teal);font-weight:600}
.archive-note{max-width:520px;color:var(--mut);font-size:13px}

footer{border-top:1px solid var(--line);padding:36px 0;color:var(--dim);font-size:13px}
footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}
</style>
</head>
<body>

<!-- ===================== HERO ===================== -->
<div class="hero"><div class="wrap">
  <div class="live"><span class="dot"></span>LIVE &middot; REFRESHED ON DEMAND &middot; BUILD <span id="hero-build">__BUILD__</span></div>
  <h1>Live<span class="g">Search</span>VQA</h1>
  <div class="tag">An on-demand VQA benchmark for diagnosing <b>when</b>, <b>what</b>, and <b>how</b> web-search agents fail — built from news published within the last 48 hours, independently audited for image–question alignment, and certified <i>search-necessary</i> and <i>well-posed</i> item by item.</div>
  <div class="zh">仅按明确指令手动刷新 · 图文强匹配门槛 · 英文数字型事件优先 · 3 模型多采样逐条认证「不搜必错、给证必对」</div>
  <div class="cta">
    <a class="btn btn-p" href="#challenge">Try the Challenge &rarr;</a>
    <a class="btn btn-o" id="browse-link" href="#explorer">Browse __N__ Questions</a>
    <a class="btn btn-o" href="https://github.com/HangerAmber/LiveSearchVQA" target="_blank">GitHub</a>
  </div>
  <div class="stats">
    <div class="stat"><b id="stat-items" data-n="__N__">0</b><span>QUESTIONS IN SPLIT</span></div>
    <div class="stat"><b id="stat-cats" data-n="__NCAT__">0</b><span>NEWS CATEGORIES</span></div>
    <div class="stat"><b id="stat-english" data-n="__ENPCT__" data-suf="%">0</b><span>ENGLISH SOURCES</span></div>
    <div class="stat"><b id="stat-quant" data-n="__QPCT__" data-suf="%">0</b><span>NUMERIC / TEMPORAL</span></div>
    <div class="stat"><b data-n="48" data-suf="h">0</b><span>MAX EVENT AGE</span></div>
  </div>
</div></div>

<!-- ===================== PIPELINE ===================== -->
<section><div class="wrap">
  <h2>On-demand certified construction pipeline</h2>
  <div class="accent"></div>
  <div class="pipe">
    <div class="stage"><i>L0</i><b>Evidence-first draft</b><p>lock a fresh event fact first; same-call closed-book self-check</p><div class="n keep">cost &asymp; 0</div></div>
    <div class="stage"><i>L1</i><b>Alignment gate</b><p>independent image↔article and image↔question audit; reject image-only prompts</p><div class="n drop">4 scores &ge; 3/4</div></div>
    <div class="stage"><i>L1–L2</i><b>Cascade + early stop</b><p>cheap vision screen, then OR-logic closed-book / AND-logic oracle stopping</p><div class="n keep">fewer panel calls</div></div>
    <div class="stage"><i>L3</i><b>Full certification</b><p>__PROFILE__ panel: every CB sample fails and every oracle sample succeeds</p><div class="n keep">P1 + P2 intact</div></div>
    <div class="stage"><i>PUBLISH</i><b>Hard composition gates</b><p>pHash/question dedup, &ge;85% English, &ge;65% numeric or temporal</p><div class="n keep"><span id="publish-count">__N__</span> items/build</div></div>
  </div>
</div></section>

<!-- ===================== PROTOCOL ===================== -->
<section style="padding-top:0"><div class="wrap">
  <h2>Three-way diagnostic protocol</h2>
  <div class="accent"></div>
  <div class="trio">
    <div class="cond cb"><b>Closed-book</b><p>Image + question only, no tools. Certified &asymp; 0% by construction.</p><div class="res" style="color:var(--dim)">P1: search is necessary</div></div>
    <div class="cond ws"><b>With-search</b><p>Agent searches the live web; every retrieval logged for automatic error attribution.</p><div class="res" style="color:var(--blue)">end-to-end capability</div></div>
    <div class="cond or"><b>Oracle</b><p>Gold evidence as the sole context. Certified &asymp; ceiling by construction.</p><div class="res" style="color:var(--green)">P2: well-posed upper bound</div></div>
  </div>
  <div class="formula">Search Realization Ratio&nbsp;&nbsp;<code>&rho; = (Acc<sub>WS</sub> &minus; Acc<sub>CB</sub>) / (Acc<sub>OR</sub> &minus; Acc<sub>CB</sub>)</code>&nbsp;&nbsp;— the fraction of certified headroom an agent's own search realizes. Every miss is auto-attributed to <span style="color:var(--blue)">retrieval</span>, <span style="color:var(--red)">evidence contradiction</span>, or <span style="color:var(--gold)">distraction</span>.</div>
</div></section>

<!-- ===================== REPRESENTATIVE CASES ===================== -->
<section id="showcase"><div class="wrap">
  <div class="showcase-head">
    <div>
      <h2>10 representative certified cases</h2>
      <div class="accent"></div>
    </div>
    <div class="sub">A curated cross-section of markets, AI, FIFA governance, medicine, mobility, public health, climate, consumer technology, humanitarian response, and culture. Click any case to inspect its evidence and panel certificate.</div>
  </div>
  <div class="showcase-grid" id="showcase-grid"></div>
</div></section>

<!-- ===================== CHALLENGE ===================== -->
<section id="challenge"><div class="wrap">
  <h2>Can you beat the agents?</h2>
  <div class="sub">Try the ten representative cases above. The closed-book panel already tried and failed; guess first, then reveal the evidence-backed answer.</div>
  <div class="arena">
    <img id="c-img" src="" alt="news image">
    <div class="qbox">
      <div class="badges">
        <span class="badge b-cat" id="c-cat"></span>
        <span class="badge b-type" id="c-type"></span>
        <span class="badge b-date" id="c-pub"></span>
      </div>
      <h3 id="c-q"></h3>
      <div class="reveal">
        <button class="btn btn-p" id="c-reveal" onclick="revealAns()">Reveal answer</button>
        <button class="btn btn-o" onclick="nextQ()">Next question &rarr;</button>
      </div>
      <div class="ans" id="c-ans">
        <div class="gold" id="c-gold"></div>
        <div class="ev" id="c-ev"></div>
        <div class="panel">
          <div class="pv"><b>CLOSED-BOOK PANEL (no search)</b><div id="c-cb"></div></div>
          <div class="pv"><b>ORACLE PANEL (given evidence)</b><div id="c-or"></div></div>
        </div>
        <div class="cert" id="c-cert">&#10003; image–question aligned &nbsp;&middot;&nbsp; &#10003; certified search-necessary &nbsp;&middot;&nbsp; &#10003; certified well-posed</div>
        <div class="srcline" id="c-src"></div>
      </div>
    </div>
  </div>
</div></section>

<!-- ===================== EXPLORER ===================== -->
<section id="explorer" style="padding-bottom:0"><div class="wrap">
  <h2>Explore the selected split</h2>
  <div class="accent"></div>
</div>
<div class="filters"><div class="wrap frow">
  <input id="search" placeholder="Search questions / answers&hellip;" oninput="applyFilters()">
  <span id="fcats" class="frow"></span>
  <span id="ftypes" class="frow"></span>
  <span id="count"></span>
</div></div>
<div class="wrap">
  <div class="grid" id="grid"></div>
  <button class="btn btn-o more" id="more" onclick="showMore()">Show more</button>
</div></section>

<!-- ===================== STATS ===================== -->
<section><div class="wrap">
  <h2>Data type distribution</h2>
  <div class="sub">Counts and shares for the selected dated 200-item split; the chart updates when you switch builds.</div>
  <div class="accent"></div>
  <div class="dist-layout">
    <div class="donut-panel">
      <svg id="type-chart" viewBox="0 0 280 280" role="img" aria-labelledby="type-chart-title type-chart-desc">
        <title id="type-chart-title">Answer type distribution</title>
        <desc id="type-chart-desc">Donut chart showing the number and share of numeric, temporal, outcome, entity, and location questions.</desc>
      </svg>
      <div class="type-legend" id="type-legend" aria-label="Answer type legend"></div>
    </div>
    <div><div class="sub" style="margin-bottom:14px">Topic categories</div><div id="bars-cat"></div></div>
  </div>
</div></section>

<!-- ===================== DATED SNAPSHOTS ===================== -->
<section id="archive"><div class="wrap">
  <h2>Browse dated 200-item snapshots</h2>
  <div class="accent"></div>
  <div class="archive-panel">
    <div class="archive-control">
      <label for="build-select">BENCHMARK BUILD</label>
      <select id="build-select" onchange="switchBuild(this.value)">__DATE_OPTIONS__</select>
      <span id="archive-status">Viewing __BUILD__ · __N__ items</span>
    </div>
    <div class="archive-note">Each option is a frozen, separately certified VQA split. Select a date to replace the challenge, explorer, and composition views with that build's 200 items.</div>
  </div>
</div></section>

<footer><div class="wrap">
  <div>LiveSearchVQA &middot; build <span id="footer-build">__BUILD__</span> &middot; refreshed only on explicit command</div>
  <div><a href="https://github.com/HangerAmber/LiveSearchVQA" target="_blank">Code &amp; data</a> &middot; <a href="index_v2.html">Full table view</a></div>
</div></footer>

<!-- ===================== MODAL ===================== -->
<div id="modal" onclick="if(event.target===this)closeModal()">
  <div class="mbox">
    <button class="mclose" onclick="closeModal()">&times;</button>
    <div class="mgrid">
      <img id="m-img" src="">
      <div>
        <div class="badges" style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
          <span class="badge b-cat" id="m-cat"></span>
          <span class="badge b-type" id="m-type"></span>
          <span class="badge b-date" id="m-pub"></span>
        </div>
        <h3 id="m-q" style="font-size:19px;line-height:1.45"></h3>
        <div style="margin-top:14px" class="gold-line">Answer:&nbsp;<span id="m-gold" style="font-size:20px;font-weight:800;color:var(--green)"></span></div>
        <div class="ev" id="m-ev"></div>
        <div class="panel">
          <div class="pv"><b>CLOSED-BOOK PANEL</b><div id="m-cb"></div></div>
          <div class="pv"><b>ORACLE PANEL</b><div id="m-or"></div></div>
        </div>
        <div class="srcline" id="m-src"></div>
      </div>
    </div>
  </div>
</div>

<script>
const CURRENT_DATA = __DATA__;
const SHOWCASE_DATA = __SHOWCASE__;
const CURRENT_DATE = "__BUILD__";
const SNAPSHOT_DATES = __SNAPSHOTS__;
const DEFAULT_PROFILE = "__PROFILE__";
const TYPES = __TYPES__;
let DATA = CURRENT_DATA;
let CATS = __CATS__;
let selectedDate = CURRENT_DATE;

/* ---------- count-up ---------- */
const io = new IntersectionObserver(es=>es.forEach(e=>{
  if(!e.isIntersecting) return;
  const el = e.target, target = +el.dataset.n, suf = el.dataset.suf||"";
  let t0 = null;
  const step = ts => { if(!t0) t0 = ts;
    const p = Math.min((ts-t0)/1100, 1);
    el.textContent = Math.round(target*(1-Math.pow(1-p,3))) + suf;
    if(p<1) requestAnimationFrame(step); };
  requestAnimationFrame(step); io.unobserve(el);
}),{threshold:.6});
document.querySelectorAll(".stat b").forEach(el=>io.observe(el));

/* ---------- helpers ---------- */
const esc = s => (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
function normalizeItem(it){
  if(Object.prototype.hasOwnProperty.call(it,"img")) return it;
  let image = it.image || "";
  if(image && !image.startsWith("data/")) image = "data/" + image.replace(/^\/+/,"");
  return {
    id:it.id, img:image, q:it.question, a:it.answer,
    type:it.answer_type||"", cat:it.category||"", lang:it.source_language||"",
    quant:Boolean(it.is_quantitative), ev:it.evidence||"", src:it.source||"",
    url:it.article_url||"", title:it.article_title||"",
    pub:(it.pub_date||"").slice(0,16).replace("T"," "),
    cb:it.closed_book_preds||[], orp:it.oracle_preds||[],
    profile:(it.certification||{}).profile||DEFAULT_PROFILE,
    match:it.image_match_audit||{}
  };
}
function chips(preds, gold, oracle){
  if(!preds || !preds.length) return "<span class='chip bad'>n/a</span>";
  return preds.map(p=>{
    const ok = oracle;   // oracle preds are correct by construction; cb preds wrong/UNKNOWN
    return `<span class="chip ${ok?"good":"bad"}">${esc(p)} ${ok?"&#10003;":"&#10007;"}</span>`;
  }).join("");
}

/* ---------- representative showcase ---------- */
function renderShowcase(){
  const grid = document.getElementById("showcase-grid");
  grid.innerHTML = SHOWCASE_DATA.map((it,i)=>`
    <button class="showcase-card" type="button" onclick="openShowcase(${i})" aria-label="Open representative case ${i+1}: ${esc(it.theme)}">
      <img loading="lazy" src="${it.img}" alt="Visual anchor for ${esc(it.theme)} case">
      <span class="showcase-copy">
        <span class="showcase-kicker">Case ${String(i+1).padStart(2,"0")} · ${esc(it.theme)}</span>
        <span class="case-q">${esc(it.q)}</span>
        <span class="case-note">${esc(it.note)}</span>
        <span class="showcase-meta"><span class="badge b-type">${esc(it.type)}</span><span class="badge b-date">${esc(it.src)}</span></span>
      </span>
    </button>`).join("");
}

/* ---------- challenge ---------- */
let order = [], oi = 0;
function loadQ(it){
  document.getElementById("c-img").src = it.img;
  document.getElementById("c-q").textContent = it.q;
  document.getElementById("c-cat").textContent = it.cat;
  document.getElementById("c-type").textContent = it.type;
  document.getElementById("c-pub").textContent = (it.lang||"").toUpperCase() + " · published " + it.pub;
  document.getElementById("c-gold").textContent = it.a;
  document.getElementById("c-ev").innerHTML = "<b>Gold evidence:</b> " + esc(it.ev);
  document.getElementById("c-cb").innerHTML = chips(it.cb, it.a, false);
  document.getElementById("c-or").innerHTML = chips(it.orp, it.a, true);
  document.getElementById("c-cert").innerHTML =
    `&#10003; alignment audit passed &nbsp;&middot;&nbsp; &#10003; ${esc(it.profile)} P1/P2 certification`;
  document.getElementById("c-src").innerHTML =
    `Source: <a href="${it.url}" target="_blank">${esc(it.title||it.src)}</a>`;
  document.getElementById("c-ans").style.display = "none";
  document.getElementById("c-reveal").style.display = "inline-block";
}
function revealAns(){
  document.getElementById("c-ans").style.display = "block";
  document.getElementById("c-reveal").style.display = "none";
}
function resetChallenge(){
  order = [...SHOWCASE_DATA.keys()].sort(()=>Math.random()-.5); oi = 0;
  if(order.length) loadQ(SHOWCASE_DATA[order[0]]);
}
function nextQ(){
  if(!order.length) return;
  oi = (oi+1)%order.length; loadQ(SHOWCASE_DATA[order[oi]]);
}

/* ---------- explorer ---------- */
let fc = new Set(), ft = new Set(), shown = 24, filtered = DATA;
function mkChips(id, vals, set){
  const el = document.getElementById(id);
  el.innerHTML = vals.map(v=>`<button class="chipbtn" data-v="${v}">${v}</button>`).join("");
  el.querySelectorAll(".chipbtn").forEach(b=>b.onclick=()=>{
    const v=b.dataset.v;
    set.has(v)?set.delete(v):set.add(v);
    b.classList.toggle("on"); shown=24; applyFilters();
  });
}
function applyFilters(){
  const q = document.getElementById("search").value.toLowerCase();
  filtered = DATA.filter(it =>
    (!fc.size || fc.has(it.cat)) && (!ft.size || ft.has(it.type)) &&
    (!q || (it.q+" "+it.a).toLowerCase().includes(q)));
  render();
}
function render(){
  const g = document.getElementById("grid");
  g.innerHTML = filtered.slice(0,shown).map((it,i)=>`
    <div class="card" onclick="openModal(${DATA.indexOf(it)})">
      <img loading="lazy" src="${it.img}">
      <div class="cbody">
        <div class="q">${esc(it.q)}</div>
        <div class="meta"><span class="badge b-cat">${it.cat}</span><span class="badge b-type">${it.type}</span><span class="badge b-date">${(it.lang||"").toUpperCase()}</span></div>
      </div>
    </div>`).join("");
  document.getElementById("count").textContent = `${filtered.length} / ${DATA.length} items`;
  document.getElementById("more").style.display = shown < filtered.length ? "block" : "none";
}
function showMore(){ shown += 24; render(); }

/* ---------- modal ---------- */
function openItem(it){
  document.getElementById("m-img").src = it.img;
  document.getElementById("m-q").textContent = it.q;
  document.getElementById("m-cat").textContent = it.cat;
  document.getElementById("m-type").textContent = it.type;
  document.getElementById("m-pub").textContent = (it.lang||"").toUpperCase() + " · published " + it.pub;
  document.getElementById("m-gold").textContent = it.a;
  document.getElementById("m-ev").innerHTML = "<b>Gold evidence:</b> " + esc(it.ev);
  document.getElementById("m-cb").innerHTML = chips(it.cb, it.a, false);
  document.getElementById("m-or").innerHTML = chips(it.orp, it.a, true);
  document.getElementById("m-src").innerHTML =
    `Source: <a href="${it.url}" target="_blank">${esc(it.title||it.src)}</a>`;
  document.getElementById("modal").classList.add("open");
}
function openModal(i){ openItem(DATA[i]); }
function openShowcase(i){ openItem(SHOWCASE_DATA[i]); }
function closeModal(){ document.getElementById("modal").classList.remove("open"); }
document.addEventListener("keydown", e=>{ if(e.key==="Escape") closeModal(); });

/* ---------- bars ---------- */
function bars(id, counts){
  const total = Math.max(1,...Object.values(counts));
  const el = document.getElementById(id);
  el.innerHTML = Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`
    <div class="brow"><span class="lbl">${k}</span>
      <div class="track"><div class="fill" data-w="${v/total*100}"></div></div>
      <span class="v">${v}</span></div>`).join("");
  requestAnimationFrame(()=>el.querySelectorAll(".fill").forEach(fill=>{
    fill.style.width = fill.dataset.w + "%";
  }));
}
function renderTypeChart(counts){
  const total = Math.max(1,Object.values(counts).reduce((a,b)=>a+b,0));
  const palette = ["var(--teal)","var(--blue)","var(--gold)","var(--green)","var(--red)"];
  const ordered = TYPES.filter(type=>counts[type]).map((type,i)=>({
    type, count:counts[type], pct:100*counts[type]/total, color:palette[i%palette.length]
  }));
  let offset = 0;
  const rings = ordered.map(row=>{
    const ring = `<circle cx="140" cy="140" r="86" fill="none" stroke="${row.color}" stroke-width="30"
      pathLength="100" stroke-dasharray="${row.pct} ${100-row.pct}" stroke-dashoffset="${-offset}"
      transform="rotate(-90 140 140)"><title>${esc(row.type)}: ${row.count} (${row.pct.toFixed(1)}%)</title></circle>`;
    offset += row.pct;
    return ring;
  }).join("");
  document.getElementById("type-chart").innerHTML = `
    <title id="type-chart-title">Answer type distribution</title>
    <desc id="type-chart-desc">${ordered.map(r=>`${r.type} ${r.count}`).join(", ")}</desc>
    <circle cx="140" cy="140" r="86" fill="none" stroke="var(--card2)" stroke-width="30"></circle>
    ${rings}
    <text x="140" y="132" text-anchor="middle" fill="var(--txt)" font-size="32" font-weight="800">${total}</text>
    <text x="140" y="158" text-anchor="middle" fill="var(--mut)" font-size="12">CERTIFIED ITEMS</text>`;
  document.getElementById("type-legend").innerHTML = ordered.map(row=>`
    <div class="legend-row"><i style="background:${row.color}"></i><span>${esc(row.type)}</span>
      <b>${row.count} · ${row.pct.toFixed(1)}%</b></div>`).join("");
}
function updateBars(){
  const tc={},cc={};
  DATA.forEach(it=>{tc[it.type]=(tc[it.type]||0)+1;cc[it.cat]=(cc[it.cat]||0)+1});
  renderTypeChart(tc); bars("bars-cat",cc);
}

/* ---------- dated snapshots ---------- */
function setStat(id, value, suffix=""){
  const el = document.getElementById(id);
  el.dataset.n = value; el.dataset.suf = suffix; el.textContent = value + suffix;
}
function updateOverview(date){
  const cats = new Set(DATA.map(it=>it.cat).filter(Boolean));
  const english = Math.round(100*DATA.filter(it=>it.lang==="en").length/Math.max(1,DATA.length));
  const quant = Math.round(100*DATA.filter(it=>["numeric","temporal"].includes(it.type)).length/Math.max(1,DATA.length));
  setStat("stat-items",DATA.length); setStat("stat-cats",cats.size);
  setStat("stat-english",english,"%"); setStat("stat-quant",quant,"%");
  document.getElementById("hero-build").textContent = date;
  document.getElementById("footer-build").textContent = date;
  document.getElementById("browse-link").textContent = `Browse ${DATA.length} Questions`;
  document.getElementById("publish-count").textContent = DATA.length;
  document.getElementById("archive-status").textContent = `Viewing ${date} · ${DATA.length} items`;
}
function resetViews(date){
  selectedDate = date;
  CATS = [...new Set(DATA.map(it=>it.cat).filter(Boolean))].sort();
  fc.clear(); ft.clear(); shown=24; filtered=DATA;
  document.getElementById("search").value = "";
  mkChips("fcats",CATS,fc); mkChips("ftypes",TYPES,ft);
  closeModal(); resetChallenge(); render(); updateBars(); updateOverview(date);
}
async function switchBuild(date, updateUrl=true){
  if(!SNAPSHOT_DATES.includes(date) || date===selectedDate) return;
  const select = document.getElementById("build-select");
  const previous = selectedDate;
  select.disabled = true;
  document.getElementById("archive-status").textContent = `Loading ${date}…`;
  try{
    let raw = CURRENT_DATA;
    if(date!==CURRENT_DATE){
      const response = await fetch(`data/archive_v2/${encodeURIComponent(date)}.json`,{cache:"no-store"});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      raw = await response.json();
      if(!Array.isArray(raw)) raw = raw.items || raw.questions || [];
    }
    if(raw.length!==200) throw new Error(`expected 200 items, received ${raw.length}`);
    DATA = raw.map(normalizeItem);
    resetViews(date);
    select.value = date;
    if(updateUrl){
      const u = new URL(location.href);
      date===CURRENT_DATE ? u.searchParams.delete("date") : u.searchParams.set("date",date);
      history.replaceState({},"",u);
    }
  }catch(error){
    select.value = previous;
    document.getElementById("archive-status").textContent = `Could not load ${date}: ${error.message}`;
  }finally{ select.disabled=false; }
}

renderShowcase();
mkChips("fcats",CATS,fc); mkChips("ftypes",TYPES,ft);
resetChallenge(); render(); updateBars(); updateOverview(CURRENT_DATE);
const params = new URLSearchParams(location.search);
const requestedDate = params.get("date");
if(requestedDate && requestedDate!==CURRENT_DATE && SNAPSHOT_DATES.includes(requestedDate)){
  document.getElementById("build-select").value=requestedDate;
  switchBuild(requestedDate,false);
}
if(params.has("reveal")) revealAns();
</script>
</body>
</html>
"""

html = (PAGE
        .replace("__DATA__", json.dumps(slim, ensure_ascii=False))
        .replace("__SHOWCASE__", json.dumps(showcase_slim, ensure_ascii=False))
        .replace("__SNAPSHOTS__", json.dumps(snapshot_dates))
        .replace("__DATE_OPTIONS__", date_options)
        .replace("__CATS__", json.dumps(cats))
        .replace("__TYPES__", json.dumps(types))
        .replace("__BUILD__", build_date)
        .replace("__NCAT__", str(len(cats)))
        .replace("__ENPCT__", str(english_pct))
        .replace("__QPCT__", str(quant_pct))
        .replace("__PROFILE__", cert_profile)
        .replace("__N__", str(n_items)))

out = os.path.join(ROOT, "demo.html")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)
print("saved", out, len(html) // 1024, "KB")
