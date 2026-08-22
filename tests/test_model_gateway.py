import pytest

from ecom_dispute.llm import LLMRequestError, ResponsesClient


class SequenceResponsesClient(ResponsesClient):
    def __init__(self, sequence: list[dict | Exception]):
        super().__init__(
            "https://example.invalid",
            "test-key",
            max_attempts=2,
            retry_backoff_seconds=0,
        )
        self.sequence = sequence
        self.calls = 0

    def _create_response_once(self, payload: dict) -> dict:
        item = self.sequence[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def test_model_gateway_retries_transient_failure_once() -> None:
    client = SequenceResponsesClient(
        [
            LLMRequestError("connection reset", retryable=True),
            {"id": "response-2", "output": []},
        ]
    )

    response = client.create_response({"model": "fake"})

    assert client.calls == 2
    assert response["id"] == "response-2"
    assert response["_ecom_request_attempts"] == 2


def test_model_gateway_does_not_retry_non_transient_failure() -> None:
    client = SequenceResponsesClient(
        [LLMRequestError("HTTP 400", retryable=False), {"id": "must-not-run"}]
    )

    with pytest.raises(LLMRequestError, match="HTTP 400"):
        client.create_response({"model": "fake"})

    assert client.calls == 1


def test_model_gateway_stops_after_retry_budget() -> None:
    client = SequenceResponsesClient(
        [
            LLMRequestError("HTTP 502", retryable=True),
            LLMRequestError("HTTP 502", retryable=True),
        ]
    )

    with pytest.raises(LLMRequestError, match="HTTP 502"):
        client.create_response({"model": "fake"})

    assert client.calls == 2
