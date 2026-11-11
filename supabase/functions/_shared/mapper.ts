export interface KeywordConfig {
  instruments: Record<string, string[]>;
  topics: Record<string, { keywords: string[]; symbols: string[] }>;
  high_impact: string[];
  high_impact_moves?: string[];
  exclude?: Record<string, string[]>;
}

export interface Match {
  symbols: string[];
  direct: string[];
  topics: string[];
  highImpact: boolean;
  highImpactHits: string[];
}

const CS_PREFIX = "cs:";
const esc = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Wariant slowa bez rozrozniania wielkosci liter (JS nie ma flagi lokalnej jak (?i:...) w Pythonie). */
function anyCase(w: string): string {
  let out = "";
  for (const ch of w.toLowerCase()) {
    const up = ch.toUpperCase();
    out += up !== ch && up.length === ch.length ? `[${esc(ch)}${esc(up)}]` : esc(ch);
  }
  return out;
}

/**
 * Jedno wyrazenie dla listy slow. Wpis "cs:Fed" jest dopasowywany z rozroznieniem wielkosci liter:
 * skroty (Fed, ETH, BoJ, LNG, CPI) sa wieloznaczne jako zwykle slowa. Pozostale wpisy ignoruja wielkosc liter.
 */
function pattern(words: string[], global = false): RegExp {
  const alts = [...words].sort((a, b) => b.length - a.length)
    .map((w) => w.startsWith(CS_PREFIX) ? esc(w.slice(CS_PREFIX.length)) : anyCase(w));
  // Granice slowa swiadome Unicode (\b w JS nie zna polskich znakow) i dzialajace dla fraz typu "opec+".
  return new RegExp(`(?<![\\p{L}\\p{N}_])(?:${alts.join("|")})(?![\\p{L}\\p{N}_])`, global ? "gu" : "u");
}

function hits(p: RegExp | null, text: string): string[] {
  if (!p) return [];
  return [...new Set([...text.matchAll(p)].map((m) => m[0].toLowerCase()))].sort();
}

/**
 * Przypisuje tekst do symboli XTB: wprost (slowa instrumentu) i posrednio (tematy makro). Logika 1:1 z Pythonem:
 * `exclude` uniewaznia dopasowanie wprost (np. "gold medal"), frazy wysokiej wagi sa szukane tylko w tytule,
 * a `high_impact_moves` (surge, plunge...) licza sie wylacznie razem z dopasowaniem wprost.
 */
export class KeywordMapper {
  private direct: [string, RegExp][];
  private exclude: Record<string, RegExp>;
  private topics: [string, RegExp, string[]][];
  private highImpact: RegExp | null;
  private highImpactMoves: RegExp | null;

  constructor(cfg: KeywordConfig) {
    this.direct = Object.entries(cfg.instruments).filter(([, w]) => w.length).map(([s, w]) => [s, pattern(w)]);
    this.exclude = Object.fromEntries(Object.entries(cfg.exclude ?? {}).filter(([, w]) => w.length).map(([s, w]) => [s, pattern(w)]));
    this.topics = Object.entries(cfg.topics).map(([n, t]) => [n, pattern(t.keywords), t.symbols]);
    this.highImpact = cfg.high_impact.length ? pattern(cfg.high_impact, true) : null;
    this.highImpactMoves = cfg.high_impact_moves?.length ? pattern(cfg.high_impact_moves, true) : null;
  }

  /** Dopasowuje tekst (tytul + opis). `title` zaweza szukanie fraz wysokiej wagi do samego tytulu. */
  match(text: string, title?: string): Match {
    const head = title ?? text;
    const direct = this.direct.filter(([s, p]) => p.test(text) && !(this.exclude[s]?.test(text))).map(([s]) => s);
    const hit = this.topics.filter(([, p]) => p.test(text));
    const symbols = [...direct];
    for (const [, , syms] of hit) for (const s of syms) if (!symbols.includes(s)) symbols.push(s);
    const found = hits(this.highImpact, head);
    if (direct.length) for (const h of hits(this.highImpactMoves, head)) if (!found.includes(h)) found.push(h);
    return { symbols, direct, topics: hit.map(([n]) => n), highImpact: found.length > 0, highImpactHits: found };
  }
}
