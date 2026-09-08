"""Tests for app/api/router_controller.py — api_router route composition."""

from fastapi.routing import APIRoute, APIRouter

from app.api.router_controller import api_router


def _route_paths() -> list[str]:
    """Collect all APIRoute paths, including those nested inside _IncludedRouter objects."""
    paths: list[str] = []
    for entry in api_router.routes:
        # FastAPI wraps include_router() entries in _IncludedRouter; unwrap to APIRouter.
        inner: APIRouter | None = getattr(entry, "original_router", None)
        if inner is not None:
            for route in inner.routes:
                if isinstance(route, APIRoute):
                    paths.append(route.path)
        elif isinstance(entry, APIRoute):
            paths.append(entry.path)
    return paths


def test_router_includes_health_routes() -> None:
    """api_router contains at least one route under /health."""
    assert any("/health" in path for path in _route_paths())


def test_router_includes_embedding_routes() -> None:
    """api_router contains at least one route under /embedding."""
    assert any("/embedding" in path for path in _route_paths())


def test_router_includes_storage_routes() -> None:
    """api_router contains at least one route under /storage."""
    assert any("/storage" in path for path in _route_paths())


def test_router_has_multiple_routes() -> None:
    """api_router composes routes from three sub-routers."""
    assert len(_route_paths()) >= 3


def test_router_health_liveness_path_present() -> None:
    """The specific liveness path /health/live is registered."""
    assert "/health/live" in _route_paths()


def test_router_embedding_save_document_path_present() -> None:
    """The save_document_vecstore path is registered."""
    assert any("save_document_vecstore" in path for path in _route_paths())


def test_router_storage_upload_path_present() -> None:
    """The storage upload path is registered."""
    assert any("/storage/upload" in path for path in _route_paths())
