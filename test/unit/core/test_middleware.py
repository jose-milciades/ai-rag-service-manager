"""Tests for app.core.middleware — CorrelationIdMiddleware.dispatch."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from app.core.logging import correlation_id_var
from app.core.middleware import CORRELATION_ID_HEADER, CorrelationIdMiddleware

# ---------------------------------------------------------------------------
# Helpers — tiny app with the middleware under test
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/echo")
    async def echo(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.correlation_id)

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dispatch_propagates_incoming_correlation_id(client: TestClient):
    """When X-Correlation-ID is in the request it must appear in the response."""
    resp = client.get("/echo", headers={CORRELATION_ID_HEADER: "abc-123"})
    assert resp.status_code == 200
    assert resp.headers[CORRELATION_ID_HEADER] == "abc-123"


def test_dispatch_generates_uuid_when_no_header(client: TestClient):
    """When header is absent a UUID is generated and returned."""
    resp = client.get("/echo")
    assert resp.status_code == 200
    generated = resp.headers.get(CORRELATION_ID_HEADER)
    assert generated is not None
    assert len(generated) > 0


def test_dispatch_two_requests_get_different_ids(client: TestClient):
    r1 = client.get("/echo")
    r2 = client.get("/echo")
    id1 = r1.headers[CORRELATION_ID_HEADER]
    id2 = r2.headers[CORRELATION_ID_HEADER]
    assert id1 != id2


def test_dispatch_sets_request_state_correlation_id(client: TestClient):
    """The /echo endpoint returns the value of request.state.correlation_id."""
    resp = client.get("/echo", headers={CORRELATION_ID_HEADER: "my-id"})
    assert resp.text == "my-id"


def test_dispatch_context_var_reset_after_request():
    """After the request the ContextVar must be back to the default value."""
    app = _make_app()

    captured_during: list[str] = []

    @app.get("/capture")
    async def capture() -> PlainTextResponse:
        captured_during.append(correlation_id_var.get())
        return PlainTextResponse("ok")

    c = TestClient(app, raise_server_exceptions=True)
    c.get("/capture", headers={CORRELATION_ID_HEADER: "ctx-test"})

    assert captured_during == ["ctx-test"]
    # After the request the ContextVar should be back to its default
    assert correlation_id_var.get() == "-"


def test_dispatch_context_var_reset_on_call_next_error():
    """The ContextVar must be reset even when call_next raises."""
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/boom")
    async def boom() -> PlainTextResponse:
        raise RuntimeError("intentional error")

    c = TestClient(app, raise_server_exceptions=False)
    c.get("/boom", headers={CORRELATION_ID_HEADER: "err-id"})

    # ContextVar must be back to default regardless of the error
    assert correlation_id_var.get() == "-"
