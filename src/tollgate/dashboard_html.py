"""Control Room WebUI — Protect · Route · Prove.

Designed for operators: see agents, set $ limits, prove failover.
"""

from __future__ import annotations

import re
from importlib.resources import files

from tollgate import i18n

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="{{ui.html_lang}}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Tollgate · Control Room</title>
<link rel="stylesheet" href="/static/np/networkpunkt-appbar.css"/>
<style>
  /* Local versioned NetzwerkPunkt basis; no CDN or new UI framework. */
  __NP_CSS__
  :root {
    --bg: var(--np-canvas); --bg2: var(--np-surface);
    --panel: var(--np-surface); --panel2: var(--np-hover);
    --line: var(--np-divider); --line2: var(--np-control-border);
    --fg: var(--np-text); --muted: var(--np-muted); --muted2: var(--np-muted);
    --ok: var(--np-success); --warn: var(--np-warning); --bad: var(--np-danger);
    --ok-dim: rgba(123,218,167,.12); --warn-dim: rgba(228,190,112,.12);
    --bad-dim: rgba(244,155,155,.12); --acc-dim: rgba(237,240,244,.12);
    --acc: var(--np-action); --acc2: var(--np-muted);
    --control: var(--np-control); --control-sm: 32px; --control-touch: var(--np-control-touch);
    --text-sm: var(--np-meta); --text-base: var(--np-body);
    --text-lg: var(--np-heading); --text-xl: var(--np-title);
    --font: var(--np-font); --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  /* ThreadDesk look; TollGate brand contours instead of white edges. */
  :root { --brand: #e77745; --line2: var(--brand); --np-focus: var(--brand); }
  :focus-visible { outline: 2px solid var(--np-focus); outline-offset: 3px; }
  .control-scope { border-left: 2px solid var(--warn); padding: .6rem .9rem; }
  @media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto !important; }
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    min-height: 100vh;
    font-family: var(--font);
    background: var(--bg);
    color: var(--fg);
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
  }
  a { color: var(--acc); text-decoration: none; }
  a:hover { text-decoration: underline; }
  button {
    font: inherit; cursor: pointer; border: 1px solid var(--acc);
    border-radius: 0;
    background: var(--acc);
    color: var(--bg); padding: .55rem 1.05rem; font-weight: 600;
    min-height: var(--control);
    transition: filter .12s ease, opacity .12s;
  }
  button:hover { filter: brightness(1.08); }
  button:disabled { opacity: .5; cursor: wait; filter: none; }
  button.ghost {
    background: transparent; color: var(--fg);
    border: 1px solid var(--line2);
    box-shadow: none;
  }
  button.ghost:hover { background: var(--panel2); border-color: var(--muted2); filter: none; }
  button.sm {
    padding: .35rem .7rem; font-size: var(--text-sm); border-radius: 0;
    min-height: var(--control-sm);
  }
  .lang-switch a, nav a {
    min-height: var(--control-sm); display: inline-flex; align-items: center;
  }
  @media (pointer: coarse) {
    /* Unter dem Finger werden alle Ziele 44px. Das ist die Zahl, die Apple
       und Material dafuer nennen — kein eigener Geschmack. Der Zeiger ist
       das richtige Signal, nicht die Fensterbreite: ein schmales
       Desktop-Fenster ist kein Finger. */
    button, button.sm, .lang-switch a, nav a,
    .field input, .field select {
      min-height: var(--control-touch);
    }
  }

  /* Header: 64-px host bar, three balanced zones; the appbar is the center. */
  header {
    display: grid;
    grid-template-columns: minmax(190px, 1fr) auto minmax(190px, 1fr);
    align-items: center; gap: 1rem;
    height: 64px; padding: 0 1.5rem;
    border-bottom: 1px solid var(--line);
    background: rgba(18,19,22,.85);
    backdrop-filter: blur(16px) saturate(1.2);
    position: sticky; top: 0; z-index: 20;
  }
  .brand {
    display: flex; align-items: center; gap: .55rem;
    min-width: 0;
  }
  .brand-mark { display: block; height: 28px; width: auto; }
  .brand em { font-style: normal; color: var(--muted); font-weight: 500; letter-spacing: 0; font-size: var(--text-sm); }
  .header-right {
    display: flex; align-items: center; justify-content: flex-end;
    gap: .5rem; min-width: 0;
  }
  .np-appbar-host { grid-column: 2; justify-self: center; display: flex; align-items: center; }
  .header-more { position: relative; }
  .header-more > summary {
    list-style: none; cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center;
    width: 44px; height: 44px;
    border: 1px solid var(--line); background: var(--panel); color: var(--fg);
    font-size: 20px; line-height: 1; user-select: none;
  }
  .header-more > summary::-webkit-details-marker { display: none; }
  .header-more > summary::marker { content: ""; }
  .header-more[open] > summary { border-color: var(--line2); }
  .more-panel {
    position: absolute; right: 0; top: calc(100% + 10px); z-index: 30;
    display: grid; gap: .55rem; padding: .75rem; min-width: 280px;
    background: var(--panel); border: 1px solid var(--line);
    box-shadow: 0 12px 32px rgba(0,0,0,.35);
  }
  .more-panel .auth-bar { max-width: 100%; }
  .auth-bar {
    display: flex; align-items: center; gap: .4rem;
    font-size: var(--text-sm); color: var(--muted);
    background: var(--panel); border: 1px solid var(--line); border-radius: 0;
    padding: .25rem .55rem .25rem .75rem;
  }
  .auth-bar input {
    background: transparent; border: 0; color: var(--fg);
    width: 7.5rem; font: inherit; outline: none;
  }
  .lang-switch {
    display: inline-flex;
    gap: 2px;
    border: 1px solid var(--line2);
    border-radius: 0;
    padding: 2px;
  }
  .ob-card .lang-switch { float: right; margin: -.25rem 0 .5rem; }
  .lang-switch a {
    border-radius: 0;
    color: var(--muted);
    font-size: var(--text-sm);
    letter-spacing: .04em;
    padding: 3px 9px;
    text-decoration: none;
  }
  .lang-switch a.on { background: var(--acc); color: var(--bg); }
  .badge {
    display: inline-flex; align-items: center; gap: .4rem;
    padding: .32rem .75rem; border-radius: 0;
    font-size: var(--text-sm); font-weight: 700; letter-spacing: .05em;
    background: var(--panel); border: 1px solid var(--line); color: var(--muted);
  }
  .badge.ok { color: var(--ok); border-color: rgba(61,155,106,.35); background: var(--ok-dim); }
  .badge.warn { color: var(--warn); border-color: rgba(201,162,39,.35); background: var(--warn-dim); }
  .badge.bad, .badge.frozen { color: var(--bad); border-color: rgba(220,112,112,.4); background: var(--bad-dim); }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }

  nav {
    display: flex; gap: .2rem; flex-wrap: wrap;
    padding: .45rem 1.5rem;
    border-bottom: 1px solid var(--line);
    background: rgba(26,27,31,.6);
  }
  nav a {
    color: var(--muted); padding: .5rem .95rem; border-radius: 0;
    font-size: var(--text-base); font-weight: 600; text-decoration: none;
  }
  nav a:hover { color: var(--fg); background: var(--panel); text-decoration: none; }
  nav a.active {
    color: var(--fg); background: var(--panel);
    border: 1px solid var(--line2);
  }

  main { max-width: 1040px; margin: 0 auto; padding: 1.5rem 1.5rem 4rem; }
  .view { display: none; animation: fade .25s ease; }
  .view.active { display: block; }
  @keyframes fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

  h1.page { font-size: var(--text-xl); font-weight: 750; margin: 0 0 .35rem; letter-spacing: -.02em; }
  .sub { color: var(--muted); margin: 0 0 1.35rem; font-size: var(--text-base); max-width: 42rem; }
  h2.sec {
    font-size: var(--text-sm); text-transform: uppercase; letter-spacing: .1em;
    color: var(--muted2); margin: 1.6rem 0 .65rem; font-weight: 700;
  }

  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 0;
    padding: 1.15rem 1.25rem;
    margin-bottom: .9rem;
  }
  .card.flat { background: var(--panel); }

  .hero {
    display: grid; grid-template-columns: 150px 1fr; gap: 1.5rem; align-items: center;
  }
  @media (max-width:720px) {
    .hero { grid-template-columns: 1fr; }
    nav { overflow-x: auto; flex-wrap: nowrap; }
  }

  .ring-box { position: relative; width: 128px; height: 128px; margin: 0 auto; }
  .ring {
    --p: 0; width: 128px; height: 128px; border-radius: 50%;
    background: conic-gradient(var(--acc) calc(var(--p) * 1%), var(--line) 0);
    display: grid; place-items: center;
  }
  .ring::before {
    content: ""; width: 94px; height: 94px; border-radius: 50%;
    background: var(--panel); border: 1px solid var(--line);
  }
  .ring-box .val {
    position: absolute; inset: 0; display: grid; place-items: center;
    font-size: var(--text-xl); font-weight: 800; letter-spacing: -.03em;
  }
  .ring-label {
    text-align: center; margin-top: .45rem;
    font-size: var(--text-sm); color: var(--muted2); text-transform: uppercase; letter-spacing: .08em;
  }
  .grade { text-align: center; font-weight: 700; font-size: var(--text-base); margin-top: .15rem; }

  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: .65rem; }
  @media (max-width:560px) { .stats { grid-template-columns: 1fr 1fr; } }
  .stat {
    background: var(--bg); border: 1px solid var(--line); border-radius: 0;
    padding: .7rem .8rem;
  }
  .stat b { display: block; font-size: var(--text-lg); font-weight: 750; font-variant-numeric: tabular-nums; }
  .stat span {
    color: var(--muted2); font-size: var(--text-sm); text-transform: uppercase;
    letter-spacing: .06em; font-weight: 600;
  }

  .muted { color: var(--muted); }
  .ok { color: var(--ok); } .warn { color: var(--warn); } .bad { color: var(--bad); }

  .row {
    display: flex; justify-content: space-between; align-items: center; gap: 1rem;
    padding: .65rem 0; border-bottom: 1px solid var(--line); font-size: var(--text-base);
  }
  .row:last-child { border-bottom: 0; }

  .pill {
    display: inline-flex; align-items: center; gap: .25rem;
    padding: .18rem .5rem; border-radius: 0;
    font-size: var(--text-sm); font-weight: 650;
    background: var(--bg); border: 1px solid var(--line); color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .pill.ok { color: var(--ok); border-color: rgba(61,155,106,.3); background: var(--ok-dim); }
  .pill.warn { color: var(--warn); border-color: rgba(201,162,39,.3); background: var(--warn-dim); }
  .pill.bad { color: var(--bad); border-color: rgba(220,112,112,.35); background: var(--bad-dim); }
  .pill.acc { color: var(--acc); border-color: rgba(143,152,168,.35); background: var(--acc-dim); }

  .bar {
    height: 6px; background: var(--line); border-radius: 0; overflow: hidden; margin-top: .5rem;
  }
  .bar i { display: block; height: 100%; background: var(--acc); }
  .bar.warn i { background: var(--warn); }
  .bar.bad i { background: var(--bad); }

  /* Agent cards */
  .agent-grid { display: grid; gap: .85rem; }
  .agent-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 0;
    padding: 1.15rem 1.25rem;
    position: relative;
    overflow: hidden;
  }
  .agent-card::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--line2);
  }
  .agent-card.is-ok::before { background: var(--ok); }
  .agent-card.is-warn::before { background: var(--warn); }
  .agent-card.is-bad::before { background: var(--bad); }
  .agent-top {
    display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;
  }
  .agent-name { font-size: var(--text-lg); font-weight: 750; letter-spacing: -.01em; }
  .agent-meta { margin-top: .3rem; font-size: var(--text-sm); }
  .agent-spend {
    text-align: right; font-variant-numeric: tabular-nums;
  }
  .agent-spend .big {
    font-size: var(--text-lg); font-weight: 800; letter-spacing: -.02em; line-height: 1.1;
  }
  .agent-spend .cap { font-size: var(--text-sm); color: var(--muted); margin-top: .15rem; }
  .limit-row {
    display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .75rem;
  }
  .agent-foot {
    display: flex; justify-content: space-between; align-items: center;
    gap: .75rem; margin-top: .85rem; flex-wrap: wrap;
  }
  .agent-foot .muted { font-size: var(--text-sm); }

  .editor {
    display: none;
    margin-top: 1rem;
    padding: 1rem;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 0;
  }
  .editor.open { display: block; }
  .editor h3 {
    margin: 0 0 .75rem; font-size: var(--text-sm); text-transform: uppercase;
    letter-spacing: .08em; color: var(--muted2); font-weight: 700;
  }
  .fields {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: .65rem;
  }
  @media (max-width:700px) { .fields { grid-template-columns: 1fr 1fr; } }
  @media (max-width:480px) { .fields { grid-template-columns: 1fr; } }
  .field { margin: 0; }
  .field label {
    display: block; font-size: var(--text-sm); color: var(--muted2);
    text-transform: uppercase; letter-spacing: .06em; margin-bottom: .3rem; font-weight: 650;
  }
  .field input, .field select {
    width: 100%; min-height: var(--control);
    background: var(--panel); border: 1px solid var(--line2);
    color: var(--fg); border-radius: 0; padding: .55rem .7rem; font: inherit;
    font-variant-numeric: tabular-nums;
  }
  .field select {
    /* Ohne das zeichnet das Betriebssystem das Menue selbst — eigener
       Rahmen, eigene Schrift, unter Windows mit 3D-Effekt. Pfeil deshalb
       selbst. Genauso in ThreadDesk und 4AllPass. */
    appearance: none;
    -webkit-appearance: none;
    padding-right: 28px;
    background-image: linear-gradient(45deg, transparent 50%, var(--muted) 50%),
                      linear-gradient(135deg, var(--muted) 50%, transparent 50%);
    background-position: calc(100% - 16px) center, calc(100% - 11px) center;
    background-size: 5px 5px, 5px 5px;
    background-repeat: no-repeat;
  }
  .field input:focus, .field select:focus {
    outline: none; border-color: var(--acc); box-shadow: 0 0 0 3px var(--acc-dim);
  }
  .field hint { display: block; margin-top: .25rem; font-size: var(--text-sm); color: var(--muted2); }
  .editor .actions { margin-top: .9rem; display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }

  .overview-agents {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .75rem;
  }
  .mini-agent {
    background: var(--bg); border: 1px solid var(--line); border-radius: 0;
    padding: .85rem .95rem; cursor: pointer; transition: border-color .15s, background .15s;
  }
  .mini-agent:hover { border-color: var(--line2); background: var(--panel2); }
  .mini-agent .n { font-weight: 700; font-size: var(--text-base); }
  .mini-agent .s { font-size: var(--text-lg); font-weight: 750; margin: .35rem 0 .2rem; font-variant-numeric: tabular-nums; }
  .mini-agent .l { font-size: var(--text-sm); color: var(--muted); }

  table { width: 100%; border-collapse: collapse; font-size: var(--text-base); }
  th, td { text-align: left; padding: .6rem .4rem; border-bottom: 1px solid var(--line); }
  th { color: var(--muted2); font-size: var(--text-sm); text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }
  tr:last-child td { border-bottom: 0; }
  tr.click { cursor: pointer; }
  tr.click:hover td { background: rgba(143,152,168,.06); }

  .kv { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem .85rem; font-size: var(--text-base); }
  .kv b { color: var(--muted); font-weight: 500; font-size: var(--text-sm); display: block; margin-bottom: .15rem; }

  .reco {
    border-left: 3px solid var(--warn); padding: .15rem 0 .15rem .9rem; margin: .55rem 0;
    font-size: var(--text-base);
  }
  .reco.ok { border-color: var(--ok); }
  .reco.bad { border-color: var(--bad); }

  .actions { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: .85rem; }
  .empty { color: var(--muted); padding: .4rem 0; font-size: var(--text-base); }
  code {
    font-family: var(--mono); background: var(--bg); padding: .12rem .35rem;
    border-radius: 0; font-size: var(--text-sm); border: 1px solid var(--line);
  }
  footer {
    margin-top: 2.5rem; padding-top: 1.25rem; border-top: 1px solid var(--line);
    color: var(--muted2); font-size: var(--text-sm); line-height: 1.7;
  }

  /* Onboarding + modal */
  #onboard {
    display: none; position: fixed; inset: 0; z-index: 50;
    background: rgba(18,19,22,.92); backdrop-filter: blur(12px);
    align-items: center; justify-content: center; padding: 1.25rem;
  }
  #onboard.open { display: flex; }
  .ob-card {
    width: min(440px, 100%); background: var(--panel); border: 1px solid var(--line);
    border-radius: 0; padding: 1.5rem;
  }
  .ob-steps { display: flex; gap: .4rem; margin: 0 0 1.1rem; }
  .ob-steps i { flex: 1; height: 4px; border-radius: 0; background: var(--line); }
  .ob-steps i.on { background: var(--acc); }
  .ob-card h1 { font-size: var(--text-lg); margin: 0 0 .4rem; }
  .ob-actions { display: flex; gap: .5rem; justify-content: space-between; margin-top: 1.1rem; flex-wrap: wrap; }
  .ob-check { margin: .4rem 0; font-size: var(--text-base); }
  .ob-check.ok { color: var(--ok); }
  .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: .65rem; }
  #blockModal {
    display: none; position: fixed; inset: 0; z-index: 60;
    background: rgba(18,19,22,.92); align-items: center; justify-content: center; padding: 1rem;
  }
  #blockModal.open { display: flex; }
  #blockModal .card {
    max-width: 440px; width: 100%; white-space: pre-wrap;
    font-family: var(--mono); font-size: var(--text-base);
  }
  #secBanner {
    display: none; margin: 0; padding: .55rem 1.5rem; font-size: var(--text-base);
    background: var(--warn-dim); color: var(--warn);
    border-bottom: 1px solid var(--warn);
  }
  #secBanner.show { display: block; }
  #secBanner.bad {
    background: var(--bad-dim); color: var(--bad); border-color: var(--bad);
  }
  .auth-bar { max-width: 100%; }
  .auth-bar input { width: 7.5rem; min-width: 0; }
  /* Neutral decorative contours; semantic badge colors keep their own rules. */
  .card, .auth-bar, .lang-switch { border-color: var(--line); }
  .np-appbar-button:focus-visible { outline-color: var(--np-text); }
  @media (max-width: 760px) {
    header {
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      gap: .4rem; padding: 0 .75rem;
    }
    .brand em { display: none; }
    .brand-mark { height: 24px; }
    .more-panel { right: -.75rem; min-width: 260px; }
    .auth-bar input { width: 5rem; }
  }
