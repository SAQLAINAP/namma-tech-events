"""Hunt for Bengaluru tech events that live only on company websites.

The idea is to look for the traces an event leaves behind:
  1. its URL         -> city / region / yyyymm tokens inside an /events/-like path
  2. its sitemap     -> companies list every event page in sitemap.xml, often with lastmod
  3. its page text   -> date + IST time + Bengaluru venue + "Register" button all on one page
  4. its siblings    -> a roadshow page for Mumbai/Singapore implies a Bengaluru twin
  5. search dorks    -> the same patterns, written as web-search queries

Usage:
  python3 -I data/hunt.py sitemap clickhouse.com rubrik.com   # scan sitemaps, then score candidate pages
  python3 -I data/hunt.py hub https://www.rubrik.com/community/h4r-events   # sites without a sitemap
  python3 -I data/hunt.py page <url> [<url>...]               # score pages
  python3 -I data/hunt.py siblings <url>                      # swap the city in an event URL, probe each twin
  python3 -I data/hunt.py dorks [Company ...]                 # print web-search queries
See data/HUNTING.md for the reasoning behind each pattern.
"""
import json, re, sys, gzip, html
from datetime import date
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) namma-tech-events hunter"}
TODAY = date.today()

# --- 1. URL fingerprints ---------------------------------------------------
CITY = r"(bengaluru|bangalore|blr|bengalore|bglr)"
# regional event series often carry a region code instead of (or next to) the city
REGION = r"(apj|apac|asean|india|in-?en|south-?asia)"
# path segments companies use for event pages
EVENT_PATH = (r"/(events?|event-detail|webinars?|community|user-?groups?|meetups?|roadshows?|summits?|"
              r"world-?tour|tour|huddles?|h4r-events|workshops?|bootcamps?|forums?|connect|live|days?|"
              r"roundtables?|dinners?|hackathons?|labs?|immersion-?days?|on-?tour|road-?to)[/-]")
# 202611, 2026-11, 2026/11, nov-2026, dec26, 26nov ...
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
SLUG_DATE = rf"(20\d\d[-_/]?(0[1-9]|1[0-2])|({MONTHS})[-_]?(20)?\d\d|\d\d?[-_]?({MONTHS}))"

RX_CITY = re.compile(CITY, re.I)
RX_REGION = re.compile(rf"(^|[/_-]){REGION}([/_-]|$)", re.I)
RX_EVENT = re.compile(EVENT_PATH, re.I)
RX_SLUGDATE = re.compile(SLUG_DATE, re.I)


def url_score(u):
    """How likely a URL is a Bengaluru event page (0-6), from the URL alone."""
    p = urlsplit(u).path.lower()
    s = 0
    if RX_CITY.search(p): s += 3
    if RX_EVENT.search(p + "/"): s += 1
    if RX_REGION.search(p): s += 1
    if RX_SLUGDATE.search(p): s += 1
    return s


# --- 3. Page-text fingerprints ---------------------------------------------
# Real Bengaluru venues: an event page often names the venue but not the city.
VENUES = (r"aloft|cessna business park|embassy (golf links|tech village|manyata)|manyata|bagmane|rmz ecospace|"
          r"ecoworld|prestige tech park|sheraton grand|brigade gateway|itc gardenia|itc windsor|taj (mg road|west end|yeshwantpur)|"
          r"jw marriott|conrad|hilton|radisson blu|shangri-la|the leela|lalit ashok|vivanta|novotel|courtyard|hyatt|"
          r"biec|ktpo|nimhans convention|bangalore international centre|iisc|wework|91springboard|cowrks|bhive|"
          r"koramangala|indiranagar|hsr layout|whitefield|outer ring road|\bORR\b|bellandur|marathahalli|domlur|"
          r"electronic city|hebbal|mg road|ulsoor|halasuru|yeshwanthpur|kadubeesanahalli|sarjapur")
