# Research playbook: turning a list of names into places[]

The map is only as good as the facts in it. This is the order that worked; adapt to the tools you have.

## 1. Inventory the candidates

- Split the user's material into: named places, Google Maps short links (`maps.app.goo.gl/…`), districts,
  vague wishes ("a sauna by the water"). Note who recommended what — that becomes `sources`.
- Deduplicate (the same place listed twice, chains with several branches).
- Add your own candidates for the city's must-sees and for what the user asked for but the list lacks
  (a viewpoint, a public bath, a market), and mark them with a separate source key so the user can tell
  friends' picks from yours.

## 2. Resolve each place to coordinates + place_id + hours

- Google Places search (a `places_search` tool, the Places API, or Google Maps in a browser) gives
  name, address, `lat/lng`, `place_id`, rating, opening hours by weekday, and recent reviews.
  Query with name + street + city; check the result is the right branch (compare the address).
- Google Maps short links do not resolve from a plain HTTP client (robots/redirect protections):
  open them in a browser tool; the final URL contains `?q=<name>,+<address>` and the `ftid`.
- Hours: take the weekdays of the trip only and write them compactly. Watch for: closed on Monday/Sunday,
  lunch breaks, kitchen closing earlier than the venue, seasonal closures (Tivoli between seasons),
  "opens 11:00" for churches, last entry times for towers.
- Reviews are useful for the note (`x`): what to order, queue times, "cash only", "no indoor seating",
  "book weeks ahead". Skip star ratings in the note — they date quickly.

## 3. What is on during the trip

- Search "<city> exhibitions <month year>", the main museums' programme pages, and city listings
  (exhibitionary.com, local culture calendars). Record for each venue: exhibition title, end date, and whether
  the trip dates are the last days (that changes priorities). Put it in `ev`.
- Season openings, vernissages, free evenings, night openings: often free and atmospheric → `ev` + `facts`.
- Combined tickets (museum passes) → a dedicated type or an `ev` line with price and rules.

## 4. Booking and tickets (`bk`)

- Find the venue's own reservation page (its site, SevenRooms/Resy/OpenTable link on the site, Billetto for
  Danish venues, the museum's ticket shop). Label the button with the action: «Забронировать стол»,
  «Записаться на сеанс», «Билет (тайм-слот)», «Купить билет».
- `k: "t"` for tables, slots and sessions; `k: "k"` for tickets. No link but booking clearly needed → `b: true`.

## 5. Photos

- Landmarks, museums, parks, districts: put the English Wikipedia article title in `w` (check it exists;
  redirects are fine). The card then shows the article's lead image.
- Everything else gets Wikimedia Commons photos taken within `pr` metres of the point — usually the street.
  That is acceptable; the card says where photos come from and links to Google Maps for the venue's own photos.
- The page fetches photos live from wikipedia.org / commons.wikimedia.org; nothing to download at build time.

## 6. Districts and outlines

- `d` should be the neighbourhood people use (Nørrebro, Christianshavn), not the postal district.
- For an area that is itself the destination (a freetown, a park, a harbour development) add `poly` from
  OpenStreetMap: Overpass `way["name"="Christiania"]["landuse"]` → `out geom`, keep every 2nd node,
  round to 5 decimals. 30–60 points is plenty.

## 7. Priorities and presets

- `1` core (the trip is poorer without it), `2` strong, `3` if nearby, `4` probably skip (kept for the record).
- Presets are half-day stories: one district → a bakery → a sight → food → the next thing, ≤10 stops,
  starting/ending at the base. Give each a name that starts with the day. Include a rainy-day preset and,
  if relevant, an "all near the hotel" one. Check every id exists (the build does too).

## 8. Facts block

Five to ten bullets the user must know before leaving: closures on their dates, exhibitions ending,
booking that must happen now, transport from the base, weather. Date-stamp the heading
(`Проверено 24.09`) so the user knows how fresh it is.

## 9. Basemap (only when the page will be viewed inside Claude)

Claude's artifact sandbox blocks external images, so map tiles and photos do not load there. Run
`scripts/fetch_basemap.py S W N E -o basemap.json` for a tight box around the places (about 10×10 km) and build
with `--basemap basemap.json --artifact`. In a normal browser (Safari/Chrome on the phone) skip this.
