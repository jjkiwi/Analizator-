import { type Classification, classifyChain, classifyRules, type Provider } from "./classify.ts";
import { type Db, getState, healthFail, healthOk, setState } from "./db.ts";
import { effectsFor, eventKey, type MacroEvent, type MacroRule, surpriseEffects } from "./macro.ts";
import { KeywordMapper } from "./mapper.ts";
import { formatMacroAfter, formatMacroBefore, formatNews, notify, type QuietHours, type Send } from "./notify.ts";
import type { NewsItem } from "./rss.ts";
import { isDuplicate, normalizeTitle, shortHash } from "./text.ts";

export interface FeedConfig {
  name: string;
  url: string;
  poll_seconds: number;
}

export interface NewsDeps {
  db: Db;
  send: Send;
  mapper: KeywordMapper;
  providers: Provider[];
  getKey: (env: string) => string | undefined;
  fetchFeed: (url: string, source: string) => Promise<NewsItem[]>;
  quiet: QuietHours;
  settings: { alert_min_importance: number; max_age_hours: number; use_llm: boolean };
  healthAlertAfter: number;
  maxFeedsPerRun: number;
  maxLlmPerRun: number;
  now?: Date;
}

/** Wybiera feedy, ktorym minal czas odpytywania; najdluzej nieodpytywane pierwsze. */
export function dueFeeds(feeds: FeedConfig[], lastFetched: Record<string, number>, nowMs: number, max: number): FeedConfig[] {
  return feeds
    .filter((f) => nowMs - (lastFetched[f.name] ?? 0) >= f.poll_seconds * 1000)
    .sort((a, b) => (lastFetched[a.name] ?? 0) - (lastFetched[b.name] ?? 0))
    .slice(0, max);
}

/** Jeden przebieg toru newsowego: pobranie -> filtr -> deduplikacja -> mapowanie -> klasyfikacja -> zapis -> alert. */
export async function runNews(feeds: FeedConfig[], d: NewsDeps): Promise<Record<string, number>> {
  const now = d.now ?? new Date();
  const lastFetched = await getState<Record<string, number>>(d.db, "feeds_last_fetched", {});
  const blockedUntil = await getState<Record<string, number>>(d.db, "llm_blocked_until", {});
  const due = dueFeeds(feeds, lastFetched, now.getTime(), d.maxFeedsPerRun);

  const results = await Promise.allSettled(due.map((f) => d.fetchFeed(f.url, f.name)));
  const items: NewsItem[] = [];
  for (let i = 0; i < due.length; i++) {
    const r = results[i];
    lastFetched[due[i].name] = now.getTime();
    if (r.status === "fulfilled") {
      items.push(...r.value);
      await healthOk(d.db, `feed:${due[i].name}`);
    } else {
      const streak = await healthFail(d.db, `feed:${due[i].name}`, String(r.reason));
      if (streak === d.healthAlertAfter) {
        await notify(d.db, d.send, d.quiet, `⚠️ Źródło 'feed:${due[i].name}' zawiodło ${streak} razy z rzędu.\nOstatni błąd: ${String(r.reason).slice(0, 200)}`, now);
      }
    }
  }
  await setState(d.db, "feeds_last_fetched", lastFetched);

  const cutoff = now.getTime() - d.settings.max_age_hours * 3600_000;
  const fresh = items.filter((it) => !it.published || it.published.getTime() >= cutoff);
  const withIds = await Promise.all(fresh.map(async (it) => ({ it, id: await shortHash(it.url || it.title) })));
  const unique = [...new Map(withIds.map((x) => [x.id, x])).values()];
  if (!unique.length) return { feeds: due.length, fetched: items.length, new: 0, alerts: 0, llm: 0 };

  const known = new Set<string>();
  for (let i = 0; i < unique.length; i += 100) {
    const ids = unique.slice(i, i + 100).map((x) => x.id);
    const rows = await d.db.select<{ id: string }>("news", { id: `in.(${ids.join(",")})`, select: "id" });
    rows.forEach((r) => known.add(r.id));
  }
  const since = new Date(now.getTime() - 48 * 3600_000).toISOString();
  const recent = (await d.db.select<{ norm_title: string }>("news", {
    fetched: `gte.${since}`, select: "norm_title", order: "fetched.desc", limit: "500",
  })).map((r) => r.norm_title);

  const blocked = new Set(Object.entries(blockedUntil).filter(([, until]) => until > now.getTime()).map(([n]) => n));
  const blockedBefore = new Set(blocked);
  const rows: Record<string, unknown>[] = [];
  const alerts: { item: NewsItem; cls: Classification; id: string }[] = [];
  let llmCalls = 0;

  for (const { it, id } of unique) {
    if (known.has(id)) continue;
    const norm = normalizeTitle(it.title);
    const dup = isDuplicate(norm, recent);
    const match = d.mapper.match(`${it.title}. ${it.summary}`);
    let cls: Classification | null = null;
    if (match.symbols.length && !dup) {
      cls = classifyRules(it, match);
      // Reguly sa bramka: do modelu trafiaja tylko newsy z waga >= 2, i nie wiecej niz limit na przebieg.
      if (d.settings.use_llm && cls.importance >= 2 && llmCalls < d.maxLlmPerRun) {
        llmCalls++;
        cls = await classifyChain(it, match, d.providers, d.getKey, blocked);
      }
    }
    const alert = cls !== null && cls.importance >= d.settings.alert_min_importance;
    rows.push({
      id, source: it.source, title: it.title, summary: it.summary, url: it.url,
      published: it.published ? it.published.toISOString() : null, norm_title: norm,
      symbols: match.symbols.join(","),
      importance: cls ? cls.importance : (dup ? 0 : null),
      direction: cls ? cls.directions : null,
      reason: cls ? cls.reason : (dup ? "duplikat" : null),
      classifier: cls ? cls.classifier : null,
      alerted: alert,
    });
    recent.unshift(norm);
    if (alert && cls) alerts.push({ item: it, cls, id });
  }

  // Najpierw zapis, potem alerty: awaria po zapisie nie spowoduje powtornego alertu przy nastepnym przebiegu.
  await d.db.upsert("news", rows, "id", true);
  for (const a of alerts) await notify(d.db, d.send, d.quiet, formatNews(a.item, a.cls), now);

  const newlyBlocked = [...blocked].filter((n) => !blockedBefore.has(n));
  if (newlyBlocked.length) {
    for (const n of newlyBlocked) blockedUntil[n] = now.getTime() + 10 * 60_000;
    await setState(d.db, "llm_blocked_until", blockedUntil);
  }
  return { feeds: due.length, fetched: items.length, new: rows.length, alerts: alerts.length, llm: llmCalls };
}

