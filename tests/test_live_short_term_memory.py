from memory.continuity.live_short_term import (
    classify_short_term_domain,
    write_short_term_memory,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        self.client.writes.append((self.table_name, self.payload))
        return FakeResponse([{"id": len(self.client.writes)}])


class FakeSupabase:
    def __init__(self):
        self.writes = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class FailingQuery(FakeQuery):
    def execute(self):
        raise RuntimeError("temporary database fault")


class FailingSupabase(FakeSupabase):
    def table(self, table_name):
        return FailingQuery(self, table_name)


def test_classifies_live_message_into_rhees_existing_domain():
    assert classify_short_term_domain("Luella had a brilliant day") == "short_term_family"
    assert classify_short_term_domain("Project L memory is working") == "short_term_project_l"
    assert classify_short_term_domain("Just checking in") == "short_term_general"


def test_project_l_architecture_does_not_match_na_inside_original():
    prompt = (
        "L, recall why we created Project L, compare the original architecture "
        "with what you can do now, identify contradictions, and recommend a path."
    )
    assert classify_short_term_domain(prompt) == "short_term_project_l"
    assert classify_short_term_domain("RIKE and Rhee architecture") == "short_term_project_l"


def test_writes_both_sides_of_an_exchange_to_the_same_domain():
    client = FakeSupabase()
    table_name = classify_short_term_domain("Luella had a brilliant day")

    user_result = write_short_term_memory(client, table_name, "user", "Luella had a brilliant day")
    assistant_result = write_short_term_memory(client, table_name, "assistant", "That sounds lovely.")

    assert user_result == {"saved": True, "table": table_name, "role": "user", "id": 1}
    assert assistant_result == {"saved": True, "table": table_name, "role": "assistant", "id": 2}
    assert client.writes == [
        (table_name, {"role": "user", "content": "Luella had a brilliant day"}),
        (table_name, {"role": "assistant", "content": "That sounds lovely."}),
    ]


def test_rejects_invalid_writes_and_degrades_gracefully():
    assert write_short_term_memory(None, "short_term_general", "user", "hello")["reason"] == "supabase_unavailable"
    assert write_short_term_memory(FakeSupabase(), "raw_catchall", "user", "hello")["reason"] == "invalid_table"
    assert write_short_term_memory(FakeSupabase(), "short_term_general", "system", "hello")["reason"] == "invalid_role"
    assert write_short_term_memory(FakeSupabase(), "short_term_general", "user", "  ")["reason"] == "empty_content"

    result = write_short_term_memory(FailingSupabase(), "short_term_general", "user", "hello")
    assert result["saved"] is False
    assert result["reason"] == "write_failed"
