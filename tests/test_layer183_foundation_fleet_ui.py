from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_foundation_fleet_route_is_owner_bound_and_not_public():
    api = text("api/foundation_companion.py")
    server = text("api/server.py")
    assert '@router.get("/fleet")' in api
    assert "foundation_fleet_status(db, owner_id(request))" in api
    public_line = next(line for line in server.splitlines() if "public_paths =" in line)
    assert "/foundation/fleet" not in public_line


def test_specialist_panel_consumes_owner_authenticated_same_origin_route():
    page = text("ui/index.html")
    tools = text("ui/chat-tools.js")
    fleet = text("ui/foundation-fleet.js")
    assert 'id="specialistsAction"' in page
    assert 'id="specialistPanel"' in page
    assert "/ui/foundation-fleet.js" in page
    assert "show('specialists')" in tools
    assert "fetch('/foundation/fleet'" in fleet
    assert "AbortSignal.timeout(10000)" in fleet
    assert ".textContent" in fleet
    assert ".innerHTML" not in fleet


def test_specialist_ui_fails_closed_when_fleet_cannot_be_verified():
    fleet = text("ui/foundation-fleet.js")
    assert "Could not verify the live specialist fleet" in fleet
    assert "will not treat an unverified specialist as ready" in fleet
