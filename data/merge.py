import json, re, sys, os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawl")
HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
files = ["v2_conferences.json", "v2_ticketing.json", "v2_luma_meetup.json", "v2_communities.json", "v2_aggregators.json", "events_luma_meetup.json", "events_ticketing.json", "events_conferences.json", "events_aggregators.json", "events_communities.json", "events_vendors.json"]
PLATS = {"Bengaluru2Go","Techsnap","Jamao","Kure-Cal","Luma","Meetup","Eventbrite","Konfhub","Townscript","Allevents","Devfolio","Unstop","HasGeek","Commudle","GDG Community","Official site","Other"}
DOMS = {"AI & ML","Cloud & DevOps","Data","Dev & Web","Security","Web3","Product & Design","Startups","Hardware & IoT","Enterprise"}

def clean_url(u):
    if not u or not re.match(r"^https?://", u): return None
    s = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(s.query) if not k.lower().startswith("utm_")]
    return urlunsplit((s.scheme, s.netloc, s.path, urlencode(q), ""))

def plat_from_url(u, p):
    h = urlsplit(u).netloc.lower()
    for k, v in [("lu.ma","Luma"),("luma.com","Luma"),("meetup.com","Meetup"),("eventbrite","Eventbrite"),("konfhub","Konfhub"),("townscript","Townscript"),("allevents","Allevents"),("devfolio","Devfolio"),("unstop","Unstop"),("hasgeek","HasGeek"),("commudle","Commudle"),("gdg.community.dev","GDG Community"),("techsnap","Techsnap"),("jamao","Jamao"),("kure-cal","Kure-Cal"),("bengaluru2go","Bengaluru2Go")]:
        if k in h: return v
    return p if p in PLATS else "Other"

def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"20[0-9][0-9]", "", t.lower()))[:18]

out, seen = [], {}
for f in files:
    p = os.path.join(D, f)
    if not os.path.exists(p):
        print("missing", f); continue
    try: data = json.load(open(p))
    except Exception as e: print("bad json", f, e); continue
    print(f, len(data))
    for e in data:
        if not isinstance(e, dict) or not e.get("title") or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date") or "")): continue
        u = clean_url(e.get("url"))
        if not u or "townscript" in u: continue
        if f.startswith("events_") and e.get("confidence") != "high": continue  # older crawl: keep only verified leftovers
        e["url"] = u
        e["platform"] = plat_from_url(u, e.get("platform"))
        if e.get("domain") not in DOMS: e["domain"] = "Dev & Web"
        if (e.get("endDate") or e["date"]) < "2026-11-18" or e["date"] > "2027-02-28": continue
        e = {k: e.get(k) for k in ["title","date","endDate","time","venue","area","organizer","platform","url","domain","tags","price","perks","audience","description","confidence","seenOn"]}
        e["tags"] = [str(t) for t in (e["tags"] or [])][:8]
        e["perks"] = [str(t) for t in (e["perks"] or [])][:6]
        k1 = urlsplit(u).netloc + urlsplit(u).path.rstrip("/")
        k2 = norm_title(e["title"]) + e["date"]
        prev = seen.get(k1) or seen.get(k2)
        if prev is not None:
            o = out[prev]
            for k, v in e.items():
                if not o.get(k) and v: o[k] = v
            if e.get("confidence") == "high": o["confidence"] = "high"
            continue
        seen[k1] = seen[k2] = len(out); out.append(e)
out.sort(key=lambda e: e["date"])
print("total", len(out))
from collections import Counter
print(Counter(e["domain"] for e in out)); print(Counter(e["platform"] for e in out))
html = open(HTML).read()
blob = json.dumps(out, ensure_ascii=False).replace("</", "<\\/")
src = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json")))["sources"]
sblob = json.dumps(src, ensure_ascii=False).replace("</", "<\\/")
html = re.sub(r"/\*SOURCES\*/.*?/\*ENDSOURCES\*/", lambda m: "/*SOURCES*/" + sblob + "/*ENDSOURCES*/", html, flags=re.S)
html = re.sub(r"/\*EVENTS\*/.*?/\*END\*/", lambda m: "/*EVENTS*/" + blob + "/*END*/", html, flags=re.S)
open(HTML, "w").write(html)
