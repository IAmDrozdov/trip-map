#!/usr/bin/env python3
"""Fetch a lightweight offline basemap (land, water, parks, main roads) for a bounding box from OpenStreetMap.

The page normally shows CARTO raster tiles. Some viewers block external images (e.g. a page published as a
Claude artifact); an embedded basemap keeps the map readable there. It is optional otherwise.

Usage:
  python3 scripts/fetch_basemap.py SOUTH WEST NORTH EAST -o basemap.json
  python3 scripts/fetch_basemap.py 55.645 12.49 55.725 12.65 -o basemap.json      # Copenhagen

Then: python3 scripts/build.py data.json --basemap basemap.json

Needs network access to overpass-api.de and the `shapely` package (pip install shapely).
Keep the box tight (roughly the area where the places are, ~10x10 km): the JSON is ~100 KB for a city centre.
"""
import argparse, json, sys, urllib.request, urllib.parse

OVERPASS = "https://overpass-api.de/api/interpreter"


def query(bbox):
    s, w, n, e = bbox
    b = f"({s},{w},{n},{e})"
    q = f"""[out:json][timeout:120];
(
  way["natural"="coastline"]{b};
  way["natural"="water"]{b};
  relation["natural"="water"]{b};
  way["leisure"="park"]{b};
  way["landuse"="cemetery"]{b};
  way["highway"~"^(motorway|trunk|primary|secondary)$"]{b};
);
out geom;"""
    req = urllib.request.Request(OVERPASS, data=("data=" + urllib.parse.quote(q)).encode(), headers={"User-Agent": "trip-map/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("south", type=float); ap.add_argument("west", type=float)
    ap.add_argument("north", type=float); ap.add_argument("east", type=float)
    ap.add_argument("-o", "--out", default="basemap.json")
    ap.add_argument("--eps", type=float, default=0.00006, help="simplification tolerance in degrees (default 0.00006 ≈ 5 m)")
    a = ap.parse_args()
    try:
        from shapely.geometry import LineString, Polygon, Point, box
        from shapely.ops import unary_union, polygonize
        from shapely.strtree import STRtree
    except ImportError:
        sys.exit("shapely is required: pip install shapely")

    bbox = (a.south, a.west, a.north, a.east)
    print("querying Overpass…", file=sys.stderr)
    data = query(bbox)
    B = box(a.west, a.south, a.east, a.north)  # x=lon, y=lat
    rnd = lambda pts: [[round(y, 4), round(x, 4)] for x, y in pts]  # -> [lat, lng]
    coast, water, parks, roads = [], [], [], []
    for el in data["elements"]:
        t = el.get("tags") or {}
        geoms = []
        if el["type"] == "way" and el.get("geometry"):
            geoms.append([(g["lon"], g["lat"]) for g in el["geometry"]])
        if el["type"] == "relation":
            for m in el.get("members") or []:
                if m.get("role") == "outer" and m.get("geometry"):
                    geoms.append([(g["lon"], g["lat"]) for g in m["geometry"]])
        for g in geoms:
            if len(g) < 2:
                continue
            if t.get("natural") == "coastline":
                coast.append(LineString(g))
            elif t.get("natural") == "water":
                if len(g) >= 4:
                    pg = Polygon(g).simplify(a.eps)
                    if pg.area > 2e-7 and pg.is_valid:
                        water.append(rnd(pg.exterior.coords))
            elif t.get("leisure") == "park" or t.get("landuse") == "cemetery":
                if len(g) >= 4:
                    pg = Polygon(g).simplify(a.eps)
                    if pg.area > 1.5e-6 and pg.is_valid:
                        parks.append(rnd(pg.exterior.coords))
            elif t.get("highway"):
                ln = LineString(g).simplify(a.eps * 1.5)
                roads.append({"k": 1 if t["highway"] in ("motorway", "trunk", "primary") else 2, "g": rnd(ln.coords)})

    # Land: polygonize coastline + bbox; OSM coastline has land on the LEFT. Vote per face, weighted by edge length.
    land_polys = []
    if coast:
        faces = [f for f in polygonize(unary_union(coast + [B.exterior])) if f.within(B.buffer(1e-9))]
        tree = STRtree(faces)
        votes = [[0.0, 0.0] for _ in faces]
        for ln in coast:
            cs = list(ln.coords)
            for i in range(len(cs) - 1):
                (x1, y1), (x2, y2) = cs[i], cs[i + 1]
                dx, dy = x2 - x1, y2 - y1
                L = (dx * dx + dy * dy) ** 0.5
                if L < 1e-7:
                    continue
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                for side, sg in ((0, 1), (1, -1)):  # 0 = left (land), 1 = right (water)
                    pt = Point(mx - sg * dy / L * 1e-5, my + sg * dx / L * 1e-5)
                    for k in tree.query(pt):
                        if faces[k].contains(pt):
                            votes[k][side] += L
        land = unary_union([f for f, v in zip(faces, votes) if v[0] >= v[1]]).simplify(a.eps / 2)
        polys = [land] if land.geom_type == "Polygon" else list(getattr(land, "geoms", []))
        for pg in polys:
            if pg.area < 2e-7:
                continue
            land_polys.append([rnd(pg.exterior.coords)] + [rnd(h.coords) for h in pg.interiors if Polygon(h).area > 2e-7])
    else:
        land_polys.append([rnd(B.exterior.coords)])  # inland city: everything is land, water comes from natural=water

    out = {"l": land_polys, "w": water, "p": parks, "r": roads}
    s = json.dumps(out, separators=(",", ":"))
    open(a.out, "w", encoding="utf-8").write(s)
    print(f"wrote {a.out}: land {len(land_polys)}, water {len(water)}, parks {len(parks)}, roads {len(roads)} ({len(s)//1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