RX_VENUE = re.compile(VENUES, re.I)
RX_DATE = re.compile(rf"\b(\d{{1,2}}(st|nd|rd|th)?\s+({MONTHS})[a-z]*,?\s+20\d\d|({MONTHS})[a-z]*\.?\s+\d{{1,2}}(st|nd|rd|th)?,?\s+20\d\d|20\d\d-\d\d-\d\d)", re.I)
RX_TIME = re.compile(r"\b\d{1,2}(:\d\d)?\s?(am|pm)\b|\b\d{1,2}:\d\d\b", re.I)
RX_IST = re.compile(r"\bIST\b|GMT\s?\+\s?5:30|UTC\s?\+\s?5:30|\+05:30|Asia/Kolkata", re.I)
RX_CTA = re.compile(r"register( now| here)?|save (your|my) (seat|spot)|rsvp|request (an )?invite|book (your|a) (seat|spot)|reserve (your|a) (seat|spot)|sign up|get tickets", re.I)
RX_INPERSON = re.compile(r"in[- ]person|venue|agenda|networking|dinner|lunch|snacks|drinks|hands[- ]on", re.I)
RX_ONLINE = re.compile(r"\b(webinar|virtual|online event|zoom|livestream only|on-demand)\b", re.I)
RX_JSONLD = re.compile(r'"@type"\s*:\s*"(\w*Event)"', re.I)
RX_LOCALITY = re.compile(r'"addressLocality"\s*:\s*"(bengaluru|bangalore)', re.I)


# recordings, blogs and press pages mention cities and dates but are not upcoming events
RX_NOT_EVENT_PATH = re.compile(r"/(videos?|blog|resources|recordings?|on-?demand|press|news|case-stud|customers?|stories|podcasts?|careers?|jobs?)/", re.I)


def page_date(text):
    """First date on the page as a datetime.date, or None."""
    from datetime import datetime
    m = RX_DATE.search(text)
    if not m: return None
    t = re.sub(r"(st|nd|rd|th)\b", "", m.group(0)).replace(",", " ").replace(".", " ")
    t = re.sub(r"\s+", " ", t).strip()
    for f in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y", "%Y-%m-%d"):
        try: return datetime.strptime(t.title() if f != "%Y-%m-%d" else t, f).date()
        except ValueError: pass
    try: return datetime.strptime(t[:3].title() + " " + " ".join(t.split()[1:]), "%b %d %Y").date()
    except ValueError: return None


