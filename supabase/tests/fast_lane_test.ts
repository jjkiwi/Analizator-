// Testy toru szybkiego bez sieci i bez zewnetrznych bibliotek: `deno test supabase/tests/`
import { classifyChain, classifyRules, parseLlmJson, type Provider } from "../functions/_shared/classify.ts";
import type { Db } from "../functions/_shared/db.ts";
import { effectsFor, eventKey, parseFairEconomy, parseValue, surpriseEffects } from "../functions/_shared/macro.ts";
import { KeywordMapper } from "../functions/_shared/mapper.ts";
import { buildDigest, inQuietHours } from "../functions/_shared/notify.ts";
import { dueFeeds, runMacro, runNews } from "../functions/_shared/pipeline.ts";
import { type NewsItem, parseFeed } from "../functions/_shared/rss.ts";
import { cleanText, isDuplicate, normalizeTitle, shortHash } from "../functions/_shared/text.ts";

function eq(actual: unknown, expected: unknown, msg = "") {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a !== e) throw new Error(`${msg}\n  otrzymano:   ${a}\n  oczekiwano: ${e}`);
}

/** Atrapa PostgREST w pamieci: tyle filtrow, ile uzywa kod. */
function memDb(): Db & { t: Record<string, Record<string, unknown>[]> } {
  const t: Record<string, Record<string, unknown>[]> = {};
  const rows = (name: string) => (t[name] ??= []);
  const test = (row: Record<string, unknown>, col: string, expr: string): boolean => {
    const v = row[col];
    if (expr === "is.false") return v === false || v === undefined;
    if (expr === "not.is.null") return v !== null && v !== undefined;
    const [op, ...rest] = expr.split(".");
    const arg = rest.join(".");
    if (op === "eq") return String(v) === arg;
    if (op === "gte") return String(v) >= arg;
    if (op === "lte") return String(v) <= arg;
    if (op === "in") return arg.slice(1, -1).split(",").includes(String(v));
    throw new Error("nieobslugiwany filtr " + expr);
  };
  const filter = (name: string, params: Record<string, string>) =>
    rows(name).filter((r) =>
      Object.entries(params).every(([k, v]) => {
        if (["select", "order", "limit"].includes(k)) return true;
        if (k === "and") return v.slice(1, -1).split(",").every((c) => { const [col, ...e] = c.split("."); return test(r, col, e.join(".")); });
        return test(r, k, v);
      })
    );
  let seq = 0;
  return {
    t,
    select: (name, params) => Promise.resolve(filter(name, params) as never),
    insert: (name, rs) => { rs.forEach((r) => rows(name).push({ id: ++seq, ...r })); return Promise.resolve(); },
    upsert: (name, rs, onConflict, ignore = false) => {
      for (const r of rs) {
        const found = rows(name).find((x) => x[onConflict] === r[onConflict]);
        if (!found) rows(name).push({ ...r });
        else if (!ignore) Object.assign(found, r);
      }
      return Promise.resolve();
    },
    update: (name, f, values) => { filter(name, f).forEach((r) => Object.assign(r, values)); return Promise.resolve(); },
    remove: (name, f) => { const gone = new Set(filter(name, f)); t[name] = rows(name).filter((r) => !gone.has(r)); return Promise.resolve(); },
  };
}

const KW = {
  instruments: { GOLD: ["gold", "złoto"], "ZAB.PL": ["żabka"], ETHEREUM: ["eth"] },
  topics: { fed: { keywords: ["fed", "fomc"], symbols: ["US500", "GOLD"] }, oil: { keywords: ["opec+"], symbols: ["OIL"] } },
  high_impact: ["record high", "holds rates"],
};
const QUIET = { start: 23, end: 8, tz: "Europe/Warsaw" };
const NOON = new Date("2026-11-10T12:00:00Z");

