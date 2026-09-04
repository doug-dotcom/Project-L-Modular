-- Follow-up to the Step 8 migration: keep only scorer-facing fields and
-- generate bounded excerpts for oversized legacy transcript rows.

create or replace function public.project_l_candidate_row(
  p_row jsonb,
  p_table text,
  p_role text,
  p_evidence text,
  p_query tsquery
)
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $function$
  select jsonb_strip_nulls(jsonb_build_object(
    'id', p_row->'id',
    'raw_id', p_row->'raw_id',
    'source_reference', p_row->'source_reference',
    'content', case
      when length(p_row->>'content') > 8000 then regexp_replace(
        ts_headline(
          'simple'::regconfig,
          p_row->>'content',
          p_query,
          'MaxWords=160, MinWords=40, ShortWord=2, MaxFragments=3, FragmentDelimiter= ... '
        ),
        '</?b>', '', 'g'
      )
      else p_row->>'content'
    end,
    'summary', p_row->'summary',
    'event_date', p_row->'event_date',
    'key', p_row->'key',
    'value', p_row->'value',
    'question', p_row->'question',
    'meaning', p_row->'meaning',
    'primary_subject', p_row->'primary_subject',
    'subjects', p_row->'subjects',
    'relationships', p_row->'relationships',
    'values', p_row->'values',
    'patterns', p_row->'patterns',
    'preferences', p_row->'preferences',
    'importance', p_row->'importance',
    'salience', p_row->'salience',
    'anchor', p_row->'anchor',
    'confidence', p_row->'confidence',
    'created_at', p_row->'created_at',
    'memory_status', p_row->'memory_status',
    '_table', p_table,
    '_source_role', p_role,
    '_provenance_evidence', p_evidence
  ));
$function$;

revoke all on function public.project_l_candidate_row(jsonb, text, text, text, tsquery) from public;
revoke all on function public.project_l_candidate_row(jsonb, text, text, text, tsquery) from anon;
revoke all on function public.project_l_candidate_row(jsonb, text, text, text, tsquery) from authenticated;
grant execute on function public.project_l_candidate_row(jsonb, text, text, text, tsquery) to service_role;

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
             'id', r.id,
             'created_at', r.created_at,
             'role', r.role,
             'source', r.source,
             'content', case
               when length(r.content) > 8000 then regexp_replace(
                 ts_headline(
                   'simple'::regconfig,
                   r.content,
                   v_query,
                   'MaxWords=160, MinWords=40, ShortWord=2, MaxFragments=3, FragmentDelimiter= ... '
                 ),
                 '</?b>', '', 'g'
               )
               else r.content
             end
           ) as row_data,
           ts_rank_cd(r.retrieval_fts, v_query) as rank,
           r.created_at
    from public.raw_catchall r
    where r.retrieval_fts @@ v_query
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
        select
          m.id::text as candidate_id,
          %L as table_name,
          'unknown' as source_role,
          'unlinked' as provenance_evidence,
          ts_rank_cd(m.retrieval_fts, $1) as rank,
          %s as priority,
          m.created_at
        from public.%I m
        where m.retrieval_fts @@ $1
      $sql$, v_table, v_priority_expression, v_table);
    else
      v_union_sql := v_union_sql || format($sql$
      select
        m.id::text as candidate_id,
        %L as table_name,
        case when source.role in ('user', 'assistant') then source.role else 'unknown' end as source_role,
        case when source.role in ('user', 'assistant') then 'raw_catchall' else 'unlinked' end as provenance_evidence,
        ts_rank_cd(m.retrieval_fts, $1) as rank,
        %s as priority,
        m.created_at
      from public.%I m
      left join public.raw_catchall source on source.id = m.%I
      where m.retrieval_fts @@ $1
    $sql$, v_table, v_priority_expression, v_table, v_source_column);
    end if;

    v_hydrate_sql := v_hydrate_sql || format($sql$
      select
        public.project_l_candidate_row(
          %s, bounded.table_name, bounded.source_role,
          bounded.provenance_evidence, $1
        ) as row_data,
        bounded.rank,
        bounded.priority,
        bounded.created_at
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
    hydrated as (
      %s
    )
    select coalesce(
      jsonb_agg(row_data order by rank desc, priority desc, created_at desc),
      '[]'::jsonb
    )
    from hydrated
  $sql$, v_union_sql, v_hydrate_sql);

  execute v_sql
    using v_query, least(greatest(p_memory_limit, 1), 500)
    into v_memories;

  return jsonb_build_object('raw', v_raw, 'memories', v_memories);
end;
$function$;

revoke all on function public.search_project_l_memory(text[], integer, integer) from public;
revoke all on function public.search_project_l_memory(text[], integer, integer) from anon;
revoke all on function public.search_project_l_memory(text[], integer, integer) from authenticated;
grant execute on function public.search_project_l_memory(text[], integer, integer) to service_role;
