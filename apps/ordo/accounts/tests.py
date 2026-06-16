from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountAuthViewTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email")
        self.assertContains(response, "Password")

    def test_unauthenticated_app_request_redirects_to_login(self):
        response = self.client.get(reverse("workspaces:shell"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('workspaces:shell')}",
            fetch_redirect_response=False,
        )

    def test_user_can_login_with_email_and_password(self):
        get_user_model().objects.create_user(
            email="member@example.com",
            password="secret12345",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "member@example.com",
                "password": "secret12345",
            },
        )

        self.assertRedirects(response, reverse("workspaces:shell"))

    def test_login_redirects_to_next_url(self):
        get_user_model().objects.create_user(
            email="member@example.com",
            password="secret12345",
        )
        next_url = reverse("workspaces:workspace_create")

        response = self.client.post(
            f"{reverse('accounts:login')}?next={next_url}",
            {
                "username": "member@example.com",
                "password": "secret12345",
            },
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_logout_redirects_to_login(self):
        user = get_user_model().objects.create_user(
            email="member@example.com",
            password="secret12345",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:login"))
