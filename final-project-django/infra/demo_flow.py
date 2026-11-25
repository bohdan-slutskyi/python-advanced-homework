"""Deterministic, secret-safe HTTP defense demo against the local Compose API.

Requires a fresh seed_demo dataset without preexisting reviews and the same
DEMO_USER_PASSWORD used when creating synthetic accounts.
"""

import argparse
import json
import os
import secrets
from datetime import datetime, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "http://127.0.0.1:18765"
checks = 0


def call(method, path, expected, *, token=None, body=None):
    global checks
    url = BASE_URL + path
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(
        url,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            actual = response.status
            raw = response.read()
    except HTTPError as exc:
        actual = exc.code
        raw = exc.read()
    if actual != expected:
        # Never log credentials, JWTs, or error response bodies.
        raise AssertionError(f"{method} {path}: HTTP {actual}, expected {expected}")
    checks += 1
    print(f"PASS {expected} {method} {path.split('?')[0]}")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def expect(condition, message):
    global checks
    if not condition:
        raise AssertionError(message)
    checks += 1


def page_results(data):
    expect(
        isinstance(data, dict) and isinstance(data.get("results"), list),
        "Expected a paginated DRF response",
    )
    return data["results"]


def run(seed, password):
    tenant_email = f"demo-{seed}-tenant-00000@example.invalid"
    landlord_email = f"demo-{seed}-landlord-00000@example.invalid"

    call("GET", "/api/auth/me/", 401)
    tenant = call(
        "POST",
        "/api/auth/login/",
        200,
        body={"email": tenant_email, "password": password},
    )["access"]
    landlord = call(
        "POST",
        "/api/auth/login/",
        200,
        body={"email": landlord_email, "password": password},
    )["access"]
    expect(bool(tenant and landlord), "Missing JWT tokens")
    expect(
        call("GET", "/api/auth/me/", 200, token=tenant)["email"] == tenant_email,
        "Incorrect tenant identity",
    )

    listing = {
        "title": f"Defense demo {seed} {secrets.token_hex(4)}",
        "description": "Synthetic listing used for final project verification",
        "city": "Berlin",
        "district": "Mitte",
        "postal_code": "10115",
        "street": "Demoallee",
        "house_number": "12",
        "housing_type": "APARTMENT",
        "rooms": 2,
        "price_per_night": "99.00",
        "is_active": True,
    }
    call("POST", "/api/listings/", 403, token=tenant, body=listing)
    created = call("POST", "/api/listings/", 201, token=landlord, body=listing)
    listing_id = created["id"]
    url = f"/api/listings/{listing_id}/"
    call("PATCH", url, 403, token=tenant, body={"title": "Forbidden"})
    call("PATCH", url, 200, token=landlord, body={"is_active": False})
    call("GET", url, 404)
    call("PATCH", url, 200, token=landlord, body={"is_active": True})
    call("GET", url, 200)
    catalog = call("GET", "/api/listings/?search=Defense&city=Berlin", 200)
    expect(
        any(obj["id"] == listing_id for obj in page_results(catalog)),
        "The new listing is missing from catalog search",
    )
    call("GET", "/api/listings/?min_price=200&max_price=10", 400)

    today = datetime.now(ZoneInfo("Europe/Berlin")).date()

    def date_after(days):
        return (today + timedelta(days=days)).isoformat()

    def booking_request(start, end):
        return {
            "listing_id": listing_id,
            "check_in": date_after(start),
            "check_out": date_after(end),
        }

    body = booking_request(30, 33)
    pending = call("POST", "/api/bookings/", 201, token=tenant, body=body)
    booking_id = pending["id"]
    expect(pending["status"] == "PENDING", "Expected PENDING state")
    expect(
        pending["total_price"] == "297.00", "Three nights at 99.00 must quote 297.00"
    )
    call("POST", f"/api/bookings/{booking_id}/confirm/", 403, token=tenant)
    confirmed = call(
        "POST", f"/api/bookings/{booking_id}/confirm/", 200, token=landlord
    )
    expect(confirmed["status"] == "CONFIRMED", "Expected CONFIRMED state")
    expect(
        confirmed["total_price"] == pending["total_price"],
        "Confirmation must preserve the booking quote",
    )
    call("POST", "/api/bookings/", 409, token=tenant, body=body)
    call("POST", f"/api/bookings/{booking_id}/confirm/", 409, token=landlord)
    rejected_id = call(
        "POST", "/api/bookings/", 201, token=tenant, body=booking_request(45, 48)
    )["id"]
    rejected = call("POST", f"/api/bookings/{rejected_id}/reject/", 200, token=landlord)
    expect(rejected["status"] == "REJECTED", "Expected REJECTED state")
    cancelled_id = call(
        "POST", "/api/bookings/", 201, token=tenant, body=booking_request(60, 62)
    )["id"]
    cancelled = call("POST", f"/api/bookings/{cancelled_id}/cancel/", 200, token=tenant)
    expect(cancelled["status"] == "CANCELLED", "Expected CANCELLED state")
    expect(
        any(
            item["id"] == booking_id
            for item in page_results(
                call("GET", "/api/bookings/?status=CONFIRMED", 200, token=tenant)
            )
        ),
        "Confirmed booking absent from tenant list",
    )
    expect(
        any(
            item["id"] == booking_id
            for item in page_results(
                call("GET", "/api/bookings/?role=landlord", 200, token=landlord)
            )
        ),
        "Confirmed booking absent from landlord list",
    )

    # seed_demo creates a historical confirmed stay for tenant #0,
    # and --reviews 0 leaves it available for an actual Review API creation.
    completed = page_results(
        call("GET", "/api/bookings/?scope=completed", 200, token=tenant)
    )
    expect(bool(completed), "No seeded completed stay; check seed_demo options")
    earliest_checkout = (today - timedelta(days=30)).isoformat()
    past = next(
        (
            item
            for item in completed
            if earliest_checkout <= item["check_out"] <= today.isoformat()
            and item["status"] == "CONFIRMED"
        ),
        None,
    )
    expect(past is not None, "Expected an eligible completed stay; use a fresh seed")
    review = call(
        "POST",
        "/api/reviews/",
        201,
        token=tenant,
        body={
            "booking_id": past["id"],
            "rating": 5,
            "comment": "Verified synthetic completed stay.",
        },
    )
    review_id = review["id"]
    call(
        "POST",
        "/api/reviews/",
        409,
        token=tenant,
        body={"booking_id": past["id"], "rating": 4, "comment": "Duplicate"},
    )
    call("PATCH", f"/api/reviews/{review_id}/", 404, token=landlord, body={"rating": 1})
    revised = call(
        "PATCH", f"/api/reviews/{review_id}/", 200, token=tenant, body={"rating": 4}
    )
    expect(revised["rating"] == 4, "Review rating was not updated")
    public = call("GET", f"/api/reviews/{review_id}/", 200)
    expect(
        "booking_id" not in public and "tenant_id" not in public,
        "Public review leaked private IDs",
    )
    summary = call("GET", f"/api/listings/{past['listing_id']}/reviews/", 200)
    expect(
        summary["review_count"] >= 1 and summary["average_rating"] is not None,
        "Review aggregates are missing",
    )

    history = page_results(
        call("GET", "/api/statistics/search-history/", 200, token=tenant)
    )
    expect(bool(history), "Tenant search history is empty")
    page_results(call("GET", "/api/statistics/view-history/", 200, token=tenant))
    page_results(call("GET", "/api/statistics/popular-searches/", 200))
    page_results(call("GET", "/api/statistics/popular-listings/", 200))
    call("GET", "/api/statistics/search-history/", 401)
    call("GET", "/api/schema/", 200)
    print(f"Demo flow verified: {checks} HTTP and content assertions; seed={seed}.")
    print("No credentials, tokens or user identifiers were printed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=27177)
    args = parser.parse_args()
    pwd = os.environ.get("DEMO_USER_PASSWORD")
    if not pwd:
        parser.error("Set DEMO_USER_PASSWORD in the calling process environment.")
    run(args.seed, pwd)