def page_score(raw, url=""):
    """Score an HTML page. >=6 is almost always a real in-person Bengaluru event."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)))
    head = (_title(raw) or "") + " " + url + " " + " ".join(re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", raw))
    # the event's own block: the first ~1500 chars of visible text, where date + venue normally sit
    lead = text[:1500] if len(text) < 4000 else text[: len(text) // 2]
    hits = {
        "city": bool(RX_CITY.search(head)) or bool(RX_CITY.search(lead)),
        "venue": bool(RX_VENUE.search(lead)),
        "date": bool(RX_DATE.search(text)),
        "time": bool(RX_TIME.search(text)),
        "ist": bool(RX_IST.search(raw)),
        "cta": bool(RX_CTA.search(text)),
        "in_person": bool(RX_INPERSON.search(text)),
        "jsonld_event": bool(RX_JSONLD.search(raw)),
        "jsonld_blr": bool(RX_LOCALITY.search(raw)),
    }
    s = (3 * hits["city"] + 2 * hits["venue"] + hits["date"] + hits["time"] + hits["ist"] + hits["cta"]
         + hits["in_person"] + hits["jsonld_event"] + 2 * hits["jsonld_blr"])
    if RX_ONLINE.search(text) and not hits["venue"]: s -= 2
    if url and RX_NOT_EVENT_PATH.search(urlsplit(url).path): s -= 4
    d = page_date(text)
    if d and d < TODAY: s -= 4          # already happened
    return s, hits, d, _title(raw)


def _title(raw):
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    return html.unescape(m.group(1)).strip()[:120] if m else None


def fetch(u, limit=3_000_000):
    with urlopen(Request(u, headers=UA), timeout=20) as r:
        b = r.read(limit)
    if u.endswith(".gz") or b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    return b.decode("utf-8", "replace")


# --- 2. Sitemaps -------------------------------------------------------------
def sitemap_urls(domain, cap=60):
    """All <loc> URLs (with lastmod) reachable from a domain's sitemap(s)."""
    roots = []
    for base in (f"https://{domain}", f"https://www.{domain}"):
        try:
            roots += re.findall(r"(?im)^sitemap:\s*(\S+)", fetch(base + "/robots.txt"))
        except Exception:
            pass
        if roots: break
    roots = roots or [f"https://{domain}/sitemap.xml", f"https://www.{domain}/sitemap.xml"]
    seen, out, queue = set(), [], list(roots)
    while queue and len(seen) < cap:
        sm = queue.pop(0)
        if sm in seen: continue
        seen.add(sm)
        try:
            x = fetch(sm)
        except Exception:
            continue
        for block in re.findall(r"(?is)<(?:url|sitemap)>(.*?)</(?:url|sitemap)>", x):
            loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
            if not loc: continue
            loc = html.unescape(loc.group(1))
            mod = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
            if re.search(r"(?is)<sitemap>", f"<sitemap>{block}") and loc.endswith((".xml", ".xml.gz")) and "<url>" not in x[:2000]:
                # nested sitemap index: only follow children that may hold events
                if re.search(r"event|webinar|communit|page|post|sitemap\d*\.xml|sitemap-\d", loc, re.I) or len(queue) < 5:
                    queue.append(loc)
                continue
            out.append((loc, mod.group(1)[:10] if mod else None))
    return out


def cmd_sitemap(domains):
    for d in domains:
        urls = sitemap_urls(d)
        cands = sorted({u for u, _ in urls if not RX_NOT_EVENT_PATH.search(urlsplit(u).path)
                        and (url_score(u) >= 3 or (RX_EVENT.search(urlsplit(u).path + "/") and RX_REGION.search(u)))})
        print(f"\n## {d}: {len(urls)} sitemap URLs, {len(cands)} look like Bengaluru/India event pages")
        for u in cands[:40]:
            try:
                s, h, dt, t = page_score(fetch(u), u)
            except Exception as e:
                print(f"  ?  {u}  ({e.__class__.__name__})"); continue
            flag = "EVENT" if s >= 6 else "maybe" if s >= 4 else "no"
            print(f"  {flag:5} score={s:2} date={dt!s:10} {t!s:60.60} {u}")


def cmd_page(urls):
    for u in urls:
        s, h, dt, t = page_score(fetch(u), u)
        print(f"score={s} date={dt} title={t}\n  {', '.join(k for k, v in h.items() if v)}\n  {u}")


def cmd_hub(urls):
    """Crawl an events/community index page and score every event-looking link on it."""
    for hub in urls:
        try:
            raw = fetch(hub)
        except Exception as e:
            # some sites (e.g. rubrik.com) refuse scripted requests: open them in a real browser instead
            print(f"\n## {hub}: blocked ({getattr(e, 'code', e.__class__.__name__)}) - read it in the browser and run `page` on the links")
            continue
        host = urlsplit(hub).netloc
        links = {html.unescape(h) for h in re.findall(r'href="([^"#]+)"', raw)}
        links = {("https://" + host + l) if l.startswith("/") else l for l in links}
        base = urlsplit(hub).path.rstrip("/")
        links = sorted(l for l in links if urlsplit(l).netloc == host and urlsplit(l).path.startswith(base + "/")
                       and not RX_NOT_EVENT_PATH.search(urlsplit(l).path))
        print(f"\n## {hub}: {len(links)} child links")
        for u in links[:60]:
            try:
                s, h, dt, t = page_score(fetch(u), u)
            except Exception as e:
                print(f"  ?  {u}  ({e.__class__.__name__})"); continue
            flag = "EVENT" if s >= 6 else "maybe" if s >= 4 else "no"
            print(f"  {flag:5} score={s:2} date={dt!s:10} {t!s:60.60} {u}")


