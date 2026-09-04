-- Make the service-only access model explicit to the RLS policy linter.

create policy "service role manages memory quarantine"
on public.memory_quarantine
for all
to service_role
using (true)
with check (true);