</style>
</head>
<body class="np-ui">
<div id="secBanner" role="status"></div>
<div id="onboard" role="dialog" aria-label="{{ui.setup}}">
  <div class="ob-card">
    <!-- Eigener Schalter im Assistenten. Der Kopf liegt unter dem Dialog, und
         wer den Assistenten nicht lesen kann, braucht den Schalter genau
         hier — nicht erst nach dem Wegklicken. -->
    <div class="lang-switch" role="group" aria-label="{{ui.lang_label}}">
      <a href="{{ui.lang_de_href}}" hreflang="de" lang="de" class="{{ui.lang_de_class}}">DE</a>
      <a href="{{ui.lang_en_href}}" hreflang="en" lang="en" class="{{ui.lang_en_class}}">EN</a>
    </div>
    <!-- Klartext ist der Normalfall, Fachsprache ist zuschaltbar. -->
    <div class="lang-switch" role="group" aria-label="{{ui.register_label}}">
      <a href="{{ui.register_plain_href}}" title="{{ui.register.plain_hint}}"
         class="{{ui.register_plain_class}}">{{ui.register.plain}}</a>
      <a href="{{ui.register_expert_href}}" title="{{ui.register.expert_hint}}"
         class="{{ui.register_expert_class}}">{{ui.register.expert}}</a>
    </div>
    <div class="ob-steps" id="obSteps"><i class="on"></i><i></i><i></i><i></i></div>
    <div id="obBody"></div>
    <div class="ob-actions">
      <button type="button" class="ghost" id="obSkip">{{ui.wizard.skip}}</button>
      <div style="display:flex;gap:.5rem">
        <button type="button" class="ghost" id="obBack" style="display:none">{{ui.wizard.back}}</button>
        <button type="button" id="obNext">{{ui.wizard.continue}}</button>
      </div>
    </div>
    <p class="muted" id="obErr" style="margin:.75rem 0 0;font-size:var(--text-base);display:none"></p>
  </div>
