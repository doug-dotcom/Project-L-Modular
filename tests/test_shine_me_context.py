import unittest

from core.cognition.shine_me import (
    approved_sources_from_cognition,
    build_shine_me_context,
    build_shine_me_from_cognition,
)


class ShineMeContextTests(unittest.TestCase):
    def build(self, **changes):
        args = {
            "verified_user_id": "user-a",
            "retrieval_owner_id": "user-a",
            "allowed_scopes": frozenset({"general"}),
            "approved_sources": frozenset({"memory_general:1"}),
            "evidence": [
                {"source": "memory_general:1", "role": "user", "quote_source": "I prefer context first."},
                {"source": "memory_health:2", "role": "user", "quote_source": "Private health information"},
            ],
        }
        args.update(changes)
        return build_shine_me_context(**args)

    def test_only_approved_and_granted_evidence_is_returned(self):
        packet = self.build()
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(len(packet["records"]), 1)
        self.assertEqual(packet["records"][0]["provenance"], "user_statement")
        self.assertNotIn("Private health", str(packet))

    def test_cross_owner_request_fails_closed(self):
        with self.assertRaises(ValueError):
            self.build(retrieval_owner_id="user-b")

    def test_scope_grant_alone_does_not_publish_memory(self):
        packet = self.build(allowed_scopes=frozenset({"health"}), approved_sources=frozenset())
        self.assertEqual(packet["status"], "no_approved_evidence")
        self.assertEqual(packet["records"], [])

    def test_model_output_is_labelled_and_never_promoted(self):
        packet = self.build(evidence=[{
            "source": "memory_general:1", "role": "assistant",
            "quote_source": "The user probably likes this.",
        }])
        self.assertEqual(packet["records"][0]["provenance"], "model_statement")

    def test_invalid_grant_is_rejected(self):
        with self.assertRaises(ValueError):
            self.build(allowed_scopes=frozenset({"everything"}))

    def gates(self, *, source="memory_general:1"):
        return {key: {
            "active": True, "surface_allowed": True,
            "decision": "surface", "source": source,
        } for key in (
            "memory_temporal_drift", "memory_privacy", "memory_identity",
            "memory_emotional_salience", "memory_causal_attribution",
        )}

    def test_full_publication_chain_yields_one_source(self):
        packet = build_shine_me_from_cognition(
            verified_user_id="user-a", retrieval_owner_id="user-a",
            rhee_packet={"evidence": [
                {"source": "memory_general:1", "role": "user", "quote_source": "Context first"},
                {"source": "memory_general:2", "role": "user", "quote_source": "Other evidence"},
            ]},
            cognitive_packet=self.gates(),
            allowed_scopes=frozenset({"general"}),
        )
        self.assertEqual([r["source"] for r in packet["records"]], ["memory_general:1"])

    def test_any_veto_or_missing_gate_blocks_publication(self):
        for key in self.gates():
            with self.subTest(key=key):
                gates = self.gates()
                gates[key] = {**gates[key], "decision": "silent", "surface_allowed": False}
                self.assertEqual(approved_sources_from_cognition(gates), frozenset())
                del gates[key]
                self.assertEqual(approved_sources_from_cognition(gates), frozenset())

    def test_mismatched_gate_source_blocks_publication(self):
        gates = self.gates()
        gates["memory_causal_attribution"]["source"] = "memory_general:2"
        self.assertEqual(approved_sources_from_cognition(gates), frozenset())

    def test_owner_binding_remains_mandatory_with_approved_gates(self):
        with self.assertRaises(ValueError):
            build_shine_me_from_cognition(
                verified_user_id="user-b", retrieval_owner_id="user-a",
                rhee_packet={"evidence": []}, cognitive_packet=self.gates(),
                allowed_scopes=frozenset({"general"}),
            )


if __name__ == "__main__":
    unittest.main()
