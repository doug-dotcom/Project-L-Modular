from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20261001024500_optimize_project_l_memory_claim_hash.sql"
)


def test_claim_hash_hotpath_reuses_owner_bound_evidence_index():
    sql = MIGRATION.read_text()

    assert "nullif(e.claim_hash,'') as indexed_claim_hash" in sql
    assert "null::text as indexed_claim_hash" in sql
    assert "claim_hashed as materialized" in sql
    assert """coalesce(
          b.indexed_claim_hash,
          private.project_l_claim_hash_v1(b.content)
        ) as diversity_claim_hash""" in sql
    assert "partition by h.diversity_claim_hash" in sql

    # The hot path must not recompute the same content hash in both the
    # projection and the window partition. One fallback call is enough.
    assert sql.count("private.project_l_claim_hash_v1(b.content)") == 1


def test_claim_hash_optimisation_preserves_retrieval_security_boundary():
    sql = MIGRATION.read_text()

    assert "STABLE SECURITY DEFINER" in sql
    assert "SET search_path TO ''" in sql
    assert "SET statement_timeout TO '5s'" in sql
    assert (
        "revoke all on function "
        "private.project_l_memory_context_v2(uuid,text[],integer,integer,integer)"
        in sql
    )
    assert "from public, anon, authenticated;" in sql
    assert (
        "grant execute on function "
        "private.project_l_memory_context_v2(uuid,text[],integer,integer,integer)"
        in sql
    )
    assert "to service_role;" in sql