</div>

<header>
  <div class="brand">
    <img class="brand-mark" alt="{{ui.brand}}" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzNTAiIGhlaWdodD0iNjQiIHZpZXdCb3g9IjAgMCAzNTAgNjQiIHJvbGU9ImltZyIgYXJpYS1sYWJlbD0iVG9sbEdhdGUiPjx0aXRsZT5Ub2xsR2F0ZTwvdGl0bGU+PHRleHQgeD0iMTc1IiB5PSI0NiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9IkFyaWFsLEhlbHZldGljYSxzYW5zLXNlcmlmIiBmb250LXNpemU9IjQ0IiBmb250LXdlaWdodD0iNzAwIiBsZXR0ZXItc3BhY2luZz0iLTEiPjx0c3BhbiBmaWxsPSIjZmZmZmZmIj5Ub2xsPC90c3Bhbj48dHNwYW4gZmlsbD0iI2U3Nzc0NSI+R2F0ZTwvdHNwYW4+PC90ZXh0Pjwvc3ZnPgo="/>
    <em id="dayLabel"></em>
  </div>
  <div class="np-appbar-host" data-product-header></div>
  <div class="header-right">
    <div class="badge ok" id="statusBadge"><span class="dot"></span><span id="statusText">…</span></div>
    <details class="header-more" id="headerMore">
      <summary aria-label="{{ui.more_tools}}" title="{{ui.more_tools}}">+</summary>
      <div class="more-panel">
        <div class="lang-switch" role="group" aria-label="{{ui.lang_label}}">
          <a href="{{ui.lang_de_href}}" hreflang="de" lang="de" class="{{ui.lang_de_class}}">DE</a>
          <a href="{{ui.lang_en_href}}" hreflang="en" lang="en" class="{{ui.lang_en_class}}">EN</a>
        </div>
        <!-- Klartext ist der Normalfall, Fachsprache ist zuschaltbar. -->
        <div class="lang-switch" role="group" aria-label="{{ui.register_label}}">
          <a href="{{ui.register_plain_href}}" title="{{ui.register.plain_hint}}"
             class="{{ui.register_plain_class}}">{{ui.register.plain}}</a>
          <a href="{{ui.register_expert_href}}" title="{{ui.register.expert_hint}}"
             class="{{ui.register_expert_class}}">{{ui.register.expert}}</a>
        </div>
        <button type="button" class="ghost sm" id="btnSetup">{{ui.setup}}</button>
        <div class="auth-bar" title="{{ui.key_hint}}">
          <span>{{ui.key}}</span>
          <input id="apiKey" placeholder="desk" value="desk" autocomplete="off"/>
        </div>
      </div>
    </details>
  </div>
</header>

<nav>
  <a href="#overview" data-view="overview" class="active">{{ui.tab.overview}}</a>
  <a href="#agents" data-view="agents">{{ui.tab.agents}}</a>
  <a href="#providers" data-view="providers">{{ui.tab.providers}}</a>
  <a href="#prove" data-view="prove">{{ui.tab.prove}}</a>
  <a href="#audit" data-view="audit">{{ui.tab.audit}}</a>
</nav>

