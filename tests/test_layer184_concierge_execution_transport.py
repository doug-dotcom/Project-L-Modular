import json

from services.foundation_companion_service import invoke_foundation_specialist


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
LINK = "33333333-3333-4333-8333-333333333333"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class FakeDb:
    def __init__(self, claim=None):
        self.claim = claim or {
            "state": "active",
            "requestId": LINK,
            "delegationExpiresAt": "2026-09-28T00:00:00Z",
            "refreshExpiresAt": "2026-10-27T00:00:00Z",
            "refreshGeneration": 1,
        }
        self.calls = []

    def rpc(self, name, params=None):
        self.calls.append((name, params or {}))
        if name == "companion_claim_foundation_refresh_v2":
            return Rpc(self.claim)
        if name == "companion_foundation_delegation_token_v1":
            return Rpc("d" * 128)
        if name == "concierge_foundation_client_token_v1":
            return Rpc("c" * 128)
        raise AssertionError(name)


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self._payload


def test_plan_then_execute_returns_only_safe_specialist_result():
    seen = []

    def post(url, *, headers, json, timeout, follow_redirects):
        seen.append((url, headers, json, timeout, follow_redirects))
        if url.endswith("/v1/concierge/plan"):
            assert json["requestId"] == REQUEST
            assert json["capabilityIds"] == ["money.explain_calculate"]
            assert json["purpose"] == "concierge.cross-project-read"
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
                "requestId": REQUEST,
                "plan": {"status": "ready"},
            })
        assert url.endswith("/v1/concierge/execute")
        assert json["requestId"] == REQUEST
        assert json["inputs"] == {
            "money.explain_calculate": {"question": "What is compound interest?"}
        }
        return FakeResponse(200, {
            "status": "completed",
            "reasonCode": "concierge-execution-completed",
            "requestId": REQUEST,
            "results": [{
                "capabilityId": "money.explain_calculate",
                "appId": "shine.money",
                "status": "completed",
                "reasonCode": "capability-invocation-completed",
                "result": {
                    "title": "Compound interest",
                    "paragraphs": ["Interest can earn interest over time."],
                    "sideEffects": False,
                },
            }],
        })

    result = invoke_foundation_specialist(
        FakeDb(),
        USER,
        request_id=REQUEST,
        capability_id="money.explain_calculate",
        input_data={"question": "What is compound interest?"},
        post_impl=post,
    )

    assert result == {
        "status": "completed",
        "reason_code": "concierge-execution-completed",
        "capability_id": "money.explain_calculate",
        "request_id": REQUEST,
        "specialist_status": "completed",
        "specialist_reason_code": "capability-invocation-completed",
        "result": {
            "title": "Compound interest",
            "paragraphs": ["Interest can earn interest over time."],
            "sideEffects": False,
        },
    }
    assert len(seen) == 2
    for _url, headers, _body, _timeout, follow_redirects in seen:
        assert headers["X-Shine-Client-Token"] == "c" * 128
        assert headers["X-Shine-Delegation-Token"] == "d" * 128
        assert follow_redirects is False
    assert "delegation_token" not in result
    assert "client_token" not in result


def test_blocked_execution_is_reported_without_fabricating_result():
    calls = 0

    def post(url, **kwargs):
        nonlocal calls
        calls += 1
        if url.endswith("/v1/concierge/plan"):
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
                "requestId": REQUEST,
                "plan": {"status": "blocked"},
            })
        return FakeResponse(409, {
            "status": "blocked",
            "reasonCode": "integration-grant-inactive",
            "requestId": REQUEST,
            "gate": {"status": "blocked"},
        })

    result = invoke_foundation_specialist(
        FakeDb(),
        USER,
        request_id=REQUEST,
        capability_id="fiona.company_brief",
        input_data={"identifier": "ASX:ANZ"},
        post_impl=post,
    )

    assert calls == 2
    assert result["status"] == "blocked"
    assert result["reason_code"] == "integration-grant-inactive"
    assert "result" not in result


def test_plan_denial_stops_before_execute():
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        return FakeResponse(403, {
            "status": "denied",
            "reasonCode": "integration-client-not-linked",
            "requestId": REQUEST,
        })

    result = invoke_foundation_specialist(
        FakeDb(),
        USER,
        request_id=REQUEST,
        capability_id="travel.plan_trip",
        input_data={"destination": "Vanuatu"},
        post_impl=post,
    )

    assert calls == [
        "https://sjpxqeyewahraxvidvcc.supabase.co/functions/v1/foundation-gateway/v1/concierge/plan"
    ]
    assert result["status"] == "denied"
    assert result["reason_code"] == "integration-client-not-linked"


def test_missing_delegated_authority_never_calls_foundation_plan():
    db = FakeDb({
        "state": "not-connected",
        "reasonCode": "integration-client-not-linked",
    })

    def forbidden(*args, **kwargs):
        raise AssertionError("network must not run without delegated authority")

    result = invoke_foundation_specialist(
        db,
        USER,
        request_id=REQUEST,
        capability_id="money.explain_calculate",
        input_data={"question": "What is an ETF?"},
        post_impl=forbidden,
    )

    assert result["status"] == "not-connected"
    assert result["reason_code"] == "integration-client-not-linked"


def test_invalid_capability_or_input_is_rejected_before_authority_lookup():
    db = FakeDb()
    for capability_id, input_data in [
        ("Money Bad", {}),
        ("money.explain_calculate", "not-an-object"),
    ]:
        try:
            invoke_foundation_specialist(
                db,
                USER,
                request_id=REQUEST,
                capability_id=capability_id,
                input_data=input_data,
            )
            raise AssertionError("expected validation failure")
        except ValueError:
            pass
    assert db.calls == []
