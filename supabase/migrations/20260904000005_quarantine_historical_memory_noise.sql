-- Preserve every historical row while excluding deterministic noise from recall.

create table if not exists public.memory_quarantine (
  source_table text not null,
  source_id text not null,
  reason_code text not null check (reason_code in (
    'historical_question',
    'failed_recall_answer',
    'same_table_exact_duplicate',
    'oversized_composite'
  )),
  content_hash text not null,
  content_length integer not null,
  source_role text not null default 'unknown',
  source_reference bigint,
  previous_status text,
  quarantined_at timestamptz not null default now(),
  restored_at timestamptz,
  primary key (source_table, source_id, reason_code)
);

alter table public.memory_quarantine enable row level security;

revoke all on table public.memory_quarantine from public;
revoke all on table public.memory_quarantine from anon;
revoke all on table public.memory_quarantine from authenticated;
grant select, insert, update on table public.memory_quarantine to service_role;

create index if not exists memory_quarantine_active_lookup_idx
  on public.memory_quarantine (source_table, source_id)
  where restored_at is null;

-- Raw history remains the immutable source of truth. The ledger only removes
-- questions and known failed-recall replies from normal evidence retrieval.
insert into public.memory_quarantine (
  source_table, source_id, reason_code, content_hash, content_length,
  source_role, source_reference, previous_status
)
select
  'raw_catchall', r.id::text, reasons.reason_code,
  md5(coalesce(r.content, '')), length(coalesce(r.content, '')),
  coalesce(r.role, 'unknown'), r.id, null
from public.raw_catchall r
cross join lateral (
  values
    (case when
      rtrim(coalesce(r.content, '')) like '%?'
      and lower(coalesce(r.content, '')) !~
        '(remember|save this|save that|mark today|note that|record this|record that|please store|add to memory)'
      then 'historical_question' end),
    (case when lower(coalesce(r.content, '')) ~
      '(do not provide an exact|does not provide an exact|currently incomplete|information is incomplete|records are incomplete|no exact date|no record of|don''t have that information|do not have that information)'
      then 'failed_recall_answer' end)
) reasons(reason_code)
where reasons.reason_code is not null
on conflict do nothing;

-- Organised memories remain untouched in their original tables. The ledger is
-- a reversible overlay: setting restored_at immediately makes a row eligible.
with organised as (
  select 'memory_family'::text table_name, id::text source_id, content body,
         memory_status previous_status, raw_id::bigint source_ref
  from public.memory_family
  union all select 'memory_identity', id::text, content, memory_status, raw_id from public.memory_identity
  union all select 'memory_relationships', id::text, content, memory_status, raw_id from public.memory_relationships
  union all select 'memory_recovery', id::text, content, memory_status, raw_id from public.memory_recovery
  union all select 'memory_health', id::text, content, memory_status, raw_id from public.memory_health
  union all select 'memory_project_l', id::text, content, memory_status, raw_id from public.memory_project_l
  union all select 'memory_general', id::text, content, memory_status, raw_id from public.memory_general
  union all select 'memory_sport', id::text, content, memory_status, raw_id from public.memory_sport
  union all select 'memory_work', id::text, content, memory_status, raw_id from public.memory_work
  union all select 'memory_research', id::text, coalesce(summary, question), memory_status, null::bigint from public.memory_research
  union all select 'episodic_memories', id::text, summary, memory_status, source_reference from public.episodic_memories
  union all select 'identity_anchors', id::text, value, memory_status, source_reference from public.identity_anchors
)
insert into public.memory_quarantine (
  source_table, source_id, reason_code, content_hash, content_length,
  source_role, source_reference, previous_status
)
select
  o.table_name, o.source_id, reasons.reason_code,
  md5(coalesce(o.body, '')), length(coalesce(o.body, '')),
  coalesce(r.role, 'unlinked'), o.source_ref, o.previous_status
