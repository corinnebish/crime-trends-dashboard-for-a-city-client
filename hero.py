"""Animated hero banner for the dashboard.

    from hero import render_hero
    render_hero(title="FIND THE NEXT EARTH", eyebrow="NASA data - machine learning",
                subtitle="Ranking every known planet by how Earth-like it is.",
                stats=[{"value": 5500, "label": "Planets analyzed"}, {"value": 12.4, "label": "Light-years", "decimals": 1}],
                motif="stars", palette={"accent": "#7dd3fc", "accent2": "#c084fc"})

motif: "stars" | "blobs" | "flow" | "grid" | "particles" | "none"
custom_js (optional): JavaScript that draws extra animation each frame. It can use the variables
    ctx (2D canvas context), w, h (size), t (seconds), P (the palette). Example, moving rails:
    "ctx.strokeStyle=P.accent; for(let i=0;i<8;i++){ctx.beginPath();ctx.moveTo(0,h*0.7+i*14);ctx.lineTo(w,h*0.7+i*14);ctx.stroke();}"
Everything runs inside the page. It loads only a Google font. People who prefer less motion see a still image.
"""
import json

import streamlit.components.v1 as components

import re

DARK = {"bg": "#070b18", "bg2": "#151c33", "text": "#ffffff", "muted": "#94a3b8",
        "accent": "#7dd3fc", "accent2": "#c084fc", "card": "rgba(255,255,255,.05)"}
LIGHT = {"bg": "#f6e9e0", "bg2": "#efe6f3", "text": "#151515", "muted": "#77716a",
         "accent": "#ff5a1f", "accent2": "#5b3fff", "card": "rgba(255,255,255,.7)"}

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600&family=Orbitron:wght@600;800&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
<style>
html,body{margin:0;height:100%;overflow:hidden;background:__BG__;font-family:__BODY__,system-ui,sans-serif}
canvas{position:absolute;inset:0;width:100%;height:100%}
.overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:space-between;
  padding:34px 16px 22px;text-align:center;pointer-events:none}
.eyebrow{color:__ACCENT__;letter-spacing:.35em;font-size:12px;text-transform:uppercase;opacity:0;animation:fade 1s .2s forwards}
h1{font-family:__TITLE__,sans-serif;font-weight:800;margin:10px 0 8px;font-size:clamp(30px,5.4vw,64px);letter-spacing:.05em;
  color:__TEXT__;text-shadow:__GLOW__;opacity:0;animation:fade 1.2s .4s forwards}
