import { cleanText, decodeEntities } from "./text.ts";

export interface NewsItem {
  source: string;
  title: string;
  url: string;
  summary: string;
  published: Date | null;
}

function tag(block: string, names: string[]): string | undefined {
  for (const name of names) {
    const m = block.match(new RegExp(`<(?:[\\w-]+:)?${name}(?:\\s[^>]*)?>([\\s\\S]*?)</(?:[\\w-]+:)?${name}>`, "i"));
    if (m) return m[1];
  }
  return undefined;
}

function link(block: string): string {
  // Atom: <link href="..."/> (preferujemy rel="alternate" albo brak rel); RSS: <link>url</link>
  const atom = [...block.matchAll(/<link\b([^>]*)\/?>/gi)].map((m) => m[1]);
  const pick = atom.find((a) => /href=/.test(a) && (!/rel=/.test(a) || /rel=["']alternate["']/.test(a))) ??
    atom.find((a) => /href=/.test(a));
  if (pick) {
    const href = pick.match(/href=["']([^"']+)["']/);
    if (href) return decodeEntities(href[1]).trim();
  }
  const rss = tag(block, ["link"]);
  return rss ? cleanText(rss) : "";
}

function parseDate(text: string | undefined): Date | null {
  if (!text) return null;
  const d = new Date(cleanText(text));
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Parsuje RSS 2.0 i Atom bez parsera XML (w srodowisku funkcji brzegowych nie ma DOMParser). */
export function parseFeed(xml: string, source: string): NewsItem[] {
  const items: NewsItem[] = [];
  for (const m of xml.matchAll(/<(item|entry)\b[^>]*>([\s\S]*?)<\/\1>/gi)) {
    const block = m[2];
    const title = cleanText(tag(block, ["title"]));
    if (!title) continue;
    items.push({
      source,
      title,
      url: link(block),
      summary: cleanText(tag(block, ["description", "summary", "content"])).slice(0, 1000),
      published: parseDate(tag(block, ["pubDate", "published", "updated", "date"])),
    });
  }
  return items;
}

export async function fetchFeed(url: string, source: string, timeoutMs = 8000, maxBytes = 3_000_000): Promise<NewsItem[]> {
  const resp = await fetch(url, {
    signal: AbortSignal.timeout(timeoutMs),
    headers: { "User-Agent": "analizator-cfd/0.3 (prywatne narzedzie; RSS)" },
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const text = await resp.text();
  if (text.length > maxBytes) throw new Error(`feed przekracza ${maxBytes} znakow`);
  return parseFeed(text, source);
}
