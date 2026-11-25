# Hunting events that aren't on Luma or Meetup

Some events never appear on Luma, Meetup or the Bengaluru listing sites. They live only on a company's own website, such as ClickHouse's "The Agentic Data Stack" (26 Nov 2026) or Rubrik's "Practitioner Huddle" (18 Dec 2026).

This note covers how to find them on purpose. Every event leaves traces; you look for the trace, not for the event.

`data/hunt.py` does most of this automatically.

## The working assumptions

1. **An office means events.** A software company with an engineering or sales office in Bengaluru runs events here, typically 2–6 a year. Any company with a Bengaluru R&D centre is worth checking.
2. **Events come in series.** Companies run named programmes in several cities: a roadshow, a world tour, a user group, a huddle. If the Mumbai, Singapore or Sydney stop exists, assume a Bengaluru stop exists or is coming.
3. **The season is predictable.** Quarter-end (Nov–Dec, Feb–Mar) and the weeks around big product launches are dense. The typical company meetup is a Thursday from 6 to 9 pm, at a hotel or the company's own office near ORR, Whitefield or Manyata.
4. **The page is built to sell seats.** A real event page has a date, a time in IST, a venue and a call to action, all close together near the top. Recordings, blogs and press releases mention cities and dates but lack the call to action and the future date.

## The traces, strongest first

### 1. The URL

Companies put the city, the region and the month straight into the address:

```
clickhouse.com/company/events/202611-APJ-Bengaluru-The-Agentic-Data-Stack
                       └ /events/  └ yyyymm └ region └ city
rubrik.com/community/h4r-events/risk-readiness-resilience-ai-age
                     └ programme hub ("Huddle for Resilience")
miro.com/events/miro-innovation-and-ai-workspace-roadshow-bangalore/
freshworks.com/partner-day-2026-bangalore/
```

Patterns (in `hunt.py`):

| Signal | Regex |
|---|---|
| City | `(bengaluru\|bangalore\|blr\|bengalore\|bglr)` |
| Region code | `(apj\|apac\|asean\|india\|south-?asia)` |
| Event-like path | `/(events?\|community\|user-?groups?\|meetups?\|roadshows?\|summits?\|world-?tour\|huddles?\|workshops?\|roundtables?\|immersion-?days?\|road-?to)[/-]` |
| Month in slug | `20\d\d[-_/]?(0[1-9]\|1[0-2])` (e.g. 202611) or `nov[-_]?26` |
| **Not** an event | `/(videos?\|blog\|resources\|recordings?\|on-demand\|press\|news\|case-stud\|careers)/` |

A URL with the city plus an event-like path is a near-certain hit.

### 2. The sitemap

Most company sites list every page in `sitemap.xml`; its location is in `robots.txt`. Scanning it with the URL patterns finds every city event at once, including ones not yet linked from the events page.

Result on clickhouse.com: 2,628 URLs became 11 candidates, which became the 2 real upcoming Bengaluru events. Those are the one you named and a 10 Dec one we'd never seen.

```bash
python3 -I data/hunt.py sitemap clickhouse.com
```

### 3. The page fingerprint

When the URL doesn't name the city (Rubrik's doesn't), the page text has to. The score adds up these signals:

| Signal | Points | What it matches |
|---|---|---|
| City in the title, URL, `<h1>` or opening text | 3 | not a "more events" sidebar |
| Bengaluru venue in the opening text | 2 | Aloft, Cessna Business Park, Manyata, Bagmane, Embassy Golf Links, Sheraton Grand, ITC Gardenia, Conrad, WeWork, Koramangala, ORR, Bellandur… |
| Date | 1 | `26 Nov 2026`, `Nov 26, 2026`, `2026-11-26` |
| Time | 1 | `6:00pm` |
| IST marker | 1 | `IST`, `GMT+5:30`, `+05:30`, `Asia/Kolkata` (often only in the page source) |
| Call to action | 1 | `Register now`, `Save your seat`, `RSVP`, `Request an invite` |
| In-person words | 1 | `agenda`, `venue`, `networking`, `dinner`, `hands-on` |
| Structured data `"@type":"Event"` | 1 | |
| Structured data `"addressLocality":"Bengaluru"` | 2 | |
| Online-only, with no venue | −2 | |
| Recording or blog path | −4 | |
| Date already passed | −4 | |

A score of 6 or more is an event; 4–5 means look by hand.

- **Venue names do a lot of the work.** Company pages often name only the hotel or office, and the hotel gives away the city.
- **The IST marker is the quiet giveaway.** ClickHouse's page says `6:00 PM GMT+5:30` and carries `Asia/Kolkata` in its source.

```bash
python3 -I data/hunt.py page <url>
python3 -I data/hunt.py hub <events-index-url>   # score every child link of an events page
```

### 4. Siblings

Take a known event in another city and swap in Bengaluru. ClickHouse's December observability workshop runs in Melbourne on 8 Dec, Sydney on 9 Dec and Bengaluru on 10 Dec, all under the same slug with only the city changed.

```bash
python3 -I data/hunt.py siblings https://clickhouse.com/company/events/202612-APJ-Sydney-Logs-Metrics-Traces-at-Scale
```

### 5. Programme names: the vocabulary

General searches like "Bangalore event December" drown in listing sites. What found Rubrik was its own programme name, "Practitioner Huddle" ("Huddle for Resilience", H4R).

Each company names its event series, and the name is the key to search on:

