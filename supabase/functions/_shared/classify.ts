import type { Match } from "./mapper.ts";
import type { NewsItem } from "./rss.ts";

export interface Classification {
  importance: number; // 1 tlo, 2 istotne, 3 pilne
  directions: Record<string, number>; // symbol -> -1 | 0 | 1
  reason: string;
  classifier: string;
}

export interface Provider {
  name: string;
  base_url: string;
  model: string;
  key_env: string;
}

const UP = /\b(surge[sd]?|soar(?:s|ed)?|jump(?:s|ed)?|rall(?:y|ies|ied)|climb(?:s|ed)?|gain(?:s|ed)?|record high|rośnie|rosną|drożeje|rekord)(?![\p{L}])/iu;
const DOWN = /\b(plunge[sd]?|tumble[sd]?|slump(?:s|ed)?|sinks?|sank|drop(?:s|ped)?|falls?|fell|slide[sd]?|crash(?:es|ed)?|record low|spada|spadają|tanieje|traci)(?![\p{L}])/iu;

/** Darmowy klasyfikator bez sieci. Wage ocenia przyzwoicie, kierunek tylko gdy news mowi wprost o ruchu ceny. */
export function classifyRules(item: NewsItem, match: Match): Classification {
  const importance = match.highImpact ? 3 : match.direct.length ? 2 : 1;
  const up = UP.test(item.title), down = DOWN.test(item.title);
  const d = up && !down ? 1 : down && !up ? -1 : 0;
  const directions: Record<string, number> = {};
  for (const s of match.symbols) directions[s] = match.direct.includes(s) ? d : 0;
  const reason = match.highImpact ? "fraza wysokiej wagi" : match.direct.length ? "dotyczy instrumentu wprost" : "temat makro";
  return { importance, directions, reason, classifier: "rules" };
}

export function buildPrompt(item: NewsItem, symbols: string[]): string {
  return `Jestes analitykiem rynkow finansowych. Ocen naglowek pod katem krotkoterminowego wplywu na wskazane instrumenty CFD.

Naglowek (moze byc w dowolnym jezyku): ${item.title}
Opis: ${item.summary.slice(0, 500) || "-"}
Zrodlo: ${item.source}
Instrumenty: ${symbols.join(", ")}

Odpowiedz WYLACZNIE obiektem JSON, bez zadnego innego tekstu:
{"importance": 1|2|3, "directions": {"SYMBOL": -1|0|1}, "reason": "jedno zdanie po polsku"}

importance: 3 = nowe, nieoczekiwane zdarzenie mogace ruszyc cena w ciagu godzin; 2 = istotne tlo; 1 = szum, komentarz, podsumowanie znanych faktow.
directions: +1 wzrostowo, -1 spadkowo, 0 niejasne lub brak wplywu. Uzyj dokladnie podanych symboli. Gdy masz watpliwosci, dawaj 0.`;
}

/** Wyciaga obiekt JSON z odpowiedzi modelu (modele czesto dodaja tekst lub \`\`\`json wokol). */
export function parseLlmJson(text: string, symbols: string[], classifier: string): Classification {
  const start = text.indexOf("{"), end = text.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("brak obiektu JSON w odpowiedzi");
  const data = JSON.parse(text.slice(start, end + 1));
  const imp = Math.trunc(Number(data.importance));
  if (!Number.isFinite(imp)) throw new Error("brak pola importance");
  const raw = (data.directions && typeof data.directions === "object") ? data.directions : {};
  const directions: Record<string, number> = {};
  for (const s of symbols) {
    const v = Math.trunc(Number(raw[s] ?? 0));
    directions[s] = Number.isFinite(v) ? Math.max(-1, Math.min(1, v)) : 0;
  }
  return { importance: Math.max(1, Math.min(3, imp)), directions, reason: String(data.reason ?? "").slice(0, 300), classifier };
}

type Post = (provider: Provider, key: string, prompt: string, timeoutMs: number) => Promise<string>;

const httpPost: Post = async (p, key, prompt, timeoutMs) => {
  const resp = await fetch(p.base_url.replace(/\/+$/, "") + "/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(timeoutMs),
    headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: p.model, temperature: 0, max_tokens: 300, messages: [{ role: "user", content: prompt }] }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  return data?.choices?.[0]?.message?.content ?? "";
};

/**
 * Lancuch dostawcow zgodnych z API OpenAI: pierwsza poprawna odpowiedz wygrywa, na koncu reguly.
 * `blocked` to nazwy dostawcow do pominiecia (np. ci, ktorzy niedawno zwrocili blad limitu);
 * funkcja dopisuje do niego tych, ktorzy zawiedli w tym wywolaniu.
 */
export async function classifyChain(
  item: NewsItem,
  match: Match,
  providers: Provider[],
  getKey: (env: string) => string | undefined,
  blocked: Set<string> = new Set(),
  timeoutMs = 20000,
  post: Post = httpPost,
): Promise<Classification> {
  const prompt = buildPrompt(item, match.symbols);
  for (const p of providers) {
    const key = getKey(p.key_env);
    if (!key || blocked.has(p.name)) continue;
    try {
      return parseLlmJson(await post(p, key, prompt, timeoutMs), match.symbols, `llm:${p.name}`);
    } catch (_err) {
      blocked.add(p.name);
    }
  }
  return classifyRules(item, match);
}
