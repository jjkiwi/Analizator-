// Tor szybki: kalendarz makro. Wywolywane co minute przez pg_cron.
import { config } from "../_shared/config.ts";
import { restDb } from "../_shared/db.ts";
import { guarded, requireEnv } from "../_shared/handler.ts";
import { parseFairEconomy } from "../_shared/macro.ts";
import { telegramSender } from "../_shared/notify.ts";
import { runMacro } from "../_shared/pipeline.ts";

const CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"; // NIESPRAWDZONE, patrz zadanie D1

Deno.serve(guarded(() =>
  runMacro({
    db: restDb(requireEnv("SUPABASE_URL"), requireEnv("SUPABASE_SERVICE_ROLE_KEY")),
    send: telegramSender(Deno.env.get("TELEGRAM_BOT_TOKEN"), Deno.env.get("TELEGRAM_CHAT_ID")),
    rules: config.macro_rules,
    symbols: new Set(config.symbols),
    quiet: config.quiet_hours,
    settings: config.macro,
    fetchCalendar: async () => {
      const resp = await fetch(CALENDAR_URL, { signal: AbortSignal.timeout(10000), headers: { "User-Agent": "analizator-cfd/0.3" } });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return parseFairEconomy(await resp.json());
    },
  })
));
