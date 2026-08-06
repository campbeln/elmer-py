-- ##################################################
-- Ticket status history — one row per status change, with optional message
-- Apply after 0001_tickets.sql.
-- ##################################################

create table public.ticket_status_updates (
    id          uuid primary key default gen_random_uuid(),
    ticket_id   uuid not null references public.tickets(id) on delete cascade,
    status      public.ticket_status not null,
    message     text check (message is null or char_length(message) <= 2000),
    created_at  timestamptz not null default now()
);

create index ticket_status_updates_ticket_idx
    on public.ticket_status_updates (ticket_id, created_at desc);

-- Same posture as tickets: RLS on, no public policies — all access flows
-- through the Elmer API with the service-role key. The public status page
-- reads through GET /tickets/:id/public, which limits the fields exposed.
alter table public.ticket_status_updates enable row level security;