Deno.test("tekst: normalizacja, encje, duplikaty, hash zgodny z Pythonem", async () => {
  eq(normalizeTitle("  Złoto: REKORD!  (S&P 500 +1.5%) "), "złoto rekord s&p 500 +1.5%");
  eq(cleanText("<![CDATA[&lt;p&gt;Bullion &amp;amp; more&#8217;s&lt;/p&gt;]]>"), "Bullion & more’s");
  eq(isDuplicate("fed holds rates steady in november", ["fed holds rates steady in november meeting"]), true);
  eq(isDuplicate("fed holds rates steady", ["opec agrees output cut"]), false);
  eq((await shortHash("abc")), "a9993e364706816a"); // sha1("abc")[:16], jak hashlib w Pythonie
});

Deno.test("rss: RSS 2.0 i Atom", () => {
  const rss = `<rss><channel><title>kanał</title><item><title>Gold surges &amp; hits record high</title>
    <link>https://ex.com/a?x=1&amp;y=2</link><description><![CDATA[<p>Bullion jumped.</p>]]></description>
    <pubDate>Mon, 09 Nov 2026 14:30:00 GMT</pubDate></item><item><title></title></item></channel></rss>`;
  const [a, ...rest] = parseFeed(rss, "s");
  eq(rest.length, 0);
  eq([a.title, a.url, a.summary, a.published?.toISOString()], ["Gold surges & hits record high", "https://ex.com/a?x=1&y=2", "Bullion jumped.", "2026-11-09T14:30:00.000Z"]);
  const atom = `<feed xmlns="http://www.w3.org/2005/Atom"><entry><title type="html">Fed holds rates</title>
    <link rel="self" href="https://ex.com/self"/><link rel="alternate" href="https://ex.com/b"/>
    <summary>FOMC</summary><updated>2026-11-09T19:00:00Z</updated></entry></feed>`;
  const [e] = parseFeed(atom, "fed");
  eq([e.title, e.url, e.published?.getUTCHours()], ["Fed holds rates", "https://ex.com/b", 19]);
});

Deno.test("mapper: slowa wprost, tematy, granice slow z polskimi znakami", () => {
  const m = new KeywordMapper(KW);
  const r = m.match("Fed holds rates as gold slips");
  eq([r.direct, r.topics, r.symbols, r.highImpact], [["GOLD"], ["fed"], ["GOLD", "US500"], true]);
  eq(m.match("OPEC+ agrees output cut").symbols, ["OIL"]);
  eq(m.match("Żabka otwiera sklepy, złoto drożeje").direct, ["GOLD", "ZAB.PL"]);
  eq(m.match("Method to feed goldfish in Bethlehem; żabkami się nie handluje").symbols, []);
});

const item = (title: string, url = "", published: Date | null = NOON): NewsItem => ({ source: "s", title, url, summary: "", published });

Deno.test("klasyfikacja: reguly, JSON z modelu, lancuch dostawcow", async () => {
  const m = new KeywordMapper(KW);
  const it = item("Gold surges to record high");
  const match = m.match(it.title);
  eq(classifyRules(it, match), { importance: 3, directions: { GOLD: 1 }, reason: "fraza wysokiej wagi", classifier: "rules" });
  eq(classifyRules(item("Fed officials speak"), m.match("Fed officials speak")).importance, 1);

  const parsed = parseLlmJson('```json\n{"importance": 9, "directions": {"GOLD": -1, "XXX": 1}, "reason": "bo"}\n```', ["GOLD", "US500"], "llm:a");
  eq(parsed, { importance: 3, directions: { GOLD: -1, US500: 0 }, reason: "bo", classifier: "llm:a" });

  const providers: Provider[] = ["a", "b", "c"].map((n) => ({ name: n, base_url: "x", model: "m", key_env: "KEY_" + n.toUpperCase() }));
  const keys: Record<string, string> = { KEY_A: "1", KEY_B: "2" }; // dostawca c nie ma klucza
  const calls: string[] = [];
  const post = (p: Provider) => { calls.push(p.name); return p.name === "a" ? Promise.reject(new Error("429")) : Promise.resolve('{"importance":2,"directions":{"GOLD":-1},"reason":"r"}'); };
  const blocked = new Set<string>();
  const cls = await classifyChain(it, match, providers, (e) => keys[e], blocked, 1000, post);
  eq([cls.classifier, cls.directions.GOLD, calls, [...blocked]], ["llm:b", -1, ["a", "b"], ["a"]]);
  const none = await classifyChain(it, match, providers, () => undefined, new Set(), 1000, post);
  eq(none.classifier, "rules");
});

