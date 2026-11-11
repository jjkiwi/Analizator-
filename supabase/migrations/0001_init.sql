-- Analizator CFD: schemat wspolnej bazy (Supabase / Postgres).
-- Pisza: funkcje brzegowe (newsy, makro) i tor wolny z GitHub Actions (sygnaly, bias, zdrowie zrodel).
-- Czyta: panel PWA (zalogowany uzytkownik). Klucz service_role omija RLS, wiec nie moze trafic do przegladarki.

create table if not exists signals (
    id            bigint generated always as identity primary key,
    symbol        text not null,
    strategy      text not null,
    interval      text not null,
    time          timestamptz not null,
    side          smallint not null check (side in (-1, 1)),
    ref_price     double precision not null,
    stop_loss     double precision not null,
    take_profit   double precision not null,
    rationale     text,
    score         double precision,
    context       jsonb not null default '{}'::jsonb,
    status        text not null default 'open' check (status in ('open', 'tp', 'sl', 'expired')),
    resolved_time timestamptz,
    r_result      double precision,
    created_at    timestamptz not null default now(),
    unique (symbol, strategy, interval, time)
);
create index if not exists signals_time on signals (time desc);

create table if not exists news (
    id          text primary key,
    source      text,
    title       text not null,
    summary     text,
    url         text,
    published   timestamptz,
    fetched     timestamptz not null default now(),
    norm_title  text,
    symbols     text not null default '',      -- symbole rozdzielone przecinkiem
    importance  smallint,                      -- null: bez instrumentu, 0: duplikat, 1-3: waga
    direction   jsonb,                         -- {symbol: -1|0|1}
    reason      text,
    classifier  text,
    alerted     boolean not null default false
);
create index if not exists news_fetched on news (fetched desc);

create table if not exists macro_events (
    id             text primary key,
    time           timestamptz not null,
    country        text,
    name           text not null,
    importance     smallint,
    actual         double precision,
    forecast       double precision,
    previous       double precision,
    unit           text,
    alerted_before boolean not null default false,
    alerted_after  boolean not null default false
);
create index if not exists macro_time on macro_events (time);

create table if not exists fundamental_bias (
    symbol     text primary key,
    bias       double precision not null,
    components jsonb,
    updated    timestamptz not null
);

create table if not exists source_health (
    source          text primary key,
    last_ok         timestamptz,
    last_error      text,
    last_error_time timestamptz,
    fail_streak     integer not null default 0
);

-- wiadomosci odlozone na czas ciszy nocnej
create table if not exists outbox (
    id      bigint generated always as identity primary key,
    created timestamptz not null default now(),
    text    text not null
);

-- stan toru szybkiego: kiedy ostatnio pobrano dany feed, kiedy odswiezono kalendarz itd.
create table if not exists kv_state (
    key     text primary key,
    value   jsonb not null,
    updated timestamptz not null default now()
);

-- RLS: wszystko zamkniete; odczyt tylko dla zalogowanych (panel). Zapis wylacznie kluczem service_role.
do $$
declare t text;
begin
    foreach t in array array['signals', 'news', 'macro_events', 'fundamental_bias', 'source_health', 'outbox', 'kv_state'] loop
        execute format('alter table %I enable row level security', t);
    end loop;
    foreach t in array array['signals', 'news', 'macro_events', 'fundamental_bias', 'source_health'] loop
        execute format('drop policy if exists "odczyt dla zalogowanych" on %I', t);
        execute format('create policy "odczyt dla zalogowanych" on %I for select to authenticated using (true)', t);
    end loop;
end $$;
