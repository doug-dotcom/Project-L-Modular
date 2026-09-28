update public.companion_foundation_pending_jobs
set final_answer_generated_at=coalesce(final_answer_generated_at,updated_at)
where synthesis_status='ready'
  and final_answer is not null
  and final_answer_sha256 is not null
  and final_answer_generated_at is null;

update private.companion_concierge_synthesis_evidence e
set synthesised_at=coalesce(e.synthesised_at,j.final_answer_generated_at,e.updated_at),
    updated_at=clock_timestamp()
from public.companion_foundation_pending_jobs j
where j.job_id=e.request_id
  and j.user_id=e.user_id
  and j.synthesis_status='ready'
  and e.synthesised_at is null;