.sub{color:__MUTED2__;font-size:clamp(14px,1.6vw,18px);max-width:660px;margin:0 auto;opacity:0;animation:fade 1s .9s forwards}
.stats{display:flex;gap:clamp(12px,3vw,40px);flex-wrap:wrap;justify-content:center;opacity:0;animation:fade 1s 1.3s forwards}
.stat{min-width:120px;padding:12px 18px;border-radius:16px;background:__CARD__;border:1px solid __LINE__;backdrop-filter:blur(6px)}
.num{font-family:__TITLE__,sans-serif;font-size:clamp(20px,2.6vw,30px);background:linear-gradient(90deg,__ACCENT__,__ACCENT2__);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.lbl{color:__MUTED__;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin-top:2px}
.cue{color:__ACCENT__;font-size:13px;letter-spacing:.2em;margin-top:14px;animation:bounce 2s infinite}
@keyframes fade{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes bounce{0%,100%{transform:translateY(0);opacity:.6}50%{transform:translateY(6px);opacity:1}}
@media (prefers-reduced-motion:reduce){.eyebrow,h1,.sub,.stats{animation:none;opacity:1}.cue{animation:none}}
</style></head><body>
<canvas id="c"></canvas>
<div class="overlay"><div><div class="eyebrow" id="eyebrow"></div><h1 id="title"></h1><div class="sub" id="sub"></div></div>
<div><div class="stats" id="stats"></div><div class="cue" id="cue"></div></div></div>
<script>
const CFG = __CONFIG__;
const P = CFG.palette, still = matchMedia('(prefers-reduced-motion: reduce)').matches;
document.getElementById('eyebrow').textContent = CFG.eyebrow;
document.getElementById('title').textContent = CFG.title;
document.getElementById('sub').textContent = CFG.subtitle;
document.getElementById('cue').textContent = CFG.cue;
const box = document.getElementById('stats');
CFG.stats.forEach(s => {
  const d = document.createElement('div'); d.className = 'stat';
  const n = document.createElement('div'); n.className = 'num'; n.textContent = '0';
  const l = document.createElement('div'); l.className = 'lbl'; l.textContent = s.label;
  d.append(n, l); box.append(d);
  const dec = s.decimals || 0, to = Number(s.value), t0 = performance.now() + 1300;
  const fmt = v => (s.prefix || '') + v.toLocaleString(undefined, {minimumFractionDigits: dec, maximumFractionDigits: dec}) + (s.suffix || '');
  if (still) { n.textContent = fmt(to); return; }
  (function tick(now){ const k = Math.min(Math.max((now - t0) / 1800, 0), 1), e = 1 - Math.pow(1 - k, 3);
    n.textContent = fmt(to * e); if (k < 1) requestAnimationFrame(tick); })(performance.now());
});
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let w = 0, h = 0, dpr = Math.min(devicePixelRatio || 1, 2);
function size(){ w = cv.clientWidth; h = cv.clientHeight; cv.width = w * dpr; cv.height = h * dpr; ctx.setTransform(dpr,0,0,dpr,0,0); }
addEventListener('resize', size); size();
const rnd = (a, b) => a + Math.random() * (b - a);
const stars = Array.from({length: 220}, () => ({x: Math.random(), y: Math.random(), z: rnd(.2, 1), p: rnd(0, 6.28)}));
const blobs = [P.accent, P.accent2, P.accent, P.accent2].map((c, i) => ({c, x: rnd(.1, .9), y: rnd(.1, .9), r: rnd(.25, .45), s: rnd(.03, .07), a: rnd(0, 6.28)}));
const dots = Array.from({length: 70}, () => ({x: Math.random(), y: Math.random(), vx: rnd(-.0003, .0003), vy: rnd(-.0003, .0003)}));
const MOTIFS = {
  stars(t){ stars.forEach(s => { const a = .4 + .6 * Math.abs(Math.sin(t * s.z + s.p)); ctx.fillStyle = 'rgba(255,255,255,' + a * s.z + ')';
      ctx.beginPath(); ctx.arc(((s.x + t * .004 * s.z) % 1) * w, s.y * h, s.z * 1.4, 0, 6.28); ctx.fill(); }); },
  blobs(t){ blobs.forEach(b => { const x = (b.x + Math.sin(t * b.s + b.a) * .08) * w, y = (b.y + Math.cos(t * b.s + b.a) * .08) * h, r = b.r * Math.max(w, h);
      const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, b.c + 'aa'); g.addColorStop(1, b.c + '00'); ctx.fillStyle = g; ctx.fillRect(0, 0, w, h); }); },
  flow(t){ for (let i = 0; i < 9; i++){ ctx.beginPath(); ctx.lineWidth = 1.5; ctx.strokeStyle = (i % 2 ? P.accent : P.accent2) + '55';
      for (let x = 0; x <= w; x += 10){ const y = h * (.25 + i * .07) + Math.sin(x * .008 + t * (.5 + i * .08) + i) * (18 + i * 3); x ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); } },
  grid(t){ ctx.strokeStyle = P.accent + '33'; ctx.lineWidth = 1; const hz = h * .55;
      for (let i = -12; i <= 12; i++){ ctx.beginPath(); ctx.moveTo(w / 2 + i * 14, hz); ctx.lineTo(w / 2 + i * w * .12, h); ctx.stroke(); }
      for (let k = 0; k < 14; k++){ const f = ((k + (t * .4) % 1) / 14), y = hz + (h - hz) * f * f; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); } },
  particles(t){ dots.forEach(d => { d.x = (d.x + d.vx + 1) % 1; d.y = (d.y + d.vy + 1) % 1; });
      dots.forEach((a, i) => { ctx.fillStyle = P.accent + 'cc'; ctx.beginPath(); ctx.arc(a.x * w, a.y * h, 2, 0, 6.28); ctx.fill();
        for (let j = i + 1; j < dots.length; j++){ const b = dots[j], dx = (a.x - b.x) * w, dy = (a.y - b.y) * h, dist = Math.hypot(dx, dy);
          if (dist < 110){ ctx.strokeStyle = P.accent2 + Math.floor((1 - dist / 110) * 90).toString(16).padStart(2, '0'); ctx.beginPath(); ctx.moveTo(a.x * w, a.y * h); ctx.lineTo(b.x * w, b.y * h); ctx.stroke(); } } }); }
};
function frame(now){
  const t = now / 1000; ctx.clearRect(0, 0, w, h);
  const bg = ctx.createLinearGradient(0, 0, 0, h); bg.addColorStop(0, P.bg); bg.addColorStop(1, P.bg2); ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h);
  if (MOTIFS[CFG.motif]) MOTIFS[CFG.motif](t);
  try { new Function('ctx', 'w', 'h', 't', 'P', CFG.custom_js)(ctx, w, h, t, P); } catch (e) {}
  if (!still) requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script></body></html>"""


def _hex(value, default):
    """Colors must be #rrggbb so transparent variants can be made from them."""
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else default


