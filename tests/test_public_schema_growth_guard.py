import re
from pathlib import Path


MIGRATIONS = Path("supabase/migrations")
CUTOFF = 20261001000000
APPROVAL_PREFIX = "data-api-public-relation-approved:"

CREATE_RELATION = re.compile(
    r"""\bcreate\s+
        (?:(?:or\s+replace)\s+)?
        (?P<kind>table|view|materialized\s+view)
        (?:\s+if\s+not\s+exists)?
        \s+(?P<name>(?:"[^"]+"|[a-zA-Z_][a-zA-Z0-9_$]*)
        (?:\.(?:"[^"]+"|[a-zA-Z_][a-zA-Z0-9_$]*))?)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def migration_timestamp(path: Path) -> int | None:
    prefix = path.stem.split("_", 1)[0]
    if len(prefix) != 14 or not prefix.isdigit():
        return None
    return int(prefix)


def normalize_identifier(value: str) -> str:
    return value.replace('"', "").strip().lower()


def public_approvals(sql: str) -> set[str]:
    approvals = set()
    for line in sql.splitlines():
        lowered = line.strip().lower()
        marker = f"-- {APPROVAL_PREFIX}"
        if lowered.startswith(marker):
            relation = lowered.split(APPROVAL_PREFIX, 1)[1].strip()
            if relation:
                approvals.add(normalize_identifier(relation))
    return approvals


def new_relation_creations():
    for path in sorted(MIGRATIONS.glob("*.sql")):
        stamp = migration_timestamp(path)
        if stamp is None or stamp < CUTOFF:
            continue
        sql = path.read_text(encoding="utf-8")
        approvals = public_approvals(sql)
        for match in CREATE_RELATION.finditer(sql):
            yield path, match.group("kind").lower(), match.group("name"), approvals


def test_new_relations_name_their_schema_explicitly():
    violations = []
    for path, kind, raw_name, _approvals in new_relation_creations():
        normalized = normalize_identifier(raw_name)
        if "." not in normalized:
            violations.append(f"{path}:{kind}:{raw_name}")

    assert not violations, (
        "New database relations must name their schema explicitly. "
        "Backend-only storage belongs in private.* by default. Violations: "
        + ", ".join(violations)
    )


def test_new_public_relations_require_explicit_data_api_approval_marker():
    violations = []
    for path, kind, raw_name, approvals in new_relation_creations():
        normalized = normalize_identifier(raw_name)
        if not normalized.startswith("public."):
            continue
        if normalized not in approvals:
            violations.append(f"{path}:{kind}:{normalized}")

    assert not violations, (
        "New public relations expand PostgREST's schema-cache surface and "
        "require an explicit per-object approval comment of the form "
        "'-- data-api-public-relation-approved: public.object_name'. "
        "Violations: " + ", ".join(violations)
    )


def test_growth_guard_cutoff_and_marker_are_stable_contracts():
    assert CUTOFF == 20261001000000
    assert APPROVAL_PREFIX == "data-api-public-relation-approved:"
