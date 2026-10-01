"""Layer 68/69 contracts for atomic, observable Shine Me owner-state sync."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui" / "shine-me.html"
SERVER = ROOT / "api" / "server.py"
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261001064214_shine_me_layer68_atomic_state_service_rpc.sql"
)
MIGRATION_69 = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261001083330_shine_me_layer69_conflict_receipts.sql"
)


def test_server_uses_one_atomic_rpc_for_owner_state_writes():
    source = SERVER.read_text()
    shine_me_wiring = source.split("app.include_router(shine_me_routes(", 1)[1].split(
        "))", 1
    )[0]
    assert "shine_me_owner_state_apply_service_v1" in shine_me_wiring
    assert ".insert(row)" not in shine_me_wiring
    assert ".update(row)" not in shine_me_wiring


def test_service_rpc_is_invoker_only_and_not_browser_executable():
    sql = MIGRATION.read_text().lower()
    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql


def test_browser_preserves_local_copy_and_refreshes_remote_on_conflict():
    html = UI.read_text()
    conflict = html.split("if(response.status===409)", 1)[1].split(
        "if(!response.ok)", 1
    )[0]
    assert "const remote=await fetchAccountState()" in conflict
    assert "await saveConflict(remote,receipt)" in conflict

    save_conflict = html.split("async function saveConflict(remote,receipt={})", 1)[1].split(
        "function applyRemoteState", 1
    )[0]
    assert "localState:stateSnapshot()" in save_conflict
    assert "remoteState:remote?.state||null" in save_conflict
    assert "remoteRevision:Number(remote?.revision||meta.remote_revision||0)" in save_conflict


def test_explicit_keep_device_rebases_before_safe_retry():
    html = UI.read_text()
    handler = html.split(
        "navSurfaceBody.querySelector('#keepDeviceCopy')?.addEventListener('click',()=>{",
        1,
    )[1].split(
        "navSurfaceBody.querySelector('#askYouMemory')",
        1,
    )[0]
    revision_pos = handler.index("syncMeta.revision=Number(conflict.remoteRevision||0)")
    retry_pos = handler.index("scheduleAccountSync(0)")
    assert revision_pos < retry_pos
    assert "syncMeta.conflict=false" in handler
    assert "syncMeta.dirty=true" in handler
    assert "localStorage.removeItem(conflictKey)" in handler


def test_explicit_account_choice_applies_remote_without_write_retry():
    html = UI.read_text()
    handler = html.split(
        "navSurfaceBody.querySelector('#useAccountCopy')?.addEventListener('click',async()=>{",
        1,
    )[1].split(
        "navSurfaceBody.querySelector('#keepDeviceCopy')",
        1,
    )[0]
    assert "applyRemoteState" in handler
    assert "scheduleAccountSync(0)" not in handler


def test_layer69_conflict_ledger_is_private_content_free_and_service_only():
    sql = MIGRATION_69.read_text().lower()
    assert "create table if not exists private.shine_me_owner_state_conflict_events" in sql
    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    forbidden = (
        " mood ",
        " journal ",
        " goals ",
        " routines ",
        " dailycheckins ",
        " state jsonb",
    )
    table_block = sql.split("create table if not exists private.shine_me_owner_state_conflict_events", 1)[1].split(");", 1)[0]
    assert all(item not in table_block for item in forbidden)


def test_layer69_browser_records_startup_conflicts_and_keeps_human_choice():
    html = UI.read_text()
    save_conflict = html.split(
        "async function saveConflict(remote,receipt={})", 1
    )[1].split("function applyRemoteState", 1)[0]
    assert "/shine-me/state/conflicts/detect" in save_conflict
    assert "local_revision:Number(localRevision||0)" in save_conflict
    assert "conflictId:meta.conflict_id||null" in save_conflict
    assert "recentConflicts24h:Number(meta.recent_conflicts_24h||0)" in save_conflict
    assert "recurring:Boolean(meta.recurring)" in save_conflict

    assert "Shine still will not choose a copy automatically." in html


def test_layer69_device_choice_carries_conflict_id_into_atomic_retry():
    html = UI.read_text()
    sync = html.split("async function syncToAccount()", 1)[1].split(
        "async function initialiseAccountSync()", 1
    )[0]
    assert "conflict_id:syncMeta.conflictId||null" in sync

    handler = html.split(
        "navSurfaceBody.querySelector('#keepDeviceCopy')?.addEventListener('click',()=>{",
        1,
    )[1].split(
        "navSurfaceBody.querySelector('#askYouMemory')",
        1,
    )[0]
    assert "syncMeta.conflictId=conflict.conflictId||syncMeta.conflictId||null" in handler
    assert handler.index("syncMeta.revision=Number(conflict.remoteRevision||0)") < handler.index("scheduleAccountSync(0)")


def test_layer69_account_choice_records_resolution_without_state_write():
    html = UI.read_text()
    handler = html.split(
        "navSurfaceBody.querySelector('#useAccountCopy')?.addEventListener('click',async()=>{",
        1,
    )[1].split(
        "navSurfaceBody.querySelector('#keepDeviceCopy')",
        1,
    )[0]
    assert "/shine-me/state/conflicts/resolve" in handler
    assert "resolution:'account_copy'" in handler
    assert "applyRemoteState" in handler
    assert "scheduleAccountSync(0)" not in handler
