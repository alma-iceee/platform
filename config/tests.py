from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthViewTests(TestCase):
    def test_health_is_public_and_checks_database(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("config.views.connection.ensure_connection", side_effect=OperationalError)
    def test_health_reports_unavailable_database(self, ensure_connection):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        ensure_connection.assert_called_once_with()