def build_hero_html(title, subtitle="", eyebrow="", stats=None, motif="stars", palette=None, dark=True,
                    title_font="Orbitron", body_font="Space Grotesk", custom_js="", cue="SCROLL TO EXPLORE"):
    """The banner as one self-contained HTML page (a string)."""
    base = DARK if dark else LIGHT
    p = dict(base)
    for key, value in (palette or {}).items():
        if key in ("card",):
            p[key] = value
        elif key in base:
            p[key] = _hex(value, base[key])
    glow = f"0 0 18px {p['accent']}88, 0 0 42px {p['accent2']}55" if dark else "none"
    config = {"title": title, "subtitle": subtitle, "eyebrow": eyebrow, "stats": stats or [], "motif": motif,
              "palette": p, "custom_js": custom_js, "cue": f"▼ {cue} ▼" if cue else ""}
    page = (_PAGE.replace("__CONFIG__", json.dumps(config).replace("</", "<\\/"))
            .replace("__BG__", p["bg"]).replace("__TEXT__", p["text"]).replace("__MUTED__", p["muted"])
            .replace("__MUTED2__", p["text"] + "cc")
            .replace("__ACCENT__", p["accent"]).replace("__ACCENT2__", p["accent2"]).replace("__CARD__", p["card"])
            .replace("__LINE__", p["accent"] + "40").replace("__GLOW__", glow)
            .replace("__TITLE__", f"'{_font(title_font)}'").replace("__BODY__", f"'{_font(body_font)}'"))
    return page


def _font(name):
    """A font name is letters, digits and spaces only (it ends up inside CSS)."""
    return re.sub(r"[^A-Za-z0-9 ]", "", str(name))[:40] or "sans-serif"


def render_hero(title, subtitle="", eyebrow="", stats=None, motif="stars", palette=None, height=520,
                dark=True, title_font="Orbitron", body_font="Space Grotesk", custom_js="",
                cue="SCROLL TO EXPLORE"):
    """Show the animated banner. `stats` is a list of {"value": 123, "label": "..."} (optional decimals, prefix, suffix)."""
    components.html(build_hero_html(title, subtitle, eyebrow, stats, motif, palette, dark, title_font,
                                    body_font, custom_js, cue), height=height)
