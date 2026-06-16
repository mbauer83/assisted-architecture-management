"""SPA-aware static serving: history-fallback to index.html for client-side routes."""

from __future__ import annotations

from typing import Any

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """StaticFiles that serves index.html for unmatched, extensionless paths.

    A single-page app routes on the client, so a deep link such as ``/entities/groups`` has no
    file on disk; plain ``StaticFiles`` 404s it. This subclass falls back to ``index.html`` for
    such paths so the SPA boots and resolves the route itself (and direct navigation / refresh
    on any route works). Guards keep the fallback narrow:

    - ``api/`` and ``mcp/`` paths are never rewritten — they are matched by their own routes
      before this mount, and if an unknown one reaches here it still 404s.
    - Paths whose final segment contains a dot (missing assets like ``assets/old.js``) 404
      normally rather than being masked by HTML.
    """

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            last_segment = path.rsplit("/", 1)[-1]
            if exc.status_code == 404 and not path.startswith(("api/", "mcp/")) and "." not in last_segment:
                return await super().get_response("index.html", scope)
            raise
