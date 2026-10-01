"""Layer 68-72 contracts for atomic, observable Shine Me owner-state sync."""

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
MIGRATION_70 = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261001084822_shine_me_layer70_conflict_health_summary.sql"
)
MIGRATION_71 = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261001092245_shine_me_layer71_conflict_health_reason_codes.sql"
)
MIGRATION_72 = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261001094307_shine_me_layer72_bounded_health_transition_receipts.sql"
)
MIGRATION_72_FIX = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261001094459_shine_me_layer72_transition_health_fields_fix.sql"
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


def test_layer70_conflict_health_is_bounded_content_free_and_service_only():
    sql = MIGRATION_70.read_text().lower()
    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "interval '24 hours'" in sql
    assert "v_detections >= 6" in sql
    assert "v_unresolved >= 2" in sql
    assert "v_oldest_minutes >= 30" in sql
    assert "'stable'" in sql
    assert "'isolated'" in sql
    assert "'recurring'" in sql
    assert "'persistent'" in sql

    function_body = sql.split(
        "create or replace function public.shine_me_owner_state_conflict_health_service_v1",
        1,
    )[1]
    forbidden = (
        "shine_me_owner_state s",
        "state::",
        "journal",
        "mood",
        "goals",
        "routines",
        "dailycheckins",
    )
    assert all(item not in function_body for item in forbidden)


def test_layer70_browser_surfaces_health_without_changing_resolution_authority():
    html = UI.read_text()
    assert "/shine-me/state/conflicts/health" in html
    assert "conflictHealthLabel" in html
    assert "conflictHealthDetail" in html
    assert "Persistent sync issue" in html
    assert "Repeated conflicts" in html
    assert "Shine will not choose a copy automatically." in html
    assert "Use account version" in html
    assert "Keep this device version" in html


def test_layer70_health_summary_does_not_clear_or_mutate_owner_state():
    sql = MIGRATION_70.read_text().lower()
    assert "update public.shine_me_owner_state" not in sql
    assert "insert into public.shine_me_owner_state" not in sql
    assert "delete from public.shine_me_owner_state" not in sql
    assert "delete from private.shine_me_owner_state_conflict_events" not in sql


def test_layer71_reason_codes_are_bounded_service_only_and_content_free():
    sql = MIGRATION_71.read_text().lower()
    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "'volume'" in sql
    assert "'unresolved_count'" in sql
    assert "'unresolved_age'" in sql
    assert "'clear'" in sql
    assert "'observing'" in sql
    assert "'resolving'" in sql
    assert "'stalled'" in sql
    assert "shine_me_owner_state_conflict_health_service_v1" in sql
    forbidden = ("journal", "mood", "goals", "routines", "dailycheckins", "state jsonb")
    assert all(item not in sql for item in forbidden)


def test_layer71_api_and_ui_keep_explanations_bounded_and_human_controlled():
    html = UI.read_text()
    source = (ROOT / "api" / "shine_me.py").read_text()
    assert 'allowed_reasons = {"volume", "unresolved_count", "unresolved_age"}' in source
    assert 'recovery_state not in {"clear", "observing", "resolving", "stalled"}' in source
    assert "conflictHealthReasonCodes" in html
    assert "conflictRecoveryState" in html
    assert "multiple conflicts in 24h" in html
    assert "more than one conflict remains unresolved" in html
    assert "a conflict has remained unresolved for 30+ minutes" in html
    assert "Shine will not choose a copy automatically." in html
    assert "Use account version" in html
    assert "Keep this device version" in html


def test_layer71_server_uses_explanation_rpc_not_direct_content_reads():
    source = SERVER.read_text()
    wiring = source.split("app.include_router(shine_me_routes(", 1)[1].split(
        "))", 1
    )[0]
    assert "shine_me_owner_state_conflict_health_explain_service_v1" in wiring
    assert "shine_me_owner_state_conflict_health_service_v1" not in wiring


def test_layer72_transition_receipts_are_private_bounded_and_content_free():
    sql = MIGRATION_72.read_text().lower()
    assert "create table if not exists private.shine_me_owner_state_conflict_health_transitions" in sql
    assert "enable row level security" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "clock_timestamp()" in sql
    assert "offset 32" in sql
    assert "'baseline'" in sql
    assert "'improving'" in sql
    assert "'worsening'" in sql
    assert "'recovered'" in sql
    assert "'mixed'" in sql
    table_block = sql.split(
        "create table if not exists private.shine_me_owner_state_conflict_health_transitions",
        1,
    )[1].split(");", 1)[0]
    forbidden = (" journal", " mood", " goals", " routines", " dailycheckins", " state jsonb")
    assert all(item not in table_block for item in forbidden)
    assert "update public.shine_me_owner_state" not in sql
    assert "insert into public.shine_me_owner_state" not in sql
    assert "delete from public.shine_me_owner_state" not in sql


def test_layer72_steady_observation_does_not_append_receipt():
    sql = MIGRATION_72.read_text().lower()
    steady_block = sql.split(
        "if v_has_previous", 1
    )[1].split(
        "if not v_has_previous", 1
    )[0]
    assert "'steady'::text" in steady_block
    assert "select\n      false" in steady_block
    assert "insert into private.shine_me_owner_state_conflict_health_transitions" not in steady_block
    assert "offset 32" in steady_block


def test_layer72_fix_preserves_layer71_health_fields_in_one_rpc():
    sql = MIGRATION_72_FIX.read_text().lower()
    assert "drop function if exists public.shine_me_owner_state_conflict_health_transition_service_v1(text)" in sql
    for field in (
        "detections_24h integer",
        "resolutions_24h integer",
        "unresolved_conflicts integer",
        "oldest_unresolved_minutes integer",
        "last_conflict_at timestamptz",
        "state_age_seconds integer",
        "episode_age_seconds integer",
        "recovery_seconds integer",
        "history_size integer",
    ):
        assert field in sql
    assert "shine_me_owner_state_conflict_health_explain_service_v1" in sql
    assert "offset 32" in sql
    assert "clock_timestamp()" in sql


def test_layer72_server_and_ui_surface_trend_without_resolution_authority():
    server = SERVER.read_text()
    html = UI.read_text()
    api = (ROOT / "api" / "shine_me.py").read_text()
    wiring = server.split("app.include_router(shine_me_routes(", 1)[1].split(
        "))", 1
    )[0]
    assert "shine_me_owner_state_conflict_health_transition_service_v1" in wiring
    assert "shine_me_owner_state_conflict_health_explain_service_v1" not in wiring
    assert '"baseline", "steady", "improving", "worsening", "recovered", "mixed"' in api
    assert "transition_history_size" in api
    assert "history_size > 32" in api
    assert "conflictTrendLabel" in html
    assert "conflictTrendDetail" in html
    assert "Improving" in html
    assert "Worsening" in html
    assert "Recovered" in html
    assert "Sync trend" in html
    assert "Use account version" in html
    assert "Keep this device version" in html
    assert "Shine will not choose a copy automatically." in html
