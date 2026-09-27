import unittest

from core.cognition.shine_me_service import prepare_shine_me_context


class ShineMeServiceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def retrieve(self, query):
        self.calls.append("retrieve")
        return {"evidence": [{
            "source": "memory_general:1", "role": "user", "quote_source": "Context first"
        }]}

    def cognize(self, query, packet):
        self.calls.append("cognize")
        return {key: {
            "active": True, "decision": "surface", "surface_allowed": True,
            "source": "memory_general:1",
        } for key in (
            "memory_temporal_drift", "memory_privacy", "memory_identity",
            "memory_emotional_salience", "memory_causal_attribution",
        )}

    def build(self, **changes):
        arguments = dict(
            query="What do you remember?",
            verified_account={"user_id": "owner-a"},
            configured_owner_id="owner-a",
            retrieve=self.retrieve,
            cognize=self.cognize,
        )
        arguments.update(changes)
        return prepare_shine_me_context(**arguments)

    def test_verified_owner_gets_only_gated_record(self):
        result = self.build()
        self.assertEqual([r["source"] for r in result["records"]], ["memory_general:1"])
        self.assertEqual(self.calls, ["retrieve", "cognize"])

    def test_other_user_never_reaches_retrieval(self):
        with self.assertRaises(PermissionError):
            self.build(verified_account={"user_id": "other"})
        self.assertEqual(self.calls, [])

    def test_absent_account_never_reaches_retrieval(self):
        with self.assertRaises(PermissionError):
            self.build(verified_account=None)
        self.assertEqual(self.calls, [])

    def test_missing_owner_configuration_fails_closed(self):
        with self.assertRaises(RuntimeError):
            self.build(configured_owner_id="")
        self.assertEqual(self.calls, [])

    def test_unbounded_query_never_reaches_retrieval(self):
        with self.assertRaises(ValueError):
            self.build(query="x" * 2001)
        self.assertEqual(self.calls, [])

    def test_malformed_approval_never_returns_evidence(self):
        with self.assertRaises(RuntimeError):
            self.build(cognize=lambda query, packet: None)

    def test_incomplete_retrieval_stops_before_cognition(self):
        for status in ("unavailable", "needs_clarification", "budget_exceeded"):
            with self.subTest(status=status):
                self.calls.clear()
                def retrieve(query):
                    self.calls.append("retrieve")
                    return {"recall_plan": {"status": status}, "evidence": [
                        {"source": "memory_general:1", "quote_source": "Stale"},
                    ]}
                with self.assertRaises(RuntimeError):
                    self.build(retrieve=retrieve)
                self.assertEqual(self.calls, ["retrieve"])

    def test_failed_freshness_check_stops_before_cognition(self):
        def retrieve(query):
            self.calls.append("retrieve")
            return {"temporal_memory": {"status": "unavailable"}, "evidence": []}
        with self.assertRaises(RuntimeError):
            self.build(retrieve=retrieve)
        self.assertEqual(self.calls, ["retrieve"])


if __name__ == "__main__":
    unittest.main()
