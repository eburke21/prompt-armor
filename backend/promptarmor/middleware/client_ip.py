"""Client IP extraction helper.

Behind a reverse proxy (Railway, Vercel, Cloudflare), `request.client.host`
is the proxy's IP, not the end user's. Per-IP rate limiting degenerates into
a global bucket in that case. When `settings.trust_forwarded_for` is enabled,
we read the X-Forwarded-For header and take the first entry (the original
client as reported by the edge).

SECURITY: This header is trivially spoofable by a client that talks to the
backend directly. Only enable `trust_forwarded_for` when the backend is
deployed behind a proxy that strips/overwrites this header on ingress.
"""

from fastapi import Request

from promptarmor.config import settings


def get_client_ip(request: Request) -> str:
    """Return the best-effort client IP for rate limiting."""
    if settings.trust_forwarded_for:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            first = fwd.split(",")[0].strip()
            if first:
                return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
