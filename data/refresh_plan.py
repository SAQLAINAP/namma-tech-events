"""Plan an incremental refetch of event sources.

  python3 refresh_plan.py [--today YYYY-MM-DD] [--force]   list sources that are due, grouped by crawl slice
  python3 refresh_plan.py --mark SLICE [SLICE ...] [--today YYYY-MM-DD]
                                                         record that those slices were just crawled

A source is due when (today - lastFetched) >= its cadence (daily 1, weekly 7, fortnightly 14 days).
Sources fetched within their window are skipped unless --force is given.
"""
import json, sys, os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "sources.json")


def load():
    with open(PATH) as f:
        return json.load(f)


def age(src, today):
    return (today - date.fromisoformat(src["lastFetched"])).days


def main(argv):
    today = date.today()
    if "--today" in argv:
        today = date.fromisoformat(argv[argv.index("--today") + 1])
    reg = load()
    days = reg["cadenceDays"]

    if "--mark" in argv:
        i = argv.index("--mark") + 1
        slices = [a for a in argv[i:] if not a.startswith("--") and a != today.isoformat()]
        n = 0
        for s in reg["sources"]:
            if s["slice"] in slices:
                s["lastFetched"] = today.isoformat()
                n += 1
        with open(PATH, "w") as f:
            json.dump(reg, f, indent=1, ensure_ascii=False)
        print(f"marked {n} sources in {', '.join(slices)} as fetched {today}")
        return

    force = "--force" in argv
    due, fresh = {}, []
    for s in reg["sources"]:
        a = age(s, today)
        if force or a >= days[s["cadence"]]:
            due.setdefault(s["slice"], []).append((s, a))
        else:
            fresh.append((s, a))
    print(f"Refresh plan for {today}: {sum(len(v) for v in due.values())} due, {len(fresh)} still fresh")
    for sl, items in sorted(due.items()):
        print(f"\n[{sl}] {len(items)} due")
        for s, a in items:
            print(f"  - {s['name']} ({s['cadence']}, last {s['lastFetched']}, {a}d ago) {s['url']}")
    if fresh:
        print("\nSkipped (fetched within cadence): " + ", ".join(f"{s['name']} ({a}d)" for s, a in fresh))


if __name__ == "__main__":
    main(sys.argv[1:])
