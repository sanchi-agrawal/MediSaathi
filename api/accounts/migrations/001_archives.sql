-- Apply manually in your Supabase project's SQL editor. No service-role key in app.
create table if not exists public.prescription_archives (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id) on delete cascade,
 version uuid not null default gen_random_uuid(),
 schema_version integer not null check (schema_version = 1),
 payload_ciphertext text not null check (length(payload_ciphertext) between 50 and 24000000),
 created_at timestamptz not null default now(),
 expires_at timestamptz not null check (expires_at > created_at and expires_at <= created_at + interval '30 days')
);
create index if not exists prescription_archives_owner_created on public.prescription_archives(owner_id,created_at desc);
alter table public.prescription_archives enable row level security;
alter table public.prescription_archives force row level security;
revoke all on public.prescription_archives from anon;
revoke all on public.prescription_archives from authenticated;
grant select, insert, delete on public.prescription_archives to authenticated;
create policy archive_read_own on public.prescription_archives for select to authenticated
 using ((select auth.uid()) = owner_id and expires_at > now());
create policy archive_insert_own on public.prescription_archives for insert to authenticated
 with check ((select auth.uid()) = owner_id and created_at <= now() and created_at > now() - interval '1 minute'
 and expires_at <= now() + interval '30 days');
create policy archive_delete_own on public.prescription_archives for delete to authenticated
 using ((select auth.uid()) = owner_id);
-- No UPDATE policy: immutable versions. Configure physical deletion/backups separately.