from organised o
left join public.raw_catchall r on r.id = o.source_ref
cross join lateral (
  values
    (case when
      o.table_name <> 'memory_research'
      and rtrim(coalesce(o.body, '')) like '%?'
      and lower(coalesce(o.body, '')) !~
        '(remember|save this|save that|mark today|note that|record this|record that|please store|add to memory)'
      then 'historical_question' end),
    (case when lower(coalesce(o.body, '')) ~
      '(do not provide an exact|does not provide an exact|currently incomplete|information is incomplete|records are incomplete|no exact date|no record of|don''t have that information|do not have that information)'
      then 'failed_recall_answer' end),
    (case when length(coalesce(o.body, '')) > 20000 and o.source_ref is not null
      then 'oversized_composite' end)
) reasons(reason_code)
where reasons.reason_code is not null
on conflict do nothing;

-- Collapse only exact duplicates inside the same organised table. Cross-table
-- copies are retained because their domain classification may be meaningful.
with organised as (
  select 'memory_family'::text table_name, id::text source_id, content body,
         memory_status previous_status, raw_id::bigint source_ref, created_at
  from public.memory_family
  union all select 'memory_identity', id::text, content, memory_status, raw_id, created_at from public.memory_identity
  union all select 'memory_relationships', id::text, content, memory_status, raw_id, created_at from public.memory_relationships
  union all select 'memory_recovery', id::text, content, memory_status, raw_id, created_at from public.memory_recovery
  union all select 'memory_health', id::text, content, memory_status, raw_id, created_at from public.memory_health
  union all select 'memory_project_l', id::text, content, memory_status, raw_id, created_at from public.memory_project_l
  union all select 'memory_general', id::text, content, memory_status, raw_id, created_at from public.memory_general
  union all select 'memory_sport', id::text, content, memory_status, raw_id, created_at from public.memory_sport
  union all select 'memory_work', id::text, content, memory_status, raw_id, created_at from public.memory_work
), ranked as (
  select
    o.*,
    coalesce(r.role, 'unlinked') source_role,
    md5(lower(regexp_replace(btrim(coalesce(o.body, '')), '\s+', ' ', 'g'))) fingerprint,
    row_number() over (
      partition by o.table_name,
        md5(lower(regexp_replace(btrim(coalesce(o.body, '')), '\s+', ' ', 'g')))
      order by
        case coalesce(r.role, 'unlinked') when 'user' then 3 when 'assistant' then 2 else 1 end desc,
        case lower(coalesce(o.previous_status, '')) when 'canonical' then 3 when 'complete' then 2 else 1 end desc,
        (o.source_ref is not null) desc,
        o.created_at asc nulls last,
        o.source_id asc
    ) duplicate_rank
  from organised o
  left join public.raw_catchall r on r.id = o.source_ref
  where btrim(coalesce(o.body, '')) <> ''
)
insert into public.memory_quarantine (
  source_table, source_id, reason_code, content_hash, content_length,
  source_role, source_reference, previous_status
)
select
  table_name, source_id, 'same_table_exact_duplicate',
  md5(coalesce(body, '')), length(coalesce(body, '')),
  source_role, source_ref, previous_status
from ranked
where duplicate_rank > 1
on conflict do nothing;

create or replace function public.restore_project_l_memory_quarantine(
  p_source_table text,
  p_source_id text,
  p_reason_code text default null
)
returns integer
language plpgsql
volatile
security invoker
set search_path = ''
as $function$
declare
  v_restored integer;
begin
  update public.memory_quarantine
  set restored_at = now()
  where source_table = p_source_table
    and source_id = p_source_id
    and restored_at is null
    and (p_reason_code is null or reason_code = p_reason_code);
  get diagnostics v_restored = row_count;
  return v_restored;
end;
$function$;

revoke all on function public.restore_project_l_memory_quarantine(text, text, text) from public;
revoke all on function public.restore_project_l_memory_quarantine(text, text, text) from anon;
revoke all on function public.restore_project_l_memory_quarantine(text, text, text) from authenticated;
grant execute on function public.restore_project_l_memory_quarantine(text, text, text) to service_role;