Deno.test("makro: wartosci, parser kalendarza, reguly, klucz zgodny z Pythonem", () => {
  eq(["0.3%", "215K", "-1.25M", "<0.1%", "", null, "n/a", 2].map(parseValue), [0.3, 215000, -1250000, 0.1, null, null, null, 2]);
  const evs = parseFairEconomy([
    { title: "CPI m/m", country: "usd", date: "2026-11-12T08:30:00-05:00", impact: "High", forecast: "0.3%", previous: "0.2%" },
    { title: "Bank Holiday", country: "JPY", date: "2026-11-12T00:00:00-05:00", impact: "Holiday" },
    { title: "Broken", country: "EUR", date: "nie-data", impact: "Low" },
  ]);
  eq(evs.length, 1);
  eq([evs[0].time.toISOString(), evs[0].country, evs[0].importance, evs[0].forecast, evs[0].actual], ["2026-11-12T13:30:00.000Z", "USD", 3, 0.3, null]);
  eq(eventKey(evs[0]), "2026-11-12t13:30|usd|cpi m/m");
  const rules = [{ name: "cpi", country: "USD", match: ["cpi"], effects: { US500: -1, USDIDX: 1 } }];
  eq(effectsFor(evs[0], rules), { US500: -1, USDIDX: 1 });
  eq(surpriseEffects({ ...evs[0], actual: 0.2 }, rules), { US500: 1, USDIDX: -1 });
  eq(surpriseEffects({ ...evs[0], actual: 0.3 }, rules), {});
  eq(surpriseEffects({ ...evs[0], country: "GBP", actual: 0.9 }, rules), {});
});

Deno.test("cisza nocna w strefie Europe/Warsaw (czas zimowy i letni) oraz podsumowanie", () => {
  eq(inQuietHours(new Date("2026-11-10T21:59:00Z"), QUIET), false); // 22:59 w Warszawie
  eq(inQuietHours(new Date("2026-11-10T22:00:00Z"), QUIET), true); // 23:00
  eq(inQuietHours(new Date("2026-11-11T06:59:00Z"), QUIET), true); // 07:59
  eq(inQuietHours(new Date("2026-11-11T07:00:00Z"), QUIET), false); // 08:00
  eq(inQuietHours(new Date("2026-07-10T21:00:00Z"), QUIET), true); // lato: 23:00 CEST
  eq(inQuietHours(NOON, { start: 0, end: 0, tz: "UTC" }), false);
  const digest = buildDigest(["a".repeat(3000), "b".repeat(3000)], 3800);
  eq([digest.length, digest[0].startsWith("🌙 Podsumowanie nocy: 2"), digest[1].startsWith("b")], [2, true, true]);
});

Deno.test("harmonogram feedow: tylko zalegle, najstarsze pierwsze, z limitem", () => {
  const feeds = [{ name: "a", url: "", poll_seconds: 60 }, { name: "b", url: "", poll_seconds: 60 }, { name: "c", url: "", poll_seconds: 600 }];
  eq(dueFeeds(feeds, { a: 1000, b: 500, c: 900_000 }, 1_000_000, 5).map((f) => f.name), ["b", "a"]);
  eq(dueFeeds(feeds, {}, 1_000_000, 2).length, 2);
});

function newsDeps(db: ReturnType<typeof memDb>, batch: NewsItem[], sent: string[], now: Date, extra = {}) {
  return {
    db, send: (t: string) => { sent.push(t); return Promise.resolve(true); }, mapper: new KeywordMapper(KW), providers: [],
    getKey: () => undefined, fetchFeed: () => Promise.resolve(batch), quiet: QUIET,
    settings: { alert_min_importance: 2, max_age_hours: 24, use_llm: true }, healthAlertAfter: 3, maxFeedsPerRun: 12, maxLlmPerRun: 8, now, ...extra,
  };
}

