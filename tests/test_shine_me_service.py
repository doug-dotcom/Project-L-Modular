import unittest

from core.cognition.shine_me_service import (
    answer_from_shine_me_context,
    prepare_shine_me_context,
)


class ShineMeServiceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def retrieve(self, query):
        self.calls.append("retrieve")
        return {"recall_plan": {"status": "checked"},
                "temporal_memory": {"status": "checked", "user_id": "owner-a"},
                "evidence": [{
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
            configured_memory_owner_id="owner-a",
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

    def test_missing_or_different_memory_namespace_never_reaches_retrieval(self):
        for memory_owner in ("", "other"):
            with self.subTest(memory_owner=memory_owner):
                with self.assertRaises(RuntimeError):
                    self.build(configured_memory_owner_id=memory_owner)
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
            return {"recall_plan": {"status": "checked"},
                    "temporal_memory": {"status": "unavailable", "user_id": "owner-a"},
                    "evidence": []}
        with self.assertRaises(RuntimeError):
            self.build(retrieve=retrieve)
        self.assertEqual(self.calls, ["retrieve"])

    def test_temporal_owner_mismatch_stops_before_cognition(self):
        def retrieve(query):
            self.calls.append("retrieve")
            return {"recall_plan": {"status": "checked"},
                    "temporal_memory": {"status": "checked", "user_id": "other"},
                    "evidence": [{"source": "memory_general:1", "quote_source": "Private"}]}
        with self.assertRaises(PermissionError):
            self.build(retrieve=retrieve)
        self.assertEqual(self.calls, ["retrieve"])

    def test_missing_retrieval_receipt_stops_before_cognition(self):
        with self.assertRaises(RuntimeError):
            self.build(retrieve=lambda query: {"evidence": []})
        self.assertEqual(self.calls, [])

    def test_answer_quotes_only_user_authored_evidence(self):
        answer = answer_from_shine_me_context(self.build())
        self.assertEqual(answer["status"], "quoted_user_memory")
        self.assertIn("Context first", answer["reply"])
        self.assertEqual(answer["evidence"], [
            {"source": "memory_general:1", "provenance": "user_statement"}
        ])

    def test_no_approved_memory_does_not_invent_an_answer(self):
        answer = answer_from_shine_me_context({"records": []})
        self.assertEqual(answer["status"], "no_approved_evidence")
        self.assertEqual(answer["evidence"], [])

    def test_model_authored_memory_cannot_be_attributed_to_user(self):
        answer = answer_from_shine_me_context({"records": [{
            "text": "The user likes blue", "source": "memory_general:5",
            "provenance": "model_statement",
        }]})
        self.assertEqual(answer["status"], "unverified_model_memory")
        self.assertTrue(answer["reply"].startswith("An earlier assistant wrote:"))


if __name__ == "__main__":
    unittest.main()
