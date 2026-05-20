import asyncio
import logging
import re
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SWITCH_URL = "https://github.com/NikiYaooo/GBA-switch/blob/main/switch.txt"
CHECK_TIMEOUT = 5

_cache: dict = {"result": None, "timestamp": 0.0}
CACHE_TTL = 30  # seconds


async def check_switch() -> bool:
    """Fetch remote switch from GitHub blob page. Returns True if content == '1'.
    Cached for CACHE_TTL seconds. Fail-open: network errors return True (allow)."""
    import requests
    loop = asyncio.get_event_loop()
    now = loop.time()
    if _cache["result"] is not None and now - _cache["timestamp"] < CACHE_TTL:
        return _cache["result"]

    try:
        def _fetch():
            r = requests.get(SWITCH_URL, timeout=CHECK_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            html = r.text
            # GitHub blob page embeds file contents in rawLines JSON field
            m = re.search(r'rawLines":\s*\[?\s*"([^"]+)"\s*\]?', html)
            return m.group(1).strip() if m else ""
        text = await loop.run_in_executor(None, _fetch)
        result = text == "1"
        _cache["result"] = result
        _cache["timestamp"] = now
        return result
    except Exception as e:
        logging.warning(f"Switch check failed (allowing): {e}")
        return True  # fail open


SKIP_PATHS = {"/", "/docs", "/openapi.json"}


class SwitchMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that checks the remote switch on every request.
    - Before request: if switch != 1, return 403 "软件权限不足"
    - After request: if switch != 1, add X-Switch-Status: off header
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in SKIP_PATHS:
            return await call_next(request)

        # Before request: check switch
        allowed = await check_switch()
        if not allowed:
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "软件权限不足"},
            )

        # Process request
        response = await call_next(request)

        # After request: check switch again
        allowed = await check_switch()
        if not allowed:
            response.headers["X-Switch-Status"] = "off"

        return response
