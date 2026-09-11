CREATE OR REPLACE FUNCTION public.l_recall_period(p_from date, p_through date, p_terms text[], p_per_month integer DEFAULT 24)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
 SET statement_timeout TO '8s'
AS $function$
declare
  v_query tsquery;
  v_month date;
  v_start date;
  v_end date;
  v_rows jsonb;
  v_months jsonb := '[]'::jsonb;
  v_limit integer := least(greatest(coalesce(p_per_month, 24), 1), 48);
begin
  if p_from is null or p_through is null or p_from > p_through or p_through - p_from > 366 then
    raise exception 'ordered period of at most one year required';
  end if;
  select to_tsquery('simple'::regconfig, string_agg(quote_literal(token) || ':*', ' | '))
    into v_query from (
      select distinct lower(parts[1]) token from unnest(coalesce(p_terms, array[]::text[])) supplied(term)
      cross join lateral regexp_matches(supplied.term, '[[:alnum:]]+', 'g') parts
      where length(parts[1]) >= 2 limit 24
    ) tokens;
  for v_month in select generate_series(date_trunc('month', p_from::timestamp),
                        date_trunc('month', p_through::timestamp), interval '1 month')::date
  loop
    v_start := greatest(v_month, p_from);
    v_end := least((v_month + interval '1 month')::date, p_through + 1);
    with candidates as (
      select 'raw_catchall:' || r.id as source, r.id as raw_id, r.role,
             (r.created_at at time zone 'Australia/Brisbane')::date::text as day,
             'recorded_at'::text as date_basis, r.content,
             coalesce(ts_rank_cd(r.retrieval_fts, v_query), 0) as rank,
             case when r.role = 'user' then 1 else 0 end as trust
      from public.raw_catchall r
      where r.created_at >= (v_start::timestamp at time zone 'Australia/Brisbane')
        and r.created_at < (v_end::timestamp at time zone 'Australia/Brisbane')
        and not exists (select 1 from public.memory_quarantine q where q.source_table = 'raw_catchall' and q.source_id = r.id::text and q.restored_at is null)
        and (v_query is null or r.retrieval_fts @@ v_query)
      union all
      select 'episodic_memories:' || e.id, e.source_reference, coalesce(r.role, 'unknown'),
             e.event_date, 'event_date', e.summary,
             coalesce(ts_rank_cd(e.retrieval_fts, v_query), 0),
             case when r.role = 'user' then 2 else 0 end
      from public.episodic_memories e
      left join public.raw_catchall r on r.id = e.source_reference
      where e.event_date ~ '^\d{4}-\d{2}-\d{2}$'
        and e.event_date >= v_start::text and e.event_date < v_end::text
        and coalesce(e.memory_status, '') <> 'QUARANTINED'
        and not exists (select 1 from public.memory_quarantine q where q.source_table = 'episodic_memories' and q.source_id = e.id::text and q.restored_at is null)
        and (v_query is null or e.retrieval_fts @@ v_query)
    ), bounded as (
      select * from candidates order by trust desc, rank desc, source limit v_limit + 1
    )
    select coalesce(jsonb_agg(jsonb_build_object(
      'source', source, 'raw_id', raw_id, 'role', role, 'date', day,
      'date_basis', date_basis, 'content', left(content, 6000),
      'truncated', length(content) > 6000
    ) order by trust desc, rank desc, source), '[]'::jsonb) into v_rows from bounded;
    v_months := v_months || jsonb_build_array(jsonb_build_object(
      'month', to_char(v_month, 'YYYY-MM'), 'rows',
      case when jsonb_array_length(v_rows) > v_limit then v_rows - v_limit else v_rows end,
      'truncated', jsonb_array_length(v_rows) > v_limit));
  end loop;
  return jsonb_build_object('months', v_months);
end;
$function$
