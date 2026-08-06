-- ##################################################
-- Distinguish staff vs. reporter authored status-history entries, and
-- allow reporter entries to carry no status (a note, not a transition).
-- Apply after 0001_tickets.sql and 0002_ticket_status_updates.sql.
-- ##################################################

create type public.ticket_update_author as enum ('staff', 'reporter');

alter table public.ticket_status_updates
    add column author public.ticket_update_author not null default 'staff';

-- Reporter-submitted entries are informational notes, not lifecycle
-- transitions — they don't set a new status, so the column must allow
-- null for them. Staff-authored rows (the existing NOT NULL behaviour)
-- are unaffected; the API always supplies a status for those.
alter table public.ticket_status_updates
    alter column status drop not null;

create index ticket_status_updates_author_idx
    on public.ticket_status_updates (ticket_id, author);
