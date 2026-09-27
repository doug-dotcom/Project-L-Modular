import unittest

from core.cognition.shine_me import build_shine_me_context


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


if __name__ == "__main__":
    unittest.main()
