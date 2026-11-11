// Narzedzia tekstowe wspolne dla toru szybkiego. Logika 1:1 z wersja w Pythonie (src/cfd/news).

export function normalizeTitle(title: string): string {
  return title.toLowerCase().replace(/[^\p{L}\p{N}_\s&+%.]/gu, " ").replace(/\s+/g, " ").trim();
}

function tokens(norm: string): Set<string> {
  return new Set(norm.split(" ").filter((t) => t.length > 2));
}

/** Ten sam news z innego zrodla: identyczny albo prawie identyczny tytul (Jaccard >= threshold). */
export function isDuplicate(norm: string, recent: string[], threshold = 0.8): boolean {
  const a = tokens(norm);
  if (a.size === 0) return false;
  for (const other of recent) {
    if (other === norm) return true;
    const b = tokens(other);
    if (b.size === 0) continue;
    let inter = 0;
    for (const t of a) if (b.has(t)) inter++;
    if (inter / (a.size + b.size - inter) >= threshold) return true;
  }
  return false;
}

export async function shortHash(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decodeEntities(text: string): string {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, code: string) => {
    if (code[0] === "#") {
      const n = code[1].toLowerCase() === "x" ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
      return Number.isFinite(n) && n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : m;
    }
    return ENTITIES[code.toLowerCase()] ?? m;
  });
}

/** Usuwa znaczniki HTML i dekoduje encje (dwukrotnie, bo RSS czesto koduje HTML w encjach). */
export function cleanText(raw: string | undefined): string {
  if (!raw) return "";
  let s = raw.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1");
  s = decodeEntities(s).replace(/<[^>]+>/g, " ");
  return decodeEntities(s).replace(/\s+/g, " ").trim();
}
