-- Optimize Project L owner-scoped memory retrieval claim deduplication.
-- Reuse the owner-bound evidence index claim hash when available and compute
-- the content hash only once as a fallback. Retrieval semantics are unchanged.

CREATE OR REPLACE FUNCTION private.project_l_memory_context_v2(p_user uuid, p_terms text[], p_limit integer DEFAULT 8, p_identity_limit integer DEFAULT 4, p_char_budget integer DEFAULT 10000)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
 SET statement_timeout TO '5s'
AS $function$
declare
  v_query tsquery;
  v_query_all tsquery;
  v_term_count integer := 0;
  v_limit integer := least(greatest(coalesce(p_limit,8),1),12);
  v_identity_limit integer := least(greatest(coalesce(p_identity_limit,4),0),8);
  v_char_budget integer := least(greatest(coalesce(p_char_budget,10000),2400),24000);
  v_per_item integer;
  v_matches jsonb := '[]'::jsonb;
  v_anchors jsonb := '[]'::jsonb;
  v_returned_count integer := 0;
  v_source_chars bigint := 0;
  v_returned_chars bigint := 0;
  v_allowed_count integer := 0;
begin
  if p_user is null then
    raise exception 'Project L memory context requires user';
  end if;

  select count(*) into v_allowed_count
  from private.l_companion_domain_scope s
  where s.user_id=p_user and s.active;

  if v_allowed_count=0 then
    return jsonb_build_object(
      'status','no_scope',
      'matches','[]'::jsonb,
      'identityAnchors','[]'::jsonb,
      'scope',jsonb_build_object('allowedDomainCount',0,'ownerBound',true),
      'compression',jsonb_build_object(
        'charBudget',v_char_budget,
        'sourceChars',0,
        'returnedChars',0,
        'ratio',null
      )
    );
  end if;

  with tokens as (
    select distinct lower(parts[1]) token
    from unnest(coalesce(p_terms,array[]::text[])) supplied(term)
    cross join lateral regexp_matches(supplied.term,'[[:alnum:]]+','g') parts
    where length(parts[1])>=2
    limit 32
  )
  select
    to_tsquery(
      'simple'::regconfig,
      string_agg(quote_literal(token)||':*',' | ' order by token)
    ),
    to_tsquery(
      'simple'::regconfig,
      string_agg(quote_literal(token)||':*',' & ' order by token)
    ),
    count(*)
  into v_query,v_query_all,v_term_count
  from tokens;

  v_per_item := greatest(700, least(2600, v_char_budget / greatest(v_limit,1)));

  if v_query is not null then
    with allowed as (
      select s.table_name,s.domain_key
      from private.l_companion_domain_scope s
      where s.user_id=p_user
        and s.active
        and s.table_name in (
          'memory_family','memory_general','memory_health','memory_identity',
          'memory_project_l','memory_recovery','memory_relationships',
          'memory_sport','memory_work'
        )
    ),
    base_candidates as (
      select
        c.table_name,c.domain_key,c.source_id,c.raw_id,c.content,c.primary_subject,
        c.importance,c.salience,c.anchor,c.created_at,c.metadata,c.retrieval_fts,
        r.role as source_role,r.source as source_system,r.created_at as source_created_at,
        ts_rank_cd(c.retrieval_fts,v_query,1) as lexical_rank,
        ts_rank_cd(
          to_tsvector('simple'::regconfig,coalesce(c.primary_subject,'')),
          v_query,
          1
        ) as subject_match_rank,
        case
          when v_term_count<=1 then true
          else c.retrieval_fts @@ v_query_all
        end as all_terms_match,
        coalesce(e.authority_precedence,25) as evidence_precedence,
        nullif(e.claim_hash,'') as indexed_claim_hash,
        false as corrected,
        null::uuid as correction_id,
        null::jsonb as correction_evidence
      from private.l_memory_catalog_v2 c
      join allowed a on a.table_name=c.table_name and a.domain_key=c.domain_key
      join private.l_memory_row_owners o
        on o.source_table=c.table_name and o.source_id=c.source_id and o.user_id=p_user
      left join public.raw_catchall r on r.id=c.raw_id
      left join private.l_memory_evidence_index e
        on e.user_id=p_user
       and e.source_table=c.table_name
       and e.source_id=c.source_id
      where upper(coalesce(c.memory_status,'ACTIVE'))='ACTIVE'
        and c.retrieval_fts @@ v_query
        and not exists (
          select 1 from public.memory_quarantine q
          where q.source_table=c.table_name
            and q.source_id=c.source_id
            and q.restored_at is null
        )
        and not exists (
          select 1
          from public.project_l_memory_corrections x
          where x.user_id=p_user
            and x.source_table=c.table_name
            and x.source_id=c.source_id
            and x.status='ACTIVE'
        )
    ),
    correction_candidates as (
      select
        c.table_name,c.domain_key,c.source_id,c.raw_id,x.corrected_content as content,
        coalesce(x.primary_subject,c.primary_subject) as primary_subject,
        c.importance,c.salience,c.anchor,c.created_at,
        c.metadata || jsonb_build_object(
          'correctedMemory',true,
          'correctionId',x.id,
          'issueKind',x.issue_kind
        ) as metadata,
        c.retrieval_fts,
        r.role as source_role,r.source as source_system,r.created_at as source_created_at,
        greatest(
          coalesce(ts_rank_cd(x.retrieval_fts,v_query,1),0),
          coalesce(ts_rank_cd(c.retrieval_fts,v_query,1),0)
        ) as lexical_rank,
        ts_rank_cd(
          to_tsvector(
            'simple'::regconfig,
            coalesce(coalesce(x.primary_subject,c.primary_subject),'')
          ),
          v_query,
          1
        ) as subject_match_rank,
        case
          when v_term_count<=1 then true
          else (
            coalesce(x.retrieval_fts @@ v_query_all,false)
            or c.retrieval_fts @@ v_query_all
          )
        end as all_terms_match,
        100 as evidence_precedence,
        null::text as indexed_claim_hash,
        true as corrected,
        x.id as correction_id,
        coalesce(x.evidence,'{}'::jsonb) as correction_evidence
      from public.project_l_memory_corrections x
      join private.l_memory_catalog_v2 c
        on c.table_name=x.source_table and c.source_id=x.source_id
      join allowed a on a.table_name=c.table_name and a.domain_key=c.domain_key
      join private.l_memory_row_owners o
        on o.source_table=c.table_name and o.source_id=c.source_id and o.user_id=p_user
      left join public.raw_catchall r on r.id=c.raw_id
      where x.user_id=p_user
        and x.status='ACTIVE'
        and upper(coalesce(c.memory_status,'ACTIVE'))='ACTIVE'
        and (x.retrieval_fts @@ v_query or c.retrieval_fts @@ v_query)
        and not exists (
          select 1 from public.memory_quarantine q
          where q.source_table=c.table_name
            and q.source_id=c.source_id
            and q.restored_at is null
        )
    ),
    all_candidates as (
      select * from base_candidates
      union all
      select * from correction_candidates
    ),
    scored as (
      select a.*,
        (
          a.lexical_rank*100
          + a.subject_match_rank*60
          + case
              when v_term_count>1 and a.all_terms_match then 20
              else 0
            end
          + case when a.corrected then 25 else 0 end
          + coalesce(a.evidence_precedence,25)::numeric/10
          + case when a.anchor then 2 else 0 end
          + least(greatest(coalesce(a.importance,50),0),100)::numeric/100
          + least(greatest(coalesce(a.salience,50),0),100)::numeric/100
        )::numeric as score
      from all_candidates a
    ),
    bounded as materialized (
      select *
      from scored
      order by score desc, lexical_rank desc, created_at desc
      limit greatest(v_limit*10,80)
    ),
    claim_hashed as materialized (
      select
        b.*,
        coalesce(
          b.indexed_claim_hash,
          private.project_l_claim_hash_v1(b.content)
        ) as diversity_claim_hash,
        coalesce(
          nullif(lower(btrim(coalesce(b.primary_subject,''))),''),
          '__source__:'||b.table_name||':'||b.source_id
        ) as diversity_subject_key
      from bounded b
    ),
    claim_ranked as (
      select
        h.*,
        row_number() over (
          partition by h.diversity_claim_hash
          order by h.score desc,h.lexical_rank desc,h.created_at desc,h.table_name,h.source_id
        ) as claim_copy_rank
      from claim_hashed h
    ),
    claim_unique as (
      select *
      from claim_ranked
      where claim_copy_rank=1
    ),
    diversity_ranked as (
      select
        c.*,
        row_number() over (
          order by c.score desc,c.lexical_rank desc,c.created_at desc,c.table_name,c.source_id
        ) as global_rank,
        row_number() over (
          partition by c.domain_key
          order by c.score desc,c.lexical_rank desc,c.created_at desc,c.table_name,c.source_id
        ) as domain_rank,
        row_number() over (
          partition by c.diversity_subject_key
          order by c.score desc,c.lexical_rank desc,c.created_at desc,c.table_name,c.source_id
        ) as subject_rank
      from claim_unique c
    ),
    frontier as (
      select
        d.*,
        max(d.score) over () as best_score,
        min(d.score) filter (
          where d.global_rank<=v_limit
        ) over () as original_cutoff_score
      from diversity_ranked d
    ),
    tiered as (
      select
        f.*,
        greatest(
          coalesce(f.original_cutoff_score,0)*0.90,
          coalesce(f.best_score,0)*0.35
        ) as diversity_promotion_floor,
        greatest(
          coalesce(f.original_cutoff_score,0)*0.80,
          coalesce(f.best_score,0)*0.25
        ) as diversity_relaxed_floor,
        case
          when f.global_rank<=3 then 0
          when f.global_rank<=greatest(v_limit*2,16)
               and f.score>=greatest(
                 coalesce(f.original_cutoff_score,0)*0.90,
                 coalesce(f.best_score,0)*0.35
               )
               and f.domain_rank<=3
               and f.subject_rank<=2
            then 1
          when f.global_rank<=greatest(v_limit*2,16)
               and f.score>=greatest(
                 coalesce(f.original_cutoff_score,0)*0.80,
                 coalesce(f.best_score,0)*0.25
               )
               and f.domain_rank<=4
               and f.subject_rank<=3
            then 2
          else 3
        end as diversity_tier
      from frontier f
    ),
    top_rows as (
      select *
      from tiered
      order by diversity_tier,score desc,lexical_rank desc,created_at desc,table_name,source_id
      limit v_limit
    ),
    hydrated as (
      select
        t.*,
        private.project_l_memory_excerpt_v2(
          p_user,t.table_name,t.source_id,t.content,v_query,v_per_item
        ) as excerpt,
        length(t.content) as source_chars
      from top_rows t
    )
    select
      coalesce(jsonb_agg(
        jsonb_build_object(
          'id',h.source_id,
          'domain',h.domain_key,
          'subject',h.primary_subject,
          'content',h.excerpt,
          'contentTruncated',h.source_chars>length(h.excerpt),
          'sourceChars',h.source_chars,
          'importance',h.importance,
          'salience',h.salience,
          'anchor',h.anchor,
          'createdAt',h.created_at,
          'matchScore',round(h.score,3),
          'lexicalRank',round(h.lexical_rank::numeric,5),
          'corrected',h.corrected,
          'retrievalDiversity',jsonb_build_object(
            'claimCopyRank',h.claim_copy_rank,
            'globalRank',h.global_rank,
            'domainRank',h.domain_rank,
            'subjectRank',h.subject_rank,
            'selectionTier',h.diversity_tier,
            'isClaimRepresentative',h.claim_copy_rank=1,
            'bestScore',round(h.best_score,3),
            'originalCutoffScore',round(h.original_cutoff_score,3),
            'promotionFloor',round(h.diversity_promotion_floor,3),
            'relaxedFloor',round(h.diversity_relaxed_floor,3),
            'relevanceRatioToBest',
              case
                when h.best_score>0 then round(h.score/h.best_score,4)
                else null
              end
          ),
          'authority',case
            when h.corrected then jsonb_build_object(
              'class','user_confirmed_correction',
              'precedence',100,
              'explanation','User-confirmed correction overlay supersedes the legacy memory.'
            )
            when h.source_role='user' then jsonb_build_object(
              'class','direct_user_promoted_memory',
              'precedence',70,
              'explanation','Promoted memory linked to a direct user source.'
            )
            when h.source_role='assistant' then jsonb_build_object(
              'class','assistant_derived_promoted_memory',
              'precedence',45,
              'explanation','Promoted memory linked to an assistant source and should not override direct user evidence.'
            )
            else jsonb_build_object(
              'class','promoted_memory_unlinked_provenance',
              'precedence',35,
              'explanation','Promoted memory without direct source-role evidence.'
            )
          end,
          'freshness',jsonb_build_object(
            'class','non_temporal_memory',
            'temporalCurrentnessHandledSeparately',true,
            'declaredValidUntil',coalesce(
              h.metadata->>'valid_until',
              h.metadata->>'fresh_until',
              h.metadata->>'freshness_expires_at'
            )
          ),
          'provenance',jsonb_build_object(
            'sourceTable',h.table_name,
            'sourceId',h.source_id,
            'rawId',h.raw_id,
            'sourceRole',coalesce(h.source_role,'unknown'),
            'sourceSystem',h.source_system,
            'sourceCreatedAt',h.source_created_at,
            'correctionId',h.correction_id,
            'correctionEvidence',h.correction_evidence,
            'ownerBound',true
          )
        )
        order by h.score desc,h.lexical_rank desc,h.created_at desc
      ),'[]'::jsonb),
      count(*),
      coalesce(sum(h.source_chars),0),
      coalesce(sum(length(h.excerpt)),0)
    into v_matches,v_returned_count,v_source_chars,v_returned_chars
    from hydrated h;
  end if;

  if v_identity_limit>0
     and exists (
       select 1 from private.l_companion_domain_scope s
       where s.user_id=p_user and s.active and s.domain_key='identity'
     ) then
    select coalesce(jsonb_agg(
      jsonb_build_object(
        'id',a.id,
        'key',a.key,
        'value',left(a.value,1600),
        'contentTruncated',length(a.value)>1600,
        'confidence',a.confidence,
        'createdAt',a.created_at,
        'authority',jsonb_build_object(
          'class','identity_anchor',
          'precedence',80,
          'explanation','Explicit Project L identity anchor.'
        ),
        'provenance',jsonb_build_object(
          'sourceTable','identity_anchors',
          'sourceId',a.id::text,
          'rawId',a.source_reference,
          'sourceRole',coalesce(r.role,'unknown'),
          'sourceSystem',r.source,
          'ownerBound',true
        )
      )
      order by a.confidence desc,a.created_at desc
    ),'[]'::jsonb)
    into v_anchors
    from (
      select a.*
      from public.identity_anchors a
      join private.l_memory_row_owners o
        on o.source_table='identity_anchors'
       and o.source_id=a.id::text
       and o.user_id=p_user
      where upper(coalesce(a.memory_status,'ACTIVE'))='ACTIVE'
        and not exists (
          select 1 from public.memory_quarantine q
          where q.source_table='identity_anchors'
            and q.source_id=a.id::text
            and q.restored_at is null
        )
      order by a.confidence desc,a.created_at desc
      limit v_identity_limit
    ) a
    left join public.raw_catchall r on r.id=a.source_reference;
  end if;

  return jsonb_build_object(
    'status','ok',
    'matches',v_matches,
    'identityAnchors',v_anchors,
    'scope',jsonb_build_object(
      'allowedDomainCount',v_allowed_count,
      'activeOnly',true,
      'ownerBound',true,
      'quarantineExcluded',true,
      'supersededExcluded',true,
      'correctionsPreferred',true,
      'bulkExport',false,
      'maxResults',v_limit
    ),
    'authorityPolicy',jsonb_build_object(
      'temporalCurrentFactPrecedence',120,
      'userConfirmedCorrectionPrecedence',100,
      'identityAnchorPrecedence',80,
      'directUserPromotedMemoryPrecedence',70,
      'assistantDerivedPromotedMemoryPrecedence',45,
      'unlinkedPromotedMemoryPrecedence',35,
      'assistantEvidenceCannotOverrideDirectUserEvidence',true
    ),
    'freshnessPolicy',jsonb_build_object(
      'temporalFactsUseEffectiveIntervals',true,
      'ordinaryLongTermMemoryDoesNotExpireByAgeAlone',true,
      'declaredValidityWindowsAreSurfaced',true,
      'staleTemporalClaimsMustYieldToCurrentTemporalFacts',true
    ),
    'compression',jsonb_build_object(
      'charBudget',v_char_budget,
      'maxCharsPerItem',v_per_item,
      'sourceChars',v_source_chars,
      'returnedChars',v_returned_chars,
      'ratio',case when v_source_chars>0 then round(v_returned_chars::numeric/v_source_chars,4) else null end
    ),
    'returnedCount',v_returned_count,
    'retrievalDiversity',jsonb_build_object(
      'policyVersion','relevance-guarded-diversity-v3',
      'exactClaimDeduplication',true,
      'protectedTopCandidates',least(v_limit,3),
      'preferredDomainCeiling',3,
      'preferredSubjectCeiling',2,
      'fallbackAllowed',true,
      'relevanceFrontierRequiredForPromotion',true,
      'promotionHorizonGlobalRank',greatest(v_limit*2,16),
      'lengthNormalisedLexicalRank',true,
      'fullQueryCoverageBonus',true,
      'subjectRelevanceBoost',true,
      'evidenceAuthorityWeighted',true,
      'promotionFloorRule','max(90% of original top-N cutoff, 35% of best score)',
      'relaxedFloorRule','max(80% of original top-N cutoff, 25% of best score)',
      'uniqueDomains',(
        select count(distinct x->>'domain')
        from jsonb_array_elements(v_matches) x
      ),
      'uniqueSubjects',(
        select count(distinct coalesce(nullif(lower(btrim(x->>'subject')),''),'(none)'))
        from jsonb_array_elements(v_matches) x
      ),
      'maxItemsFromOneDomain',(
        select coalesce(max(cnt),0)
        from (
          select count(*) cnt
          from jsonb_array_elements(v_matches) x
          group by x->>'domain'
        ) d
      ),
      'maxItemsFromOneSubject',(
        select coalesce(max(cnt),0)
        from (
          select count(*) cnt
          from jsonb_array_elements(v_matches) x
          group by coalesce(nullif(lower(btrim(x->>'subject')),''),'(none)')
        ) s
      ),
      'diversityPromotedItems',(
        select count(*)
        from jsonb_array_elements(v_matches) x
        where coalesce((x->'retrievalDiversity'->>'globalRank')::integer,0)>v_limit
      ),
      'protectedTopRetained',(
        select count(*)
        from jsonb_array_elements(v_matches) x
        where coalesce((x->'retrievalDiversity'->>'globalRank')::integer,999999)<=least(v_limit,3)
      ),
      'fallbackUsed',(
        select exists(
          select 1
          from jsonb_array_elements(v_matches) x
          where coalesce((x->'retrievalDiversity'->>'selectionTier')::integer,0)=3
        )
      )
    )
  );
end;
$function$


revoke all on function private.project_l_memory_context_v2(uuid,text[],integer,integer,integer)
from public, anon, authenticated;
grant execute on function private.project_l_memory_context_v2(uuid,text[],integer,integer,integer)
to service_role;
