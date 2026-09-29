#!/usr/bin/env python3
"""Build a trip-map page: data.json + assets/planner.template.html -> one self-contained HTML file.

Usage:
  python3 scripts/build.py data.json                       # -> data.html next to data.json
  python3 scripts/build.py data.json -o out.html
  python3 scripts/build.py data.json --basemap basemap.json # embed an offline land/water/roads layer
  python3 scripts/build.py data.json --artifact -o page.html # body-only page for publishing as a Claude artifact
  python3 scripts/build.py data.json --offline --map city.pmtiles -o out.html  # zero network requests (needs pillow)
  python3 scripts/build.py data.json --check               # validate only, write nothing

Exit code 1 on validation errors (they are printed with the offending place id / preset name).
"""
import argparse, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "planner.template.html"
REQ_PLACE = ["id", "n", "a", "lat", "lng", "t", "d", "p", "s", "h", "x"]
MODES = {"walking", "transit", "bicycling", "driving"}


def validate(d):
    errors, warns = [], []
    meta = d.get("meta") or {}
    if not isinstance(meta, dict) or not meta.get("title"):
        errors.append("meta.title is required (page title, e.g. 'Lisbon, 3–5 May')")
    if not meta.get("city"):
        warns.append("meta.city is empty: Google Maps queries will not be scoped to a city; set it to the city name in the local language")
    max_stops = int(meta.get("maxStops") or 10)
    types = d.get("types") or {}
    if not isinstance(types, dict) or not types:
        errors.append("types must be a non-empty object {key: {l: label, c: '#hex'}}")
    else:
        for k, t in types.items():
            if not isinstance(t, dict) or not t.get("l") or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(t.get("c", ""))):
                errors.append(f"types.{k}: needs l (label) and c (#rrggbb colour)")
    prios = {str(k): v for k, v in (d.get("priorities") or {}).items()}
    if not prios:
        errors.append("priorities must be an object like {'1': 'Core', '2': 'Strong', '3': 'If nearby', '4': 'Probably skip'}")
    sources = d.get("sources") or {}
    if not sources:
        warns.append("sources is empty: the 'Источник' clustering will show '—'")
    places = d.get("places")
    if not isinstance(places, list) or not places:
        errors.append("places must be a non-empty list")
        return errors, warns, max_stops
    ids = {}
    no_pid, no_w, bases = 0, 0, 0
    for i, p in enumerate(places):
        tag = f"places[{i}] ({p.get('id', '?')})"
        for f in REQ_PLACE:
            if f not in p or p[f] in ("", None):
                errors.append(f"{tag}: missing '{f}'")
        pid = p.get("id")
        if pid in ids:
            errors.append(f"{tag}: duplicate id '{pid}'")
        ids[pid] = True
        try:
            if not (-90 <= float(p["lat"]) <= 90 and -180 <= float(p["lng"]) <= 180):
                errors.append(f"{tag}: lat/lng out of range")
        except Exception:
            errors.append(f"{tag}: lat/lng must be numbers")
        if p.get("t") not in types:
            errors.append(f"{tag}: type '{p.get('t')}' is not in types")
        if str(p.get("p")) not in prios:
            errors.append(f"{tag}: priority '{p.get('p')}' is not in priorities")
        if sources and p.get("s") not in sources:
            warns.append(f"{tag}: source '{p.get('s')}' is not in sources")
        bk = p.get("bk")
        if bk is not None:
            if not isinstance(bk, dict) or bk.get("k") not in ("t", "k") or not bk.get("l") or not str(bk.get("u", "")).startswith("http"):
                errors.append(f"{tag}: bk must be {{k: 't'|'k', l: button label, u: https://...}}")
        poly = p.get("poly")
        if poly is not None and not (isinstance(poly, list) and len(poly) >= 3 and all(isinstance(q, list) and len(q) == 2 for q in poly)):
            errors.append(f"{tag}: poly must be a list of [lat, lng] pairs (3+)")
        if not p.get("pid"):
            no_pid += 1
        if p.get("t") in ("sight", "museum", "area", "park", "gallery") and not p.get("w"):
            no_w += 1
        if p.get("base"):
            bases += 1
    if no_pid:
        warns.append(f"{no_pid} place(s) have no Google place_id (pid): Google Maps will match them by name+address text, which is less reliable")
    if no_w:
        warns.append(f"{no_w} landmark-type place(s) have no Wikipedia title (w): their card photo will be a nearby Commons photo instead of the landmark itself")
    if bases == 0:
        warns.append("no place has base: true (hotel / starting point). Add one so routes can start and end there")
    for j, pr in enumerate(d.get("presets") or []):
        tag = f"presets[{j}] ({pr.get('n', '?')})"
        if not pr.get("n") or not isinstance(pr.get("ids"), list) or not pr["ids"]:
            errors.append(f"{tag}: needs n (name) and a non-empty ids list")
            continue
        missing = [x for x in pr["ids"] if x not in ids]
        if missing:
            errors.append(f"{tag}: unknown place ids {missing}")
        if len(pr["ids"]) > max_stops:
            errors.append(f"{tag}: {len(pr['ids'])} stops, but the route limit is {max_stops} (Google Maps directions links take origin + 8 waypoints + destination)")
        if pr.get("m") and pr["m"] not in MODES:
            errors.append(f"{tag}: mode '{pr['m']}' must be one of {sorted(MODES)}")
    bm = d.get("basemap")
    if bm is not None and not (isinstance(bm, dict) and all(k in bm for k in ("l", "w", "p", "r"))):
        errors.append("basemap must have keys l, w, p, r (see scripts/fetch_basemap.py)")
    return errors, warns, max_stops


