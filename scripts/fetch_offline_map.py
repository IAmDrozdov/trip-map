#!/usr/bin/env python3
"""Extract an offline vector map (Protomaps PMTiles, OpenStreetMap data) for the places of a trip.

Usage:
  python3 scripts/fetch_offline_map.py data.json -o city.pmtiles
  python3 scripts/fetch_offline_map.py data.json -o city.pmtiles --pad-km 2 --maxzoom 15
  python3 scripts/fetch_offline_map.py --bbox 55.645 12.49 55.725 12.65 -o city.pmtiles

The region is the padded bounding box of all places that are not `far`, plus a padded box around every `far` place.
Needs the `pmtiles` CLI (brew install pmtiles) and network access to build.protomaps.com.
Then: python3 scripts/build.py data.json --offline --map city.pmtiles -o out.html
"""
import argparse, json, math, pathlib, shutil, subprocess, sys, tempfile, urllib.request

BUILDS = "https://build-metadata.protomaps.dev/builds.json"
BUILD_URL = "https://build.protomaps.com/{key}"


def latest_build_url():
    req = urllib.request.Request(BUILDS, headers={"User-Agent": "trip-map/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        builds = json.load(r)
    keys = sorted(b["key"] for b in builds if b["key"].endswith(".pmtiles"))
    if not keys:
        sys.exit("no Protomaps builds found")
    return BUILD_URL.format(key=keys[-1])


def padded_box(lat_min, lng_min, lat_max, lng_max, pad_km):
    dlat = pad_km / 111.0
    mid = math.radians((lat_min + lat_max) / 2)
    dlng = pad_km / (111.0 * max(math.cos(mid), 0.1))
    return [lng_min - dlng, lat_min - dlat, lng_max + dlng, lat_max + dlat]


def ring(box):
    w, s, e, n = box
    return [[w, s], [e, s], [e, n], [w, n], [w, s]]


def region_from_places(places, pad_km):
    near = [p for p in places if not p.get("far")] or places
    far = [p for p in places if p.get("far") and p not in near]
    boxes = [padded_box(min(p["lat"] for p in near), min(p["lng"] for p in near),
                        max(p["lat"] for p in near), max(p["lng"] for p in near), pad_km)]
    boxes += [padded_box(p["lat"], p["lng"], p["lat"], p["lng"], pad_km) for p in far]
    return {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": [[ring(b)] for b in boxes]}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?", help="data.json")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"))
    ap.add_argument("-o", "--out", default="city.pmtiles")
    ap.add_argument("--pad-km", type=float, default=1.5)
    ap.add_argument("--maxzoom", type=int, default=15)
    ap.add_argument("--source", help="pmtiles archive URL or path (default: latest Protomaps daily build)")
    a = ap.parse_args()

    if not shutil.which("pmtiles"):
        sys.exit("the pmtiles CLI is required: brew install pmtiles (or https://github.com/protomaps/go-pmtiles/releases)")
    if a.bbox:
        s, w, n, e = a.bbox
        region = {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": [[ring([w, s, e, n])]]}}
    elif a.data:
        region = region_from_places(json.loads(pathlib.Path(a.data).read_text(encoding="utf-8"))["places"], a.pad_km)
    else:
        sys.exit("give data.json or --bbox")

    source = a.source or latest_build_url()
    print(f"source: {source}", file=sys.stderr)
    with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as f:
        json.dump(region, f)
        region_path = f.name
    try:
        subprocess.run(["pmtiles", "extract", source, a.out, f"--region={region_path}", f"--maxzoom={a.maxzoom}"], check=True)
    finally:
        pathlib.Path(region_path).unlink(missing_ok=True)
    print(f"wrote {a.out} ({pathlib.Path(a.out).stat().st_size / 1e6:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
