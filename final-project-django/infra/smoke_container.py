"""Read-only HTTP checks for the local Docker Compose API."""

import json
import os
from urllib.error import HTTPError
from urllib.request import urlopen

BASE_URL = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:18765").rstrip("/")


def check(path: str, expected_status: int) -> bytes:
    url = f"{BASE_URL}{path}"
    try:
        with urlopen(url, timeout=10) as response:
            status = response.status
            body = response.read()
    except HTTPError as exc:
        status = exc.code
        body = exc.read()
    if status != expected_status:
        raise AssertionError(
            f"{path}: expected HTTP {expected_status}, got {status}: {body[:200]!r}"
        )
    print(f"PASS {expected_status} {path}")
    return body


def main() -> None:
    check("/api/schema/", 200)
    listings = json.loads(check("/api/listings/", 200))
    assert isinstance(listings["results"], list), listings
    check("/api/statistics/popular-listings/", 200)
    check("/api/auth/me/", 401)
    check("/api/listings/?min_price=invalid", 400)


if __name__ == "__main__":
    main()
