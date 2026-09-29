# data.json schema

Top level: `meta`, `types`, `priorities`, `sources`, `places`, `presets`, optional `basemap`.
`scripts/build.py --check data.json` validates all of this and prints warnings for the soft rules.

## meta

| field | type | required | meaning |
|---|---|---|---|
| `title` | string | yes | Page title and header, e.g. `"Copenhagen, 25–27 сентября"`. Also the first line of the shared route text. |
| `subtitle` | string | no | Small line under the title (default `карта мест`); the place count is appended automatically. |
| `base` | string | no | Name of the hotel/base, shown as `база: …` in the subtitle. |
| `city` | string | yes* | City name appended to every Google Maps query (`"København"`). *Warned if missing. |
| `storageKey` | string | no | Namespace for localStorage (`"cph2026"`). Change it to reset users' saved route/filters. Default `trip`. |
| `maxStops` | int | no | Route limit, default 10. Google Maps directions links take origin + 8 waypoints + destination. |
| `center`, `zoom` | [lat,lng], int | no | Initial view. Default: fit all places that are not `far`. |
| `defaultDims` | string[] | no | Initial clustering keys, default `["d"]`. Keys: `d` district, `t` type, `p` priority, `s` source, `b` booking. |
| `defaultPreset` | bool | no | `false` = start with an empty route instead of `presets[0]`. |
| `factsTitle` | string | no | Heading of the collapsible facts block (`"Проверено 24.09 — что изменилось"`). |
| `facts` | string[] | no | Bullet points; `<b>` allowed. Closures, last days of exhibitions, tickets, transport from the base. |
| `weather` | object[] | no | `{d: "Пт 25", t: "13–16°", r: "10% 🌧"}` per day, shown as tiles under the facts. |
| `tiles` | bool | no | `false` disables raster tiles (use with an embedded `basemap`). |
| `tileUrl`, `tileAttribution` | string | no | Tile template + attribution HTML. Default: OpenStreetMap standard tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`, no API key; dark theme via a CSS filter). CARTO/Stadia/MapTiler need keys on hosted domains. |
| `photos` | bool | no | `false` disables Wikipedia/Wikimedia photo lookups in cards. |
| `mapLang` | string | no | Language of map labels in the offline vector map (`en`, `de`, `ru`...). Default `en`. |
| `glyphRanges` | string[] | no | Extra glyph ranges for the offline map labels, e.g. `["1280-1535"]`. Default covers Latin, Cyrillic and punctuation. |
| `offline` | bool | no | Set by `build.py --offline`; never write it by hand. |

## types

Object keyed by a short id. Order = order of the filter chips.

```json
"types": {
  "sight":  {"l": "Достопримечательность", "c": "#1F6F78", "pr": 200},
  "area":   {"l": "Район / прогулка",      "c": "#3D8B5A", "pr": 350},
  "bakery": {"l": "Пекарня",               "c": "#C98F2A"},
  "hotel":  {"l": "Отель",                 "c": "#E8B500"}
}
```

| field | meaning |
|---|---|
| `l` | label |
| `c` | colour `#rrggbb` (marker colour when clustering by type; chip dot) |
| `s` | optional short label for list rows (default: first word of `l`) |
| `pr` | optional photo search radius in metres around the point for Commons photos (default 120; use 200–350 for landmarks/areas) |

## priorities and sources

```json
"priorities": {"1": "Ядро", "2": "Сильный кандидат", "3": "Если по пути", "4": "Скорее пропустить"},
"sources":    {"f": "Список друзей", "m": "Ссылка друга (Maps)", "a": "Добавлено при планировании", "e": "Афиши выставок", "t": "TikTok"}
```

Priority 1 gets the biggest marker and a ★ in lists. Sources are free-form keys — name them after where the recommendation came from; the clustering «Источник» uses them.

## places[]