<main>
  <section class="view active" id="view-overview">
    <h1 class="page">{{ui.control_room}}</h1>
    <p class="sub">{{ui.overview.lead}}</p>
    <aside class="control-scope" aria-label="{{ui.control.scope_title}}">
      <strong>{{ui.control.scope_title}}</strong>
      <p>{{ui.control.scope_body}}</p>
    </aside>

    <div class="card hero">
      <div>
        <div class="ring-box">
          <div class="ring" id="ring" style="--p:0"></div>
          <div class="val" id="ringVal">—</div>
        </div>
        <div class="ring-label">{{ui.reliability}}</div>
        <div class="grade" id="grade">—</div>
      </div>
      <div>
        <div class="stats" id="stats"></div>
        <p class="muted" style="margin:.9rem 0 0;font-size:var(--text-base)" id="headline"></p>
      </div>
    </div>

    <h2 class="sec">{{ui.agents.heading}}</h2>
    <div class="card flat">
      <div class="overview-agents" id="costSplit"><div class="empty">{{ui.loading}}</div></div>
      <div class="actions" style="margin-top:.85rem">
        <a href="#agents" class="ghost" style="display:inline-flex;padding:.45rem .9rem;border-radius:0;border:1px solid var(--line2);font-weight:600;color:var(--fg);text-decoration:none">{{ui.manage_limits}}</a>
      </div>
    </div>

    <h2 class="sec">{{ui.needs_attention}}</h2>
    <div class="card" id="attention"><div class="empty">{{ui.loading}}</div></div>

    <h2 class="sec">{{ui.recommendations}}</h2>
    <div class="card" id="reco"><div class="empty">{{ui.loading}}</div></div>

    <h2 class="sec">{{ui.tab.providers}}</h2>
    <div class="card" id="provGlance"><div class="empty">{{ui.loading}}</div></div>

    <div class="actions">
      <button type="button" class="ghost" id="btnLoopTest">{{ui.test_loop_block}}</button>
      <button type="button" class="ghost" id="btnUnfreeze" style="display:none">{{ui.unfreeze}}</button>
    </div>
  </section>

  <div id="blockModal"><div class="card" id="blockModalBody"></div></div>

  <section class="view" id="view-agents">
    <h1 class="page">{{ui.tab.agents}}</h1>
    <p class="sub">{{ui.limits.intro_a}} <b>{{ui.limits.edit}}</b>{{ui.limits.intro_b}}</p>
    <div class="agent-grid" id="agentsList"><div class="card empty">{{ui.loading}}</div></div>
  </section>

  <section class="view" id="view-providers">
    <h1 class="page">{{ui.tab.providers}}</h1>
    <p class="sub">{{ui.providers.lead}}</p>
    <div class="card">
      <table>
        <thead><tr><th>{{ui.col.provider}}</th><th>{{ui.col.health}}</th><th>{{ui.col.success}}</th><th>{{ui.col.latency}}</th><th>{{ui.col.cost_day}}</th><th>{{ui.col.circuit}}</th></tr></thead>
        <tbody id="provTable"></tbody>
      </table>
    </div>
    <div id="provDetail"></div>
  </section>

  <section class="view" id="view-prove">
    <h1 class="page">{{ui.tab.prove}}</h1>
    <p class="sub">{{ui.prove.lead}}</p>
    <div class="card" id="proveScore"></div>
    <div class="card">
      <h2 class="sec" style="margin-top:0">{{ui.prove.test_title}}</h2>
      <p class="muted" id="proveLast">{{ui.prove.last_none}}</p>
      <div class="actions">
        <label class="muted" style="display:flex;align-items:center;gap:.4rem">{{ui.col.provider}}
          <input id="chaosProvider" value="opencode_zen"
            style="background:var(--bg);border:1px solid var(--line2);color:var(--fg);border-radius:0;padding:.4rem .55rem"/>
        </label>
        <button id="btnChaos">{{ui.prove.run}}</button>
        <button class="ghost" id="btnCert">{{ui.prove.refresh_cert}}</button>
      </div>
      <pre id="proveOut" class="muted" style="margin-top:1rem;white-space:pre-wrap;font-size:var(--text-base);font-family:var(--mono)"></pre>
    </div>
    <div class="card" id="certCard"></div>
  </section>

  <section class="view" id="view-audit">
    <h1 class="page">{{ui.tab.audit}}</h1>
    <p class="sub">{{ui.audit.lead}}</p>
    <div class="actions" style="margin-bottom:.75rem">
      <button class="ghost" id="btnAudit">{{ui.refresh}}</button>
      <button class="ghost" id="btnAuditDenies">{{ui.denies_only}}</button>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>{{ui.col.when}}</th><th>{{ui.col.agent}}</th><th>{{ui.col.event}}</th><th>{{ui.col.provider}}</th><th>{{ui.col.detail}}</th></tr></thead>
        <tbody id="auditTable"></tbody>
      </table>
    </div>
  </section>

  <footer>
    {{ui.footer.lead}}
    <a href="/docs">{{ui.footer.api}}</a> ·
    <a href="https://landjunge.github.io/TollGate/" target="_blank" rel="noopener">{{ui.footer.website}}</a> ·
    <a href="https://github.com/landjunge/TollGate">{{ui.footer.github}}</a> ·
    <code>{{ui.footer.help}}</code>
  </footer>
</main>

<script>
const $ = (id) => document.getElementById(id);

// Everything below builds DOM with innerHTML. Any value that originated outside
// this process — consumer labels from X-Consumer-Key, provider ids from config,
// chaos labels — must pass through esc() first. The dashboard shares an origin
// with /v1/config, and in open mode every caller is admin, so markup rendered
// here runs with full control-plane authority.
function esc(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function key() { return ($('apiKey').value || 'desk').trim(); }
function headers() {
  const k = key();
  return {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'X-Consumer-Key': k,
    'Authorization': 'Bearer ' + k,
  };
}
function cls(s) {
  s = (s || '').toLowerCase();
  if (['ok','healthy','pass','protected','closed'].includes(s)) return 'ok';
  if (['warn','likely_over','degraded','half_open','approaching','ready','not_run'].includes(s)) return 'warn';
  return 'bad';
}
function money(n) {
  const v = Number(n || 0);
  return '$' + (Math.abs(v) >= 10 ? v.toFixed(2) : v.toFixed(2));
}
function money4(n) { return '$' + Number(n || 0).toFixed(4); }
function pct(n) { return n == null ? '—' : (Number(n) * 100).toFixed(1) + '%'; }
function when(ts) {
  if (ts == null || ts === '') return '—';
  try {
    const t = Number(ts) > 1e12 ? Number(ts) : Number(ts) * 1000;
    return new Date(t).toLocaleString();
  } catch { return String(ts); }
}
function grade(score) {
  if (score == null) return { t: '—', c: 'muted' };
  if (score >= 85) return { t: '{{ui.grade.good}}', c: 'ok' };
  if (score >= 65) return { t: '{{ui.grade.fair}}', c: 'warn' };
  return { t: '{{ui.grade.weak}}', c: 'bad' };
}
function cardTone(c) {
  if (!c.protected) return 'is-warn';
  if (c.status === 'over_budget' || c.status === 'blocked') return 'is-bad';
  if (c.status === 'warn' || c.status === 'likely_over') return 'is-warn';
  return 'is-ok';
}
function limitPills(c) {
  const pills = [];
  if (c.max_usd_day) pills.push(`<span class="pill acc" title="{{ui.pill.day}}">{{ui.pill.day_short}} ${money(c.max_usd_day)}</span>`);
  if (c.max_usd_hour) pills.push(`<span class="pill warn" title="{{ui.pill.hour}}">{{ui.pill.hour_short}} ${money(c.max_usd_hour)}</span>`);
  if (c.max_usd_request) pills.push(`<span class="pill" title="{{ui.pill.request}}">{{ui.pill.req_short}} ${money4(c.max_usd_request)}</span>`);
  if (c.max_tool_calls) pills.push(`<span class="pill" title="{{ui.pill.tool_stop}}">{{ui.pill.tools_short}} ${c.max_tool_calls}</span>`);
  if (c.max_requests_minute) pills.push(`<span class="pill">${c.max_requests_minute}{{ui.per_min}}</span>`);
  if (!pills.length) pills.push(`<span class="pill bad">{{ui.no_hard_limits}}</span>`);
  return pills.join('');
}

let CTRL = null;
let CERT = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(r.status + ' ' + t.slice(0, 180));
  }
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('json')) return r.json();
  return r.text();
}

function setStatus(ctrl) {
  const fr = ctrl.freeze || {};
  const att = ctrl.attention || [];
  const urgent = att.filter(a => a.level === 'error' || a.level === 'warn');
  const badge = $('statusBadge');
  const text = $('statusText');
  badge.className = 'badge';
  if (fr.frozen) {
    badge.classList.add('frozen');
    text.textContent = 'FROZEN';
  } else if (urgent.some(a => a.level === 'error')) {
    badge.classList.add('bad');
    text.textContent = 'ATTENTION';
  } else if (urgent.length) {
    badge.classList.add('warn');
    text.textContent = 'ATTENTION';
  } else {
    badge.classList.add('ok');
    text.textContent = 'PROTECTED';
  }
}

