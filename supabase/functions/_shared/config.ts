// Typowany dostep do config.json (plik generowany poleceniem `cfd export-config` z plikow YAML).
import raw from "./config.json" with { type: "json" };
import type { Provider } from "./classify.ts";
import type { MacroRule } from "./macro.ts";
import type { KeywordConfig } from "./mapper.ts";
import type { QuietHours } from "./notify.ts";
import type { FeedConfig } from "./pipeline.ts";

export interface AppConfig {
  symbols: string[];
  feeds: FeedConfig[];
  keywords: KeywordConfig;
  macro_rules: MacroRule[];
  llm: { timeout_seconds: number; providers: Provider[] };
  news: { alert_min_importance: number; max_age_hours: number; use_llm: boolean };
  macro: { refresh_minutes: number; alert_minutes_before: number; alert_min_importance: number };
  quiet_hours: QuietHours;
}

export const config = raw as unknown as AppConfig;
