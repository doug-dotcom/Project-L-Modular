"""Production-safe smoke checks for Project L's Concierge fleet integration."""

import json

from services.capability_router_service import route_capability
from services.foundation_companion_service import foundation_fleet_status

USER = "11111111-1111-4111-8111-111111111111"
LINK = "22222222-2222-4222-8222-222222222222"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class FakeDb:
    def rpc(self, name, params=None):
        if name == "companion_claim_foundation_refresh_v2":
            return Rpc({
                "state": "active",
                "requestId": LINK,
                "delegationExpiresAt": "2026-09-28T00:00:00Z",
                "refreshExpiresAt": "2026-10-27T00:00:00Z",
                "refreshGeneration": 1,
            })
        if name == "companion_foundation_delegation_token_v1":
            return Rpc("d" * 128)
        if name == "concierge_foundation_client_token_v1":
            return Rpc("c" * 128)
        raise AssertionError(name)


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self._payload


seen = {}


def get(url, *, headers, timeout, follow_redirects):
    seen.update(url=url, headers=headers, timeout=timeout, follow_redirects=follow_redirects)
    return FakeResponse({
        "status": "ok",
        "fleet": {
            "status": "healthy",
            "specialistCount": 2,
            "executableCount": 2,
            "blockedCount": 0,
            "specialists": [
                {
                    "appId": "shine.fiona",
                    "appName": "Fiona Finance",
                    "capabilityId": "fiona.company_brief",
                    "displayName": "Company evidence brief",
                    "mode": "advisory",
                    "executable": True,
                    "reasonCode": "capability-ready",
                    "grantStatus": "active",
                    "runtimeStatus": {
                        "available": True,
                        "reasonCode": "capability-available",
                    },
                },
                {
                    "appId": "shine.travel",
                    "appName": "Shine Travel",
                    "capabilityId": "travel.plan_trip",
                    "displayName": "Plan a trip",
                    "mode": "advisory",
                    "executable": True,
                    "reasonCode": "capability-ready",
                    "grantStatus": "active",
                    "runtimeStatus": {
                        "available": True,
                        "reasonCode": "capability-available",
                    },
                },
            ],
        },
    })


fleet = foundation_fleet_status(FakeDb(), USER, get_impl=get)
assert fleet["status"] == "healthy"
assert fleet["executable_count"] == 2
assert "delegation_token" not in fleet
assert seen["headers"]["X-Shine-Client-Token"] == "c" * 128
assert seen["headers"]["X-Shine-Delegation-Token"] == "d" * 128

route = route_capability(
    "Fiona: give me a company brief on ASX:ANZ",
    foundation_fleet=fleet,
)
assert route["capability"] == "foundation_specialist"
assert route["status"] == "ready"
assert route["foundation_specialist"]["capability_id"] == "fiona.company_brief"
assert route["foundation_specialist"]["executable"] is True

ambiguous = route_capability(
    "Plan a trip and give me a company brief",
    foundation_fleet=fleet,
)
assert ambiguous["capability"] == "l_core"

print("Project L Concierge fleet smoke: PASS")
