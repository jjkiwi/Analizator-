import type { Db } from "./db.ts";
import type { Classification } from "./classify.ts";
import type { NewsItem } from "./rss.ts";
import type { MacroEvent } from "./macro.ts";

export interface QuietHours {
  start: number;
  end: number;
  tz: string;
}

/** Czy `now` wypada w ciszy nocnej [start, end) liczonej w strefie `tz`. start == end wylacza cisze. */
export function inQuietHours(now: Date, q: QuietHours): boolean {
  if (q.start === q.end) return false;
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "2-digit", hourCycle: "h23", timeZone: q.tz }).format(now));
  return q.start < q.end ? hour >= q.start && hour < q.end : hour >= q.start || hour < q.end;
}

const ARROW: Record<string, string> = { "1": "↑", "-1": "↓", "0": "·" };

export function formatNews(item: NewsItem, cls: Classification): string {
  const syms = Object.entries(cls.directions).map(([s, d]) => `${s}${ARROW[String(d)]}`).join(" ");
  const head = cls.importance >= 3 ? "🔴 PILNE" : cls.importance === 2 ? "🟡 ISTOTNE" : "NEWS";
  const lines = [`${head}: ${item.title}`, `Instrumenty: ${syms}`];
  if (cls.reason) lines.push(`Ocena (${cls.classifier}): ${cls.reason}`);
  if (item.url) lines.push(item.url);
  return lines.join("\n");
}

const num = (v: number | null) => (v === null ? "–" : String(Number(v.toPrecision(6))));

export function formatMacroBefore(ev: MacroEvent, symbols: string[], minutes: number): string {
  return `⏰ Za ${minutes} min: ${ev.country} ${ev.name}\nprognoza ${num(ev.forecast)}, poprzednio ${num(ev.previous)}\nDotyczy: ${symbols.join(", ")}`;
}

export function formatMacroAfter(ev: MacroEvent, effects: Record<string, number>): string {
  const syms = Object.entries(effects).map(([s, d]) => `${s}${ARROW[String(d)]}`).join(" ");
  return `📊 ${ev.country} ${ev.name}: odczyt ${num(ev.actual)} vs prognoza ${num(ev.forecast)}\nPodręcznikowa reakcja: ${syms}`;
}

export type Send = (text: string) => Promise<boolean>;

export function telegramSender(token: string | undefined, chatId: string | undefined): Send {
  return async (text) => {
    if (!token || !chatId) {
      console.log("[brak Telegrama] " + text);
      return true;
    }
    try {
      const resp = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        signal: AbortSignal.timeout(10000),
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, text: text.slice(0, 4000), disable_web_page_preview: true }),
      });
      return resp.ok;
    } catch (_err) {
      return false;
    }
  };
}

/** Dzieli zalegle wiadomosci na porcje mieszczace sie w limicie Telegrama. */
export function buildDigest(texts: string[], limit = 3800): string[] {
  const chunks: string[] = [];
  let current = `🌙 Podsumowanie nocy: ${texts.length} powiadomień\n\n`;
  for (const t of texts) {
    const block = t + "\n\n———\n\n";
    if (current.length + block.length > limit && current.length > 0) {
      chunks.push(current);
      current = "";
    }
    current += block;
  }
  chunks.push(current);
  return chunks.map((c) => c.replace(/[—\n ]+$/, ""));
}

/** Wysyla wiadomosc albo, w ciszy nocnej, odklada ja do tabeli outbox. Poza cisza najpierw oproznia outbox. */
export async function notify(db: Db, send: Send, q: QuietHours, text: string, now = new Date()): Promise<void> {
  if (inQuietHours(now, q)) {
    await db.insert("outbox", [{ text }]);
    return;
  }
  await flushOutbox(db, send, q, now);
  await send(text);
}

export async function flushOutbox(db: Db, send: Send, q: QuietHours, now = new Date()): Promise<number> {
  if (inQuietHours(now, q)) return 0;
  const rows = await db.select<{ id: number; text: string }>("outbox", { select: "id,text", order: "id.asc", limit: "200" });
  if (!rows.length) return 0;
  for (const chunk of buildDigest(rows.map((r) => r.text))) {
    if (!(await send(chunk))) return 0; // nie kasujemy, sprobujemy przy nastepnym wywolaniu
  }
  await db.remove("outbox", { id: `lte.${rows[rows.length - 1].id}` });
  return rows.length;
}