function renderOverview(ctrl, cert) {
  const s = ctrl.summary || {};
  const res = ctrl.resilience || {};
  const score = res.score != null ? Number(res.score) : null;
  const g = grade(score);
  $('ring').style.setProperty('--p', score == null ? 0 : Math.max(0, Math.min(100, score)));
  $('ringVal').textContent = score == null ? '—' : Math.round(score);
  $('grade').innerHTML = `<span class="${g.c}">${g.t}</span>`;
  $('dayLabel').textContent = ctrl.day ? '· ' + ctrl.day : '';
  $('headline').textContent = ctrl.headline || '';
  $('stats').innerHTML = [
    ['{{ui.stat.spent_today}}', money(s.usd)],
    ['{{ui.stat.requests}}', String(s.calls ?? 0)],
    ['{{ui.stat.success}}', s.errors != null && s.calls ? pct(1 - (s.errors / (s.calls || 1))) : '—'],
    ['{{ui.stat.agent_stops}}', String(s.agent_protection_blocks ?? 0)],
    ['{{ui.stat.circuits_open}}', String(s.circuits_open ?? 0)],
    ['{{ui.stat.agents_protected}}', String(s.consumers_protected ?? 0)],
  ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('');

  const consumers = ctrl.consumers || [];
  if (!consumers.length) {
    $('costSplit').innerHTML = `<div class="empty">{{ui.agents.none_traffic}}</div>`;
  } else {
    $('costSplit').innerHTML = consumers.slice(0, 12).map(c => {
      const day = c.max_usd_day ? money(c.max_usd_day) + '/day' : '{{ui.no_day_cap}}';
      const hour = c.max_usd_hour ? ' · ' + money(c.max_usd_hour) + '/hour' : '';
      return `<div class="mini-agent" data-goto-agent="${esc(c.consumer)}">
        <div class="n">${esc(c.consumer)}</div>
        <div class="s">${money4(c.usd)}</div>
        <div class="l">${day}${hour} · ${c.calls || 0} {{ui.suffix.req}}</div>
      </div>`;
    }).join('');
    document.querySelectorAll('[data-goto-agent]').forEach(el => {
      el.onclick = () => {
        location.hash = '#agents';
        onHash();
        setTimeout(() => {
          const name = el.getAttribute('data-goto-agent');
          const cards = document.querySelectorAll('.agent-card');
          cards.forEach(card => {
            if (card.dataset.name === name) {
              const ed = card.querySelector('.editor');
              if (ed) {
                ed.classList.add('open');
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            }
          });
        }, 80);
      };
    });
  }

  const att = ctrl.attention || [];
  if (!att.length) {
    $('attention').innerHTML = `<div class="ok">{{ui.nothing_urgent}}</div>`;
  } else {
    $('attention').innerHTML = `<div class="muted" style="margin-bottom:.5rem">${att.length} item(s)</div>` +
      att.map(a => {
        const c = a.level === 'ok' ? 'ok' : (a.level === 'error' ? 'bad' : 'warn');
        const mark = a.level === 'ok' ? '✓' : (a.level === 'error' ? '⛔' : '⚠');
        return `<div class="row"><span class="${c}">${mark} ${esc(a.message || '')}</span><span class="muted">${esc(a.code || '')}</span></div>`;
      }).join('');
  }

  const recos = [];
  if (ctrl.freeze && ctrl.freeze.frozen) {
    recos.push({ level: 'bad', text: '{{ui.frozen_note}}', href: null });
  }
  consumers.filter(c => !c.protected && c.consumer).forEach(c => {
    recos.push({ level: 'warn', text: `«${esc(c.consumer)}» has weak limits — set day/hour budgets under Agents.`, href: '#agents' });
  });
  consumers.filter(c => ['warn', 'likely_over', 'over_budget'].includes(c.status)).forEach(c => {
    recos.push({
      level: c.status === 'over_budget' ? 'bad' : 'warn',
      text: `«${esc(c.consumer)}» ${money4(c.usd)}` + (c.max_usd_day ? ` / ${money(c.max_usd_day)} day` : '') + ` (${esc(c.status)})`,
      href: '#agents',
    });
  });
  const last = (ctrl.chaos || {}).last_report;
  if (!last) {
    recos.push({ level: 'warn', text: '{{ui.prove_pending}}', href: '#prove' });
  } else if (last.survived === false) {
    recos.push({ level: 'bad', text: `Last DR test failed for ${esc(last.chaos_provider)}.`, href: '#prove' });
  }
  if (!recos.length) recos.push({ level: 'ok', text: '{{ui.desk_protected}}', href: null });
  $('reco').innerHTML = recos.map(r =>
    `<div class="reco ${r.level}">${esc(r.text)}${r.href ? ` <a href="${esc(r.href)}">{{ui.open_arrow}}</a>` : ''}</div>`
  ).join('');

  const provs = (ctrl.providers || []).filter(p => p.enabled !== false).slice(0, 6);
  if (!provs.length) {
    $('provGlance').innerHTML = `<div class="empty">{{ui.no_provider_traffic}}</div>`;
  } else {
    $('provGlance').innerHTML = provs.map(p =>
      `<div class="row">
        <span><b>${esc(p.provider)}</b> <span class="pill ${cls(p.status)}">${esc(p.status)}</span></span>
        <span class="muted">${pct(p.success_rate)} · ${p.latency_ms_avg != null ? Math.round(p.latency_ms_avg) + 'ms' : '—'} · ${money4(p.usd)}</span>
      </div>`
    ).join('');
  }

  const uf = $('btnUnfreeze');
  if (uf) uf.style.display = (ctrl.freeze && ctrl.freeze.frozen) ? '' : 'none';
}

function renderAgents(ctrl) {
  const list = ctrl.consumers || [];
  if (!list.length) {
    $('agentsList').innerHTML = `<div class="card empty">{{ui.agents.none}}
      <div class="actions"><button type="button" id="btnSetupAgents">{{ui.protect_first}}</button></div></div>`;
    const b = $('btnSetupAgents');
    if (b) b.onclick = () => { OB.step = 0; renderObSteps(); showOnboard(true); };
    return;
  }
  $('agentsList').innerHTML = list.map((c, i) => {
    const max = Number(c.max_usd_day || 0);
    const used = Number(c.usd || 0);
    const rem = max > 0 ? Math.max(0, (c.remaining_usd != null ? Number(c.remaining_usd) : max - used)) : null;
    const ratio = max > 0 ? Math.min(100, (used / max) * 100) : 0;
    const barC = (c.status === 'over_budget' || c.status === 'blocked') ? 'bad'
      : (c.status === 'warn' || c.status === 'likely_over') ? 'warn' : '';
    const st = c.protected ? (c.status === 'ok' ? 'Protected' : c.status) : 'Unprotected';
    const stc = c.protected && c.status === 'ok' ? 'ok' : cls(c.status);
    return `<div class="agent-card ${cardTone(c)}" data-name="${esc(c.consumer)}" id="agent-card-${i}">
      <div class="agent-top">
        <div>
          <div class="agent-name">${esc(c.consumer)}</div>
          <div class="agent-meta ${stc}">● ${esc(st)}${c.uses_default_only ? ' {{ui.default_policy}}' : ''}</div>
        </div>
        <div class="agent-spend">
          <div class="big">${money4(used)}</div>
          <div class="cap">${max > 0 ? '{{ui.of_open}}' + money(max) + '{{ui.per_day}}' : '{{ui.spent_today_lower}}'}${rem != null && max > 0 ? ' · ' + money4(rem) + '{{ui.left_suffix}}' : ''}</div>
        </div>
      </div>
      ${max > 0 ? `<div class="bar ${barC}"><i style="width:${ratio}%"></i></div>` : ''}
      <div class="limit-row">${limitPills(c)}</div>
      <div class="agent-foot">
        <span class="muted">${c.calls || 0} {{ui.eod_line}} ${money4(c.projected_usd_eod)}</span>
        <div style="display:flex;gap:.4rem">
          <button type="button" class="ghost sm" data-edit="${i}">{{ui.limits.edit}}</button>
          <button type="button" class="ghost sm" data-loop="${esc(c.consumer)}">{{ui.test_loop}}</button>
        </div>
      </div>
      <div class="editor" id="agent-d-${i}">
        <h3>{{ui.limits_for_open}}${esc(c.consumer)}{{ui.limits_for_close}}</h3>
        <div class="fields">
          <div class="field">
            <label>{{ui.budget.day}}</label>
            <input id="ed-day-${i}" type="number" min="0" step="0.5" value="${c.max_usd_day ?? ''}" placeholder="{{ui.eg.5}}"/>
            <span class="hint">{{ui.budget.day_hint}}</span>
          </div>
          <div class="field">
            <label>{{ui.budget.hour}}</label>
            <input id="ed-hour-${i}" type="number" min="0" step="0.25" value="${c.max_usd_hour ?? ''}" placeholder="{{ui.eg.2}}"/>
            <span class="hint">{{ui.budget.hour_hint}}</span>
          </div>
          <div class="field">
            <label>{{ui.budget.request}}</label>
            <input id="ed-req-${i}" type="number" min="0" step="0.05" value="${c.max_usd_request ?? ''}" placeholder="{{ui.eg.050}}"/>
            <span class="hint">{{ui.budget.request_hint}}</span>
          </div>
          <div class="field">
            <label>{{ui.budget.tool_calls}}</label>
            <input id="ed-tools-${i}" type="number" min="0" step="1" value="${c.max_tool_calls ?? ''}" placeholder="{{ui.eg.20}}"/>
            <span class="hint">{{ui.budget.tool_calls_hint}}</span>
          </div>
          <div class="field">
            <label>{{ui.budget.rpm}}</label>
            <input id="ed-rpm-${i}" type="number" min="0" step="1" value="${c.max_requests_minute ?? ''}" placeholder="{{ui.eg.40}}"/>
            <span class="hint">{{ui.budget.rpm_hint}}</span>
          </div>
        </div>
        <div class="actions">
          <button type="button" data-save="${i}" data-name="${esc(c.consumer)}">{{ui.save_limits}}</button>
          <button type="button" class="ghost" data-edit-close="${i}">{{ui.cancel}}</button>
          <span id="ed-msg-${i}" class="muted" style="font-size:var(--text-base)"></span>
        </div>
      </div>
    </div>`;
  }).join('');

  document.querySelectorAll('[data-edit]').forEach(btn => {
    btn.onclick = () => {
      const i = btn.getAttribute('data-edit');
      const ed = $('agent-d-' + i);
      const open = !ed.classList.contains('open');
      document.querySelectorAll('.editor').forEach(e => e.classList.remove('open'));
      document.querySelectorAll('[data-edit]').forEach(b => { b.textContent = '{{ui.limits.edit}}'; });
      if (open) {
        ed.classList.add('open');
        btn.textContent = 'Hide';
      }
    };
  });
  document.querySelectorAll('[data-edit-close]').forEach(btn => {
    btn.onclick = () => {
      const i = btn.getAttribute('data-edit-close');
      $('agent-d-' + i).classList.remove('open');
      const t = document.querySelector('[data-edit="'+i+'"]');
      if (t) t.textContent = '{{ui.limits.edit}}';
    };
  });
  document.querySelectorAll('[data-loop]').forEach(btn => {
    btn.onclick = () => simulateLoopBlock(btn.dataset.loop);
  });
  document.querySelectorAll('[data-save]').forEach(btn => {
    btn.onclick = () => saveAgentProtection(Number(btn.dataset.save), btn.dataset.name);
  });
}

function renderProviders(ctrl) {
  const rows = ctrl.providers || [];
  if (!rows.length) {
    $('provTable').innerHTML = `<tr><td colspan="6" class="muted">{{ui.no_provider_data}}</td></tr>`;
    return;
  }
  $('provTable').innerHTML = rows.map((p, i) =>
    `<tr class="click" data-prov="${i}">
      <td><b>${esc(p.provider)}</b>${p.enabled === false ? ' <span class="muted">{{ui.off}}</span>' : ''}</td>
      <td class="${cls(p.status)}">${esc(p.status)}</td>
      <td>${pct(p.success_rate)}</td>
      <td>${p.latency_ms_avg != null ? Math.round(p.latency_ms_avg) + ' ms' : '—'}</td>
      <td>${money4(p.usd)}</td>
      <td><span class="pill">${p.circuit || 'closed'}</span></td>
    </tr>`
  ).join('');
  document.querySelectorAll('[data-prov]').forEach(tr => {
    tr.onclick = () => {
      const p = rows[Number(tr.dataset.prov)];
      $('provDetail').innerHTML = `<div class="card">
        <b style="font-size:var(--text-lg)">${esc(p.provider)}</b>
        <div class="kv" style="margin-top:.75rem">
          <div><b>{{ui.health_score}}</b>${p.score ?? '—'}</div>
          <div><b>{{ui.status}}</b><span class="${cls(p.status)}">${esc(p.status)}</span></div>
          <div><b>{{ui.requests_today}}</b>${p.calls ?? 0}</div>
          <div><b>{{ui.errors}}</b>${p.errors ?? 0}</div>
          <div><b>{{ui.col.success}}</b>${pct(p.success_rate)}</div>
          <div><b>{{ui.avg_latency}}</b>${p.latency_ms_avg != null ? Math.round(p.latency_ms_avg) + ' ms' : '—'}</div>
          <div><b>{{ui.usd_today}}</b>${money4(p.usd)}</div>
          <div><b>{{ui.col.circuit}}</b>${esc(p.circuit)}</div>
        </div>
      </div>`;
    };
  });
}

function renderProve(ctrl, cert) {
  const res = ctrl.resilience || {};
  const last = (ctrl.chaos || {}).last_report;
  const score = res.score;
  $('proveScore').innerHTML = `
    <div class="stats">
      <div class="stat"><b>${score != null ? Math.round(score) : '—'}</b><span>{{ui.resilience}}</span></div>
      <div class="stat"><b>${res.policy_compliant === true ? 'OK' : (res.policy_compliant === false ? '⚠' : '—')}</b><span>{{ui.policy}}</span></div>
      <div class="stat"><b>${(ctrl.chaos && ctrl.chaos.history || []).length}</b><span>{{ui.dr_history}}</span></div>
    </div>
    <p class="muted" style="margin:.75rem 0 0">${esc(res.summary || ctrl.promise || '')}</p>`;
  if (!last) {
    $('proveLast').innerHTML = `
      <div style="margin-bottom:.5rem">{{ui.last_test}} <span class="warn">{{ui.never_run}}</span></div>
      <div class="muted" style="font-size:var(--text-base);line-height:1.5">
        {{ui.prove.needs_two}}
      </div>`;
  } else {
    const ok = last.survived;
    $('proveLast').innerHTML = `{{ui.last_test}} <span class="${ok ? 'ok' : 'bad'}">${ok ? '{{ui.passed}}' : '{{ui.failed}}'}</span>
      · ${esc(last.chaos_provider)} · ${last.successful || 0}/${last.requests_tested || 0} · recovery ${last.recovery_time_ms_best ?? '—'} ms
      <div style="margin-top:.35rem">${esc(last.message || '')}</div>`;
  }
  if (cert) {
    const checks = (cert.checks || []).map(ch =>
      `<div class="row"><span>${esc(ch.label)}</span><span class="${cls(ch.status)}">${esc(ch.status)}</span></div>
       ${ch.detail ? `<div class="muted" style="font-size:var(--text-sm);margin:-.2rem 0 .45rem">${esc(ch.detail)}</div>` : ''}`
    ).join('');
    $('certCard').innerHTML = `<h2 class="sec" style="margin-top:0">{{ui.report_title}}</h2>
      <div class="muted">${esc(cert.application || '')} {{ui.suffix.overall}} <b class="${cls(cert.overall)}">${esc(cert.overall)}</b></div>
      ${checks}
      <div style="margin-top:.75rem">{{ui.resilience}} <b>${cert.resilience_score ?? '—'}</b>/100</div>`;
  }
}

function renderAudit(events) {
  if (!events || !events.length) {
    $('auditTable').innerHTML = `<tr><td colspan="5" class="muted">{{ui.no_audit_rows}}</td></tr>`;
    return;
  }
  $('auditTable').innerHTML = events.map(e => {
    const ev = e.event || '—';
    const detail = (e.error || e.reason || (e.extra && JSON.stringify(e.extra)) || '—');
    const short = String(detail).slice(0, 90);
    return `<tr>
      <td class="muted">${when(e.ts)}</td>
      <td>${esc(e.consumer || '—')}</td>
      <td class="${ev === 'admit_deny' ? 'bad' : ''}">${esc(ev)}</td>
      <td>${esc(e.provider || '—')}</td>
      <td class="muted" title="${esc(short)}">${esc(short)}</td>
    </tr>`;
  }).join('');
}

async function loadAll() {
  try {
    CTRL = await api('/v1/control');
    setStatus(CTRL);
    try { CERT = await api('/v1/certificate'); } catch { CERT = null; }
    renderOverview(CTRL, CERT);
    renderAgents(CTRL);
    renderProviders(CTRL);
    renderProve(CTRL, CERT);
  } catch (e) {
    $('headline').textContent = '{{ui.err.control_plane}} ' + e.message;
  }
}

async function loadAudit(deniesOnly) {
  try {
    const q = deniesOnly ? '?event=admit_deny&limit=40' : '?limit=40';
    const d = await api('/v1/audit' + q);
    renderAudit(d.events || []);
  } catch (e) {
    $('auditTable').innerHTML = `<tr><td colspan="5" class="bad">${esc(e.message)}</td></tr>`;
  }
}

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
  const el = $('view-' + name);
  if (el) el.classList.add('active');
  const link = document.querySelector(`nav a[data-view="${name}"]`);
  if (link) link.classList.add('active');
  if (name === 'audit') loadAudit(false);
  if (name === 'prove' && CTRL) renderProve(CTRL, CERT);
}

function onHash() {
  const h = (location.hash || '#overview').replace('#', '') || 'overview';
  showView(h);
}

window.addEventListener('hashchange', onHash);
$('apiKey').addEventListener('change', loadAll);
$('btnAudit').onclick = () => loadAudit(false);
$('btnAuditDenies').onclick = () => loadAudit(true);
$('btnCert').onclick = async () => {
  try {
    CERT = await api('/v1/certificate');
    if (CTRL) renderProve(CTRL, CERT);
    $('proveOut').textContent = '{{ui.cert_refreshed}}';
  } catch (e) { $('proveOut').textContent = e.message; }
};
$('btnChaos').onclick = async () => {
  const btn = $('btnChaos');
  btn.disabled = true;
  $('proveOut').textContent = '{{ui.running_test}}';
  try {
    const provider = $('chaosProvider').value.trim() || 'opencode_zen';
    const rep = await api('/v1/chaos/test', {
      method: 'POST',
      body: JSON.stringify({ provider, requests: 8, intent: 'free_llm' }),
    });
    const lines = [
      rep.survived ? '{{ui.test_passed}}' : '{{ui.test_failed}}',
      '',
      `Provider:     ${rep.chaos_provider}`,
      `Requests:     ${rep.requests_tested}`,
      `Successful:   ${rep.successful}`,
      `Failed:       ${rep.failed}`,
      `Failover %:   ${rep.automatic_failover_pct}`,
      `Recovery ms:  ${rep.recovery_time_ms_best}`,
      '',
      rep.message || '',
    ];
    $('proveOut').textContent = lines.join('\n');
    await loadAll();
    showView('prove');
  } catch (e) {
    $('proveOut').textContent = '{{ui.err.test_start}} ' + e.message;
  } finally {
    btn.disabled = false;
  }
};

try {
  const saved = localStorage.getItem('tollgate_api_key');
  if (saved) $('apiKey').value = saved;
} catch {}
$('apiKey').addEventListener('change', () => {
  try { localStorage.setItem('tollgate_api_key', key()); } catch {}
});

function showBlockModal(text) {
  $('blockModalBody').textContent = text;
  $('blockModal').classList.add('open');
}
$('blockModal').onclick = (e) => {
  if (e.target.id === 'blockModal') $('blockModal').classList.remove('open');
};

async function simulateLoopBlock(consumer) {
  const name = (consumer || '').trim() || 'support-agent';
  showBlockModal('{{ui.testing_loop}} ' + name + '…');
  try {
    const r = await fetch('/v1/invoke', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Consumer-Key': name,
        'Authorization': 'Bearer ' + name,
      },
      body: JSON.stringify({
        provider: 'opencode_zen',
        op: 'chat',
        tool_calls_est: 999,
        tokens_est: 10,
        // Nutzlast an den Provider, kein Bildschirmtext: bleibt stabil,
        // damit Audit-Zeilen zwischen Sprachen vergleichbar bleiben.
        arguments: { message: 'ui loop test' },
        agent_id: name,
        request_class: 'interactive',
      }),
    });
    const d = await r.json();
    const msg = (d.blocked && d.blocked.message) || d.message || d.error || JSON.stringify(d, null, 2);
    const header = d.ok === false ? 'Aha — Protect works\n\n' : 'Unexpected allow\n\n';
    showBlockModal(header + msg);
    await loadAll();
  } catch (e) {
    showBlockModal('{{ui.err.test}} ' + e.message);
  }
}

