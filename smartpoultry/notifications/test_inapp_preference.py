from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.views import ensure_month_end_forecast_notification
from notifications.models import Notification, NotificationPreference
from notifications.utils import create_activity_notification


class InAppPreferenceTests(TestCase):
    """INT-033: activity notifications follow the In-app notifications setting."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('inapp-owner', email='inapp@example.com', password='Secret!123')

    def turn_off_in_app(self):
        NotificationPreference.objects.update_or_create(user=self.user, defaults={'in_app_notifications': False})

    def test_activity_notification_created_when_in_app_is_on(self):
        self.assertIsNotNone(create_activity_notification(self.user, 'Saved', 'Record saved.'))
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_activity_notification_skipped_when_in_app_is_off(self):
        self.turn_off_in_app()
        self.assertIsNone(create_activity_notification(self.user, 'Saved', 'Record saved.'))
        self.assertFalse(Notification.objects.filter(user=self.user).exists())

    def test_month_end_forecast_reminder_does_not_fail_when_in_app_is_off(self):
        self.turn_off_in_app()
        with mock.patch('core.views.timezone.localdate', return_value=date(2026, 11, 30)):
            ensure_month_end_forecast_notification(self.user)
        self.assertFalse(Notification.objects.filter(user=self.user).exists())

    def test_month_end_forecast_reminder_created_once_when_in_app_is_on(self):
        with mock.patch('core.views.timezone.localdate', return_value=date(2026, 11, 30)):
            ensure_month_end_forecast_notification(self.user)
            ensure_month_end_forecast_notification(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user, related_object_type='month_end_forecast').count(), 1)
