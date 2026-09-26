revoke execute on function public.l_task_claim(uuid)
from service_role;

comment on function public.l_task_claim(uuid) is
  'Retired by Project L Layer 172. Use public.l_task_claim_bound(uuid, uuid); legacy unbound claims are not runtime-authorized.';
