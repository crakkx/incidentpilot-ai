from typing import Any


class RCAClientError(RuntimeError):
    pass


class RCARequestError(RCAClientError):
    provider = "llm"


class MistralRequestError(RCARequestError):
    provider = "mistral"


class InvalidRCAOutputError(RCAClientError):
    def __init__(
        self,
        message: str,
        *,
        debug: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.debug = debug or {
            "attempts": [],
            "final_raw_output": None,
            "final_metadata": {},
            "final_validation_errors": [],
        }
