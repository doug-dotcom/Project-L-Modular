from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928100600_project_l_layer201_foundation_chain_checkpoint.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer201_checkpoint_has_project_l_only_vault_hmac():
    sql = source()

    assert "project_l_foundation_chain_checkpoint_hmac_v1" in sql
    assert "vault.create_secret" in sql
    assert "vault.decrypted_secrets" in sql
    assert "shine:project-l:foundation-witness-chain-checkpoint:v1" in sql


def test_layer201_checkpoint_store_is_not_directly_writable():
    sql = source()

    assert "shine_ai_foundation_chain_checkpoint_state" in sql
    assert "shine_ai_foundation_chain_checkpoint_ledger" in sql
    assert "enable row level security" in sql
    assert (
        "revoke all on public.shine_ai_foundation_chain_checkpoint_state"
        in sql
    )
    assert (
        "revoke all on public.shine_ai_foundation_chain_checkpoint_ledger"
        in sql
    )
    assert "grant insert" not in sql
    assert "grant update" not in sql


def test_layer201_snapshot_authenticates_full_checkpoint_history():
    sql = source()

    assert "foundation-chain-checkpoint-ledger-count-mismatch" in sql
    assert "foundation-chain-checkpoint-sequence-gap" in sql
    assert "foundation-chain-checkpoint-link-mismatch" in sql
    assert "foundation-chain-checkpoint-auth-failed" in sql
    assert "foundation-chain-checkpoint-high-water-mismatch" in sql
    assert "foundation-chain-checkpoint-state-ledger-mismatch" in sql
    assert "foundation-chain-checkpoint-state-auth-failed" in sql


def test_layer201_observe_rejects_rollback_fork_gap_and_bad_predecessor():
    sql = source()

    assert "foundation-chain-checkpoint-rollback" in sql
    assert "foundation-chain-checkpoint-equivocation" in sql
    assert "foundation-chain-checkpoint-sequence-gap" in sql
    assert "foundation-chain-checkpoint-predecessor-mismatch" in sql
    assert "foundation-chain-checkpoint-genesis-invalid" in sql
    assert "pg_advisory_xact_lock" in sql


def test_layer201_only_accepts_foundation_chain_v1():
    sql = source()

    assert "p_witness_id<>'foundation-project-l'" in sql
    assert "p_chain_version<>1" in sql
    assert "p_sequence<>1" in sql
    assert "p_previous_chain_tag<>repeat('0',64)" in sql


def test_layer201_rpc_surface_is_service_role_only():
    sql = source()

    assert (
        "shine_ai_foundation_chain_checkpoint_snapshot_v1"
        in sql
    )
    assert (
        "shine_ai_foundation_chain_checkpoint_observe_v1"
        in sql
    )
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
