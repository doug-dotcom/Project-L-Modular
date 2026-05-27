# =====================================================
# SHORT-TERM RETRIEVAL ENGINE
# =====================================================

def build_short_term_packet(
    rows
):

    if not rows:
        return ""

    packet = ""

    for row in rows:

        role = row.get(
            "role",
            ""
        )

        content = row.get(
            "content",
            ""
        )

        packet += (
            f"{role}: {content}\n"
        )

    return packet