create or replace function public.search_project_l_memory(
  p_terms text[],
  p_raw_limit integer default 200,
  p_memory_limit integer default 200
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
as $function$
declare
  v_query tsquery;
  v_raw jsonb := '[]'::jsonb;
  v_memories jsonb := '[]'::jsonb;
  v_union_sql text := '';
  v_hydrate_sql text := '';
  v_sql text;
  v_table text;
  v_source_column text;
  v_kind text;
  v_row_expression text;
  v_priority_expression text;
begin
  select to_tsquery(
    'simple'::regconfig,
    string_agg(quote_literal(token) || ':*', ' | ' order by token)
  )
  into v_query
  from (
    select distinct lower(parts[1]) as token
    from unnest(coalesce(p_terms, array[]::text[])) as supplied(term)
    cross join lateral regexp_matches(supplied.term, '[[:alnum:]]+', 'g') as parts
    where length(parts[1]) >= 2
    limit 64
  ) tokens;

  if v_query is null then
    return jsonb_build_object('raw', v_raw, 'memories', v_memories);
  end if;

  select coalesce(jsonb_agg(row_data order by rank desc, created_at desc), '[]'::jsonb)
  into v_raw
  from (
    select jsonb_build_object(
             'id', r.id, 'created_at', r.created_at, 'role', r.role,
             'source', r.source,
             'content', case
               when length(r.content) > 8000 then regexp_replace(
                 ts_headline('simple'::regconfig, r.content, v_query,
                   'MaxWords=160, MinWords=40, ShortWord=2, MaxFragments=3, FragmentDelimiter= ... '),
                 '</?b>', '', 'g')
               else r.content
             end
           ) row_data,
           ts_rank_cd(r.retrieval_fts, v_query) rank,
           r.created_at
    from public.raw_catchall r
    where r.retrieval_fts @@ v_query
      and not exists (
        select 1 from public.memory_quarantine q
        where q.source_table = 'raw_catchall'
          and q.source_id = r.id::text
          and q.restored_at is null
      )
    order by rank desc, r.created_at desc
    limit least(greatest(p_raw_limit, 1), 500)
  ) ranked_raw;

  for v_table, v_source_column, v_kind in
    values
      ('memory_family', 'raw_id', 'common'),
      ('memory_identity', 'raw_id', 'common'),
      ('memory_relationships', 'raw_id', 'common'),
      ('memory_recovery', 'raw_id', 'common'),
      ('memory_health', 'raw_id', 'common'),
      ('memory_project_l', 'raw_id', 'common'),
      ('memory_general', 'raw_id', 'general'),
      ('memory_sport', 'raw_id', 'common'),
      ('memory_work', 'raw_id', 'common'),
      ('memory_research', '', 'research'),
      ('episodic_memories', 'source_reference', 'episodic'),
      ('identity_anchors', 'source_reference', 'anchor')
  loop
    if v_union_sql <> '' then
      v_union_sql := v_union_sql || ' union all ';
      v_hydrate_sql := v_hydrate_sql || ' union all ';
    end if;

    if v_kind = 'common' then
      v_row_expression := $expression$jsonb_build_object(
        'id', m.id, 'raw_id', m.raw_id, 'content', m.content,
        'primary_subject', m.primary_subject, 'subjects', m.subjects,
        'relationships', m.relationships, 'values', m.values,
        'patterns', m.patterns, 'preferences', m.preferences,
        'importance', m.importance, 'salience', m.salience,
        'anchor', m.anchor, 'created_at', m.created_at,
        'memory_status', m.memory_status
      )$expression$;
      v_priority_expression := 'coalesce(m.importance, 0) + coalesce(m.salience, 0)';
    elsif v_kind = 'general' then
      v_row_expression := $expression$jsonb_build_object(
        'id', m.id, 'raw_id', m.raw_id, 'content', m.content,
        'primary_subject', m.primary_subject, 'subjects', m.subjects,
        'relationships', m.relationships, 'values', m.values,
        'preferences', m.preferences, 'importance', m.importance,
        'salience', m.salience, 'anchor', m.anchor,
        'created_at', m.created_at, 'memory_status', m.memory_status
      )$expression$;
      v_priority_expression := 'coalesce(m.importance, 0) + coalesce(m.salience, 0)';
    elsif v_kind = 'research' then
      v_row_expression := $expression$jsonb_build_object(
        'id', m.id, 'question', m.question, 'summary', m.summary,
        'meaning', m.meaning, 'relationships', m.relationships,
        'importance', m.importance, 'salience', m.salience,
        'anchor', m.anchor, 'confidence', m.confidence,
        'created_at', m.created_at, 'memory_status', m.memory_status
      )$expression$;
      v_priority_expression := 'coalesce(m.importance, 0) + coalesce(m.salience, 0)';
    elsif v_kind = 'episodic' then
      v_row_expression := $expression$jsonb_build_object(
        'id', m.id, 'source_reference', m.source_reference,
        'event_date', m.event_date, 'summary', m.summary,
        'confidence', m.confidence, 'created_at', m.created_at,
        'memory_status', m.memory_status
      )$expression$;
      v_priority_expression := 'coalesce(m.confidence, 0) * 100';
    else
      v_row_expression := $expression$jsonb_build_object(
        'id', m.id, 'source_reference', m.source_reference,
        'key', m.key, 'value', m.value, 'confidence', m.confidence,
        'created_at', m.created_at, 'memory_status', m.memory_status
      )$expression$;
      v_priority_expression := 'coalesce(m.confidence, 0) * 100';
    end if;

    if v_source_column = '' then
      v_union_sql := v_union_sql || format($sql$
        select m.id::text candidate_id, %L table_name,
          'unknown' source_role, 'unlinked' provenance_evidence,
          ts_rank_cd(m.retrieval_fts, $1) rank,
          %s priority, m.created_at
        from public.%I m
        where m.retrieval_fts @@ $1
          and not exists (
            select 1 from public.memory_quarantine q
            where q.source_table = %L and q.source_id = m.id::text
              and q.restored_at is null
          )
      $sql$, v_table, v_priority_expression, v_table, v_table);
    else
      v_union_sql := v_union_sql || format($sql$
        select m.id::text candidate_id, %L table_name,
          case when source.role in ('user', 'assistant') then source.role else 'unknown' end source_role,
          case when source.role in ('user', 'assistant') then 'raw_catchall' else 'unlinked' end provenance_evidence,
          ts_rank_cd(m.retrieval_fts, $1) rank,
          %s priority, m.created_at
        from public.%I m
        left join public.raw_catchall source on source.id = m.%I
        where m.retrieval_fts @@ $1
          and not exists (
            select 1 from public.memory_quarantine q
            where q.source_table = %L and q.source_id = m.id::text
              and q.restored_at is null
          )
      $sql$, v_table, v_priority_expression, v_table, v_source_column, v_table);
    end if;

    v_hydrate_sql := v_hydrate_sql || format($sql$
      select public.project_l_candidate_row(
          %s, bounded.table_name, bounded.source_role,
          bounded.provenance_evidence, $1
        ) row_data,
        bounded.rank, bounded.priority, bounded.created_at
      from bounded
      join public.%I m on m.id::text = bounded.candidate_id
      where bounded.table_name = %L
    $sql$, v_row_expression, v_table, v_table);
  end loop;

  v_sql := format($sql$
    with bounded as materialized (
      select candidate_id, table_name, source_role, provenance_evidence,
             rank, priority, created_at
      from (%s) all_candidates
      order by rank desc, priority desc, created_at desc
      limit $2
    ),
    hydrated as (%s)
    select coalesce(
      jsonb_agg(row_data order by rank desc, priority desc, created_at desc),
      '[]'::jsonb
    )
    from hydrated
  $sql$, v_union_sql, v_hydrate_sql);

  execute v_sql using v_query, least(greatest(p_memory_limit, 1), 500)
  into v_memories;

  return jsonb_build_object('raw', v_raw, 'memories', v_memories);
end;
$function$;

revoke all on function public.search_project_l_memory(text[], integer, integer) from public;
revoke all on function public.search_project_l_memory(text[], integer, integer) from anon;
revoke all on function public.search_project_l_memory(text[], integer, integer) from authenticated;
grant execute on function public.search_project_l_memory(text[], integer, integer) to service_role;