function numField(id) {
  const el = $(id);
  if (!el) return 0;
  const raw = el.value;
  if (raw === '' || raw == null) return 0;
  const n = Number(raw);
  return Number.isNaN(n) ? NaN : n;
}

async function saveAgentProtection(i, name) {
  const msg = $('ed-msg-' + i);
  try {
    const day = numField('ed-day-' + i);
    const hour = numField('ed-hour-' + i);
    const req = numField('ed-req-' + i);
    const tools = numField('ed-tools-' + i);
    const rpm = numField('ed-rpm-' + i);
    if ([day, hour, req, tools, rpm].some(n => Number.isNaN(n) || n < 0)) {
      throw new Error('{{ui.numbers_hint}}');
    }
    const env = {
      max_usd_day: day,
      max_usd_hour: hour,
      max_usd_request: req,
      max_tool_calls: Math.floor(tools),
      max_requests_minute: Math.floor(rpm),
    };
    if (msg) { msg.textContent = '{{ui.saving}}'; msg.className = 'muted'; }
    await api('/v1/config', {
      method: 'POST',
      body: JSON.stringify({ consumer_envelopes: { [name]: env } }),
    });
    if (msg) { msg.textContent = 'Saved.'; msg.className = 'ok'; }
    await loadAll();
    const ed = $('agent-d-' + i);
    if (ed) ed.classList.add('open');
    const t = document.querySelector('[data-edit="'+i+'"]');
    if (t) t.textContent = 'Hide';
  } catch (e) {
    if (msg) { msg.textContent = e.message; msg.className = 'bad'; }
  }
}

