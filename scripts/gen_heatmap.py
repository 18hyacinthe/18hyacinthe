#!/usr/bin/env python3
"""
gen_heatmap.py — Heatmap de contributions GitHub, temps réel, façon terminal (SVG).

Usage:
    python gen_heatmap.py <username> <svg_out> [--html fichier_local]

- Récupère le calendrier PUBLIC de contributions (aucun token requis) sur
    https://github.com/users/<username>/contributions
- Calcule le total, la série en cours, la série record, le meilleur jour.
- Rend un SVG stylé "fenêtre terminal" avec une vague d'apparition animée.

Conçu pour tourner en boucle via GitHub Actions (cron) : le SVG committé se
met à jour tout seul à chaque exécution.
"""
import sys, re, html, argparse, datetime, urllib.request

PALETTE = {0: "#151b23", 1: "#0e4429", 2: "#006d32", 3: "#26a641", 4: "#39d353"}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def fetch_html(username):
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (profile-heatmap-generator)",
        "Accept": "text/html",
        "X-Requested-With": "XMLHttpRequest",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def parse_days(doc):
    """Retourne une liste triée de dict {date, level, count}."""
    # tooltips : id de composant -> nombre de contributions
    counts = {}
    for m in re.finditer(r'<tool-tip[^>]*\bfor="(contribution-day-component-[\d-]+)"[^>]*>(.*?)</tool-tip>', doc, re.S):
        cid, txt = m.group(1), m.group(2)
        if txt.strip().lower().startswith("no contribution"):
            counts[cid] = 0
        else:
            nm = re.match(r'\s*([\d,]+)', txt)
            counts[cid] = int(nm.group(1).replace(",", "")) if nm else 0

    days = []
    for m in re.finditer(r'<td[^>]*\bclass="[^"]*ContributionCalendar-day[^"]*"[^>]*>', doc):
        tag = m.group(0)
        d = re.search(r'data-date="([\d-]+)"', tag)
        lv = re.search(r'data-level="(\d+)"', tag)
        cid = re.search(r'id="(contribution-day-component-[\d-]+)"', tag)
        if not d or not lv:
            continue
        date = datetime.date.fromisoformat(d.group(1))
        level = int(lv.group(1))
        count = counts.get(cid.group(1) if cid else "", None)
        if count is None:
            count = [0, 2, 6, 12, 22][min(level, 4)]  # repli approximatif
        days.append({"date": date, "level": level, "count": count})
    days.sort(key=lambda x: x["date"])
    return days

def compute_stats(days):
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"count": 0, "date": None}

    # série record (plus longue suite de jours consécutifs actifs)
    longest = cur = 0
    for d in days:
        if d["count"] > 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0

    # série en cours : on remonte depuis le dernier jour ; on tolère que le
    # tout dernier jour (aujourd'hui) soit encore vide.
    current = 0
    seq = list(days)
    if seq and seq[-1]["count"] == 0:
        seq = seq[:-1]
    for d in reversed(seq):
        if d["count"] > 0:
            current += 1
        else:
            break
    return {"total": total, "active": active, "best": best,
            "longest": longest, "current": current}

