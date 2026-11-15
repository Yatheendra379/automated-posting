from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

from app.domain import Publication, PublishingError


def require_config(**values):
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise PublishingError("Missing configuration: " + ", ".join(missing))


def https_base(value: str) -> str:
    url = urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username is not None or url.query or url.fragment:
        raise PublishingError("The configured platform URL must be an HTTPS base URL.")
    return value.rstrip("/")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def post(client: httpx.AsyncClient, url: str, **kwargs) -> dict:
    response = await client.post(url, **kwargs)
    if not response.is_success:
        descriptions = {401: "Authentication failed", 403: "Access denied", 429: "Rate limit exceeded"}
        detail = descriptions.get(response.status_code, "Platform rejected the request")
        raise PublishingError(f"{detail} (HTTP {response.status_code}).")
    data = response.json()
    if not isinstance(data, dict):
        raise PublishingError("Platform returned an invalid response.")
    return data


def publication(url: str, public: bool, timestamp: str) -> Publication:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise PublishingError("Platform did not return a valid post URL.")
    posted_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    return Publication(url, public, posted_at.astimezone(timezone.utc))