| field | type | required | meaning |
|---|---|---|---|
| `id` | string | yes | Unique slug, used in presets and localStorage (`"juno"`). |
| `n` | string | yes | Display name (`"Juno the Bakery"`). |
| `a` | string | yes | Street address, short (`"Århusgade 48, Østerbro"`). Used in Google queries. |
| `lat`, `lng` | number | yes | WGS84. |
| `pid` | string | no* | Google Maps place_id (`"ChIJ…"`). Makes Google Maps links exact. *Warned if missing. |
| `t` | string | yes | Key from `types`. |
| `d` | string | yes | District / neighbourhood (`"Nørrebro"`); the default clustering. |
| `p` | int | yes | Priority key. |
| `s` | string | yes | Source key. |
| `h` | string | yes | Hours for the trip's days: `"пт–сб 7:30–18 · вс 7:30–16 · пн закрыто"`. |
| `x` | string | yes | The note: 1–3 sentences a knowledgeable friend would say. |
| `ev` | string | no | What is on there during the trip: exhibition + end date, a vernissage, a combined ticket. Shown as «Сейчас идёт». |
| `bk` | object | no | Booking: `{"k": "t", "l": "Забронировать стол", "u": "https://…"}`. `k`: `"t"` = table/slot/session (📅), `"k"` = tickets (🎟). `u` = the venue's own page. |
| `b` | bool | no | Booking needed but no link known → shows a «бронь» chip and counts as «Нужна бронь» in clustering. |
| `img` | string[] | no | Direct image URLs to embed as card photos in `--offline` builds; they come before Wikipedia and Commons photos. Use it for bakeries, cafes and other places without a Wikipedia article. |
| `w` | string | no | English Wikipedia article title for the card photo (`"Church of Our Saviour, Copenhagen"`). |
| `pr` | int | no | Per-place photo search radius (overrides the type's). |
| `base` | bool | no | The hotel / starting point: always visible, biggest marker. Exactly one is recommended. |
| `far` | bool | no | Day trip outside the city (Louisiana, the airport): excluded from map fitting so the city stays readable. |
| `closed` | bool | no | Closed on the trip dates (e.g. Tivoli between seasons): grey marker, struck-through in lists, red chip. Keep it in the data so the user sees it was checked. |
| `poly` | [[lat,lng],…] | no | Outline of an area (Christiania, a park). Drawn dashed; tapping it opens the card. Get it from OSM (Overpass: `way["name"="…"]`, take every 2nd node, round to 5 decimals). |

Example:

```json
{"id":"saviour","n":"Vor Frelsers Kirke (башня)","a":"Sankt Annæ Gade 29","lat":55.6729387,"lng":12.5942102,
 "pid":"ChIJye06RjlTUkYRK7RPt-oBGME","t":"sight","d":"Christianshavn","p":1,"s":"a",
 "h":"башня 9–20 · 70 DKK","x":"400 ступеней, последние 150 по внешней спирали. Одна смотровая на всю поездку: эта лучше Rundetårn.",
 "bk":{"k":"t","l":"Билет в башню (слот)","u":"https://billetto.dk/e/vor-frelsers-kirkes-tarn-…"},
 "w":"Church of Our Saviour, Copenhagen"}
```

## presets[]

```json
{"n": "Сб · Christianshavn → Refshaleøen", "ids": ["christianshavn","saviour","lille","copenhill"], "m": "walking", "me": false}
```

| field | meaning |
|---|---|
| `n` | name shown in the «Загрузить черновик…» menu; start with the day (`Пт утро ·`, `Вс ·`, `Дождь ·`) |
| `ids` | ordered place ids, ≤ `meta.maxStops` (build fails otherwise) |
| `m` | travel mode: `walking` (default), `transit`, `bicycling`, `driving`. Transit links ignore waypoints in Google Maps — use it only for a single hop |
| `me` | `true` = start from the user's current location instead of the first stop |

## basemap (optional)

Output of `scripts/fetch_basemap.py`: `{"l": [[ring, hole…]…], "w": [ring…], "p": [ring…], "r": [{"k": 1|2, "g": [[lat,lng]…]}…]}` —
land polygons with holes, water, parks, roads (k=1 main). Pass it with `build.py --basemap` or put it in `data.json` under `basemap`.
