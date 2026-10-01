create or replace function private.shine_me_owner_state_apply_v1(
  p_owner_id text,
  p_expected_revision bigint,
  p_state jsonb
)
returns table (
  owner_id text,
  revision bigint,
  updated_at timestamptz
)
language plpgsql
set search_path = ''
as $$
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;

  if p_state is null then
    raise exception 'STATE_REQUIRED';
  end if;

  if p_expected_revision = 0 then
    return query
    insert into public.shine_me_owner_state as s(owner_id, state, revision)
    values (p_owner_id, p_state, 1)
    on conflict on constraint shine_me_owner_state_pkey do nothing
    returning s.owner_id, s.revision, s.updated_at;

    if found then
      return;
    end if;

    raise exception 'REVISION_CONFLICT';
  end if;

  return query
  update public.shine_me_owner_state s
     set state = p_state,
         revision = s.revision + 1,
         updated_at = now()
   where s.owner_id = p_owner_id
     and s.revision = p_expected_revision
  returning s.owner_id, s.revision, s.updated_at;

  if not found then
    raise exception 'REVISION_CONFLICT';
  end if;
end;
$$;
