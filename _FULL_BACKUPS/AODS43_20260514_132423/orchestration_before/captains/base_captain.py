# ============================================================
# SHINE L BASE CAPTAIN
# Officer Doctrine
# ============================================================

class BaseCaptain:

    def __init__(
        self,
        name,
        domain,
        rank="Captain",
        active=True
    ):

        self.name = name
        self.domain = domain
        self.rank = rank
        self.active = active

    # ========================================================
    # OFFICER STATUS
    # ========================================================

    def status(self):

        return {
            "name": self.name,
            "domain": self.domain,
            "rank": self.rank,
            "active": self.active
        }

    # ========================================================
    # SHOULD HANDLE
    # ========================================================

    def should_handle(
        self,
        user_msg
    ):

        raise NotImplementedError(
            f"{self.name} must implement should_handle()"
        )

    # ========================================================
    # EXECUTE
    # ========================================================

    def execute(
        self,
        user_msg
    ):

        raise NotImplementedError(
            f"{self.name} must implement execute()"
        )

    # ========================================================
    # REPRESENTATION
    # ========================================================

    def __repr__(self):

        return (
            f"<{self.rank} "
            f"{self.name} "
            f"({self.domain})>"
        )
