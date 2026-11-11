export interface KeywordConfig {
  instruments: Record<string, string[]>;
  topics: Record<string, { keywords: string[]; symbols: string[] }>;
  high_impact: string[];
}

export interface Match {
  symbols: string[];
  direct: string[];
  topics: string[];
  highImpact: boolean;
}

function pattern(words: string[]): RegExp {
  const alts = words.map((w) => w.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a, b) => b.length - a.length);
  // Granice slowa swiadome Unicode (\b w JS nie zna polskich znakow) i dzialajace dla fraz typu "opec+".
  return new RegExp(`(?<![\\p{L}\\p{N}_])(?:${alts.join("|")})(?![\\p{L}\\p{N}_])`, "iu");
}

/** Przypisuje tekst do symboli XTB: wprost (slowa instrumentu) i posrednio (tematy makro). */
export class KeywordMapper {
  private direct: [string, RegExp][];
  private topics: [string, RegExp, string[]][];
  private highImpact: RegExp | null;

  constructor(cfg: KeywordConfig) {
    this.direct = Object.entries(cfg.instruments).filter(([, w]) => w.length).map(([s, w]) => [s, pattern(w)]);
    this.topics = Object.entries(cfg.topics).map(([n, t]) => [n, pattern(t.keywords), t.symbols]);
    this.highImpact = cfg.high_impact.length ? pattern(cfg.high_impact) : null;
  }

  match(text: string): Match {
    const direct = this.direct.filter(([, p]) => p.test(text)).map(([s]) => s);
    const hit = this.topics.filter(([, p]) => p.test(text));
    const symbols = [...direct];
    for (const [, , syms] of hit) for (const s of syms) if (!symbols.includes(s)) symbols.push(s);
    return { symbols, direct, topics: hit.map(([n]) => n), highImpact: this.highImpact?.test(text) ?? false };
  }
}
