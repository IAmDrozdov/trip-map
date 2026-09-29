import base64, hashlib, io, json, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "photos"
UA = "trip-map/1.0 (https://github.com/iamdrozdov/trip-map; offline builder)"
WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
BAD_TITLE = re.compile(r"\b(map|plan|logo|coat of arms|diagram|flag|sign|locator|panorama of|route|poster|scheme|floor|seal)\b", re.I)
MIN_WIDTH = 800
MAX_PHOTOS = 3
THUMB_WIDTH = 640
OUT_HEIGHT = 300
OUT_MAX_WIDTH = 560
WEBP_QUALITY = 72


def http_get(url, retries=4):
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return b""


def api(base, **params):
    params.setdefault("format", "json")
    time.sleep(0.08)
    return json.loads(http_get(base + "?" + urllib.parse.urlencode(params)))


def norm_name(title):
    return re.sub(r"^File:", "", title).replace(" ", "_").lower()


def imageinfo(titles):
    if not titles:
        return []
    out = []
    for i in range(0, len(titles), 40):
        j = api(COMMONS, action="query", prop="imageinfo", iiprop="url|mime|size", iiurlwidth=THUMB_WIDTH,
                titles="|".join(titles[i:i + 40]))
        pages = sorted((j.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        for pg in pages:
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii or ii.get("mime") != "image/jpeg" or ii.get("width", 0) < MIN_WIDTH:
                continue
            if BAD_TITLE.search(pg["title"]):
                continue
            out.append({"name": norm_name(pg["title"]), "src": ii.get("thumburl") or ii["url"], "page": ii["descriptionurl"], "title": pg["title"]})
    return out


def wikipedia_pageimage(title):
    j = api(WIKI, action="query", prop="pageimages|pageprops", piprop="name", ppprop="wikibase_item", redirects=1, titles=title)
    pg = next(iter((j.get("query") or {}).get("pages", {}).values()), {})
    name = pg.get("pageimage")
    qid = (pg.get("pageprops") or {}).get("wikibase_item")
    return name, qid


def wikidata_files(qid):
    if not qid:
        return [], None
    j = api(WIKIDATA, action="wbgetentities", ids=qid, props="claims")
    claims = ((j.get("entities") or {}).get(qid) or {}).get("claims", {})
    def vals(prop):
        return [c["mainsnak"]["datavalue"]["value"] for c in claims.get(prop, []) if c.get("mainsnak", {}).get("datavalue")]
    return ["File:" + v for v in vals("P18")], (vals("P373") or [None])[0]


def category_files(category, limit=30):
    if not category:
        return []
    j = api(COMMONS, action="query", list="categorymembers", cmtitle="Category:" + category, cmtype="file", cmlimit=limit)
    return [m["title"] for m in (j.get("query") or {}).get("categorymembers", [])]


def geosearch(p, radius):
    j = api(COMMONS, action="query", generator="geosearch", ggscoord=f"{p['lat']}|{p['lng']}", ggsradius=min(radius, 10000),
            ggslimit=40, ggsnamespace=6, prop="coordinates", colimit=40)
    pages = sorted((j.get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 0))
    return [pg["title"] for pg in pages]


def name_overlap(title, place):
    words = {w for w in re.findall(r"\w{4,}", place["n"].lower())}
    return sum(1 for w in words if w in title.lower())


def pick_candidates(p, types):
    picked, seen = [], set()

    def add(items):
        for it in items:
            if it["name"] in seen or len(picked) >= MAX_PHOTOS:
                continue
            seen.add(it["name"])
            picked.append(it)

    for url in p.get("img") or []:
        add([{"name": url.lower(), "src": url, "page": url, "title": url}])
    if p.get("w") and len(picked) < MAX_PHOTOS:
        name, qid = wikipedia_pageimage(p["w"])
        if name:
            add(imageinfo(["File:" + name]))
        files, category = wikidata_files(qid)
        add(imageinfo(files))
        if len(picked) < MAX_PHOTOS:
            add(imageinfo(category_files(category)))
    if len(picked) < MAX_PHOTOS:
        rad = p.get("pr") or (types.get(p["t"]) or {}).get("pr") or 120
        for r in (rad, rad * 2.5):
            titles = geosearch(p, r)
            titles.sort(key=lambda t: -name_overlap(t, p))
            add(imageinfo(titles))
            if len(picked) >= MAX_PHOTOS:
                break
    return picked


def encode(data):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    scale = OUT_HEIGHT / h
    nw = min(int(w * scale), OUT_MAX_WIDTH)
    im = im.resize((int(w * scale), OUT_HEIGHT), Image.LANCZOS)
    if nw < im.size[0]:
        left = (im.size[0] - nw) // 2
        im = im.crop((left, 0, left + nw, OUT_HEIGHT))
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def cache_key(p):
    raw = json.dumps([p.get("w"), p.get("img"), p["lat"], p["lng"], p.get("pr"), p["t"]], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def photos_for(p, types):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{p['id']}.json"
    key = cache_key(p)
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("key") == key:
            return cached["ph"]
    out = []
    for c in pick_candidates(p, types):
        try:
            out.append({"src": encode(http_get(c["src"])), "page": c["page"]})
        except Exception as e:
            print(f"warn: {p['id']}: photo {c['title']} skipped ({e})", file=sys.stderr)
    path.write_text(json.dumps({"key": key, "ph": out}, ensure_ascii=False), encoding="utf-8")
    return out


def embed_photos(data):
    types = data.get("types") or {}
    places = data["places"]
    total = 0
    for i, p in enumerate(places, 1):
        try:
            p["ph"] = photos_for(p, types)
        except Exception as e:
            print(f"warn: {p['id']}: photo lookup failed ({e})", file=sys.stderr)
            p["ph"] = []
        total += len(p["ph"])
        print(f"photos {i}/{len(places)} {p['id']}: {len(p['ph'])}", file=sys.stderr)
    return total
