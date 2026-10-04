import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).parents[1] / 'core/cognition/shine_ai_bridge.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.mark.parametrize('detail,reason', [
    ("Authenticated app 'unregistered' has no Shine-AI policy.", 'app_policy_missing'),
    ('Authenticated app requested the trusted companion prompt envelope without permission.', 'trusted_prompt_not_permitted'),
    ('Authenticated app requires an approved prompt profile before model execution.', 'prompt_profile_required'),
    ('Sensitive upstream text must not be persisted', 'permission_denied'),
])
def test_permission_receipts_are_safe_and_do_not_fallback(detail, reason):
    class Response:
        status_code = 403
        def json(self): return {'detail': detail}
    class Fallback:
        available = True
        def generate(self, request): raise AssertionError('No permission bypass')
    adapter = module.ShineAIModelAdapter(base_url='https://ai.example',app_id='shine-companion',key_id='key',secret='x'*48,post_impl=lambda *a,**kw: Response(),fallback=Fallback())
    with pytest.raises(module.ShineAIBridgeError) as caught:
        adapter.generate({'messages':[{'role':'user','content':'Test'}]})
    receipt = caught.value.receipt
    assert receipt['reason'] == reason
    assert receipt['provider_status'] == 403
    assert detail not in str(receipt)
    assert 'x'*48 not in str(receipt)
