-- ##################################################
-- Elmer support tickets — Supabase schema
-- Apply via the Supabase SQL editor or `supabase db push`.
-- ##################################################

-- Priority follows the published severity ladder:
--   P1 Critical    Complete production service outage, active security
--                  incident, data loss, or failure of core production
--                  functionality with material business impact and no
--                  reasonable workaround.
--   P2 High        Major degradation of core functionality or partial loss
--                  of production service that materially impacts use of
--                  the Platform.
--   P3 Medium      Non-critical issue with limited impact, minor
--                  degradation, or issue where a reasonable workaround is
--                  available.
--   P4 Low/Request General inquiry, cosmetic issue, documentation
--                  question, enhancement request, or other issue with no
--                  material operational impact.

create type public.ticket_priority as enum ('P1', 'P2', 'P3', 'P4');

create type public.ticket_status as enum (
    'open', 'acknowledged', 'in_progress', 'resolved', 'closed'
);

create table public.tickets (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),

    -- reporter
    name        text not null check (char_length(name) between 1 and 200),
    email       text not null check (email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
    company     text,

    -- ticket body
    subject     text not null check (char_length(subject) between 1 and 300),
    description text not null check (char_length(description) between 1 and 10000),
    priority    public.ticket_priority not null default 'P4',
    status      public.ticket_status  not null default 'open',

    -- correlation with Elmer's X-Request-Id tracing
    trace_id    text
);

create index tickets_status_idx   on public.tickets (status);
create index tickets_priority_idx on public.tickets (priority);
create index tickets_created_idx  on public.tickets (created_at desc);

-- keep updated_at fresh
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end $$;

create trigger tickets_touch_updated_at
    before update on public.tickets
    for each row execute function public.touch_updated_at();

-- Row Level Security: the API talks to Supabase with the service-role key,
-- which bypasses RLS. Enabling RLS with no permissive policies means the
-- anon/public key can neither read nor write tickets directly — all access
-- must flow through the Elmer API.
alter table public.tickets enable row level security;
