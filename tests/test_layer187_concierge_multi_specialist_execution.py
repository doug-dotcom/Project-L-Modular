import json

from services.concierge_execution_service import (
    bind_concierge_execution,
    execute_concierge_route,
)


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


class Query:
    def __init__(self, db, table, mode="select", payload=None):
        self.db = db
        self.table_name = table
        self.mode = mode
        self.payload = payload
        self.filters = {}

    def select(self, *args):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def neq(self, key, value):
        self.filters["__neq__:" + key] = value
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        return self

    def insert(self, payload):
        return Query(self.db, self.table_name, "insert", payload)

    def update(self, payload):
        return Query(self.db, self.table_name, "update", payload)

    def execute(self):
        rows = self.db.tables.setdefault(self.table_name, [])
        if self.mode == "select":
            return Result([
                row.copy() for row in rows
                if all(
                    str(row.get(k.removeprefix("__neq__:"))) != str(v)
                    if k.startswith("__neq__:")
                    else str(row.get(k)) == str(v)
                    for k, v in self.filters.items()
                )
            ])
        if self.mode == "insert":
            rows.append(self.payload.copy())
            return Result([self.payload.copy()])
        if self.mode == "update":
            changed = []
            for row in rows:
                if all(str(row.get(k)) == str(v) for k, v in self.filters.items()):
                    row.update(self.payload)
                    changed.append(row.copy())
            return Result(changed)
        raise AssertionError(self.mode)


class FakeDb:
    def __init__(self):
        self.calls = []
        self.tables = {
            "companion_foundation_pending_jobs": [],
        }

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        self.calls.append((name, params or {}))
        if name == "companion_claim_foundation_refresh_v2":
            return Rpc({
                "state": "active",
                "requestId": LINK,
                "delegationExpiresAt": "2026-09-28T01:00:00Z",
                "refreshExpiresAt": "2026-10-28T01:00:00Z",
                "refreshGeneration": 1,
            })
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


def multi_route():
    return {
        "handled": False,
        "capability": "foundation_orchestration",
        "status": "ready",
        "reply": "",
        "foundation_orchestration": {
            "status": "ready",
            "reason_code": "shine-ai-plan-ready",
            "selected_capabilities": [
                "travel.plan_trip",
                "dive.destination_brief",
            ],
            "steps": [
                {
                    "capability_id": "travel.plan_trip",
                    "app_name": "Shine Travel",
                    "display_name": "Plan a trip",
                    "status": "ready",
                    "reason_code": "specialist-ready",
                    "runtime_available": True,
                    "executable": True,
                    "input_contract": {
                        "status": "ready",
                        "input_data": {"destination": "Vanuatu"},
                    },
                },
                {
                    "capability_id": "dive.destination_brief",
                    "app_name": "Shine Dive",
                    "display_name": "Destination dive brief",
                    "status": "ready",
                    "reason_code": "specialist-ready",
                    "runtime_available": True,
                    "executable": True,
                    "input_contract": {
                        "status": "ready",
                        "input_data": {"destination": "Vanuatu"},
                    },
                },
            ],
        },
    }


def test_multi_specialist_route_uses_one_foundation_plan_and_one_execute():
    seen = []

    def post(url, *, headers, json, timeout, follow_redirects):
        seen.append((url, headers, json, timeout, follow_redirects))
        if url.endswith("/v1/concierge/plan"):
            assert json["capabilityIds"] == [
                "travel.plan_trip",
                "dive.destination_brief",
            ]
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
                "requestId": REQUEST,
                "plan": {"status": "ready"},
            })
        assert url.endswith("/v1/concierge/execute")
        assert json["inputs"] == {
            "travel.plan_trip": {"destination": "Vanuatu"},
            "dive.destination_brief": {"destination": "Vanuatu"},
        }
        return FakeResponse(200, {
            "status": "completed",
            "reasonCode": "concierge-execution-completed",
            "requestId": REQUEST,
            "results": [
                {
                    "capabilityId": "travel.plan_trip",
                    "appId": "shine.travel",
                    "status": "completed",
                    "reasonCode": "capability-completed",
                    "result": {"summary": "Trip result"},
                },
                {
                    "capabilityId": "dive.destination_brief",
                    "appId": "shine.dive",
                    "status": "completed",
                    "reasonCode": "capability-completed",
                    "result": {"summary": "Dive result"},
                },
            ],
            "synthesisReady": True,
            "synthesisMustDisclosePartial": False,
        })

    execution = execute_concierge_route(
        FakeDb(),
        USER,
        request_id=REQUEST,
        route=multi_route(),
        post_impl=post,
    )
    assert len(seen) == 2
    assert execution["status"] == "completed"
    assert execution["completed_capabilities"] == [
        "travel.plan_trip",
        "dive.destination_brief",
    ]
    assert execution["synthesis_ready"] is True

    bound = bind_concierge_execution(multi_route(), execution)
    assert bound["handled"] is True
    evidence = json.loads(bound["reply"])
    assert len(evidence["results"]) == 2
    assert evidence["synthesis_must_disclose_partial"] is False