$('btnLoopTest').onclick = () => {
  const list = (CTRL && CTRL.consumers) || [];
  const c = list.find(x => x.protected) || list[0];
  simulateLoopBlock(c ? c.consumer : (OB.name || 'support-agent'));
};
$('btnUnfreeze').onclick = async () => {
  try {
    await api('/v1/freeze', { method: 'POST', body: JSON.stringify({ frozen: false }) });
    await loadAll();
  } catch (e) {
    alert('{{ui.err.unfreeze}} ' + e.message);
  }
};

const OB = {
  step: 0,
  name: 'support-agent',
  maxUsdDay: 20,
  maxUsdReq: 2,
  maxToolCalls: 20,
  maxRpm: 50,
};

function obDone() {
  try { return localStorage.getItem('tollgate_onboarded') === '1'; } catch { return false; }
}
function setObDone() {
  try { localStorage.setItem('tollgate_onboarded', '1'); } catch {}
}
function needsOnboarding(ctrl) {
  if (obDone()) return false;
  const list = (ctrl && ctrl.consumers) || [];
  return !list.some(c => c.protected);
}
function showOnboard(show) {
  $('onboard').classList.toggle('open', !!show);
}
function renderObSteps() {
  const dots = $('obSteps').querySelectorAll('i');
  dots.forEach((d, i) => d.classList.toggle('on', i <= OB.step));
  $('obBack').style.display = OB.step > 0 ? '' : 'none';
  const next = $('obNext');
  next.textContent = OB.step === 0 ? '{{ui.get_started}}' : (OB.step === 3 ? 'Finish' : 'Continue');
  const body = $('obBody');
  $('obErr').style.display = 'none';

  if (OB.step === 0) {
    body.innerHTML = `
      <h1>{{ui.wizard.welcome}}</h1>
      <p class="sub">{{ui.wizard.lead}}</p>
      <div class="ob-check ok">{{ui.wizard.claim}}</div>
      <div class="ob-check">{{ui.wizard.step1}}</div>
      <div class="ob-check">{{ui.wizard.step2}}</div>
      <div class="ob-check">{{ui.wizard.step3}}</div>`;
  } else if (OB.step === 1) {
    body.innerHTML = `
      <h1>{{ui.wizard.who}}</h1>
      <p class="sub">{{ui.wizard.who_hint}}</p>
      <div class="field">
        <label>{{ui.wizard.app_name}}</label>
        <input id="obName" value="${esc(OB.name)}" placeholder="support-agent"/>
      </div>`;
  } else if (OB.step === 2) {
    body.innerHTML = `
      <h1>{{ui.wizard.set_protection}}</h1>
      <p class="sub">{{ui.wizard.set_hint}}</p>
      <div class="field-row">
        <div class="field"><label>{{ui.wizard.daily_budget}}</label>
          <input id="obDay" type="number" min="0" step="0.5" value="${OB.maxUsdDay}"/></div>
        <div class="field"><label>{{ui.wizard.per_task}}</label>
          <input id="obReq" type="number" min="0" step="0.1" value="${OB.maxUsdReq}"/></div>
      </div>
      <div class="field-row">
        <div class="field"><label>{{ui.wizard.tool_calls}}</label>
          <input id="obTools" type="number" min="1" step="1" value="${OB.maxToolCalls}"/></div>
        <div class="field"><label>{{ui.wizard.rpm}}</label>
          <input id="obRpm" type="number" min="1" step="1" value="${OB.maxRpm}"/></div>
      </div>`;
  } else {
    body.innerHTML = `
      <h1>{{ui.wizard.protected}}</h1>
      <p class="sub">{{ui.wizard.lane}} <b>${esc(OB.name)}</b> {{ui.wizard.will_get}}</p>
      <div class="ob-check ok">{{ui.wizard.ok_budget}}</div>
      <div class="ob-check ok">{{ui.wizard.ok_loop}}</div>
      <div class="ob-check ok">{{ui.wizard.ok_rate}}</div>`;
  }
}

