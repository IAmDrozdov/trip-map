import base64, hashlib, json, pathlib, re, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "vendor"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

FONTS_CSS = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700"
             "&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap")
KEEP_SUBSETS = {"latin", "cyrillic"}

CDN_SCRIPTS = [
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.2/Sortable.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js",
]
OFFLINE_SCRIPTS = [
    CDN_SCRIPTS[0],
    "https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.js",
    "https://cdn.jsdelivr.net/npm/@maplibre/maplibre-gl-leaflet@0.1.4/dist/leaflet-maplibre-gl.js",
    "https://cdn.jsdelivr.net/npm/pmtiles@4.5.0/dist/pmtiles.js",
    "https://cdn.jsdelivr.net/npm/@protomaps/basemaps@5.7.2/dist/basemaps.js",
    CDN_SCRIPTS[1],
    CDN_SCRIPTS[2],
]
MAPLIBRE_CSS = "https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.css"

GLYPH_BASE = "https://protomaps.github.io/basemaps-assets/fonts/{stack}/{rng}.pbf"
GLYPH_STACKS = ["Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"]
GLYPH_RANGES = ["0-255", "256-511", "512-767", "1024-1279", "7680-7935", "8192-8447"]


def fetch_cached(url, ua=None, optional=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    ext = pathlib.Path(urllib.parse.urlparse(url).path).suffix[:8]
    path = CACHE / (hashlib.sha1((url + (ua or "")).encode()).hexdigest() + ext)
    if path.exists():
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": ua or "trip-map/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception:
        if optional:
            return None
        raise
    path.write_bytes(data)
    return data


def data_uri(data, mime):
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def safe_js(src):
    src = re.sub(r"^//# sourceMappingURL=.*$", "", src, flags=re.M)
    return src.replace("</script", "<\\/script")


def inline_fonts_css():
    css = fetch_cached(FONTS_CSS, ua=BROWSER_UA).decode("utf-8")
    blocks = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, re.S)
    out = []
    for subset, block in blocks:
        if subset not in KEEP_SUBSETS:
            continue
        def repl(m):
            font = fetch_cached(m.group(1), ua=BROWSER_UA)
            return f"url({data_uri(font, 'font/woff2')})"
        out.append(re.sub(r"url\((https://[^)]+)\)", repl, block))
    return "\n".join(out)


def vendor_head(offline):
    if not offline:
        return ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                f'<link rel="stylesheet" href="{FONTS_CSS}">')
    maplibre_css = fetch_cached(MAPLIBRE_CSS).decode("utf-8")
    return f"<style>\n{inline_fonts_css()}\n{maplibre_css}\n</style>"


def vendor_scripts(offline):
    if not offline:
        return "\n".join(f'<script src="{u}"></script>' for u in CDN_SCRIPTS)
    return "\n".join(f"<script>{safe_js(fetch_cached(u).decode('utf-8'))}</script>" for u in OFFLINE_SCRIPTS)


def glyph_bundle(extra_ranges=()):
    bundle = {}
    for stack in GLYPH_STACKS:
        for rng in list(GLYPH_RANGES) + list(extra_ranges):
            url = GLYPH_BASE.format(stack=urllib.parse.quote(stack), rng=rng)
            data = fetch_cached(url, optional=True)
            if data:
                bundle[f"{stack}/{rng}"] = base64.b64encode(data).decode()
    return bundle


def offline_assets_html(pmtiles_path, extra_ranges=()):
    parts = []
    if pmtiles_path:
        blob = base64.b64encode(pathlib.Path(pmtiles_path).read_bytes()).decode()
        parts.append(f'<script id="offline-map" type="text/plain">{blob}</script>')
        parts.append(f'<script id="offline-glyphs" type="application/json">{json.dumps(glyph_bundle(extra_ranges), separators=(",", ":"))}</script>')
    return "\n".join(parts)
