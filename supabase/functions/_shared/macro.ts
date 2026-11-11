export interface MacroEvent {
  id?: string;
  time: Date;
  country: string;
  name: string;
  importance: number;
  actual: number | null;
  forecast: number | null;
  previous: number | null;
}

export interface MacroRule {
  name: string;
  country?: string;
  match: string[];
  effects: Record<string, number>;
}

const MULT: Record<string, number> = { "": 1, "%": 1, K: 1e3, M: 1e6, B: 1e9, T: 1e12 };

/** '0.3%' -> 0.3, '215K' -> 215000, '<0.1%' -> 0.1, '' -> null. */
export function parseValue(text: unknown): number | null {
  if (text === null || text === undefined) return null;
  if (typeof text === "number") return Number.isFinite(text) ? text : null;
  const m = String(text).replace(/[<>]/g, "").replace("\u2212", "-").match(/^\s*([-+]?\d+(?:[.,]\d+)?)\s*([KMBT%]?)/i);
  if (!m) return null;
  return parseFloat(m[1].replace(",", ".")) * MULT[m[2].toUpperCase()];
}

const IMPACT: Record<string, number> = { high: 3, medium: 2, low: 1 };

/** Tygodniowy kalendarz w JSON (feed uzywany przez ForexFactory). Format NIESPRAWDZONY na zywych danych. */
export function parseFairEconomy(rows: unknown): MacroEvent[] {
  if (!Array.isArray(rows)) return [];
  const out: MacroEvent[] = [];
  for (const row of rows) {
    const impact = IMPACT[String(row?.impact ?? "").toLowerCase()];
    if (!impact || !row?.date || !row?.title) continue; // swieta i wpisy bez godziny
    const when = new Date(String(row.date));
    if (Number.isNaN(when.getTime())) continue;
    out.push({
      time: when,
      country: String(row.country ?? "").toUpperCase(),
      name: String(row.title).trim(),
      importance: impact,
      actual: parseValue(row.actual),
      forecast: parseValue(row.forecast),
      previous: parseValue(row.previous),
    });
  }
  return out;
}

export function effectsFor(ev: MacroEvent, rules: MacroRule[]): Record<string, number> {
  const name = ev.name.toLowerCase();
  for (const r of rules) {
    if ((!r.country || r.country === ev.country) && r.match.some((m) => name.includes(m))) return { ...r.effects };
  }
  return {};
}

/** Kierunek pierwszej reakcji per symbol dla odczytu innego niz prognoza. Pusty obiekt = brak niespodzianki. */
export function surpriseEffects(ev: MacroEvent, rules: MacroRule[]): Record<string, number> {
  if (ev.actual === null || ev.forecast === null || ev.actual === ev.forecast) return {};
  const sign = ev.actual > ev.forecast ? 1 : -1;
  const out: Record<string, number> = {};
  for (const [s, d] of Object.entries(effectsFor(ev, rules))) out[s] = d * sign;
  return out;
}

/** Identyfikator zgodny z wersja w Pythonie: czas do minuty (UTC) | kraj | nazwa, malymi literami. */
export function eventKey(ev: MacroEvent): string {
  return `${ev.time.toISOString().slice(0, 16)}|${ev.country}|${ev.name}`.toLowerCase();
}
