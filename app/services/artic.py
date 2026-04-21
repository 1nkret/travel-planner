import httpx

from app.cache import cache_get, cache_set
from app.config import settings


ARTWORK_FIELDS = "id,title,artist_title,date_display,place_of_origin"


class ArticError(Exception):
    """Raised when the Art Institute API behaves unexpectedly."""


class ArticClient:
    """Tiny wrapper around the Art Institute of Chicago public API.

    We only need two things here: check that an artwork exists and grab its
    title to store alongside the external_id.
    """

    def __init__(self, base_url: str = settings.artic_base_url, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_artwork(self, artwork_id: int) -> dict | None:
        """Return artwork payload or None if it doesn't exist."""
        key = f"artic:artwork:{artwork_id}"

        cached = await cache_get(key)
        if cached is not None:
            # empty dict is our marker for "known to not exist" (see below)
            return cached or None

        url = f"{self._base_url}/artworks/{artwork_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params={"fields": ARTWORK_FIELDS})

        if resp.status_code == 404:
            # short-lived negative cache so bad IDs don't hammer the API
            await cache_set(key, {}, ttl=min(settings.artic_cache_ttl, 300))
            return None

        if resp.status_code >= 500:
            raise ArticError(f"artic api returned {resp.status_code}")

        resp.raise_for_status()
        data = resp.json().get("data")
        if not data:
            return None

        await cache_set(key, data, ttl=settings.artic_cache_ttl)
        return data


def get_artic_client() -> ArticClient:
    return ArticClient()
