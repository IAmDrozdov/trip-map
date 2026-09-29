#!/usr/bin/env node
// Smoke-test a built page with Playwright: loads it at desktop and iPhone sizes, reports JS errors,
// counts markers, opens a card, exercises the type filter and the route panel, and saves screenshots.
//
//   node scripts/check.mjs out.html [screenshot-dir]
//   node scripts/check.mjs out.html [screenshot-dir] --offline   # also blocks all network, checks vector map, embedded photos, dark mode
//
// Needs: npm i playwright   (and a Chromium: npx playwright install chromium, or set PLAYWRIGHT_CHROMIUM=/path/to/chromium)
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { mkdirSync } from "node:fs";

const offline = process.argv.includes("--offline");
const args = process.argv.slice(2).filter(a => a !== "--offline");
const file = args[0];
if (!file) { console.error("usage: node scripts/check.mjs out.html [screenshot-dir] [--offline]"); process.exit(2); }
const dir = args[1] || "check-shots";
mkdirSync(dir, { recursive: true });

let pw;
try { pw = await import("playwright"); } catch { console.error("playwright is not installed: npm i playwright && npx playwright install chromium"); process.exit(2); }
const { chromium, devices } = pw;
const launch = { ...(process.env.PLAYWRIGHT_CHROMIUM ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM } : {}) };
const browser = await chromium.launch(launch);
const url = pathToFileURL(resolve(file)).href;
let failed = false;

async function run(name, ctxOpts, mobile) {
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  const errors = [];
  const external = [];
  page.on("pageerror", e => errors.push(e.message));
  if (offline) {
    await ctx.route("**/*", route => {
      const u = route.request().url();
      if (/^(data|blob|file):/.test(u)) return route.continue();
      external.push(u);
      return route.abort();
    });
  }
  await page.goto(url);
  await page.waitForTimeout(offline ? 3000 : 1200);
  const info = await page.evaluate(() => ({
    places: typeof P !== "undefined" ? P.length : -1,
    markers: document.querySelectorAll("path.leaflet-interactive").length,
    types: document.querySelectorAll("#types .tchip").length,
    presets: document.querySelectorAll("#preset option").length - 1,
    route: typeof route !== "undefined" ? route.length : -1,
    links: document.querySelectorAll("#links a").length,
  }));
  await page.screenshot({ path: `${dir}/${name}-1-map.png` });
  // open a card for the first place
  await page.evaluate(() => { const p = P[0]; showCard(p, map.latLngToContainerPoint([p.lat, p.lng]), true); });
  await page.waitForTimeout(400);
  const cardOk = await page.evaluate(() => !document.getElementById("card").hidden && !!document.getElementById("cAdd"));
  await page.screenshot({ path: `${dir}/${name}-2-card.png` });
  // solo the first type, then reset
  const soloOk = await page.evaluate(() => {
    document.querySelector("#types [data-solo]").click();
    const shown = P.filter(visible).every(p => p.base || p.t === Object.keys(TYPES)[0]);
    document.getElementById("allTypes").click();
    return shown && hiddenTypes.size === 0;
  });
  // route panel
  if (mobile) { await page.tap('[data-tab="route"]'); } else { await page.evaluate(() => document.getElementById("sheetRoute").scrollIntoView()); }
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${dir}/${name}-3-route.png` });
  const capOk = await page.evaluate(() => { const before = route.length; for (let i = 0; i < 12; i++) addStop(P[i % P.length].id); const ok = route.length <= MAX_STOPS; route = route.slice(0, before); saveRender(); return ok; });
  let offlineOk = true;
  let offlineNote = "";
  if (offline) {
    const view = async (lat, lng, z) => {
      await page.evaluate(([a, b, c]) => map.setView([a, b], c, { animate: false }), [lat, lng, z]);
      await page.waitForFunction(() => tiles && tiles.getMaplibreMap && tiles.getMaplibreMap().loaded(), null, { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(800);
      return page.evaluate(() => tiles.getMaplibreMap().queryRenderedFeatures().length);
    };
    const near = await page.evaluate(() => { const p = P.find(x => !x.far && !x.base) || P[0]; return [p.lat, p.lng]; });
    const f13 = await view(near[0], near[1], 13);
    await page.screenshot({ path: `${dir}/${name}-4-z13.png` });
    const f18 = await view(near[0], near[1], 18);
    await page.screenshot({ path: `${dir}/${name}-5-z18.png` });
    const bg = () => page.evaluate(() => JSON.stringify(tiles.getMaplibreMap().getStyle().layers[0].paint));
    const light = await bg();
    await page.emulateMedia({ colorScheme: "dark" });
    await page.waitForTimeout(2500);
    const darkBg = await bg();
    await page.screenshot({ path: `${dir}/${name}-6-dark.png` });
    await page.emulateMedia({ colorScheme: "light" });
    const imgs = await page.evaluate(async () => {
      const p = P.find(x => x.ph && x.ph.length);
      if (!p) return -1;
      showCard(p, map.latLngToContainerPoint([p.lat, p.lng]), true);
      await new Promise(r => setTimeout(r, 800));
      return document.querySelectorAll('#ph img[src^="data:"]').length;
    });
    offlineOk = f13 > 0 && f18 > 0 && light !== darkBg && imgs > 0 && external.length === 0;
    offlineNote = ` features z13=${f13} z18=${f18} darkRerender=${light !== darkBg} dataImgs=${imgs} external=${external.length}${external.length ? " " + external.slice(0, 5).join(",") : ""}`;
  }
  await ctx.close();
  if (!offlineOk) failed = true;
  const bad = errors.length || !cardOk || !soloOk || !capOk || info.markers === 0;
  if (bad) failed = true;
  console.log(`${bad ? "FAIL" : "ok  "} ${name}: ${JSON.stringify(info)} card=${cardOk} solo=${soloOk} cap=${capOk}${offlineNote}${errors.length ? "\n  errors: " + errors.join(" | ") : ""}`);
}

await run("desktop", { viewport: { width: 1400, height: 850 } }, false);
await run("iphone", { ...devices["iPhone 15 Pro"] }, true);
await browser.close();
console.log(`screenshots in ${dir}/`);
process.exit(failed ? 1 : 0);
