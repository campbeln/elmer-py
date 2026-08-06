"""
##################################################
#
#           Rate limiting (added by security audit, 2026-08-06)
#
##################################################
Version: 2026-08-06

Fixed-window, in-process rate limiting for the endpoints where the audit
found no throttling at all: login/basic-auth (brute-force target) and
public ticket submission (spam/resource-exhaustion target).

HONEST LIMITATION: state is a plain dict in process memory. That is
sufficient on the Docker/traditional deployment path (one long-lived
process). On Vercel it is best-effort only — concurrent invocations may
land in different containers that don't share this dict, and any
container recycle resets the counters. This is the same constraint this
project already documents for elmer.app.cache and the /elmer/proxy
registry (see README's "Deploying to Vercel" section); a deployment that
needs rate limiting to hold under serverless concurrency should back this
with Redis or a Supabase table instead. Documented rather than silently
assumed away.
"""

import time

from libs.ish.ish import Obj

#: {bucket_key: [(window_start_epoch_seconds, count), ...]} — one entry
#: per (limiter name, client identity).
_WINDOWS = {}


def _client_id(request):
    """Best-effort caller identity for bucketing.

    Prefers the left-most X-Forwarded-For hop (set by most reverse proxies
    and by Vercel) over the raw socket address, which is meaningless
    behind a proxy/serverless edge. This is trivially spoofable by a
    direct client that isn't behind a trusted proxy — acceptable for
    abuse-mitigation throttling, not for identity/authorization.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(request.raw, "remote_addr", None) or "unknown"


def check(name, request, max_requests, window_seconds):
    """Direct rate-limit check for use inside a single handler.

    Router middleware (see limiter() below) applies to every route on a
    router, which is too coarse when only one or two routes on a shared
    router need throttling — e.g. /tickets carries both public creation
    (needs throttling) and admin-key-gated browsing (already access
    controlled, would be wrongly penalised by sharing a creation-spam
    bucket). Returns (allowed: bool, retry_after_seconds: int).
    """
    key = (name, _client_id(request))
    now = time.time()
    window_start, count = _WINDOWS.get(key, (now, 0))

    if now - window_start >= window_seconds:
        window_start, count = now, 0

    count += 1
    _WINDOWS[key] = (window_start, count)

    if count > max_requests:
        return False, max(1, int(window_seconds - (now - window_start)))
    return True, 0


def limiter(name, max_requests, window_seconds):
    """Build a fixed-window rate-limit middleware.

    name: bucket namespace (so /login and /tickets don't share a counter).
    max_requests: allowed requests per client within window_seconds.
    """

    def middleware(request, response, fn_continue):
        key = (name, _client_id(request))
        now = time.time()
        window_start, count = _WINDOWS.get(key, (now, 0))

        if now - window_start >= window_seconds:
            window_start, count = now, 0

        count += 1
        _WINDOWS[key] = (window_start, count)

        if count > max_requests:
            retry_after = max(1, int(window_seconds - (now - window_start)))
            response.set("Retry-After", str(retry_after))
            response.status(429).json({
                "success": False,
                "error": "Too many requests. Try again shortly.",
                "retryAfterSeconds": retry_after,
            })
            return

        fn_continue()

    return middleware
