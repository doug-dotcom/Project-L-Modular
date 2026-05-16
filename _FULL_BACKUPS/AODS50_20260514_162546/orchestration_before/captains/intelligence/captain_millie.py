from orchestration.captains.base_captain import (
    BaseCaptain
)

class CaptainMillie(BaseCaptain):

    def __init__(
        self,
        should_handle_fn,
        execute_fn
    ):

        super().__init__(
            name="Millie",
            domain="memory"
        )

        self._should_handle = should_handle_fn
        self._execute = execute_fn

    def should_handle(
        self,
        user_msg
    ):

        return self._should_handle(
            user_msg
        )

    def execute(
        self,
        user_msg
    ):

        return self._execute(
            user_msg
        )
