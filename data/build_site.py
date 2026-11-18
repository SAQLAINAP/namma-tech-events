"""Build the static GitHub Pages site in ../docs from the app source (../index.html).

The app source is written for the claude.ai artifact viewer, which supplies the
document shell. This wraps it in a full HTML document and copies the icons.
"""
import json, os, re, shutil
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs")
ASSETS = os.path.join(ROOT, "site-assets")
BASE = "https://saqlainap.github.io/namma-tech-events/"

src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
events = json.loads(re.search(r"/\*EVENTS\*/(.*?)/\*END\*/", src, re.S).group(1).replace("<\\/", "</"))
n = len(events)

# head-only pieces of the source move into <head>; everything after the stylesheet is the body
src = re.sub(r'<meta charset="utf-8">\s*', "", src)
src = re.sub(r"<title>.*?</title>\s*", "", src)
src = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\s*', "", src)
head_extra, body = src.split("</style>", 1)
head_extra += "</style>"

desc = f"{n} upcoming tech events in Bengaluru: browse by domain, registration platform, date and perks, with registration links for every event."
head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Namma Tech Events</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}">
<meta name="theme-color" content="#f5f5f2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#111111" media="(prefers-color-scheme: dark)">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="icon-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Namma Tech Events">
<meta property="og:title" content="Namma Tech Events">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{BASE}">
<meta property="og:image" content="{BASE}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Namma Tech Events">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{BASE}og.png">
<style>
:root{{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}
body{{margin:0;font:14px/1.4 system-ui,-apple-system,sans-serif}}
img{{max-width:100%}}
[hidden]{{display:none!important}}
</style>
"""

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(head + head_extra + "\n</head>\n<body>\n" + body.strip() + "\n</body>\n</html>\n")

for name in ["favicon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "og.png"]:
    shutil.copy(os.path.join(ASSETS, name), os.path.join(OUT, name))

json.dump({
    "name": "Namma Tech Events", "short_name": "Tech Events BLR",
    "description": desc, "start_url": "./", "scope": "./", "display": "standalone",
    "background_color": "#111111", "theme_color": "#e04a2f",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"},
    ],
}, open(os.path.join(OUT, "manifest.webmanifest"), "w"), indent=2)

open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")
open(os.path.join(OUT, "sitemap.xml"), "w").write(
    f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"  <url><loc>{BASE}</loc><lastmod>{date.today().isoformat()}</lastmod><changefreq>daily</changefreq></url>\n</urlset>\n")
open(os.path.join(OUT, ".nojekyll"), "w").write("")
open(os.path.join(OUT, "404.html"), "w", encoding="utf-8").write(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Page not found · Namma Tech Events</title><link rel="icon" href="{BASE}favicon.svg" type="image/svg+xml">
<style>:root{{--bg:#f5f5f2;--ink:#171717;--ink-2:#5b5b58;--accent:#e04a2f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--ink:#ececE8;--ink-2:#a9a9a4;--accent:#ff6b4f;color-scheme:dark}}}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,sans-serif;padding:24px}}
main{{max-width:420px;text-align:center}} h1{{font-size:28px;margin:16px 0 6px}} p{{color:var(--ink-2);margin:0 0 20px}}
a{{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;padding:10px 18px;border-radius:6px}}</style></head>
<body><main><img src="{BASE}favicon.svg" width="56" height="56" alt=""><h1>Page not found</h1><p>That link doesn't lead anywhere. The full event library is on the home page.</p><a href="{BASE}">Browse events</a></main></body></html>
""")
print(f"built docs/ with {n} events")