Deno.test("przebieg newsow: filtr, duplikaty, alerty od wagi 2, brak powtorek, cisza nocna", async () => {
  const db = memDb(), sent: string[] = [];
  const feeds = [{ name: "f", url: "u", poll_seconds: 60 }];
  const batch = [
    item("Gold surges to record high", "https://x/1"),
    item("Gold surges to a record high", "https://y/1"), // duplikat z innego zrodla
    item("Gold steady in quiet trade", "https://x/5"), // waga 2 -> alert
    item("Fed officials speak on outlook", "https://x/2"), // waga 1 -> bez alertu
    item("Local sports results", "https://x/3"), // bez instrumentu
    item("Gold old story", "https://x/4", new Date(NOON.getTime() - 3 * 86400_000)), // za stary
  ];
  const r1 = await runNews(feeds, newsDeps(db, batch, sent, NOON));
  eq(r1, { feeds: 1, fetched: 6, new: 5, alerts: 2, llm: 2 });
  eq(sent.map((s) => s.split(":")[0]), ["🔴 PILNE", "🟡 ISTOTNE"]);
  eq(db.t.news.map((n) => n.importance), [3, 0, 2, 1, null]);
  eq(db.t.source_health[0], { source: "feed:f", last_ok: db.t.source_health[0].last_ok, fail_streak: 0 });

  const later = new Date(NOON.getTime() + 30_000); // feed jeszcze nie jest zalegly
  eq((await runNews(feeds, newsDeps(db, batch, sent, later))).feeds, 0);
  const next = new Date(NOON.getTime() + 61_000); // zalegly, ale wszystko juz znane
  eq((await runNews(feeds, newsDeps(db, batch, sent, next))).new, 0);
  eq(sent.length, 2);

  const night = new Date("2026-11-10T23:30:00Z");
  const nightBatch = [item("Gold jumps to record high again overnight", "https://x/9", night)];
  await runNews(feeds, newsDeps(db, nightBatch, sent, night));
  eq([sent.length, db.t.outbox.length], [2, 1]);
  const morning = new Date("2026-11-11T07:05:00Z");
  await runNews(feeds, newsDeps(db, [item("Gold slumps after open", "https://x/10", morning)], sent, morning));
  eq([sent.length, sent[2].startsWith("🌙 Podsumowanie nocy: 1"), db.t.outbox.length], [4, true, 0]);
});

Deno.test("przebieg newsow: zepsuty feed -> alert po trzeciej porazce, reszta dziala", async () => {
  const db = memDb(), sent: string[] = [];
  const feeds = [{ name: "bad", url: "u", poll_seconds: 60 }];
  for (let i = 0; i < 4; i++) {
    const now = new Date(NOON.getTime() + i * 61_000);
    await runNews(feeds, newsDeps(db, [], sent, now, { fetchFeed: () => Promise.reject(new Error("HTTP 503")) }));
  }
  eq([db.t.source_health[0].fail_streak, sent.length, sent[0].includes("feed:bad")], [4, 1, true]);
});

Deno.test("przebieg makro: odswiezenie, alert przed, reakcja po, bez powtorek i bez kasowania odczytu", async () => {
  const db = memDb(), sent: string[] = [];
  const now = new Date("2026-11-10T13:05:00Z");
  const cpi = { time: new Date(now.getTime() + 25 * 60_000), country: "USD", name: "CPI m/m", importance: 3, actual: null as number | null, forecast: 0.3, previous: 0.2 };
  const tankan = { time: new Date(now.getTime() + 10 * 60_000), country: "JPY", name: "Tankan", importance: 3, actual: null, forecast: null, previous: null };
  let calendar = [cpi, tankan];
  const deps = (at: Date) => ({
    db, send: (t: string) => { sent.push(t); return Promise.resolve(true); },
    rules: [{ name: "cpi", country: "USD", match: ["cpi"], effects: { US500: -1, NIEMA: 1 } }], symbols: new Set(["US500"]), quiet: QUIET,
    settings: { refresh_minutes: 60, alert_minutes_before: 30, alert_min_importance: 3 }, fetchCalendar: () => Promise.resolve(calendar), now: at,
  });
  eq(await runMacro(deps(now)), { refreshed: 2, alerts: 1 });
  eq([sent[0].includes("Za 25 min"), sent[0].includes("US500"), sent[0].includes("NIEMA")], [true, true, false]);
  eq(await runMacro(deps(new Date(now.getTime() + 60_000))), { refreshed: 0, alerts: 0 });

  // godzine pozniej kalendarz zwraca odczyt; kolejne odswiezenie bez odczytu nie moze go skasowac
  calendar = [{ ...cpi, actual: 0.5 }];
  eq(await runMacro(deps(new Date(now.getTime() + 61 * 60_000))), { refreshed: 1, alerts: 1 });
  eq(sent[1].includes("US500↓"), true);
  calendar = [cpi];
  eq(await runMacro(deps(new Date(now.getTime() + 122 * 60_000))), { refreshed: 1, alerts: 0 });
  eq(db.t.macro_events.find((e) => e.name === "CPI m/m")?.actual, 0.5);
});

