// Minimalny klient PostgREST (bez zewnetrznych bibliotek). Uzywa klucza service_role: tylko po stronie serwera.

export interface Db {
  select<T = Record<string, unknown>>(table: string, params: Record<string, string>): Promise<T[]>;
  insert(table: string, rows: Record<string, unknown>[]): Promise<void>;
  upsert(table: string, rows: Record<string, unknown>[], onConflict: string, ignoreDuplicates?: boolean): Promise<void>;
  update(table: string, filter: Record<string, string>, values: Record<string, unknown>): Promise<void>;
  remove(table: string, filter: Record<string, string>): Promise<void>;
}

export function restDb(url: string, serviceKey: string): Db {
  const base = url.replace(/\/+$/, "") + "/rest/v1";
  const headers = { apikey: serviceKey, Authorization: `Bearer ${serviceKey}`, "Content-Type": "application/json" };

  async function call(method: string, table: string, params: Record<string, string>, body?: unknown, prefer?: string) {
    const qs = new URLSearchParams(params).toString();
    const resp = await fetch(`${base}/${table}${qs ? "?" + qs : ""}`, {
      method,
      signal: AbortSignal.timeout(15000),
      headers: prefer ? { ...headers, Prefer: prefer } : headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`${method} ${table}: HTTP ${resp.status} ${(await resp.text()).slice(0, 200)}`);
    return resp;
  }

  return {
    async select(table, params) {
      return await (await call("GET", table, params)).json();
    },
    async insert(table, rows) {
      if (rows.length) await call("POST", table, {}, rows, "return=minimal");
    },
    async upsert(table, rows, onConflict, ignoreDuplicates = false) {
      if (!rows.length) return;
      const mode = ignoreDuplicates ? "resolution=ignore-duplicates" : "resolution=merge-duplicates";
      await call("POST", table, { on_conflict: onConflict }, rows, `${mode},return=minimal`);
    },
    async update(table, filter, values) {
      await call("PATCH", table, filter, values, "return=minimal");
    },
    async remove(table, filter) {
      await call("DELETE", table, filter, undefined, "return=minimal");
    },
  };
}

export async function getState<T>(db: Db, key: string, fallback: T): Promise<T> {
  const rows = await db.select<{ value: T }>("kv_state", { key: `eq.${key}`, select: "value" });
  return rows.length ? rows[0].value : fallback;
}

export async function setState(db: Db, key: string, value: unknown): Promise<void> {
  await db.upsert("kv_state", [{ key, value, updated: new Date().toISOString() }], "key");
}

export async function healthOk(db: Db, source: string): Promise<void> {
  await db.upsert("source_health", [{ source, last_ok: new Date().toISOString(), fail_streak: 0 }], "source");
}

/** Zapisuje porazke zrodla. Zwraca nowa dlugosc serii porazek. */
export async function healthFail(db: Db, source: string, error: string): Promise<number> {
  const rows = await db.select<{ fail_streak: number }>("source_health", { source: `eq.${source}`, select: "fail_streak" });
  const streak = (rows[0]?.fail_streak ?? 0) + 1;
  await db.upsert("source_health", [{
    source, last_error: error.slice(0, 300), last_error_time: new Date().toISOString(), fail_streak: streak,
  }], "source");
  return streak;
}
