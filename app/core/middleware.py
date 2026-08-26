"""Correlation id propagation middleware.

Lee ``X-Correlation-ID`` del request entrante (o genera uno nuevo), lo deja
disponible en ``request.state.correlation_id`` y en el ``ContextVar`` que usa
``CorrelationIdFilter`` (app.core.logging) para que aparezca en cada linea de
log emitida durante esa request, y lo devuelve en la respuesta para que quien
llamo al servicio pueda seguir la traza.
"""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import correlation_id_var

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())
        token = correlation_id_var.set(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