# --- 4. Sibling probing ------------------------------------------------------
OTHER_CITIES = r"(mumbai|delhi|new-delhi|gurgaon|gurugram|noida|hyderabad|chennai|pune|kolkata|singapore|sydney|melbourne|tokyo|jakarta|kuala-lumpur|dubai|london|bengaluru|bangalore)"


def cmd_siblings(urls):
    """Replace the city in an event URL with Bengaluru spellings and see which pages exist."""
    for u in urls:
        if not re.search(OTHER_CITIES, u, re.I):
            print(f"no city token in {u}"); continue
        for city in ("Bengaluru", "Bangalore", "bengaluru", "bangalore", "BLR"):
            v = re.sub(OTHER_CITIES, city, u, count=1, flags=re.I)
            if v == u: continue
            try:
                s, h, dt, t = page_score(fetch(v), v)
                print(f"  HIT score={s} date={dt} {v}")
            except Exception as e:
                print(f"  --  {getattr(e, 'code', e.__class__.__name__)}  {v}")


# --- 5. Search dorks ---------------------------------------------------------
def dorks(companies):
    y, nxt = TODAY.year, TODAY.year + 1
    mon = TODAY.strftime("%B")
    general = [
        f'inurl:events (inurl:bengaluru OR inurl:bangalore) {y}',
        f'(inurl:bengaluru OR inurl:bangalore) (inurl:user-group OR inurl:roadshow OR inurl:huddle OR inurl:world-tour OR inurl:summit) {y}',
        f'"Bengaluru" "Register now" "{mon} {y}" -site:luma.com -site:meetup.com -site:allevents.in',
        f'"Bangalore" ("user group" OR "huddle" OR "roadshow" OR "immersion day") "{y}" "register"',
        f'"GMT+5:30" "Register" "{y}" (Bengaluru OR Bangalore) -site:luma.com',
        f'("Aloft" OR "Sheraton Grand" OR "ITC Gardenia" OR "JW Marriott" OR "Conrad") Bengaluru "{y}" (workshop OR meetup OR summit) register',
        f'("Embassy Golf Links" OR "Manyata" OR "Bagmane" OR "RMZ Ecospace") "{y}" (meetup OR workshop) register',
        f'site:splashthat.com (Bengaluru OR Bangalore)',
        f'site:goldcast.io (Bengaluru OR Bangalore) {y}',
        f'site:bevy.com (Bengaluru OR Bangalore)',
        f'site:cvent.com (Bengaluru OR Bangalore) {y}',
        f'site:zuddl.com (Bengaluru OR Bangalore) {y}',
        f'site:linkedin.com/events (Bengaluru OR Bangalore) {y}',
        f'"APJ" OR "APAC" roadshow {y} (Bengaluru OR Bangalore OR Mumbai OR Singapore) register',
        f'"India" "{y}" "world tour" OR "roadshow" OR "on tour" Bengaluru',
        f'"Bengaluru" "{nxt}" (summit OR "user conference") register',
    ]
    per = []
    for c in companies:
        dom = c.lower().replace(" ", "") + ".com"
        per += [
            f'site:{dom} (Bengaluru OR Bangalore) (event OR meetup OR workshop OR "user group")',
            f'"{c}" (Bengaluru OR Bangalore) ("{mon} {y}" OR "{y}") (meetup OR workshop OR roadshow OR huddle OR "user group") register',
        ]
    return general + per


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "sitemap": cmd_sitemap(args)
    elif cmd == "page": cmd_page(args)
    elif cmd == "hub": cmd_hub(args)
    elif cmd == "siblings": cmd_siblings(args)
    elif cmd == "dorks": print("\n".join(dorks(args)))
    else: sys.exit(__doc__)