def test_foundation_partial_result_is_preserved_for_one_l_synthesis():
    def post(url, **kwargs):
        if url.endswith("/v1/concierge/plan"):
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
            })
        return FakeResponse(200, {
            "status": "partial",
            "reasonCode": "concierge-execution-partial",
            "results": [
                {
                    "capabilityId": "travel.plan_trip",
                    "appId": "shine.travel",
                    "status": "completed",
                    "reasonCode": "capability-completed",
                    "result": {"summary": "Trip result"},
                },
                {
                    "capabilityId": "dive.destination_brief",
                    "appId": "shine.dive",
                    "status": "failed",
                    "reasonCode": "capability-endpoint-unavailable",
                },
            ],
            "retry": {"queued": True},
            "synthesisReady": True,
            "synthesisMustDisclosePartial": True,
        })

    execution = execute_concierge_route(
        FakeDb(),
        USER,
        request_id=REQUEST,
        route=multi_route(),
        post_impl=post,
    )
    assert execution["status"] == "partial"
    assert execution["completed_capabilities"] == ["travel.plan_trip"]
    assert execution["unavailable_capabilities"] == ["dive.destination_brief"]
    assert execution["retry_scheduled"] is True
    assert execution["synthesis_ready"] is True
    assert execution["synthesis_must_disclose_partial"] is True

    bound = bind_concierge_execution(multi_route(), execution)
    assert bound["handled"] is True
    assert bound["status"] == "partial"
    evidence = json.loads(bound["reply"])
    assert evidence["synthesis_must_disclose_partial"] is True


def test_ready_subset_executes_while_missing_input_is_disclosed_as_skipped():
    route = multi_route()
    plan = route["foundation_orchestration"]
    plan["status"] = "partial"
    plan["steps"][1] = {
        **plan["steps"][1],
        "status": "needs_input",
        "reason_code": "specialist-input-missing",
        "input_contract": {
            "status": "needs_input",
            "reason_code": "specialist-input-missing",
            "missing_fields": ["destination"],
        },
    }
    seen = []

    def post(url, *, json, **kwargs):
        seen.append((url, json))
        if url.endswith("/v1/concierge/plan"):
            assert json["capabilityIds"] == ["travel.plan_trip"]
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
            })
        assert json["inputs"] == {
            "travel.plan_trip": {"destination": "Vanuatu"}
        }
        return FakeResponse(200, {
            "status": "completed",
            "reasonCode": "concierge-execution-completed",
            "results": [{
                "capabilityId": "travel.plan_trip",
                "appId": "shine.travel",
                "status": "completed",
                "reasonCode": "capability-completed",
                "result": {"summary": "Trip result"},
            }],
            "synthesisReady": True,
            "synthesisMustDisclosePartial": False,
        })

    execution = execute_concierge_route(
        FakeDb(),
        USER,
        request_id=REQUEST,
        route=route,
        post_impl=post,
    )
    assert len(seen) == 2
    assert execution["status"] == "partial"
    assert execution["completed_capabilities"] == ["travel.plan_trip"]
    assert execution["skipped_capabilities"][0]["capability_id"] == "dive.destination_brief"
    assert execution["skipped_capabilities"][0]["missing_fields"] == ["destination"]
    assert execution["synthesis_must_disclose_partial"] is True


def test_no_ready_step_performs_no_network_or_authority_lookup():
    route = multi_route()
    for step in route["foundation_orchestration"]["steps"]:
        step["status"] = "needs_input"
        step["input_contract"] = {
            "status": "needs_input",
            "missing_fields": ["destination"],
        }
    route["foundation_orchestration"]["status"] = "needs_input"
    db = FakeDb()

    def forbidden(*args, **kwargs):
        raise AssertionError("no Foundation HTTP call expected")

    execution = execute_concierge_route(
        db,
        USER,
        request_id=REQUEST,
        route=route,
        post_impl=forbidden,
    )
    assert execution["status"] == "needs_input"
    assert execution["execution_performed"] is False
    assert execution["synthesis_ready"] is False
    assert db.calls == []


