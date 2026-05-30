# =====================================================
# SHORT TERM RETRIEVAL ENGINE
# =====================================================

MAX_ROW_CHARS = 2000
MAX_PACKET_CHARS = 12000

def build_short_term_packet(rows):

    if not rows:
        return ""

    packet = ""

    total_chars = 0

    print("")
    print("======================================")
    print("SHORT TERM PACKET BUILD")
    print("======================================")

    for idx, row in enumerate(rows):

        role = str(
            row.get(
                "role",
                ""
            )
        )

        content = str(
            row.get(
                "content",
                ""
            )
        )

        original_size = len(content)

        print(
            f"ROW {idx+1} | "
            f"ROLE={role} | "
            f"SIZE={original_size}"
        )

        # =============================================
        # CAP INDIVIDUAL MEMORY SIZE
        # =============================================

        if len(content) > MAX_ROW_CHARS:

            print(
                f"ROW {idx+1} TRIMMED "
                f"{len(content)} -> "
                f"{MAX_ROW_CHARS}"
            )

            content = (
                content[:MAX_ROW_CHARS]
                + "\n[TRIMMED]"
            )

        line = (
            f"{role}: {content}\n"
        )

        # =============================================
        # CAP TOTAL PACKET SIZE
        # =============================================

        if (
            total_chars
            + len(line)
        ) > MAX_PACKET_CHARS:

            print(
                "PACKET LIMIT REACHED"
            )

            packet += (
                "\n[SHORT TERM PACKET "
                "TRIMMED]"
            )

            break

        packet += line

        total_chars += len(line)

    print(
        f"FINAL PACKET SIZE: "
        f"{len(packet)}"
    )

    print("======================================")
    print("")

    return packet