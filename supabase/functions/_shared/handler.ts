/** Wspolna obsluga wywolania: sprawdzenie sekretu z naglowka i jednolita odpowiedz JSON. */
export function guarded(run: () => Promise<Record<string, unknown>>): (req: Request) => Promise<Response> {
  return async (req) => {
    const secret = Deno.env.get("CRON_SECRET");
    if (!secret || req.headers.get("x-cron-secret") !== secret) {
      return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401, headers: { "Content-Type": "application/json" } });
    }
    try {
      return new Response(JSON.stringify({ ok: true, ...(await run()) }), { headers: { "Content-Type": "application/json" } });
    } catch (err) {
      console.error(err);
      return new Response(JSON.stringify({ ok: false, error: String(err).slice(0, 300) }), { status: 500, headers: { "Content-Type": "application/json" } });
    }
  };
}

export function requireEnv(name: string): string {
  const v = Deno.env.get(name);
  if (!v) throw new Error(`brak zmiennej ${name}`);
  return v;
}
