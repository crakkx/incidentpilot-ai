from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject request bodies over ``max_bytes`` with 413 before they reach
    any route handler. Checks ``Content-Length`` up front, then enforces the
    same cap against the actual body in case the header is absent or
    understated.

    Reads via ``request.body()`` rather than manually re-wrapping
    ``receive`` — Starlette's ``BaseHTTPMiddleware`` hands ``dispatch`` a
    ``_CachedRequest`` whose ``call_next`` replays from its own internal
    cache, not from anything reassigned on the ``Request`` object, so
    ``request.body()`` is both the simplest and the only correct way to
    consume-then-forward the body here.
    """

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body exceeds {self.max_bytes} bytes"},
            )

        body = await request.body()
        if len(body) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body exceeds {self.max_bytes} bytes"},
            )

        return await call_next(request)
