"""Build the secret-free Postman v2.1 collection for LMS 271."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEST = """pm.test("HTTP {code}", () => pm.response.to.have.status({code}));
{json_test}
{extra}"""


def request(
    name, method, path, *, status=200, body=None, auth="tenant", extra="", pre=""
):
    url = "{{base_url}}" + path
    spec = {"method": method, "header": [], "url": url}
    if auth == "public":
        spec["auth"] = {"type": "noauth"}
    elif auth == "landlord":
        spec["auth"] = {
            "type": "bearer",
            "bearer": [
                {"key": "token", "value": "{{landlord_access_token}}", "type": "string"}
            ],
        }
    if body is not None:
        spec["header"].append({"key": "Content-Type", "value": "application/json"})
        spec["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2, ensure_ascii=False),
        }
    events = [
        {
            "listen": "test",
            "script": {
                "type": "text/javascript",
                "exec": TEST.format(
                    code=status,
                    json_test=(
                        ""
                        if status == 204
                        else 'pm.test("JSON content type", () => pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json"));'
                    ),
                    extra=extra,
                ).splitlines(),
            },
        }
    ]
    if pre:
        events.insert(
            0,
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": pre.splitlines(),
                },
            },
        )
    return {"name": name, "request": spec, "event": events}


def folder(name, items):
    return {"name": name, "item": items}


tenant_login = request(
    "Login — Tenant",
    "POST",
    "/api/auth/login/",
    auth="public",
    body={"email": "{{tenant_email}}", "password": "{{tenant_password}}"},
    extra='const j = pm.response.json(); pm.test("JWT pair", () => { pm.expect(j.access).to.be.a("string"); pm.expect(j.refresh).to.be.a("string"); }); pm.environment.set("tenant_access_token", j.access); pm.environment.set("tenant_refresh_token", j.refresh);',
)
landlord_login = request(
    "Login — Landlord",
    "POST",
    "/api/auth/login/",
    auth="public",
    body={"email": "{{landlord_email}}", "password": "{{landlord_password}}"},
    extra='const j = pm.response.json(); pm.environment.set("landlord_access_token", j.access); pm.environment.set("landlord_refresh_token", j.refresh);',
)
listing_body = {
    "title": "Postman demo — apartment",
    "description": "Synthetic demonstration listing",
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
create_listing = request(
    "Create listing — Landlord",
    "POST",
    "/api/listings/",
    status=201,
    auth="landlord",
    body=listing_body,
    extra='pm.environment.set("listing_id", pm.response.json().id);',
)
create_booking = request(
    "Create booking — Tenant",
    "POST",
    "/api/bookings/",
    status=201,
    body={
        "listing_id": "{{listing_id}}",
        "check_in": "{{check_in}}",
        "check_out": "{{check_out}}",
    },
    pre='const dateAfter = n => { const d = new Date(); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }; pm.environment.set("check_in", dateAfter(30)); pm.environment.set("check_out", dateAfter(33));',
    extra=(
        'const j = pm.response.json(); pm.test("Pending booking", () => pm.expect(j.status).to.eql("PENDING")); pm.environment.set("booking_id", j.id);\n'
        "const quoted = pm.response.json().total_price;\n"
        'pm.test("Total price is a positive fixed two-decimal quote", () => { pm.expect(Number(quoted).toFixed(2)).to.eql(quoted); pm.expect(Number(quoted)).to.be.above(0); });\n'
        'pm.environment.set("booking_total_price", quoted);'
    ),
)
confirm_booking = request(
    "Confirm booking — Landlord",
    "POST",
    "/api/bookings/{{booking_id}}/confirm/",
    auth="landlord",
    extra=(
        'pm.test("Confirmed", () => pm.expect(pm.response.json().status).to.eql("CONFIRMED"));\n'
        'pm.test("Confirmation preserves original booking quote", () => pm.expect(pm.response.json().total_price).to.eql(pm.environment.get("booking_total_price")));'
    ),
)
collection = {
    "info": {
        "name": "Python Developer — Final Project (Django)",
        "description": "LMS 271. All accounts and data are synthetic. Set the two local demo passwords in the private Postman environment. Run Demo flow in folder order; other folders are reference and edge-case requests. Secrets are never part of this exported collection.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "auth": {
        "type": "bearer",
        "bearer": [
            {"key": "token", "value": "{{tenant_access_token}}", "type": "string"}
        ],
    },
    "item": [
        folder(
            "Demo flow",
            [
                tenant_login,
                landlord_login,
                create_listing,
                create_booking,
                confirm_booking,
                request(
                    "List confirmed tenant bookings",
                    "GET",
                    "/api/bookings/?status=CONFIRMED",
                ),
                request(
                    "Public listing details",
                    "GET",
                    "/api/listings/{{listing_id}}/",
                    auth="public",
                ),
                request(
                    "Popular listings",
                    "GET",
                    "/api/statistics/popular-listings/",
                    auth="public",
                ),
            ],
        ),
        folder(
            "Auth",
            [
                request(
                    "Register new Tenant",
                    "POST",
                    "/api/auth/register/",
                    status=201,
                    auth="public",
                    body={
                        "email": "{{registration_email}}",
                        "display_name": "Postman Demo",
                        "password": "{{registration_password}}",
                    },
                ),
                request(
                    "Tenant login",
                    "POST",
                    "/api/auth/login/",
                    auth="public",
                    body={
                        "email": "{{tenant_email}}",
                        "password": "{{tenant_password}}",
                    },
                    extra='const j = pm.response.json(); pm.environment.set("tenant_access_token", j.access); pm.environment.set("tenant_refresh_token", j.refresh);',
                ),
                request(
                    "Landlord login",
                    "POST",
                    "/api/auth/login/",
                    auth="public",
                    body={
                        "email": "{{landlord_email}}",
                        "password": "{{landlord_password}}",
                    },
                    extra='const j = pm.response.json(); pm.environment.set("landlord_access_token", j.access); pm.environment.set("landlord_refresh_token", j.refresh);',
                ),
                request("Who am I", "GET", "/api/auth/me/"),
                request(
                    "Refresh JWT",
                    "POST",
                    "/api/auth/refresh/",
                    auth="public",
                    body={"refresh": "{{tenant_refresh_token}}"},
                    extra='pm.environment.set("tenant_access_token", pm.response.json().access);',
                ),
                request(
                    "Logout JWT refresh",
                    "POST",
                    "/api/auth/logout/",
                    status=204,
                    body={"refresh": "{{tenant_refresh_token}}"},
                ),
            ],
        ),
        folder(
            "Listings",
            [
                request("List public listings", "GET", "/api/listings/", auth="public"),
                create_listing,
                request(
                    "Get listing", "GET", "/api/listings/{{listing_id}}/", auth="public"
                ),
                request(
                    "Update own listing",
                    "PATCH",
                    "/api/listings/{{listing_id}}/",
                    auth="landlord",
                    body={"title": "Updated Postman demo listing"},
                ),
                request(
                    "Soft delete own listing — terminal step",
                    "DELETE",
                    "/api/listings/{{listing_id}}/",
                    status=204,
                    auth="landlord",
                ),
            ],
        ),
        folder(
            "Search & Filters",
            [
                request(
                    "Keyword, city and price",
                    "GET",
                    "/api/listings/?search=demo&city=Berlin&min_price=40&max_price=180",
                    auth="public",
                ),
                request(
                    "Rooms and housing type",
                    "GET",
                    "/api/listings/?rooms_min=1&rooms_max=3&housing_type=APARTMENT",
                    auth="public",
                ),
                request(
                    "Popularity and pagination",
                    "GET",
                    "/api/listings/?ordering=popular&page=1",
                    auth="public",
                ),
                request(
                    "Invalid price range — 400",
                    "GET",
                    "/api/listings/?min_price=200&max_price=10",
                    status=400,
                    auth="public",
                ),
            ],
        ),
        folder(
            "Bookings",
            [
                create_booking,
                request("Tenant bookings", "GET", "/api/bookings/?scope=active"),
                request(
                    "Landlord incoming",
                    "GET",
                    "/api/bookings/?role=landlord",
                    auth="landlord",
                ),
                request("Booking details", "GET", "/api/bookings/{{booking_id}}/"),
                confirm_booking,
                request(
                    "Reject pending booking — separate pending ID",
                    "POST",
                    "/api/bookings/{{pending_booking_id}}/reject/",
                    auth="landlord",
                ),
                request(
                    "Cancel booking — Tenant",
                    "POST",
                    "/api/bookings/{{booking_id}}/cancel/",
                ),
                request("Completed stays", "GET", "/api/bookings/?scope=completed"),
            ],
        ),
        folder(
            "Reviews",
            [
                request(
                    "Create after completed stay",
                    "POST",
                    "/api/reviews/",
                    status=201,
                    body={
                        "booking_id": "{{completed_booking_id}}",
                        "rating": 5,
                        "comment": "Synthetic stay completed successfully.",
                    },
                    extra='pm.environment.set("review_id", pm.response.json().id);',
                ),
                request(
                    "Public review", "GET", "/api/reviews/{{review_id}}/", auth="public"
                ),
                request(
                    "Edit own review",
                    "PATCH",
                    "/api/reviews/{{review_id}}/",
                    body={"rating": 4, "comment": "Updated synthetic review."},
                ),
                request(
                    "Listing reviews and average",
                    "GET",
                    "/api/listings/{{listing_id}}/reviews/",
                    auth="public",
                ),
            ],
        ),
        folder(
            "Statistics",
            [
                request(
                    "Private search history", "GET", "/api/statistics/search-history/"
                ),
                request("Private view history", "GET", "/api/statistics/view-history/"),
                request(
                    "Public popular searches",
                    "GET",
                    "/api/statistics/popular-searches/",
                    auth="public",
                ),
                request(
                    "Public popular listings",
                    "GET",
                    "/api/statistics/popular-listings/",
                    auth="public",
                ),
            ],
        ),
        folder(
            "OpenAPI",
            [
                request("Schema", "GET", "/api/schema/", auth="public", extra=""),
                request("Swagger UI", "GET", "/api/docs/", auth="public"),
            ],
        ),
    ],
    "variable": [{"key": "base_url", "value": "http://127.0.0.1:8765"}],
}

# OpenAPI endpoints return YAML/HTML; override JSON content type test.
for item in collection["item"][-1]["item"]:
    item["event"][0]["script"]["exec"] = [
        "pm.test('HTTP 200', () => pm.response.to.have.status(200));"
    ]

environment = {
    "name": "Django Final Project — Local (template)",
    "values": [
        {"key": "base_url", "value": "http://127.0.0.1:8765", "enabled": True},
        {
            "key": "tenant_email",
            "value": "demo-27150-tenant-00000@example.invalid",
            "enabled": True,
        },
        {
            "key": "landlord_email",
            "value": "demo-27150-landlord-00000@example.invalid",
            "enabled": True,
        },
        *[
            {"key": key, "value": "", "type": "secret", "enabled": True}
            for key in (
                "tenant_password",
                "landlord_password",
                "registration_password",
                "tenant_access_token",
                "landlord_access_token",
                "tenant_refresh_token",
                "landlord_refresh_token",
            )
        ],
        *[
            {"key": key, "value": "", "enabled": True}
            for key in (
                "registration_email",
                "listing_id",
                "booking_id",
                "booking_total_price",
                "pending_booking_id",
                "completed_booking_id",
                "review_id",
                "check_in",
                "check_out",
            )
        ],
    ],
    "_postman_variable_scope": "environment",
}
(ROOT / "Django.postman_collection.json").write_text(
    json.dumps(collection, ensure_ascii=False, indent=2) + "\n"
)
(ROOT / "Django.local.postman_environment.json").write_text(
    json.dumps(environment, ensure_ascii=False, indent=2) + "\n"
)
print("Collection:", sum(len(f["item"]) for f in collection["item"]), "requests")
