---
name: trip-map
description: Build an interactive, phone-friendly HTML map for a city trip from a list of candidate places — clustered by district/type/priority/source, with tap cards (photos, hours, what's on, booking links) and a drag-and-drop route of up to 10 stops that becomes a Google Maps walking link shareable to Telegram. Use it whenever someone plans a trip, weekend or day out in a city and wants places visualised, grouped or turned into routes — including "make a map of these places", "куда сходить в X", "собери маршрут", "визуализируй места", or a dump of friends' recommendations / Google Maps links. The agent researches the places and fills data.json; the page itself is a fixed template.
---

# trip-map

One HTML file, no backend: Leaflet map + sidebar of places grouped into clusters + route panel.
All trip content lives in `data.json`; `assets/planner.template.html` never changes per trip.
UI language is Russian (the audience is Russian-speaking); write data in the user's language.

```
trip-map/
├── SKILL.md
├── assets/planner.template.html   # the page (Leaflet, Sortable, qrcode from cdnjs; Leaflet CSS inlined)
├── scripts/build.py               # data.json (+ basemap) -> html; validates the schema
├── scripts/fetch_basemap.py       # optional offline land/water/roads layer from OSM (Overpass + shapely)
├── scripts/check.mjs              # optional Playwright smoke test (desktop + iPhone screenshots)
├── references/data-schema.md      # every field of data.json, with examples
├── references/research.md         # how to gather places: coords, place_id, hours, photos, what's on, bookings
└── examples/copenhagen/           # a real trip: data.json (91 places, 14 types, 9 presets) + basemap.json
```

## Workflow

1. **Understand the trip.** Dates, base (hotel/apartment — it becomes the start/end of routes), who is going,
   what they care about (walking, food, art, saunas…), what they do not (shopping, bars…). If the user has
   a handoff/knowledge base or a friends' list, treat it as candidates, not requirements.
2. **Research the places** (see `references/research.md`). For each candidate you need coordinates, an address,
   a Google `place_id`, opening hours *for the trip's days*, a 1–3 sentence note, and a priority. Verify
   time-sensitive things (closed days, seasonal closures, exhibitions ending, booking pages) — stale facts
   are the most common way these maps go wrong. Look for what is on in the city on those dates (exhibitions,
   season openings) and for niche spots beyond the friends' list; add them with their own source key.
3. **Design the categories for this trip.** `types` (colour-coded, e.g. sight / area / bakery / sauna / museum),
   `priorities` (1 core … 4 probably skip), `sources` (friends' list, friend's Maps link, added, TikTok…).
   Categories are per trip: a beach weekend needs different types than an art weekend. Keep 6–14 types.
   When several museums share one ticket (e.g. Parkmuseerne), a dedicated type for them is clearer than a note.
4. **Write `data.json`** (schema: `references/data-schema.md`; start from `examples/copenhagen/data.json`).
   Mark the base with `base: true`, far-away day trips with `far: true` (kept out of the initial map fit),
   temporary exhibitions in `ev`, official booking/ticket pages in `bk`, closures with `closed: true`.
   Draw a district outline with `poly` when an area (not a point) is the thing to visit.
5. **Add 3–8 route drafts (`presets`)** — one coherent story per half-day, ≤10 stops, walking by default,
   starting and ending at the base when it makes sense. These are starting points the user reorders.
6. **Build:** `python3 scripts/build.py data.json -o <city>.html`. Validation errors name the place/preset.
   - Publishing as a Claude artifact? Add `--artifact` (body-only page) and embed a basemap
     (`scripts/fetch_basemap.py` → `--basemap basemap.json`), because the artifact sandbox blocks map tiles
     and photos; in a normal browser tiles and Wikimedia photos load and the basemap is unnecessary.
7. **Check** before delivering: open the file (or `node scripts/check.mjs <city>.html`) — no JS errors,
   markers present, a card opens, the type filter and the route link work. Fix data, rebuild.
8. **Deliver** the HTML file (and/or the artifact) and summarise in a few lines: what was verified, what
   changed vs. the user's assumptions (closed venues, ended exhibitions), what still needs a booking.

## What the page does (so you know what the data feeds)

- **Clustering** by district `d`, type `t`, priority `p`, source `s`, booking `bk` — combinable, order = click order.
- **Type filter**: tap a chip to hide/show, `◎` shows only that type, «Все» resets. Counts come from `places`.
- **Card** on hover/tap: type/district/priority chips, address, hours `h`, «Сейчас идёт» from `ev`, note `x`,
  «+ В маршрут», booking button from `bk` (📅 table/slot, 🎟 tickets), «Google Maps ↗» (uses `pid` when present),
  photos: Wikipedia page image via `w` + Wikimedia Commons photos near the point (radius `pr`).
- **Route**: drag from the list (desktop) or «+» (phone); max `meta.maxStops` (10) — Google Maps directions
  take origin + 8 waypoints + destination; travel mode defaults to walking; «от моего местоположения» option.
  Output: one Google Maps link, «Поделиться…» (Web Share sheet → Telegram/Messages/AirDrop; hidden where the
  API is missing), a direct Telegram button (`t.me/share/url`, works everywhere), Copy, QR.
  A «Забронировать / купить заранее» checklist lists the stops that have `bk`.
- **Phone layout** (<980px): full-screen map, bottom tabs Карта / Места / Маршрут as sheets; drag-in from the
  list is disabled there (it fights scrolling) — «+» is the way.
- State (route, filters, clustering) is saved in localStorage under `meta.storageKey`; change the key when
  you ship a substantially different version of the same trip so stale routes do not come back.

## Rules of thumb

- Hours in `h` are for the trip's weekdays, compact: `пт 10–18 · сб–вс 11–17 · вс закрыто`. A place closed
  on one of the days is more useful with that fact in `h` than with generic hours.
- `x` is what a well-travelled friend would say: what to order, when the queue starts, why it beats the
  alternative, how far from the base. Not a Wikipedia summary.
- `bk.u` must be the venue's own booking/ticket page (or its reservation provider), never an aggregator.
- Priority 4 (likely skip) items stay in the data — the user can hide them by type, and the map is
  the record of what was considered.
- Use `w` (English Wikipedia title) for landmarks, parks, museums so the card shows the place itself;
  cafés rarely have articles — their photo will be the street nearby, and the card says so.
- Keep `meta.facts` for things the user must know before the trip: closures, last days of exhibitions,
  a free vernissage on Friday, combined tickets, weather. Facts may contain `<b>` HTML.
- The Google Maps URL is built from `pid` when every stop has one; without `pid` Google matches by
  name + address + `meta.city` text, which sometimes picks the wrong branch — get place_ids.

## Updating an existing map

Edit `data.json` (add/remove places, change types, refresh hours), rebuild, redeliver. Tell the user which
places changed. If types were removed, presets referencing their places must be fixed — the build fails
loudly on unknown ids, on purpose.