Deno.test("mapper i reguly v0.3.1: skroty z wielkoscia liter, wykluczenia, tytul, zapowiedzi (1:1 z Pythonem)", () => {
  const m = new KeywordMapper({
    instruments: { GOLD: ["gold", "złoto"], JP225: ["nikkei", "cs:BOJ"] },
    topics: { fed: { keywords: ["cs:Fed", "fomc"], symbols: ["US500"] } },
    high_impact: ["rate cut", "cs:CPI"], high_impact_moves: ["surges", "record high"],
    exclude: { GOLD: ["gold medal"] },
  });
  eq(m.match("He was fed up and fed the dog").topics, []);
  eq(m.match("The Fed holds").topics, ["fed"]);
  eq(m.match("FOMC minutes").topics, ["fed"]);
  eq(m.match("boj to gratka; BOJ holds").direct, ["JP225"]);
  eq(m.match("boj o medale").direct, []);
  eq(m.match("She won a gold medal").direct, []);
  eq(m.match("ZŁOTO drożeje").direct, ["GOLD"]);
  // fraza wysokiej wagi liczy sie tylko w tytule
  eq(m.match("Markets calm. Analysts discuss a rate cut", "Markets calm").highImpact, false);
  eq(m.match("Fed delivers rate cut. More soon", "Fed delivers rate cut").highImpactHits, ["rate cut"]);
  // ruch ceny liczy sie tylko razem z instrumentem wprost
  eq(m.match("Tech surges", "Tech surges").highImpact, false);
  eq(m.match("Gold surges to record high", "Gold surges to record high").highImpactHits, ["record high", "surges"]);
  const item = (title: string): NewsItem => ({ source: "t", title, summary: "", url: "u", published: null });
  const cls = (t: string) => classifyRules(item(t), m.match(t, t)).importance;
  eq([cls("Fed delivers rate cut"), cls("Will the Fed deliver a rate cut?"), cls("CPI preview: what to expect"), cls("Gold steady")], [3, 2, 2, 2]);
});

Deno.test("przebieg newsow: druga waga 3 na ten sam temat w oknie spada do 2", async () => {
  const db = memDb();
  const mapper = new KeywordMapper({ instruments: { GOLD: ["gold"] }, topics: {}, high_impact: ["cs:CPI"] });
  const now = new Date("2026-11-10T14:00:00Z");
  const item = (title: string, n: number): NewsItem => ({ source: "f", title, summary: "", url: `https://x/${n}`, published: now });
  const settings = { alert_min_importance: 2, max_age_hours: 24, use_llm: false, repeat_cooldown_minutes: 60 };
  const feeds = [{ name: "f", url: "u", poll_seconds: 0, enabled: true }];
  await runNews(feeds, newsDeps(db, [item("Gold jumps after CPI comes in hot", 1), item("CPI shock sends gold price higher today", 2)], [], now, { mapper, settings }));
  eq(db.t.news.map((r) => r.importance), [3, 2]);
  await runNews(feeds, newsDeps(db, [item("Bullion: gold extends rally on CPI surprise", 3)], [], new Date(now.getTime() + 600_000), { mapper, settings }));
  eq(db.t.news.at(-1)!.importance, 2); // pamiec z bazy
});
