"""Safe sport entry point for Carol's canonical curator."""

from agents.carol.carol import process_domain


SOURCE_TABLE = "short_term_sport"
TARGET_TABLE = "memory_sport"


def run_carol_sport(limit=10):
    return process_domain(SOURCE_TABLE, TARGET_TABLE, limit=limit)


if __name__ == "__main__":
    print(run_carol_sport())
