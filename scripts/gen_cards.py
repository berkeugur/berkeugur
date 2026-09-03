#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub API'den veri cekip profil README'si icin animasyonlu SVG kart uretir.

Ucuncu parti kart servislerine (github-readme-stats vb.) bagimli olmamak icin var:
o servisler sik sik rate limit'e giriyor ya da tamamen kapaniyor.

Kullanim:  GH_TOKEN=... python3 scripts/gen_cards.py <kullanici-adi>
Cikti:     assets/stats-{dark,light}.svg, assets/langs-{dark,light}.svg
Bagimlilik yok — sadece standart kutuphane.
"""
import json
import os
import subprocess
import sys

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 12, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

DARK = {
    "bg": "#0B0906", "panel": "#12100B", "bar": "#191509", "border": "#4A3A14",
    "shadow": "#000000", "amber": "#FFB000", "amberd": "#C98A0E",
    "text": "#EDE6D8", "muted": "#9E9486", "track": "#241C0C",
}
LIGHT = {
    "bg": "#EDE6D8", "panel": "#F6F1E6", "bar": "#E4DBC9", "border": "#1A1712",
    "shadow": "#1A1712", "amber": "#B4520A", "amberd": "#8A4208",
    "text": "#1A1712", "muted": "#6B6255", "track": "#DDD3BE",
}

CSS = """
    .mono { font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
    .fade { opacity: 0; animation: fade .55s ease-out forwards; }
    @keyframes fade { to { opacity: 1; } }
    @media (prefers-reduced-motion: reduce) { .fade { opacity: 1; animation: none; } }
"""


def gql(login, token):
    """GraphQL sorgusunu curl ile calistirir.

    urllib yerine curl: sistem sertifika deposunu kullaniyor, boylece hem
    GitHub runner'inda hem de CA paketi kurulu olmayan yerel Python'larda calisiyor.
    Token argv'ye degil stdin'e gidiyor ki surec listesinde gorunmesin."""
    payload = json.dumps({"query": QUERY, "variables": {"login": login}})
    proc = subprocess.run(
        ["curl", "-sS", "--fail-with-body", "-X", "POST",
         "-H", "@-", "-H", "Content-Type: application/json",
         "-H", "User-Agent: berkeugur-profile-cards",
         "--data-binary", payload, "https://api.github.com/graphql"],
        input="Authorization: bearer " + token, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise SystemExit(f"curl hatasi ({proc.returncode}): {proc.stderr.strip()[:300]}")
    body = json.loads(proc.stdout)
    if "errors" in body:
        raise SystemExit("GraphQL hatasi: " + json.dumps(body["errors"], ensure_ascii=False))
    return body["data"]["user"]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def group(n):
    return f"{n:,}".replace(",", ".")


def stats_svg(u, p):
    c = u["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    rows = [
        ("Katki (12 ay)", group(c["contributionCalendar"]["totalContributions"])),
        ("Commit", group(c["totalCommitContributions"])),
        ("Pull request", group(c["totalPullRequestContributions"])),
        ("Issue", group(c["totalIssueContributions"])),
        ("Ozel depo katkisi", group(c["restrictedContributionsCount"])),
        ("Yildiz", group(stars)),
        ("Acik depo", group(u["repositories"]["totalCount"])),
        ("Takipci", group(u["followers"]["totalCount"])),
    ]
    # Turkce etiketler (kaynakta ascii tutuldu, ciktida dogru harfler)
    rows[0] = ("Katkı (12 ay)", rows[0][1])
    rows[4] = ("Özel depo katkısı", rows[4][1])
    rows[5] = ("Yıldız", rows[5][1])
    rows[6] = ("Açık depo", rows[6][1])
    rows[7] = ("Takipçi", rows[7][1])
    rows = [r for r in rows if r[1] != "0"]

    h = 44 + len(rows) * 26 + 14
    body = []
    for i, (label, val) in enumerate(rows):
        y = 58 + i * 26
        d = 0.25 + i * 0.09
        body.append(
            f'<g class="fade" style="animation-delay:{d:.2f}s">'
            f'<rect x="20" y="{y - 9}" width="6" height="6" fill="{p["amber"]}" opacity=".8"/>'
            f'<text class="mono" x="38" y="{y}" font-size="13" fill="{p["muted"]}">{esc(label)}</text>'
            f'<text class="mono" x="470" y="{y}" font-size="13.5" font-weight="700" '
            f'fill="{p["text"]}" text-anchor="end">{esc(val)}</text>'
            f'<line x1="38" y1="{y + 7}" x2="470" y2="{y + 7}" stroke="{p["border"]}" '
            f'stroke-width="1" opacity=".45"/></g>'
        )
    return panel(490, h, "İSTATİSTİK", "02", "\n    ".join(body), p)


def langs_svg(u, p):
    tot = {}
    meta = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            tot[n] = tot.get(n, 0) + e["size"]
            meta[n] = e["node"]["color"] or p["amber"]
    top = sorted(tot.items(), key=lambda kv: -kv[1])[:7]
    s = sum(v for _, v in top) or 1

    BAR_X, BAR_W, BAR_Y = 20, 450, 60
    segs, legend, x = [], [], float(BAR_X)
    for i, (name, size) in enumerate(top):
        w = BAR_W * size / s
        segs.append(
            f'<rect x="{x:.1f}" y="{BAR_Y}" width="{w:.1f}" height="14" fill="{meta[name]}">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" dur=".7s" '
            f'begin="{0.2 + i * 0.1:.2f}s" fill="freeze"/></rect>'
        )
        x += w
        col, row = i % 2, i // 2
        lx, ly = 20 + col * 232, 104 + row * 24
        segs.append("")
        legend.append(
            f'<g class="fade" style="animation-delay:{0.5 + i * 0.07:.2f}s">'
            f'<rect x="{lx}" y="{ly - 9}" width="9" height="9" fill="{meta[name]}"/>'
            f'<text class="mono" x="{lx + 16}" y="{ly}" font-size="12.5" fill="{p["text"]}">{esc(name)}</text>'
            f'<text class="mono" x="{lx + 210}" y="{ly}" font-size="12" fill="{p["muted"]}" '
            f'text-anchor="end">{size * 100.0 / s:.1f}%</text></g>'
        )
    h = 104 + ((len(top) + 1) // 2) * 24 + 16
    inner = (
        f'<rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="14" fill="{p["track"]}"/>\n    '
        + "\n    ".join(x for x in segs if x)
        + f'\n    <rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="14" fill="none" '
        f'stroke="{p["border"]}" stroke-width="1"/>\n    '
        + "\n    ".join(legend)
    )
    return panel(490, h, "DİLLER", "03", inner, p)


def panel(w, h, title, num, inner, p):
    W, H = w + 10, h + 10
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(title)}">
  <title>{esc(title)}</title>
  <defs><style>{CSS}</style></defs>
  <rect width="{W}" height="{H}" fill="{p["bg"]}"/>
  <rect x="6" y="6" width="{w}" height="{h}" fill="{p["shadow"]}"/>
  <rect x="2" y="2" width="{w}" height="{h}" fill="{p["panel"]}" stroke="{p["border"]}" stroke-width="1.25"/>
  <rect x="2" y="2" width="{w}" height="28" fill="{p["bar"]}"/>
  <line x1="2" y1="30" x2="{w + 2}" y2="30" stroke="{p["border"]}" stroke-width="1.25"/>
  <rect x="20" y="12" width="8" height="8" fill="{p["amber"]}"/>
  <text class="mono" x="38" y="21" font-size="12" letter-spacing="2.4" fill="{p["amber"]}">{esc(title)}</text>
  <text class="mono" x="{w - 16}" y="21" font-size="12" letter-spacing="1.6" fill="{p["muted"]}" text-anchor="end">{esc(num)}</text>
    {inner}
</svg>
'''


def main():
    login = sys.argv[1] if len(sys.argv) > 1 else "berkeugur"
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN gerekli")
    u = gql(login, token)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    os.makedirs(out, exist_ok=True)
    for suffix, pal in (("dark", DARK), ("light", LIGHT)):
        for name, fn in (("stats", stats_svg), ("langs", langs_svg)):
            path = os.path.join(out, f"{name}-{suffix}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(u, pal))
            print("yazildi:", os.path.relpath(path), os.path.getsize(path), "B")


if __name__ == "__main__":
    main()