def render_svg(username, days, stats, out_path):
    if not days:
        raise SystemExit("Aucune donnée de contribution trouvée.")

    cell, gap = 11, 3
    step = cell + gap
    left = 34          # marge pour les libellés de jours
    top = 58           # barre de titre + libellés de mois
    pad_r, pad_b = 18, 46

    origin = days[0]["date"]
    # aligne l'origine sur le dimanche (colonne 0, ligne 0 = dimanche)
    origin -= datetime.timedelta(days=(origin.weekday() + 1) % 7)

    def pos(date):
        delta = (date - origin).days
        return delta // 7, delta % 7  # (col, row)

    max_col = max(pos(d["date"])[0] for d in days)
    width = left + (max_col + 1) * step + pad_r
    height = top + 7 * step + pad_b
    header_h = 30

    P = []
    P.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
    )
    P.append(
        '<style>@keyframes pop{0%{opacity:0;transform:translateY(-5px) scale(.4)}'
        '100%{opacity:1;transform:translateY(0) scale(1)}}'
        '.c{opacity:0;animation:pop .45s cubic-bezier(.2,.8,.2,1) both;transform-box:fill-box;transform-origin:center}'
        '@keyframes blink{0%,100%{opacity:.9}50%{opacity:.25}}</style>'
    )
    P.append(
        '<defs><linearGradient id="hbg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0d1420"/><stop offset="1" stop-color="#060a10"/></linearGradient>'
        '<linearGradient id="ln" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#39d353"/><stop offset="1" stop-color="#58a6ff"/></linearGradient></defs>'
    )
    P.append(f'<rect width="{width}" height="{height}" rx="12" fill="url(#hbg)"/>')
    P.append(f'<rect x="0.75" y="0.75" width="{width-1.5}" height="{height-1.5}" rx="12" '
             f'fill="none" stroke="url(#ln)" stroke-width="1.5" stroke-opacity="0.6"/>')
    # barre de titre
    P.append(f'<line x1="0" y1="{header_h}" x2="{width}" y2="{header_h}" stroke="#1f6feb" stroke-opacity="0.35"/>')
    P.append('<circle cx="22" cy="15" r="5.5" fill="#ff5f56"/>')
    P.append('<circle cx="40" cy="15" r="5.5" fill="#ffbd2e"/>')
    P.append('<circle cx="58" cy="15" r="5.5" fill="#27c93f"/>')
    P.append(f'<text x="{width/2:.0f}" y="19.5" fill="#7d8590" font-size="12.5" '
             f'text-anchor="middle">{html.escape(username)}@github: ~/contributions --live</text>')

    # libellés de mois (au premier jour de chaque mois qui ouvre une colonne)
    seen = set()
    for d in days:
        col, row = pos(d["date"])
        key = (d["date"].year, d["date"].month)
        if d["date"].day <= 7 and key not in seen:
            seen.add(key)
            x = left + col * step
            P.append(f'<text x="{x}" y="{top-8}" fill="#7d8590" font-size="10">{MONTHS[d["date"].month-1]}</text>')

    # libellés de jours
    for lbl, r in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = top + r * step + cell - 2
        P.append(f'<text x="6" y="{y}" fill="#7d8590" font-size="9">{lbl}</text>')

    # cellules avec vague d'apparition
    for d in days:
        col, row = pos(d["date"])
        x = left + col * step
        y = top + row * step
        fill = PALETTE.get(d["level"], PALETTE[0])
        delay = col * 0.026 + row * 0.010
        plural = "contribution" if d["count"] == 1 else "contributions"
        P.append(
            f'<rect class="c" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" '
            f'fill="{fill}" style="animation-delay:{delay:.3f}s">'
            f'<title>{d["date"].isoformat()} — {d["count"]} {plural}</title></rect>'
        )

    # pied de stats
    fy = height - 16
    best = stats["best"]
    best_txt = f'{best["count"]} le {best["date"].strftime("%d/%m")}' if best.get("date") else "—"
    footer = (
        f'<tspan fill="#39d353">\u25b6</tspan>'
        f'<tspan fill="#c9d1d9"> S\u00e9rie actuelle </tspan><tspan fill="#39d353" font-weight="bold">{stats["current"]} j</tspan>'
        f'<tspan fill="#30363d">   \u2502   </tspan>'
        f'<tspan fill="#c9d1d9">Record </tspan><tspan fill="#58a6ff" font-weight="bold">{stats["longest"]} j</tspan>'
        f'<tspan fill="#30363d">   \u2502   </tspan>'
        f'<tspan fill="#c9d1d9">\u03a3 </tspan><tspan fill="#f0f6fc" font-weight="bold">{stats["total"]:,}</tspan><tspan fill="#c9d1d9"> contributions</tspan>'
        f'<tspan fill="#30363d">   \u2502   </tspan>'
        f'<tspan fill="#c9d1d9">Meilleur jour </tspan><tspan fill="#ffbd2e" font-weight="bold">{best_txt}</tspan>'
    )
    P.append(f'<text x="{left}" y="{fy}" font-size="11.5">{footer}</text>')

    # petite légende "Less -> More" en bas à droite
    lx = width - pad_r - (5 * (cell) + 4 * 3) - 62
    P.append(f'<text x="{lx-6}" y="{fy}" fill="#7d8590" font-size="10" text-anchor="end">Moins</text>')
    for i in range(5):
        P.append(f'<rect x="{lx + i*(cell+2)}" y="{fy-9}" width="{cell-1}" height="{cell-1}" rx="2" fill="{PALETTE[i]}"/>')
    P.append(f'<text x="{lx + 5*(cell+2) + 2}" y="{fy}" fill="#7d8590" font-size="10">Plus</text>')

    P.append('</svg>')
    with open(out_path, "w") as f:
        f.write("".join(P))
    return width, height

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("username")
    ap.add_argument("svg_out")
    ap.add_argument("--html", help="fichier HTML local (test hors-ligne)")
    args = ap.parse_args()

    doc = open(args.html, encoding="utf-8").read() if args.html else fetch_html(args.username)
    days = parse_days(doc)
    stats = compute_stats(days)
    w, h = render_svg(args.username, days, stats, args.svg_out)
    print(f"Heatmap -> {args.svg_out} ({w}x{h}) | total={stats['total']:,} "
          f"actifs={stats['active']} série={stats['current']}j record={stats['longest']}j "
          f"meilleur={stats['best']['count']}")
