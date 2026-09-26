revoke execute on function public.l_task_progress_bound(uuid,uuid,text,jsonb,text)
from service_role;
revoke execute on function public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb)
from service_role;
revoke execute on function public.l_task_confirm_action_bound(uuid,uuid,text,jsonb,jsonb)
from service_role;
revoke execute on function public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)
from service_role;
revoke execute on function public.l_task_confirm_finish_bound(uuid,uuid,text,jsonb,text,jsonb)
from service_role;
revoke execute on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)
from service_role;

comment on function public.l_task_progress_bound(uuid,uuid,text,jsonb,text) is
  'Retired by Project L Layer 174. Use l_task_progress_claim_bound with the exact one-shot claim token.';
comment on function public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb) is
  'Retired by Project L Layer 174. Use l_task_record_action_claim_bound with the exact one-shot claim token.';
comment on function public.l_task_confirm_action_bound(uuid,uuid,text,jsonb,jsonb) is
  'Retired by Project L Layer 174. Use l_task_confirm_action_claim_bound with the exact one-shot claim token.';
comment on function public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb) is
  'Retired by Project L Layer 174. Use l_task_finish_claim_bound with the exact one-shot claim token.';
comment on function public.l_task_confirm_finish_bound(uuid,uuid,text,jsonb,text,jsonb) is
  'Retired by Project L Layer 174. Use l_task_confirm_finish_claim_bound with the exact one-shot claim token.';
comment on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb) is
  'Retired by Project L Layer 174. Use l_task_reject_claim_bound with the exact one-shot claim token.';