| Kind | Names to search with Bengaluru or Bangalore |
|---|---|
| Roadshows and tours | "World Tour", "Roadshow", "On Tour", "Road to …", "City Tour", "Summit India", "Forum India" |
| Community | "User Group", "Huddle", "Community Day", "Meetup", "Chapter", "Circle", "Champions" |
| Hands-on | "Immersion Day", "Workshop", "Bootcamp", "Hands-on Lab", "Build Day", "Jam" |
| Executive | "Executive Roundtable", "CXO Dinner", "CISO Forum", "Leadership Breakfast", "Data for Breakfast" |
| Partners | "Partner Day", "Partner Summit" |
| Known names | ClickHouse "Open House" · Rubrik "Huddle for Resilience" · Snowflake "Data for Breakfast", "World Tour" · Databricks "Data + AI World Tour" · AWS "Community Day", "Immersion Day" · Google "Cloud Summit", "DevFest" · Salesforce "World Tour", "Agentforce World Tour" · Freshworks "Partner Day" · Miro "AI Workspace Roadshow" · MongoDB ".local" · Elastic "ElasticON" · Confluent "Data in Motion Tour" · Microsoft "AI Tour" |

The search pattern is:

```
"<Company>" + ("<programme name>") + (Bengaluru OR Bangalore) + "<Month> <Year>"
```

### 6. Search queries ("dorks")

These are the patterns above written as search queries. `hunt.py dorks [Company…]` prints them for the current month. The most useful:

```
inurl:events (inurl:bengaluru OR inurl:bangalore) 2026
"GMT+5:30" "Register" "2026" (Bengaluru OR Bangalore) -site:luma.com
("Aloft" OR "Sheraton Grand" OR "ITC Gardenia" OR "Conrad") Bengaluru 2026 (workshop OR meetup) register
site:splashthat.com (Bengaluru OR Bangalore)
site:goldcast.io (Bengaluru OR Bangalore) 2026
site:bevy.com (Bengaluru OR Bangalore)
"<Company>" (Bengaluru OR Bangalore) ("huddle" OR "user group" OR "roadshow") 2026 register
```

The `-site:` exclusions remove Luma, Meetup and AllEvents, which we already crawl, so only the hidden events are left.

### 7. Hosted event platforms

When a company's own site doesn't hold the page, its sign-up usually sits on a hosted event platform:

- Splash (`*.splashthat.com`)
- Goldcast
- Bevy (`*.bevy.com`, `gdg.community.dev`, `usergroups.<co>.com`)
- Cvent, Zuddl, Bizzabo, Hubilo, RainFocus

These pages carry the same fingerprint, so search each with `site:` plus the city.

## What the first sweep showed (Nov 2026, ~100 companies)

The 6 data and AI events this sweep found came from these routes, in order of yield:

1. **Community chapter pages on Bevy.** The address pattern is `usergroups.<company>.com/<city>/` or `community.<company>.com/...` (Snowflake, Databricks, Tableau, UiPath, Adobe). Each chapter page has an "Upcoming events" block. Visit the Bengaluru or Bangalore chapter directly instead of searching.
2. **Searching an events page's HTML for the city.** Many events pages embed every event as JSON or `data-location=` attributes, even when the cards are drawn by JavaScript. One `curl … | grep -i bengaluru` found Cockroach Connect, and a Yugabyte listing that turned out to be part of another organiser's show.
3. **City search on the company's event finder, in a browser.** Microsoft Reactor (`developer.microsoft.com/reactor/?search=bengaluru`) and BrowserStack StackConnect only show events after JavaScript runs. Reactor holds hands-on Bengaluru workshops that appear nowhere else.
4. **Searching the series name with the city.** "ObservabilityCON on the Road Bengaluru" and "Intuit India AI Summit" were found this way; general searches were not.
5. **Sitemaps are better for learning URL patterns than for finding new events.** A new event page often isn't in the sitemap for days. ClickHouse is the exception: its sitemap updates promptly.

Searching the hosted platforms by name (`site:splashthat.com`, `site:goldcast.io`) found nothing this round.

Many companies (Databricks, Confluent, Elastic, Redis, GitLab, Cloudflare and others) had no Bengaluru event in the window; their last ones were earlier in 2026. That fits assumption 3: they hold one or two big city stops a year, so check them every fortnight rather than expecting a steady flow.

## What doesn't work, and how to handle it

- **Pages that need a real browser.** Some sites, like rubrik.com, block scripted requests. Read them in a browser, then score the event links with `hunt.py page`. Don't disguise the script as a browser.
- **Pages built in the browser.** JavaScript-rendered event hubs show nothing to a plain fetch. Use the browser, or look for the site's JSON or iCal feed.
- **Registration-only details.** Many pages hide the venue until you register ("exact address shown to approved guests"). Keep the event, but mark it "To confirm".
- **Invite-only dinners.** These have no public sign-up. Skip them unless they have a "Request an invite" form.

## Routine

1. **Fortnightly:** run `hunt.py sitemap` across the company list (`data/sources.json`, the vendor slice), plus `hunt.py hub` for companies without a sitemap.
2. **Monthly:** run `hunt.py dorks` with the current month through web search, and add any new company or programme name to the tables above.
3. **When a new event series appears anywhere in APAC:** run `hunt.py siblings` on it.
4. **Every hit:** add the company's events page to `data/sources.json` so the regular refresh covers it.