function readObFields() {
  if (OB.step === 1) {
    const n = ($('obName') && $('obName').value || '').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-');
    if (!n) throw new Error('{{ui.err.name_required}}');
    OB.name = n.slice(0, 64);
  }
  if (OB.step === 2) {
    OB.maxUsdDay = Math.max(0, Number($('obDay').value) || 0);
    OB.maxUsdReq = Math.max(0, Number($('obReq').value) || 0);
    OB.maxToolCalls = Math.max(0, parseInt($('obTools').value, 10) || 0);
    OB.maxRpm = Math.max(0, parseInt($('obRpm').value, 10) || 0);
    if (!OB.maxUsdDay && !OB.maxToolCalls) {
      throw new Error('{{ui.err.limit_required}}');
    }
  }
}

async function applyProtection() {
  const env = {};
  if (OB.maxUsdDay > 0) env.max_usd_day = OB.maxUsdDay;
  if (OB.maxUsdReq > 0) env.max_usd_request = OB.maxUsdReq;
  if (OB.maxToolCalls > 0) env.max_tool_calls = OB.maxToolCalls;
  if (OB.maxRpm > 0) env.max_requests_minute = OB.maxRpm;
  env.allowed_intents = ['free_llm', 'llm'];
  env.allowed_ops = ['chat', 'status', 'search'];
  await api('/v1/config', {
    method: 'POST',
    body: JSON.stringify({ consumer_envelopes: { [OB.name]: env } }),
  });
}

$('obSkip').onclick = () => { setObDone(); showOnboard(false); };
$('obBack').onclick = () => { if (OB.step > 0) { OB.step -= 1; renderObSteps(); } };
$('obNext').onclick = async () => {
  try { readObFields(); }
  catch (e) { $('obErr').style.display = ''; $('obErr').textContent = e.message; return; }
  if (OB.step < 3) { OB.step += 1; renderObSteps(); return; }
  $('obNext').disabled = true;
  try {
    await applyProtection();
    setObDone();
    showOnboard(false);
    await loadAll();
    location.hash = '#agents';
    onHash();
    setTimeout(() => simulateLoopBlock(OB.name), 400);
  } catch (e) {
    $('obErr').style.display = '';
    $('obErr').textContent = '{{ui.err.save_protection}} ' + e.message;
  } finally {
    $('obNext').disabled = false;
  }
};
$('btnSetup').onclick = () => { OB.step = 0; renderObSteps(); showOnboard(true); };

const _loadAllOrig = loadAll;
loadAll = async function () {
  await _loadAllOrig();
  if (CTRL && needsOnboarding(CTRL)) {
    OB.step = 0;
    renderObSteps();
    showOnboard(true);
  }
};

loadAll();
onHash();
setInterval(loadAll, 15000);
</script>
<script>
// Native family-switch bridge: only the catalog id crosses to the host. The
// host supplies its own PID and the fixed argv; the web never sends a URL,
// PID or argv.
window.__tgFamilySwitchResolvers = {};
window.__tgFamilySwitchResolve = function(requestId, outcome) {
  var resolve = window.__tgFamilySwitchResolvers[requestId];
  if (resolve) { delete window.__tgFamilySwitchResolvers[requestId]; resolve(outcome); }
};
window.__tgFamilySwitch = function(appId) {
  var handler = (window.webkit && window.webkit.messageHandlers &&
                 window.webkit.messageHandlers.familySwitch) || null;
  if (!handler) return Promise.resolve("missing");
  return new Promise(function(resolve) {
    var requestId = "fs-" + Date.now() + "-" + Math.random().toString(36).slice(2);
    window.__tgFamilySwitchResolvers[requestId] = resolve;
    handler.postMessage({requestId: requestId, appId: appId});
  });
};
</script>
<script>
(() => {
  const more = document.getElementById("headerMore");
  if (!more) return;
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && more.open) {
      more.open = false;
      const summary = more.querySelector("summary");
      if (summary) summary.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (more.open && !more.contains(event.target)) more.open = false;
  });
})();
</script>
<script type="module">
import {mountProductHeader} from "/static/np/networkpunkt-product-header.js";
mountProductHeader(document.querySelector("[data-product-header]"), {selfId:"tollgate", locale:document.documentElement.lang,
  openTarget: (appId) => window.__tgFamilySwitch(appId),
  readSelf:async ({signal}) => {
    const r = await fetch("/v1/health", {signal, cache:"no-store"});
    if (!r.ok) return {state:"error"};
    const h = await r.json();
    return {state:h.ok ? "confirmed" : "error", version:h.version};
  }});
</script>
</body>
</html>
"""


_MARKER = re.compile(r"\{\{([\w.]+)\}\}")

# Diese Marken setzt dashboard_html() selbst zusammen; sie stehen nicht im
# Katalog. Die Liste steht hier und nicht im Test, damit sie nur an einer
# Stelle gepflegt wird.
COMPOSED_MARKERS = frozenset(
    {
        "ui.html_lang",
        "ui.lang_label",
        "ui.lang_de_class",
        "ui.lang_en_class",
        "ui.lang_de_href",
        "ui.lang_en_href",
        "ui.register_label",
        "ui.register_plain_class",
        "ui.register_expert_class",
        "ui.register_plain_href",
        "ui.register_expert_href",
    }
)


def dashboard_html(
    language: str = i18n.DEFAULT_LANGUAGE, register: str = i18n.DEFAULT_REGISTER
) -> str:
    """Das Control Room in einer Sprache und auf einer Sprachebene.

    Die Marken werden hier ersetzt, nicht im Browser. Damit steht der Text
    schon im ausgelieferten HTML — er ist ohne JavaScript lesbar und
    Suchmaschinen sehen ihn.
    """
    code = i18n.normalise(language)
    level = i18n.normalise_register(register)
    # Jeder Schalter traegt die Wahl des anderen mit, sonst wirft ein Klick
    # auf EN die Sprachebene weg und umgekehrt.
    extra = {
        "ui.html_lang": code,
        "ui.lang_label": i18n.translate("ui.lang_label_text", code, level),
        "ui.lang_de_class": "on" if code == "de" else "",
        "ui.lang_en_class": "on" if code == "en" else "",
        "ui.lang_de_href": f"?lang=de&amp;mode={level}",
        "ui.lang_en_href": f"?lang=en&amp;mode={level}",
        "ui.register_label": i18n.translate("ui.register_label_text", code, level),
        "ui.register_plain_class": "on" if level == i18n.PLAIN else "",
        "ui.register_expert_class": "on" if level == i18n.EXPERT else "",
        "ui.register_plain_href": f"?mode={i18n.PLAIN}&amp;lang={code}",
        "ui.register_expert_href": f"?mode={i18n.EXPERT}&amp;lang={code}",
    }

    def pick(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in extra:
            return extra[key]
        return i18n.translate(key, code, level)

    return _MARKER.sub(pick, _TEMPLATE).replace(
        "__NP_CSS__",
        files("tollgate")
        .joinpath("static/np/networkpunkt.css")
        .read_text(encoding="utf-8"),
    )
