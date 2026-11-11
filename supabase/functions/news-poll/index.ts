// Tor szybki: newsy. Wywolywane co minute przez pg_cron (patrz supabase/cron.sql.template).
import { config } from "../_shared/config.ts";
import { restDb } from "../_shared/db.ts";
import { guarded, requireEnv } from "../_shared/handler.ts";
import { KeywordMapper } from "../_shared/mapper.ts";
import { telegramSender } from "../_shared/notify.ts";
import { runNews } from "../_shared/pipeline.ts";
import { fetchFeed } from "../_shared/rss.ts";

const mapper = new KeywordMapper(config.keywords);

Deno.serve(guarded(() =>
  runNews(config.feeds, {
    db: restDb(requireEnv("SUPABASE_URL"), requireEnv("SUPABASE_SERVICE_ROLE_KEY")),
    send: telegramSender(Deno.env.get("TELEGRAM_BOT_TOKEN"), Deno.env.get("TELEGRAM_CHAT_ID")),
    mapper,
    // Ollama dziala tylko lokalnie, wiec w chmurze pomijamy dostawcow z adresem localhost.
    providers: config.llm.providers.filter((p) => !p.base_url.includes("localhost")),
    getKey: (env) => Deno.env.get(env),
    fetchFeed,
    quiet: config.quiet_hours,
    settings: config.news,
    healthAlertAfter: 3,
    maxFeedsPerRun: 12,
    maxLlmPerRun: 8,
  })
));
