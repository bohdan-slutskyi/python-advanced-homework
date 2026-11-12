
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import RevokedAccessToken, Task


PASSWORD = "StrongPass2026!"


class JwtCookieFlowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="existing", email="existing@example.test", password=PASSWORD
        )
        self.browser = APIClient(enforce_csrf_checks=True)

    def csrf(self, client=None):
        client = client or self.browser
        response = client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("csrftoken", client.cookies)
        return client.cookies["csrftoken"].value

    def payload(self, **kwargs):
        data = {
            "username": "newuser",
            "email": "newuser@example.test",
            "password": PASSWORD,
        }
        return data | kwargs

    def browser_post(self, path, data, client=None):
        client = client or self.browser
        return client.post(
            path,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )

    def login(self, client=None):
        client = client or self.browser
        self.csrf(client)
        response = self.browser_post(
            "/api/login/",
            {"username": "existing", "password": PASSWORD},
            client=client,
        )
        self.assertEqual(response.status_code, 200, response.data)
        return client, response

    def test_register_requires_csrf(self):
        self.assertEqual(
            self.browser.post("/api/register/", self.payload(), format="json").status_code,
            403,
        )
        self.assertFalse(get_user_model().objects.filter(username="newuser").exists())

    def test_registration_hashes_password_and_sets_http_only_cookies(self):
        self.csrf()
        response = self.browser_post("/api/register/", self.payload())
        self.assertEqual(response.status_code, 201, response.data)
        user = get_user_model().objects.get(username="newuser")
        self.assertTrue(check_password(PASSWORD, user.password))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(user.email, "newuser@example.test")
        self.assertNotIn("password", str(response.data))
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        for cookie in ("access_token", "refresh_token"):
            self.assertIn(cookie, response.cookies)
            self.assertTrue(response.cookies[cookie]["httponly"])
            self.assertEqual(response.cookies[cookie]["samesite"], "Lax")
            self.assertEqual(response.cookies[cookie]["path"], "/api/")
            self.assertEqual(response.cookies[cookie]["secure"], "")
        self.assertEqual(self.browser.get("/api/tasks/my/").status_code, 200)

    def test_registration_validation_missing_invalid_duplicate_email_login(self):
        self.csrf()
        missing = self.browser_post(
            "/api/register/", {"username": "abc", "email": "abc@example.test"}
        )
        self.assertEqual(missing.status_code, 400)
        self.assertIn("password", missing.data)
        for data, field in [
            (self.payload(email="not-an-email"), "email"),
            (self.payload(username="existing"), "username"),
            (self.payload(username="NEWUSER", email="existing@EXAMPLE.test"), "email"),
            (self.payload(password="short"), "password"),
            (self.payload(password="alllowercase123!"), "password"),
            (self.payload(username="not allowed"), "username"),
        ]:
            with self.subTest(data=data):
                response = self.browser_post("/api/register/", data)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)
        self.assertFalse(get_user_model().objects.filter(username="newuser").exists())

    def test_duplicate_user_and_email_case_insensitive(self):
        self.csrf()
        response = self.browser_post("/api/register/", self.payload())
        self.assertEqual(response.status_code, 201)
        response = self.browser_post(
            "/api/register/", self.payload(username="NEWUSER", email="other@example.test")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        response = self.browser_post(
            "/api/register/", self.payload(username="another", email="NewUser@Example.test")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_login_requires_csrf_and_valid_credentials(self):
        self.assertEqual(
            self.browser.post(
                "/api/login/",
                {"username": "existing", "password": PASSWORD},
                format="json",
            ).status_code,
            403,
        )
        self.csrf()
        denied = self.browser_post(
            "/api/login/", {"username": "existing", "password": "wrong"}
        )
        self.assertEqual(denied.status_code, 400)
        self.assertNotIn("refresh_token", self.browser.cookies)
        response = self.browser_post(
            "/api/login/", {"username": "existing", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["username"], "existing")
        self.assertIn("access_token", self.browser.cookies)
        self.assertIn("refresh_token", self.browser.cookies)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_cookie_protected_get_and_csrf_guarded_writes(self):
        self.login()
        self.assertEqual(self.browser.get("/api/tasks/my/").status_code, 200)
        deadline = (timezone.now() + timedelta(days=2)).isoformat()
        payload = {"title": "From cookie", "description": "Secure", "deadline": deadline}
        response = self.browser.post("/api/tasks/", payload, format="json")
        self.assertEqual(response.status_code, 403, response.data)
        allowed = self.browser_post("/api/tasks/", payload)
        self.assertEqual(allowed.status_code, 201, allowed.data)
        self.assertEqual(Task.objects.get(pk=allowed.data["id"]).owner, self.user)

    def test_header_bearer_still_works_without_csrf(self):
        token = RefreshToken.for_user(self.user)
        api = APIClient(enforce_csrf_checks=True)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        response = api.post(
            "/api/tasks/",
            {
                "title": "From bearer",
                "description": "HTTP API",
                "deadline": (timezone.now() + timedelta(days=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_refresh_rotation_blacklists_old_refresh(self):
        self.login()
        old_refresh = self.browser.cookies["refresh_token"].value
        response = self.browser_post("/api/auth/refresh/", {})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access_token", response.cookies)
        self.assertNotEqual(self.browser.cookies["refresh_token"].value, old_refresh)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=RefreshToken(old_refresh,verify=False)["jti"]).exists())
        self.browser.cookies["refresh_token"] = old_refresh
        failed = self.browser_post("/api/auth/refresh/", {})
        self.assertEqual(failed.status_code, 401, failed.data)
        self.assertEqual(self.browser.cookies["refresh_token"].value, "")

    def test_auto_refresh_on_get_and_replay_rejected(self):
        self.csrf()
        refresh = RefreshToken.for_user(self.user)
        expired = refresh.access_token
        expired.set_exp(lifetime=timedelta(seconds=-5))
        self.browser.cookies["access_token"] = str(expired)
        self.browser.cookies["refresh_token"] = str(refresh)
        response = self.browser.get("/api/tasks/my/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertNotEqual(response.cookies["refresh_token"].value, str(refresh))
        self.assertEqual(self.browser.get("/api/tasks/my/").status_code, 200)
        # Старый refresh нельзя предъявить повторно.
        self.browser.cookies["access_token"] = ""
        self.browser.cookies["refresh_token"] = str(refresh)
        self.assertEqual(self.browser.get("/api/tasks/my/").status_code, 401)

    def test_no_refresh_on_unsafe_request_without_explicit_refresh(self):
        self.csrf()
        refresh = RefreshToken.for_user(self.user)
        expired = refresh.access_token
        expired.set_exp(lifetime=timedelta(seconds=-5))
        self.browser.cookies["access_token"] = str(expired)
        self.browser.cookies["refresh_token"] = str(refresh)
        response = self.browser_post("/api/logout/", {})
        self.assertEqual(response.status_code, 401)
        response = self.browser_post("/api/auth/refresh/", {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.browser_post("/api/logout/", {}).status_code, 204)

    def test_logout_revokes_refresh_access_and_clears_cookies(self):
        self.login()
        access = self.browser.cookies["access_token"].value
        refresh = self.browser.cookies["refresh_token"].value
        self.assertEqual(
            self.browser.post(
                "/api/logout/", {}, format="json"
            ).status_code,
            403,
        )
        response = self.browser_post("/api/logout/", {})
        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(RevokedAccessToken.objects.exists())
        for name in ("access_token", "refresh_token"):
            self.assertEqual(response.cookies[name].value, "")
        old_header_client = APIClient()
        old_header_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(old_header_client.get("/api/tasks/my/").status_code, 401)
        self.assertEqual(self.browser.get("/api/tasks/my/").status_code, 401)
        self.browser.cookies["refresh_token"] = refresh
        self.assertEqual(
            self.browser_post("/api/auth/refresh/", {}).status_code, 401
        )

    def test_logout_with_authorization_header_revokes_access_too(self):
        pair = self.client.post(
            "/api/token/", {"username": "existing", "password": PASSWORD}, format="json"
        )
        self.assertEqual(pair.status_code, 200)
        browser = APIClient(enforce_csrf_checks=True)
        self.csrf(browser)
        browser.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.data['access']}")
        response = self.browser_post("/api/logout/", {}, browser)
        self.assertEqual(response.status_code, 204, response.data)
        self.assertEqual(browser.get("/api/tasks/my/").status_code, 401)

    def test_refresh_without_cookie_fails(self):
        self.csrf()
        response = self.browser_post("/api/auth/refresh/", {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Отсутствует refresh cookie.")

    def test_cookie_secure_flag_for_https(self):
        self.csrf()
        with self.settings(AUTH_COOKIE_SECURE=True):
            response = self.browser_post(
                "/api/login/", {"username": "existing", "password": PASSWORD}
            )
        self.assertEqual(response.status_code, 200)
        for name in ("access_token", "refresh_token"):
            self.assertTrue(response.cookies[name]["secure"])

    def test_cross_origin_login_rejected(self):
        self.csrf()
        response = self.browser.post(
            "/api/login/",
            {"username": "existing", "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=self.browser.cookies["csrftoken"].value,
            HTTP_ORIGIN="https://external.example.test",
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("access_token", self.browser.cookies)

    def test_invalid_jwt_not_accepted_as_cookie(self):
        self.csrf()
        self.browser.cookies["access_token"] = "not-a-real-token"
        self.assertEqual(self.browser.get("/api/tasks/my/").status_code, 401)

    def test_django_csrf_cookie_sent_on_get(self):
        response = self.browser.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
        self.assertNotIn("refresh_token", response.cookies)