def test_single_specialist_route_uses_same_foundation_execution_path():
    route = {
        "handled": False,
        "capability": "foundation_specialist",
        "status": "ready",
        "reply": "",
        "foundation_specialist": {
            "capability_id": "fiona.company_brief",
            "app_name": "Fiona Finance",
            "display_name": "Company evidence brief",
            "executable": True,
            "runtime_available": True,
            "reason_code": "capability-ready",
            "input_contract": {
                "status": "ready",
                "input_data": {"identifier": "ASX:ANZ"},
            },
        },
    }

    def post(url, *, json, **kwargs):
        if url.endswith("/v1/concierge/plan"):
            assert json["capabilityIds"] == ["fiona.company_brief"]
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
            })
        assert json["inputs"] == {
            "fiona.company_brief": {"identifier": "ASX:ANZ"}
        }
        return FakeResponse(200, {
            "status": "completed",
            "reasonCode": "concierge-execution-completed",
            "results": [{
                "capabilityId": "fiona.company_brief",
                "appId": "shine.fiona",
                "status": "completed",
                "reasonCode": "capability-completed",
                "result": {"brief": "ANZ evidence brief"},
            }],
            "synthesisReady": True,
            "synthesisMustDisclosePartial": False,
        })

    execution = execute_concierge_route(
        FakeDb(),
        USER,
        request_id=REQUEST,
        route=route,
        post_impl=post,
    )
    assert execution["status"] == "completed"
    assert execution["completed_capabilities"] == ["fiona.company_brief"]



def test_large_specialist_evidence_is_bounded_without_claiming_empty_success():
    route = multi_route()
    execution = {
        "status": "completed",
        "reason_code": "concierge-execution-completed",
        "foundation_status": "completed",
        "completed_capabilities": ["travel.plan_trip"],
        "unavailable_capabilities": [],
        "skipped_capabilities": [],
        "retry_scheduled": False,
        "synthesis_ready": True,
        "synthesis_must_disclose_partial": False,
        "results": [{
            "capability_id": "travel.plan_trip",
            "app_name": "Shine Travel",
            "display_name": "Plan a trip",
            "status": "completed",
            "reason_code": "capability-completed",
            "result": {"summary": "x" * 20000},
        }],
    }
    bound = bind_concierge_execution(route, execution)
    assert bound["handled"] is True
    assert len(bound["reply"]) <= 12000
    evidence = json.loads(bound["reply"])
    assert evidence["result_payloads_truncated_for_context_budget"] is True
    assert evidence["results"][0]["result_preview"]
    assert evidence["results"][0]["result_truncated"] is True


def test_server_executes_concierge_before_working_memory_and_cognition():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    execute_index = source.index("concierge_execution = execute_concierge_route(")
    bind_index = source.index("route = bind_concierge_execution(", execute_index)
    working_index = source.index(
        "working_memory_packet = active_context_service.begin_turn(",
        bind_index,
    )
    cognition_index = source.index("cognitive_packet = run_cognitive_core(", working_index)
    assert execute_index < bind_index < working_index < cognition_index
    assert "checkpoint(\"concierge_execution\")" in source



def test_foundation_can_block_after_plan_without_being_misreported_as_bad_result():
    def post(url, **kwargs):
        if url.endswith("/v1/concierge/plan"):
            return FakeResponse(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
            })
        return FakeResponse(409, {
            "status": "blocked",
            "reasonCode": "integration-grant-inactive",
            "gate": {"status": "blocked"},
        })

    execution = execute_concierge_route(
        FakeDb(),
        USER,
        request_id=REQUEST,
        route=multi_route(),
        post_impl=post,
    )
    assert execution["status"] == "blocked"
    assert execution["reason_code"] == "integration-grant-inactive"
    assert execution["results"] == []
    assert execution["synthesis_ready"] is False

    bound = bind_concierge_execution(multi_route(), execution)
    assert bound["handled"] is False
    assert bound["reply"] == ""
    assert bound["foundation_execution"]["status"] == "blocked"