def to_artifact(html):
    """Strip the document wrapper so the page follows the Claude Artifact page contract
    (title first, no doctype/html/head/body; the platform adds its own skeleton)."""
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    title = m.group(0) if m else ""
    html = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>\s*", "", html, flags=re.I)
    html = re.sub(r'<meta charset="utf-8">\s*<meta name="viewport"[^>]*>\s*', "", html)
    html = html.replace(title, "", 1)
    html = html.replace("</head>\n<body>\n", "").replace("</body>\n</html>", "")
    return title + "\n" + html.lstrip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", help="data.json (see references/data-schema.md)")
    ap.add_argument("-o", "--out", help="output .html (default: <data>.html)")
    ap.add_argument("--basemap", help="basemap.json from scripts/fetch_basemap.py; embedded into the page")
    ap.add_argument("--artifact", action="store_true", help="emit a body-only page for publishing as a Claude artifact")
    ap.add_argument("--title", help="override the <title> (default: meta.title)")
    ap.add_argument("--check", action="store_true", help="validate only")
    ap.add_argument("--offline", action="store_true", help="inline libraries, fonts and photos: the page makes no network requests")
    ap.add_argument("--map", help="city.pmtiles from scripts/fetch_offline_map.py; embedded when --offline is set")
    ap.add_argument("--no-photos", action="store_true", help="with --offline: do not embed photos")
    a = ap.parse_args()

    src = pathlib.Path(a.data)
    d = json.loads(src.read_text(encoding="utf-8"))
    if a.basemap:
        d["basemap"] = json.loads(pathlib.Path(a.basemap).read_text(encoding="utf-8"))
    errors, warns, max_stops = validate(d)
    for w in warns:
        print("warn:", w)
    for e in errors:
        print("ERROR:", e)
    if errors:
        sys.exit(1)
    if a.check:
        print(f"ok: {len(d['places'])} places, {len(d.get('presets') or [])} presets, {len(d['types'])} types, route limit {max_stops}")
        return

    if a.artifact and a.offline:
        sys.exit("--artifact and --offline cannot be combined")
    if a.map and not a.offline:
        sys.exit("--map needs --offline")
    sizes = {}
    if a.offline:
        import offline_assets
        d.setdefault("meta", {})["offline"] = True
        if not a.map:
            print("warn: --offline without --map: the page will have no street map (only the optional basemap layer)")
        if not a.no_photos:
            import offline_photos
            n = offline_photos.embed_photos(d)
            sizes["photos"] = sum(len(f["src"]) for p in d["places"] for f in p.get("ph", []))
            print(f"embedded {n} photos")
        head = offline_assets.vendor_head(True)
        scripts = offline_assets.vendor_scripts(True)
        assets = offline_assets.offline_assets_html(a.map, d["meta"].get("glyphRanges") or ())
        sizes["js+fonts"] = len(head) + len(scripts)
        sizes["map"] = len(assets)
    else:
        import offline_assets
        head, scripts, assets = offline_assets.vendor_head(False), offline_assets.vendor_scripts(False), ""

    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("<!--VENDOR_HEAD-->", head).replace("<!--VENDOR_SCRIPTS-->", scripts).replace("<!--OFFLINE_ASSETS-->", assets)
    html = html.replace("<!--TRIP_DATA-->", payload).replace("{{TITLE}}", (a.title or d["meta"]["title"]).replace("<", "&lt;"))
    if a.artifact:
        html = to_artifact(html)
    out = pathlib.Path(a.out) if a.out else src.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB): {len(d['places'])} places, {len(d.get('presets') or [])} presets, "
          f"{'with' if d.get('basemap') else 'no'} basemap, {'artifact' if a.artifact else 'offline' if a.offline else 'standalone'} mode")
    if sizes:
        print("size breakdown: " + ", ".join(f"{k} {v / 1e6:.1f} MB" for k, v in sizes.items()))


if __name__ == "__main__":
    main()