export interface MacroDeps {
  db: Db;
  send: Send;
  rules: MacroRule[];
  symbols: Set<string>;
  quiet: QuietHours;
  settings: { refresh_minutes: number; alert_minutes_before: number; alert_min_importance: number };
  fetchCalendar: () => Promise<MacroEvent[]>;
  now?: Date;
}

interface MacroRow {
  id: string; time: string; country: string; name: string; importance: number;
  actual: number | null; forecast: number | null; previous: number | null;
}

const toEvent = (r: MacroRow): MacroEvent => ({ ...r, time: new Date(r.time) });

/** Jeden przebieg kalendarza: okresowe odswiezenie, alert przed publikacja, reakcja na odczyt. */
export async function runMacro(d: MacroDeps): Promise<Record<string, number>> {
  const now = d.now ?? new Date();
  let refreshed = 0;
  const last = await getState<number>(d.db, "macro_last_refresh", 0);
  if (now.getTime() - last >= d.settings.refresh_minutes * 60_000) {
    await setState(d.db, "macro_last_refresh", now.getTime());
    try {
      const events = await d.fetchCalendar();
      const rows = await Promise.all(events.map(async (e) => {
        const row: Record<string, unknown> = {
          id: await shortHash(eventKey(e)), time: e.time.toISOString(), country: e.country, name: e.name, importance: e.importance,
        };
        // Pola puste pomijamy, zeby ponowne pobranie nie skasowalo znanego juz odczytu.
        if (e.actual !== null) row.actual = e.actual;
        if (e.forecast !== null) row.forecast = e.forecast;
        if (e.previous !== null) row.previous = e.previous;
        return row;
      }));
      // PostgREST wymaga jednakowych kluczy w jednym zadaniu: grupujemy wiersze wg zestawu pol.
      const groups = new Map<string, Record<string, unknown>[]>();
      for (const r of rows) {
        const k = Object.keys(r).sort().join(",");
        groups.set(k, [...(groups.get(k) ?? []), r]);
      }
      for (const g of groups.values()) await d.db.upsert("macro_events", g, "id");
      refreshed = rows.length;
      await healthOk(d.db, "macro");
    } catch (err) {
      await healthFail(d.db, "macro", String(err));
    }
  }

  let sent = 0;
  const horizon = new Date(now.getTime() + d.settings.alert_minutes_before * 60_000).toISOString();
  const soon = await d.db.select<MacroRow>("macro_events", {
    and: `(time.gte.${now.toISOString()},time.lte.${horizon})`,
    importance: `gte.${d.settings.alert_min_importance}`, alerted_before: "is.false", order: "time.asc",
  });
  for (const row of soon) {
    const ev = toEvent(row);
    const symbols = Object.keys(effectsFor(ev, d.rules)).filter((s) => d.symbols.has(s));
    await d.db.update("macro_events", { id: `eq.${row.id}` }, { alerted_before: true });
    if (symbols.length) {
      const minutes = Math.max(Math.floor((ev.time.getTime() - now.getTime()) / 60_000), 0);
      await notify(d.db, d.send, d.quiet, formatMacroBefore(ev, symbols, minutes), now);
      sent++;
    }
  }

  const sinceIso = new Date(now.getTime() - 6 * 3600_000).toISOString();
  const released = await d.db.select<MacroRow>("macro_events", {
    time: `gte.${sinceIso}`, actual: "not.is.null", forecast: "not.is.null", alerted_after: "is.false",
  });
  for (const row of released) {
    const ev = toEvent(row);
    const effects = Object.fromEntries(Object.entries(surpriseEffects(ev, d.rules)).filter(([s]) => d.symbols.has(s)));
    await d.db.update("macro_events", { id: `eq.${row.id}` }, { alerted_after: true });
    if (Object.keys(effects).length && ev.importance >= d.settings.alert_min_importance) {
      await notify(d.db, d.send, d.quiet, formatMacroAfter(ev, effects), now);
      sent++;
    }
  }
  return { refreshed, alerts: sent };
}
